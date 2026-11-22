"""Independent integrity and transaction replay for HV01 serial captures."""
from __future__ import annotations

import argparse, csv, hashlib, json, math, struct, zlib
from datetime import datetime, timezone
from pathlib import Path

from ml.parity.contract import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, SCHEMA_VERSION, SEMANTIC_CONTRACT_VERSION, VALIDITY_POLICY_VERSION

ROOT=Path(__file__).resolve().parents[2]
TYPES={1:"RUN_BEGIN",2:"CASE_BEGIN",3:"SAMPLES",4:"CASE_END",5:"RUN_END",
       128:"HELLO",129:"ACK",130:"RESULT",131:"CASE_DONE",132:"RUN_DONE",143:"ERROR"}
TX={1,2,3,4,5}; RX={128,129,130,131,132,143}
STATUSES={"OK","FRAME_ERROR","TIMEOUT","READ_ERROR","WRITE_COUNT_UNKNOWN","PARTIAL_WRITE","WRITE_COUNT_INVALID","WRITE_ERROR"}

class VerifyError(ValueError): pass

def _need(ok: bool, message: str) -> None:
    if not ok: raise VerifyError(message)

def _jsonl(path: Path) -> list[dict]:
    try: rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError,json.JSONDecodeError) as exc: raise VerifyError(f"JSONL không hợp lệ: {exc}") from exc
    _need(bool(rows) and all(isinstance(r,dict) for r in rows),"Transcript rỗng hoặc record không phải object")
    return rows

def _frame(raw: bytes, seq: int) -> dict:
    _need(len(raw)>=14 and raw[:2]==b"\x53\x56","Frame ngắn hoặc sync sai")
    version,kind,number,size=struct.unpack_from("<BBIH",raw,2)
    _need(version==1 and kind in TYPES and size<=384 and len(raw)==size+14,"Version/type/length sai")
    _need(number==seq,f"Sequence sai: nhận {number}, cần {seq}")
    _need(zlib.crc32(raw[2:-4])&0xffffffff==struct.unpack_from("<I",raw,len(raw)-4)[0],"CRC32 sai")
    return dict(type=kind,name=TYPES[kind],seq=number,payload=raw[10:-4],raw=raw)

def _id(p: bytes, cap: int) -> tuple[str,int]:
    _need(bool(p) and 0<p[0]<=cap and len(p)>=1+p[0],"ID payload thiếu/sai độ dài")
    try: value=p[1:1+p[0]].decode("ascii")
    except UnicodeDecodeError as exc: raise VerifyError("ID không phải ASCII") from exc
    _need(all(c.isalnum() or c in "_.-" for c in value) and value.isascii(),"ID chứa ký tự không hợp lệ")
    return value,1+p[0]

def _fixture(suite: str) -> tuple[str,dict]:
    manifest_path=ROOT/"ml/parity/fixtures/manifest.json"; raw=manifest_path.read_bytes(); manifest=json.loads(raw)
    digest=hashlib.sha256(raw).hexdigest(); names=("synthetic","real") if suite=="all" else (suite,)
    _need(suite in ("synthetic","real","all"),"Suite không hợp lệ")
    cases={}
    for name in names:
        case_path=ROOT/f"ml/parity/fixtures/{name}/cases.json"; cbytes=case_path.read_bytes(); rel=case_path.relative_to(ROOT).as_posix()
        entry=manifest.get("files",{}).get(rel)
        _need(entry and entry.get("sha256")==hashlib.sha256(cbytes).hexdigest() and entry.get("bytes")==len(cbytes),f"Manifest cases sai: {name}")
        spec=json.loads(cbytes)
        _need(spec.get("suite")==name and spec.get("feature_order")==list(FEATURE_ORDER) and spec.get("schema_version")==SCHEMA_VERSION and spec.get("schema_sha256")==manifest.get("schema_sha256"),"Case schema/order sai")
        for case in spec["cases"]:
            cid=case["case_id"]; csv_path=ROOT/case["input_file"]; data=csv_path.read_bytes(); file_entry=manifest.get("files",{}).get(case["input_file"])
            sha=hashlib.sha256(data).hexdigest()
            _need(file_entry and file_entry.get("sha256")==sha and file_entry.get("bytes")==len(data) and sha==case["input_sha256"],f"CSV SHA/manifest sai: {cid}")
            rows=list(csv.DictReader(data.decode("utf-8").splitlines()))
            _need(rows and list(rows[0])==["sample_index","time_seconds","roll_deg","pitch_deg","source_sample_index"],f"CSV header sai: {cid}")
            _need(len(rows)==case["n_samples"] and [int(r["sample_index"]) for r in rows]==list(range(len(rows))),f"CSV sample index/count sai: {cid}")
            records=b"".join(struct.pack("<ffBB",float(r["roll_deg"]),float(r["pitch_deg"]),2,1) for r in rows)
            endpoints=[int(e["endpoint_index"]) for e in case["endpoints"]]
            _need(endpoints and endpoints==sorted(set(endpoints)) and endpoints[-1]<len(rows),f"Endpoint sai: {cid}")
            _need(cid not in cases,"Case ID fixture trùng")
            cases[cid]=dict(sha=sha,count=len(rows),records=records,endpoints=endpoints,provenance="SIMULATION" if name=="synthetic" else "SENSOR",source=[int(r["source_sample_index"]) for r in rows])
    _need(bool(cases),"Không có fixture cases")
    return digest,cases

def _result(p: bytes) -> dict:
    cid,at=_id(p,48); _need(len(p)==at+150,"RESULT length sai")
    endpoint,sha,elapsed,mask,flags=struct.unpack_from("<I32sIIB",p,at); at+=45
    n60,n180,consec=struct.unpack_from("<HHH",p,at); at+=6; quality=struct.unpack_from("<f",p,at)[0]; at+=4
    qstatus,qreason,count=p[at:at+3]; at+=3
    _need(count==23 and mask>>23==0 and flags&~3==0 and math.isfinite(quality) and 0<=quality<=100,"RESULT metadata sai")
    bits=struct.unpack_from("<23I",p,at); values=[]
    for i,b in enumerate(bits):
        v=struct.unpack("<f",struct.pack("<I",b))[0]
        _need(math.isfinite(v) if mask>>i&1 else b==0x7fc00000,f"RESULT feature {i} validity/value sai")
        values.append(v)
    return dict(case_id=cid,endpoint=endpoint,sha=sha.hex(),mask=mask,values=values,bits=bits,elapsed=elapsed,
        flags=flags,n60=n60,n180=n180,consec=consec,quality=quality,qstatus=qstatus,qreason=qreason)

def _parse(kind: int,p: bytes) -> dict:
    if kind==128:
        _need(len(p)>=10,"HELLO ngắn"); ver,n,order=struct.unpack_from("<BBI",p); pos=6; strings=[]
        for _ in range(9):
            _need(pos<len(p) and pos+1+p[pos]<=len(p),"HELLO string thiếu")
            size=p[pos]; strings.append(p[pos+1:pos+1+size].decode("utf-8")); pos+=size+1
        _need(pos+4==len(p),"HELLO length sai"); rev,cpu=struct.unpack_from("<HH",p,pos)
        return dict(protocol_version=ver,feature_count=n,feature_order_crc32=order,feature_schema=strings[0],semantic_version=strings[1],validity_version=strings[2],parity_schema=strings[3],harness=strings[4],build_flags=strings[5],compiler=strings[6],sdk=strings[7],chip=strings[8],chip_revision=rev,cpu_mhz=cpu)
    if kind==129:
        _need(len(p)==9,"ACK length sai"); a,c,s=struct.unpack("<IBI",p); return dict(host_seq=a,code=c,samples=s)
    if kind==130: return _result(p)
    if kind in (131,132):
        cap=48 if kind==131 else 32; ident,at=_id(p,cap)
        if kind==131:
            _need(len(p)==at+10,"CASE_DONE length sai"); samples,endpoints,crc,status=struct.unpack_from("<IBIB",p,at)
            return dict(id=ident,samples=samples,endpoints=endpoints,crc=crc,status=status)
        _need(len(p)==at+35,"RUN_DONE length sai"); count,sha,status=struct.unpack_from("<H32sB",p,at)
        return dict(id=ident,count=count,sha=sha.hex(),status=status)
    if kind==143:
        _need(len(p)==2 and p[1]==1,"ERROR payload sai"); raise VerifyError(f"Target ERROR code={p[0]}")
    raise VerifyError(f"Unexpected target type {kind}")

def verify_capture(capture: Path) -> dict:
    capture=Path(capture); errors=[]; counts={"tx":0,"rx":0,"cases":0,"endpoints":0,"results":0}
    try:
        meta=json.loads((capture/"metadata.json").read_text()); summary=json.loads((capture/"transport_summary.json").read_text())
        raw_bytes=(capture/"serial_transcript.jsonl").read_bytes(); transcript=_jsonl(capture/"serial_transcript.jsonl")
        sha=hashlib.sha256(raw_bytes).hexdigest()
        _need(meta.get("serial_transcript_sha256")==sha and summary.get("serial_transcript_sha256")==sha,"Transcript SHA không khớp metadata/summary")
        _need(meta.get("serial_transcript_event_count")==len(transcript),"Transcript event count sai")
        monotonic=-1; wall=None; frames=[]; incomplete=False; seqs={"TX":0,"RX":0}
        for i,e in enumerate(transcript):
            _need(e.get("event_index")==i and e.get("direction") in seqs and e.get("status") in STATUSES,f"Event index/direction/status sai tại {i}")
            stamp=datetime.fromisoformat(e["timestamp_utc"].replace("Z","+00:00")); _need(stamp.tzinfo is not None and stamp.utcoffset()==timezone.utc.utcoffset(stamp) and (wall is None or stamp>=wall),f"Timestamp UTC sai/thụt lùi tại {i}"); wall=stamp
            mono=e.get("monotonic_ns"); _need(isinstance(mono,int) and mono>=monotonic,f"Monotonic timestamp lùi tại {i}"); monotonic=mono
            try: b=bytes.fromhex(e["raw_frame_hex"])
            except (KeyError,ValueError) as exc: raise VerifyError(f"Raw hex sai tại {i}: {exc}") from exc
            _need(e.get("frame_length")==len(b),f"Frame length sai tại {i}")
            if len(b)>=4: _need(e.get("type_id")==b[3] and e.get("frame_type")==TYPES.get(b[3]),f"Frame type metadata sai tại {i}")
            if len(b)>=8: _need(e.get("sequence")==struct.unpack_from("<I",b,4)[0],f"Sequence metadata sai tại {i}")
            if len(b)>=10:
                n=struct.unpack_from("<H",b,8)[0]; _need(n<=384 and e.get("declared_payload_length")==n and e.get("expected_frame_length")==n+14,f"Payload length metadata sai tại {i}")
            _need(e.get("frame_complete") is (e["status"]=="OK"),f"frame_complete/status sai tại {i}")
            if e["status"]!="OK": incomplete=True; continue
            f=_frame(b,seqs[e["direction"]]); seqs[e["direction"]]+=1
            allowed=TX if e["direction"]=="TX" else RX; _need(f["type"] in allowed,f"Frame sai hướng tại {i}")
            frames.append((e["direction"],f))
            counts["tx" if e["direction"]=="TX" else "rx"]+=1
        if incomplete:
            _need(summary.get("transport_status")!="TRANSPORT_COMPLETE" and not meta.get("serial_transcript_complete"),"Transcript có event lỗi nhưng công bố COMPLETE")
            return _report("TRANSCRIPT_INCOMPLETE",capture,sha,counts,errors+["Transcript có frame/transport event chưa hoàn chỉnh"],False,meta)
        _need(meta.get("protocol_version")==1 and meta.get("feature_schema_version")==FEATURE_SCHEMA_VERSION and meta.get("semantic_contract_version")==SEMANTIC_CONTRACT_VERSION and meta.get("validity_policy_version")==VALIDITY_POLICY_VERSION and meta.get("parity_schema_version")==SCHEMA_VERSION,"Metadata contract version sai")
        manifest_sha,cases=_fixture(meta.get("suite")); _need(meta.get("manifest_sha256")==manifest_sha,"Golden manifest SHA sai")
        _need(meta.get("execution_kind") in ("serial_target","host_mock"),"execution_kind thiếu/sai")
        _need(meta.get("capture_status")==("HOST_MOCK_VERIFIED" if meta["execution_kind"]=="host_mock" else "TARGET_CAPTURE_COLLECTED") and meta.get("target_evidence_status")=="TARGET_EVIDENCE_NOT_VERIFIED" and meta.get("numerical_parity")=="NUMERICAL_PARITY_NOT_RUN","Capture/evidence status metadata sai")
        cap_cases=meta.get("cases") or []; _need([c.get("case_id") for c in cap_cases]==list(cases),"Metadata case order/count không khớp fixture")
        for c in cap_cases:
            g=cases[c["case_id"]]; _need(c.get("input_sha256")==g["sha"] and c.get("sample_count")==g["count"] and c.get("endpoints")==g["endpoints"] and c.get("source_sample_index")==g["source"] and c.get("provenance")==g["provenance"],f"Metadata fixture case sai: {c.get('case_id')}")
        _replay(frames,meta,manifest_sha,cases,counts)
        _cross(capture,frames,meta,summary,cases,manifest_sha)
        _need(summary.get("transport_status")=="TRANSPORT_COMPLETE" and summary.get("numerical_parity")=="NUMERICAL_PARITY_NOT_RUN" and summary.get("cases_expected")==len(cases) and summary.get("cases_completed")==len(cases) and summary.get("result_count")==counts["results"] and summary.get("serial_transcript_complete") is True and summary.get("capture_status")==meta.get("capture_status") and summary.get("target_evidence_status")==meta.get("target_evidence_status") and not summary.get("error"),"Transport summary không khớp replay")
        _need(meta.get("serial_transcript_complete") is True,"Metadata không công bố transcript hoàn chỉnh")
        verdict="TRANSCRIPT_VERIFIED" if meta.get("execution_kind")=="serial_target" else "TARGET_EVIDENCE_NOT_VERIFIED"
        return _report(verdict,capture,sha,counts,errors,True,meta)
    except (VerifyError,OSError,KeyError,ValueError,TypeError,struct.error,json.JSONDecodeError) as exc:
        errors.append(str(exc)); return _report("TRANSCRIPT_FAILED",capture,locals().get("sha","NOT_AVAILABLE"),counts,errors,False,locals().get("meta",{}))

def _replay(frames: list,meta: dict,manifest_sha: str,cases: dict,counts: dict) -> None:
    _need(bool(frames) and frames[0][0]=="RX" and frames[0][1]["type"]==128,"HELLO đầu tiên thiếu")
    pending=None; wait_terminal=None; active=None; run=None; expected_cases=None; completed=[]; results=[]; seen_hello=0; last_count=0; done=False
    for direction,f in frames:
        k,p=f["type"],f["payload"]
        if done: raise VerifyError("Message thừa sau RUN_DONE")
        if direction=="TX":
            _need(pending is None and wait_terminal is None,"Host phát request trước response/terminal trước đó")
            _need(k in TX,"TX message type sai")
            if k==1:
                rid,at=_id(p,32); _need(len(p)==at+34,"RUN_BEGIN length sai"); expected_cases=struct.unpack_from("<H",p,at)[0]; sha=p[at+2:at+34].hex()
                _need(1<=expected_cases<=64 and expected_cases==len(cases) and sha==manifest_sha and rid==meta.get("run_id"),"RUN_BEGIN ID/count/manifest sai")
                run=rid; pending=dict(frame=f,kind=k,samples=0)
            elif k==2:
                _need(run is not None and active is None and len(completed)<expected_cases,"CASE_BEGIN ngoài state")
                cid,at=_id(p,48); _need(len(p)>=at+41,"CASE_BEGIN ngắn"); count,ne=struct.unpack_from("<IB",p,at); at+=5
                _need(1<=count<=4096 and 1<=ne<=32 and len(p)==at+ne*4+36,"CASE_BEGIN length/count sai")
                endpoints=list(struct.unpack_from("<"+"I"*ne,p,at)); at+=4*ne; sha=p[at:at+32].hex(); at+=32; crc=struct.unpack_from("<I",p,at)[0]
                _need(endpoints==sorted(set(endpoints)) and endpoints[-1]<count,"CASE_BEGIN endpoints sai")
                g=cases.get(cid); _need(g is not None and cid not in completed and count==g["count"] and endpoints==g["endpoints"] and sha==g["sha"] and crc==zlib.crc32(g["records"])&0xffffffff,"CASE_BEGIN không khớp fixture")
                active=dict(id=cid,count=count,endpoints=endpoints,sha=sha,crc=crc,received=0,samples=b"",result_pos=0); pending=dict(frame=f,kind=k,samples=0)
            elif k==3:
                _need(active is not None and len(p)>=5,"SAMPLES ngoài case/thiếu header")
                first,n=struct.unpack_from("<IB",p); records=p[5:]; _need(1<=n<=32 and len(p)==5+10*n and first==active["received"] and first+n<=active["count"],"SAMPLES index/batch/length sai")
                want=cases[active["id"]]["records"][first*10:(first+n)*10]; _need(records==want,"SAMPLES bytes khác canonical float32 fixture")
                _need(all(records[i+8]<=2 and records[i+9]<=1 for i in range(0,len(records),10)),"SAMPLES nraw/valid sai")
                active["samples"]+=records; active["received"]+=n
                eps=[e for e in active["endpoints"] if first<=e<first+n]; active["got"]=[]
                pending=dict(frame=f,kind=k,samples=first+n,wanted=eps)
            elif k==4:
                _need(active is not None and not p and active["received"]==active["count"] and active["result_pos"]==len(active["endpoints"]),"CASE_END incomplete/sai")
                pending=dict(frame=f,kind=k,samples=active["count"])
            elif k==5:
                _need(active is None and len(completed)==expected_cases and not p,"RUN_END ngoài state/incomplete")
                pending=dict(frame=f,kind=k,samples=last_count)
            else: raise VerifyError("Host gửi type không hợp lệ")
        elif k==128:
            seen_hello+=1; _need(run is None or (pending and pending["kind"]==1),"HELLO sau khi RUN_BEGIN hoàn tất")
            h=_parse(k,p); order=zlib.crc32(b"".join(x.encode()+b"\0" for x in FEATURE_ORDER))&0xffffffff
            _need((h["protocol_version"],h["feature_count"],h["feature_order_crc32"],h["feature_schema"],h["semantic_version"],h["validity_version"],h["parity_schema"])==(1,23,order,FEATURE_SCHEMA_VERSION,SEMANTIC_CONTRACT_VERSION,VALIDITY_POLICY_VERSION,SCHEMA_VERSION),"HELLO contract/order sai")
            dh=meta.get("device_hello") or {}; keys=("protocol_version","feature_count","feature_order_crc32","feature_schema","semantic_version","validity_version","parity_schema","harness","build_flags","compiler","sdk","chip","chip_revision","cpu_mhz")
            _need(all(h[x]==dh.get(x) for x in keys),"HELLO metadata không khớp metadata.json")
        elif k==130:
            _need(pending is not None and pending["kind"]==3 and active is not None,"RESULT ngoài SAMPLES transaction")
            r=_parse(k,p); batch=pending["wanted"]
            _need(len(active["got"])<len(batch) and r["case_id"]==active["id"] and r["sha"]==active["sha"] and r["endpoint"]==batch[len(active["got"])],"RESULT ID/SHA/endpoint sai")
            active["got"].append(r); active["result_pos"]+=1; results.append((f,r))
        elif k==129:
            _need(pending is not None,"ACK/NACK không có host request"); a=_parse(k,p); req=pending["frame"]
            _need(a["host_seq"]==req["seq"] and a["code"]==0 and a["samples"]==pending["samples"],"ACK sequence/code/samples sai")
            if pending["kind"]==3:
                _need([r["endpoint"] for r in active["got"]]==pending["wanted"],"RESULT thiếu/trùng/thừa trước ACK")
            kind=pending["kind"]; pending=None
            if kind==4: wait_terminal=131
            elif kind==5: wait_terminal=132
        elif k in (131,132):
            _need(pending is None and wait_terminal==k,"CASE_DONE/RUN_DONE thiếu hoặc ngoài state")
            d=_parse(k,p)
            if k==131:
                _need(active is not None and (d["id"],d["samples"],d["endpoints"],d["crc"],d["status"])==(active["id"],active["count"],len(active["endpoints"]),zlib.crc32(active["samples"])&0xffffffff,0),"CASE_DONE không khớp case/sample/endpoint/CRC/status")
                completed.append(active["id"]); last_count=active["count"]; counts["endpoints"]+=len(active["endpoints"]); active=None; wait_terminal=None; counts["cases"]+=1
            else:
                _need(active is None and (d["id"],d["count"],d["sha"],d["status"])==(run,expected_cases,manifest_sha,0),"RUN_DONE không khớp ID/count/manifest/status")
                done=True; wait_terminal=None
        else: raise VerifyError(f"Unexpected RX type {k}")
    _need(seen_hello>=1 and done and pending is None and wait_terminal is None and counts["cases"]==len(cases),"Transcript thiếu RUN_DONE/CASE_DONE hoặc giao dịch chưa hoàn tất")
    counts["results"]=len(results)

def _cross(capture: Path,frames: list,meta: dict,summary: dict,cases: dict,manifest_sha: str) -> None:
    try: rows=[json.loads(x) for x in (capture/"raw_results.jsonl").read_text().splitlines() if x.strip()]
    except (OSError,json.JSONDecodeError) as exc: raise VerifyError(f"raw_results không hợp lệ: {exc}") from exc
    actual=[(f,_result(f["payload"])) for direction,f in frames if direction=="RX" and f["type"]==130]
    _need(len(rows)==len(actual)==summary.get("result_count"),"Raw RESULT count khác transcript/summary")
    for i,(row,(f,r)) in enumerate(zip(rows,actual)):
        _need(row.get("raw_frame_hex")==f["raw"].hex() and row.get("payload_hex")==f["payload"].hex(),f"Raw RESULT frame/payload khác transcript tại {i}")
        v=row.get("result") or {}; _need(v.get("case_id")==r["case_id"] and v.get("endpoint_index")==r["endpoint"] and v.get("input_csv_sha256")==r["sha"] and v.get("valid_mask")==r["mask"],f"Parsed RESULT ID/SHA/mask sai tại {i}")
        values=v.get("values"); _need(isinstance(values,list) and len(values)==23,f"Parsed RESULT feature count sai tại {i}")
        for j,x in enumerate(values):
            _need(x is None if not (r["mask"]>>j&1) else x is not None and math.isfinite(float(x)) and struct.pack("<f",float(x))==struct.pack("<f",r["values"][j]),f"Parsed feature value sai tại {i}:{j}")
        _need(row.get("provisional") is False,"Raw RESULT provisional/incomplete")
    _need(meta.get("manifest_sha256")==manifest_sha,"Metadata manifest không khớp")

def _report(verdict: str,capture: Path,sha: str,counts: dict,errors: list,transport_complete: bool,meta: dict) -> dict:
    return dict(verdict=verdict,transcript_sha256=sha,tx_frames=counts["tx"],rx_frames=counts["rx"],cases=counts["cases"],endpoints=counts["endpoints"],results=counts["results"],
        frame_crc_sequence_valid=not errors,transport_complete=transport_complete,capture_execution_kind=meta.get("execution_kind","NOT_AVAILABLE"),
        target_evidence_status="TARGET_EVIDENCE_NOT_VERIFIED",physical_board_verified=False,numerical_parity="NUMERICAL_PARITY_NOT_RUN",errors=errors)

def main(argv: list[str] | None=None) -> int:
    ap=argparse.ArgumentParser(description="Xác minh độc lập transcript Serial HV01; không so sánh numerical parity.")
    ap.add_argument("--capture",required=True,type=Path); ap.add_argument("--out",type=Path)
    args=ap.parse_args(argv); report=verify_capture(args.capture)
    if args.out:
        out=args.out; path=out/"verification.json"
        if out.exists() and any(out.iterdir()): ap.error(f"Thư mục report không rỗng: {out}")
        out.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["verdict"] in ("TRANSCRIPT_VERIFIED","TARGET_EVIDENCE_NOT_VERIFIED") else 1

if __name__=="__main__": raise SystemExit(main())
