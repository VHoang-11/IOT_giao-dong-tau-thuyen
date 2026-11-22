import hashlib, json, shutil, struct, zlib
from datetime import datetime, timezone, timedelta

import pytest

from ml.parity import compare, esp32_target, esp32_verify as v, golden
from ml.parity.contract import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, SCHEMA_VERSION, SEMANTIC_CONTRACT_VERSION, VALIDITY_POLICY_VERSION

def wire(kind,seq,payload=b""):
    body=struct.pack("<BBIH",1,kind,seq,len(payload))+payload
    return b"SV"+body+struct.pack("<I",zlib.crc32(body)&0xffffffff)

def hello_payload():
    fields=(FEATURE_SCHEMA_VERSION,SEMANTIC_CONTRACT_VERSION,VALIDITY_POLICY_VERSION,SCHEMA_VERSION,
        "hv01-a-1 / esp32dev / Arduino","flags","compiler","sdk","ESP32")
    order=zlib.crc32(b"".join(n.encode()+b"\0" for n in FEATURE_ORDER))&0xffffffff
    return struct.pack("<BBI",1,23,order)+b"".join(bytes([len(s)])+s.encode() for s in fields)+struct.pack("<HH",1,240)

def append_event(events,direction,kind,seq,payload=b""):
    raw=wire(kind,seq,payload); events.append(dict(event_index=len(events),direction=direction,
        frame_type=v.TYPES[kind],type_id=kind,sequence=seq,timestamp_utc=(datetime.now(timezone.utc)+timedelta(microseconds=len(events))).isoformat(),
        monotonic_ns=1000+len(events),frame_length=len(raw),declared_payload_length=len(payload),
        expected_frame_length=len(raw),raw_frame_hex=raw.hex(),frame_complete=True,status="OK",detail=None))
    return raw

def make_capture(path):
    root=v.ROOT; manifest_raw=(root/"ml/parity/fixtures/manifest.json").read_bytes(); manifest=json.loads(manifest_raw)
    suite_path=root/"ml/parity/fixtures/synthetic/cases.json"; suite=json.loads(suite_path.read_text())
    event=[]; tx=rx=0; results=[]; cap_cases=[]; cases=[]; run_id="verify_mock"
    def send(kind,payload=b""):
        nonlocal tx
        raw=append_event(event,"TX",kind,tx,payload); seq=tx; tx+=1; return seq,raw
    def recv(kind,payload=b""):
        nonlocal rx
        raw=append_event(event,"RX",kind,rx,payload); rx+=1; return raw
    recv(128,hello_payload()); recv(128,hello_payload())
    msha=hashlib.sha256(manifest_raw).digest(); rid=run_id.encode()
    hseq,_=send(1,bytes([len(rid)])+rid+struct.pack("<H",len(suite["cases"]))+msha)
    recv(129,struct.pack("<IBI",hseq,0,0))
    for c in suite["cases"]:
        csv_path=root/c["input_file"]; data=csv_path.read_bytes(); rows=list(__import__("csv").DictReader(data.decode().splitlines()))
        records=b"".join(struct.pack("<ffBB",float(r["roll_deg"]),float(r["pitch_deg"]),2,1) for r in rows)
        endpoints=[e["endpoint_index"] for e in c["endpoints"]]; crc=zlib.crc32(records)&0xffffffff; cid=c["case_id"].encode(); sha=bytes.fromhex(c["input_sha256"])
        cases.append(dict(id=c["case_id"],count=len(rows),records=records,endpoints=endpoints,sha=c["input_sha256"],crc=crc))
        cap_cases.append(dict(case_id=c["case_id"],input_sha256=c["input_sha256"],sample_count=len(rows),endpoints=endpoints,
            source_sample_index=[int(r["source_sample_index"]) for r in rows],provenance="SIMULATION"))
        payload=bytes([len(cid)])+cid+struct.pack("<IB",len(rows),len(endpoints))+struct.pack("<"+"I"*len(endpoints),*endpoints)+sha+struct.pack("<I",crc)
        hseq,_=send(2,payload); recv(129,struct.pack("<IBI",hseq,0,0))
        for first in range(0,len(rows),32):
            n=min(32,len(rows)-first); block=records[first*10:(first+n)*10]
            hseq,_=send(3,struct.pack("<IB",first,n)+block)
            for ep in endpoints:
                if first<=ep<first+n:
                    vals=[0x7fc00000]*23
                    rp=(bytes([len(cid)])+cid+struct.pack("<I32sIIB",ep,sha,10,0,0)+
                        struct.pack("<HHHfBBB",0,0,0,0.0,0,0,23)+struct.pack("<23I",*vals))
                    raw=recv(130,rp); results.append(dict(raw_frame_hex=raw.hex(),payload_hex=rp.hex(),provisional=False,
                        result=dict(case_id=c["case_id"],endpoint_index=ep,input_csv_sha256=c["input_sha256"],valid_mask=0,values=[None]*23)))
            recv(129,struct.pack("<IBI",hseq,0,first+n))
        hseq,_=send(4); recv(129,struct.pack("<IBI",hseq,0,len(rows)))
        recv(131,bytes([len(cid)])+cid+struct.pack("<IBIB",len(rows),len(endpoints),crc,0))
    hseq,_=send(5); recv(129,struct.pack("<IBI",hseq,0,cases[-1]["count"]))
    recv(132,bytes([len(run_id)])+run_id.encode()+struct.pack("<H32sB",len(cases),msha,0))
    path.mkdir(); transcript=path/"serial_transcript.jsonl"
    transcript.write_text("".join(json.dumps(e,separators=(",",":"))+"\n" for e in event))
    digest=hashlib.sha256(transcript.read_bytes()).hexdigest()
    order=zlib.crc32(b"".join(x.encode()+b"\0" for x in FEATURE_ORDER))&0xffffffff
    dh=dict(protocol_version=1,feature_count=23,feature_order_crc32=order,feature_schema=FEATURE_SCHEMA_VERSION,
        semantic_version=SEMANTIC_CONTRACT_VERSION,validity_version=VALIDITY_POLICY_VERSION,parity_schema=SCHEMA_VERSION,
        harness="hv01-a-1 / esp32dev / Arduino",build_flags="flags",compiler="compiler",sdk="sdk",chip="ESP32",chip_revision=1,cpu_mhz=240)
    meta=dict(run_id=run_id,suite="synthetic",manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),protocol_version=1,
        feature_schema_version=FEATURE_SCHEMA_VERSION,semantic_contract_version=SEMANTIC_CONTRACT_VERSION,
        validity_policy_version=VALIDITY_POLICY_VERSION,parity_schema_version=SCHEMA_VERSION,execution_kind="host_mock",target_evidence_status="TARGET_EVIDENCE_NOT_VERIFIED",numerical_parity="NUMERICAL_PARITY_NOT_RUN",
        capture_status="HOST_MOCK_VERIFIED",device_hello=dh,cases=cap_cases,serial_transcript_sha256=digest,
        serial_transcript_event_count=len(event),serial_transcript_complete=True)
    summary=dict(transport_status="TRANSPORT_COMPLETE",numerical_parity="NUMERICAL_PARITY_NOT_RUN",
        cases_expected=len(cases),cases_completed=len(cases),result_count=len(results),error=None,
        serial_transcript_sha256=digest,serial_transcript_complete=True,capture_status="HOST_MOCK_VERIFIED",target_evidence_status="TARGET_EVIDENCE_NOT_VERIFIED")
    (path/"metadata.json").write_text(json.dumps(meta)); (path/"transport_summary.json").write_text(json.dumps(summary))
    (path/"raw_results.jsonl").write_text("".join(json.dumps(r)+"\n" for r in results))
    return event

@pytest.fixture(scope="module")
def capture(tmp_path_factory):
    path=tmp_path_factory.mktemp("valid")/"capture"; make_capture(path); return path

def clone(capture,tmp_path):
    path=tmp_path/"capture"; shutil.copytree(capture,path); return path

@pytest.mark.parametrize("suite,sender_path,golden_root",[("synthetic",esp32_target.SYNTHETIC_CASES,golden.SYNTHETIC_ROOT),("real",esp32_target.REAL_CASES,golden.REAL_ROOT)])
def test_fixture_path_mapping_matches_sender_comparator_and_golden(suite,sender_path,golden_root):
    case_path=v._case_path(suite)
    assert case_path.resolve()==sender_path.resolve()==(v.ROOT/golden_root/"cases.json").resolve()
    assert case_path.resolve()==(v.ROOT/compare.suite_root(suite)/"cases.json").resolve()
    if suite=="real":
        if not case_path.is_file(): pytest.skip("Real fixtures NOT_AVAILABLE trong worktree này")
        _,cases=v._fixture("real"); assert len(cases)==5

def refresh(path,renumber=False):
    tp=path/"serial_transcript.jsonl"; events=[json.loads(x) for x in tp.read_text().splitlines()]
    if renumber:
        seq={"TX":0,"RX":0}
        for e in events:
            raw=bytearray.fromhex(e["raw_frame_hex"]); struct.pack_into("<I",raw,4,seq[e["direction"]]); seq[e["direction"]]+=1
            raw[-4:]=struct.pack("<I",zlib.crc32(raw[2:-4])&0xffffffff); e["raw_frame_hex"]=raw.hex(); e["sequence"]=struct.unpack_from("<I",raw,4)[0]
    for i,e in enumerate(events): e["event_index"]=i
    tp.write_text("".join(json.dumps(e,separators=(",",":"))+"\n" for e in events)); sha=hashlib.sha256(tp.read_bytes()).hexdigest()
    for name,key in (("metadata.json","serial_transcript_sha256"),("transport_summary.json","serial_transcript_sha256")):
        p=path/name; d=json.loads(p.read_text()); d[key]=sha
        if name=="metadata.json": d["serial_transcript_event_count"]=len(events)
        p.write_text(json.dumps(d))
    return events

def test_happy_path_replays_multicase_batches_and_never_promotes_mock(capture):
    report=v.verify_capture(capture)
    assert report["verdict"]=="TARGET_EVIDENCE_NOT_VERIFIED"
    assert report["cases"]==31 and report["results"]==488 and report["tx_frames"]>31
    assert report["target_evidence_status"]=="TARGET_EVIDENCE_NOT_VERIFIED" and not report["physical_board_verified"]

@pytest.mark.parametrize("mutation",["crc","tx_sequence","rx_sequence","ack_host_seq","ack_samples","nack","missing_case_done","missing_run_done","case_crc","run_manifest","duplicate_result","missing_result","raw_result","sha","partial","frame_type"])
def test_corruption_or_incomplete_transaction_is_rejected(capture,tmp_path,mutation):
    path=clone(capture,tmp_path); events=[json.loads(x) for x in (path/"serial_transcript.jsonl").read_text().splitlines()]
    def kind(e): return bytes.fromhex(e["raw_frame_hex"])[3]
    if mutation=="crc":
        e=next(x for x in events if x["direction"]=="TX"); b=bytearray.fromhex(e["raw_frame_hex"]); b[-1]^=1; e["raw_frame_hex"]=b.hex()
    elif mutation in ("tx_sequence","rx_sequence"):
        direction="TX" if mutation=="tx_sequence" else "RX"; e=next(x for x in events if x["direction"]==direction); b=bytearray.fromhex(e["raw_frame_hex"]); struct.pack_into("<I",b,4,9); b[-4:]=struct.pack("<I",zlib.crc32(b[2:-4])&0xffffffff); e["raw_frame_hex"]=b.hex(); e["sequence"]=9
    elif mutation in ("ack_host_seq","ack_samples","nack"):
        e=next(x for x in events if x["direction"]=="RX" and kind(x)==129); b=bytearray.fromhex(e["raw_frame_hex"]); at=10 if mutation=="ack_host_seq" else 15 if mutation=="ack_samples" else 14; struct.pack_into("<I" if mutation!="nack" else "<B",b,at,55 if mutation!="nack" else 1); b[-4:]=struct.pack("<I",zlib.crc32(b[2:-4])&0xffffffff); e["raw_frame_hex"]=b.hex()
    elif mutation in ("missing_case_done","missing_run_done","missing_result"):
        target=131 if mutation=="missing_case_done" else 132 if mutation=="missing_run_done" else 130
        idx=next(i for i,e in enumerate(events) if e["direction"]=="RX" and kind(e)==target); events.pop(idx); (path/"serial_transcript.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events)); refresh(path,True); return_bad=True
    elif mutation in ("case_crc","run_manifest"):
        target=131 if mutation=="case_crc" else 132; e=next(x for x in events if x["direction"]=="RX" and kind(x)==target); b=bytearray.fromhex(e["raw_frame_hex"]); at=10+1+b[10]+(5 if target==131 else 2); b[at]^=1; b[-4:]=struct.pack("<I",zlib.crc32(b[2:-4])&0xffffffff); e["raw_frame_hex"]=b.hex()
    elif mutation=="duplicate_result":
        idx=next(i for i,e in enumerate(events) if e["direction"]=="RX" and kind(e)==130); events.insert(idx+1,dict(events[idx])); (path/"serial_transcript.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events)); refresh(path,True); return_bad=True
    elif mutation=="raw_result":
        rows=[json.loads(x) for x in (path/"raw_results.jsonl").read_text().splitlines()]; rows[0]["payload_hex"]="00"; (path/"raw_results.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows)); return_bad=True
    elif mutation=="sha":
        m=path/"metadata.json"; d=json.loads(m.read_text()); d["serial_transcript_sha256"]="0"*64; m.write_text(json.dumps(d)); return_bad=True
    elif mutation=="partial":
        e=events[0]; e["status"]="TIMEOUT"; e["frame_complete"]=False; (path/"serial_transcript.jsonl").write_text("".join(json.dumps(x)+"\n" for x in events)); m=json.loads((path/"metadata.json").read_text()); m["serial_transcript_complete"]=False; (path/"metadata.json").write_text(json.dumps(m)); s=json.loads((path/"transport_summary.json").read_text()); s["transport_status"]="FAIL_TRANSPORT"; (path/"transport_summary.json").write_text(json.dumps(s)); refresh(path); return_bad=True
    elif mutation=="frame_type":
        events[0]["frame_type"]="ACK"
    if "return_bad" not in locals():
        (path/"serial_transcript.jsonl").write_text("".join(json.dumps(e,separators=(",",":"))+"\n" for e in events)); refresh(path); return_bad=True
    report=v.verify_capture(path)
    assert report["verdict"] in ("TRANSCRIPT_FAILED","TRANSCRIPT_INCOMPLETE")

def test_cli_help_and_report_does_not_touch_capture(capture,tmp_path,capsys):
    with pytest.raises(SystemExit) as exc: v.main(["--help"])
    assert exc.value.code==0
    out=tmp_path/"report"; assert v.main(["--capture",str(capture),"--out",str(out)])==0
    assert json.loads((out/"verification.json").read_text())["verdict"]=="TARGET_EVIDENCE_NOT_VERIFIED"
