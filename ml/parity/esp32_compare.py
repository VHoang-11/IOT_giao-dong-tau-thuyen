"""Adapter and comparator for HV01-B1b ESP32 raw captures."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from ml.parity import c_host, compare, esp32_target, interchange
from ml.parity.contract import FEATURE_ORDER, SCHEMA_VERSION
from ml.parity.golden import MANIFEST, read_inputs

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "ml/data/parity/runs"
class CaptureError(ValueError):
    """Capture is incomplete, inconsistent, or does not match current golden data."""


def _read_json(path: Path) -> dict:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise CaptureError(f"Không đọc được {path}: {exc}") from exc


def _window_counts(frame, endpoint: int) -> dict:
    r=frame.roll_deg.to_numpy(float); p=frame.pitch_deg.to_numpy(float); end=endpoint+1
    short=r[max(0,end-600):end]; short_p=p[max(0,end-600):end]
    long_r=r[max(0,end-1800):end]; long_p=p[max(0,end-1800):end]
    both=np.isfinite(long_r)&np.isfinite(long_p); rf=np.isfinite(long_r)
    pairs=np.isfinite(short[:-1])&np.isfinite(short[1:])
    run=0
    for a,b in zip(r[:end][::-1],p[:end][::-1]):
        if math.isfinite(a) and math.isfinite(b): break
        run+=1
    ready_long=end>=1800
    blocks=[0,0,0]
    if ready_long:
        for j in range(3):
            lo=end-1800+j*600; blocks[j]=int(np.isfinite(r[lo:lo+600]).sum())
    return dict(ready_short=end>=600,ready_long=ready_long,
        n_valid_60=min(int(np.isfinite(short).sum()),int(np.isfinite(short_p).sum())),
        n_valid_180=int(both.sum()),roll_finite_60=int(np.isfinite(short).sum()),
        pitch_finite_60=int(np.isfinite(short_p).sum()),roll_pairs_60=int(pairs.sum()),
        roll_finite_180=int(rf.sum()),block0_finite=blocks[0],block1_finite=blocks[1],
        block2_finite=blocks[2],consec_invalid=min(run,65535))


def adapt_capture(capture: Path, suite: str, repo_root: Path=ROOT) -> tuple[list[dict],dict,dict]:
    """Validate a completed B1b run and convert target values to long interchange records."""
    capture=Path(capture); root=Path(repo_root).resolve()
    meta=_read_json(capture/"metadata.json"); summary=_read_json(capture/"transport_summary.json")
    if summary.get("transport_status")!="TRANSPORT_COMPLETE" or summary.get("numerical_parity")!="NUMERICAL_PARITY_NOT_RUN":
        raise CaptureError("Run transport không hoàn tất; capture không được dùng parity")
    if summary.get("cases_expected")!=summary.get("cases_completed") or summary.get("error"):
        raise CaptureError("Run thiếu case hoặc có lỗi transport")
    if not esp32_target.ID.fullmatch(str(meta.get("run_id",""))): raise CaptureError("run_id sai/thiếu")
    if meta.get("suite")!=suite: raise CaptureError("suite capture không khớp yêu cầu")
    if (meta.get("protocol_version")!=esp32_target.VERSION or meta.get("parity_schema_version")!=SCHEMA_VERSION
            or meta.get("feature_schema_version")!=esp32_target.FEATURE_SCHEMA_VERSION
            or meta.get("semantic_contract_version")!=esp32_target.SEMANTIC_CONTRACT_VERSION
            or meta.get("validity_policy_version")!=esp32_target.VALIDITY_POLICY_VERSION):
        raise CaptureError("Version protocol/feature/contract không khớp")
    hello=meta.get("device_hello") or {}
    if (hello.get("feature_count")!=23 or hello.get("feature_order_crc32")!=esp32_target.ORDER_CRC
            or hello.get("feature_schema")!=esp32_target.FEATURE_SCHEMA_VERSION
            or hello.get("semantic_version")!=esp32_target.SEMANTIC_CONTRACT_VERSION
            or hello.get("validity_version")!=esp32_target.VALIDITY_POLICY_VERSION
            or hello.get("parity_schema")!=SCHEMA_VERSION): raise CaptureError("HELLO không khớp schema/order")
    manifest_path=root/MANIFEST; manifest_raw=manifest_path.read_bytes(); manifest_sha=hashlib.sha256(manifest_raw).hexdigest()
    manifest_data=json.loads(manifest_raw)
    if meta.get("manifest_sha256")!=manifest_sha: raise CaptureError("Manifest SHA-256 khác golden hiện tại")
    suites=("synthetic","real") if suite=="all" else (suite,)
    if suite not in ("synthetic","real","all"): raise CaptureError("suite không hợp lệ")
    cases={}; frames={}; case_meta={}
    for name in suites:
        for filename in ("cases.json","expected_features.csv"):
            rel=(compare.suite_root(name)/filename).as_posix(); path=root/rel; entry=manifest_data.get("files",{}).get(rel)
            if not entry or hashlib.sha256(path.read_bytes()).hexdigest()!=entry.get("sha256") or path.stat().st_size!=entry.get("bytes"):
                raise CaptureError(f"Golden manifest SHA/size sai: {rel}")
        _,gold=compare.load_golden(root,name)
        for cid,c in gold.items():
            cases[cid]=c; case_meta[cid]=name
            path=root/c["input_file"]
            digest=hashlib.sha256(path.read_bytes()).hexdigest(); entry=manifest_data.get("files",{}).get(c["input_file"])
            if digest!=c["input_sha256"] or not entry or digest!=entry.get("sha256") or path.stat().st_size!=entry.get("bytes"):
                raise CaptureError(f"CSV SHA/manifest sai: {cid}")
            frames[cid]=read_inputs(path)
    cap_cases=meta.get("cases") or []
    if len(cap_cases)!=summary["cases_expected"] or len({c.get("case_id") for c in cap_cases})!=len(cap_cases):
        raise CaptureError("Case count hoặc case ID trùng trong metadata")
    for c in cap_cases:
        cid=c.get("case_id")
        if cid not in cases: raise CaptureError(f"Case ngoài suite golden: {cid}")
        g=cases[cid]; frame=frames[cid]
        if (c.get("input_sha256")!=g["input_sha256"] or c.get("sample_count")!=len(frame)
                or c.get("endpoints")!=[int(e["endpoint_index"]) for e in g["endpoints"]]
                or c.get("source_sample_index")!=frame.source_sample_index.tolist()
                or c.get("provenance")!=("SIMULATION" if case_meta[cid]=="synthetic" else "SENSOR")):
            raise CaptureError(f"Case provenance/SHA/endpoints không khớp: {cid}")
    if {c["case_id"] for c in cap_cases}!=set(cases): raise CaptureError("Capture thiếu case golden")
    records=[]; seen=set(); last_seq=-1
    expected_order=[(c["case_id"],int(e["endpoint_index"])) for c in cap_cases for e in cases[c["case_id"]]["endpoints"]]
    raw_path=capture/"raw_results.jsonl"
    try: raw_rows=[json.loads(s) for s in raw_path.read_text(encoding="utf-8").splitlines() if s.strip()]
    except (OSError,json.JSONDecodeError) as exc: raise CaptureError(f"raw_results.jsonl không hợp lệ: {exc}") from exc
    if summary.get("result_count")!=len(raw_rows): raise CaptureError("Số RESULT không khớp transport summary")
    for item in raw_rows:
        if item.get("provisional") is not False: raise CaptureError("RESULT provisional/incomplete không thể so sánh")
        try:
            frame_wire=esp32_target.decode_frame(bytes.fromhex(item["raw_frame_hex"]))
            payload=bytes.fromhex(item["payload_hex"])
            parsed=esp32_target.parse_result(payload)
        except (KeyError,ValueError,esp32_target.ProtocolError) as exc: raise CaptureError(f"RESULT frame sai: {exc}") from exc
        if frame_wire.kind!=130 or frame_wire.payload!=payload: raise CaptureError("Raw RESULT frame/payload không khớp")
        if frame_wire.seq<=last_seq: raise CaptureError("RESULT sequence không tăng")
        last_seq=frame_wire.seq
        result=item.get("result") or {}; cid=result.get("case_id"); ep=result.get("endpoint_index")
        key=(cid,ep)
        if key in seen: raise CaptureError(f"RESULT duplicate: {key}")
        seen.add(key)
        if key not in expected_order: raise CaptureError(f"RESULT endpoint thừa: {key}")
        if (result.get("input_csv_sha256")!=cases[cid]["input_sha256"]
                or parsed["case_id"]!=cid or parsed["endpoint_index"]!=ep
                or parsed["input_csv_sha256"]!=result.get("input_csv_sha256")
                or result.get("valid_mask")!=parsed["valid_mask"]): raise CaptureError(f"RESULT ID/SHA/mask sai: {key}")
        values=result.get("values")
        if not isinstance(values,list) or len(values)!=23 or result.get("feature_count",23)!=23:
            raise CaptureError("RESULT không có đúng 23 giá trị")
        mask=result["valid_mask"]
        if not isinstance(mask,int) or mask<0 or mask>>23: raise CaptureError("valid_mask ngoài 23 bit")
        if any(mask>>i&1 and (v is None or not math.isfinite(float(v))) for i,v in enumerate(values)):
            raise CaptureError(f"Feature VALID nhưng value null/non-finite: {key}")
        for i,value in enumerate(values):
            if ((mask>>i&1 and float(value)!=parsed["values"][i])
                    or (not (mask>>i&1) and value is not None)):
                raise CaptureError(f"JSON value không khớp raw RESULT (invalid không được thành 0): {key}, feature {i}")
        counts=_window_counts(frames[cid],ep); row=dict(counts,valid_mask=mask)
        target_counters=("ready_short","ready_long","n_valid_60","n_valid_180","consec_invalid")
        if any(result.get(k)!=counts[k] for k in target_counters): raise CaptureError(f"Counter target không khớp input: {key}")
        for i,name in enumerate(FEATURE_ORDER):
            value=values[i]; row[f"v{i:02d}"]=math.nan if value is None else float(value)
            status,reason,derived=c_host.derive_status(row,i)
            group=c_host.representability(frames[cid].time_seconds.to_numpy(float),ep)[c_host.feature_group(i)]
            if group: status,reason,derived=compare.NOT_EVALUABLE_STATUS,group,None
            records.append(dict(schema_version=SCHEMA_VERSION,case_id=cid,input_sha256=result["input_csv_sha256"],
                endpoint_index=ep,endpoint_time_seconds=float(frames[cid].time_seconds.iloc[ep]),feature_index=i,
                feature_name=name,status=status,reason_code=reason,value=value if status=="VALID" else derived))
    if seen!=set(expected_order) or [(r["result"]["case_id"],r["result"]["endpoint_index"]) for r in raw_rows]!=expected_order:
        raise CaptureError("RESULT endpoint thiếu hoặc sai thứ tự/count")
    return records,meta,summary


def compare_capture(capture: Path, suite: str, out_dir: Path, repo_root: Path=ROOT) -> dict:
    records,source,transport=adapt_capture(capture,suite,repo_root); results=[]
    manifest_sha=hashlib.sha256((Path(repo_root)/MANIFEST).read_bytes()).hexdigest()
    for name in (("synthetic","real") if suite=="all" else (suite,)):
        subset=[r for r in records if r["case_id"].startswith("SYN" if name=="synthetic" else "REAL_")]
        candidate=Path(out_dir)/f"{name}.csv"; metadata_path=Path(out_dir)/f"{name}.metadata.json"
        interchange.write_csv(subset,candidate)
        metadata={"interchange_schema":interchange.INTERCHANGE_SCHEMA,"schema_version":SCHEMA_VERSION,
            "golden_manifest_sha256":manifest_sha,"producer":{"kind":"independent_c_implementation",
            "name":"svmg_esp32_target_capture","version":"HV01-B2","source_commit":"NOT_AVAILABLE",
            "compiler":(source.get("device_hello") or {}).get("compiler","NOT_AVAILABLE"),"compiler_flags":(source.get("device_hello") or {}).get("build_flags","NOT_AVAILABLE"),
            "target":"esp32","float_type":"float32","accumulator_type":"float64"},
            "capture_host_source_commit":source.get("source_commit","NOT_AVAILABLE"),
            "firmware_sha256":source.get("firmware_sha256","NOT_AVAILABLE"),
            "status_adapter":c_host.STATUS_ADAPTER["name"],
            "not_evaluable_reason":c_host.NE_NO_TIMESTAMP,
            "execution_kind":source.get("execution_kind","NOT_AVAILABLE"),
            "target_evidence_status":"WOKWI_SIMULATION_ONLY" if source.get("execution_kind")=="wokwi_simulation" else "TARGET_EVIDENCE_NOT_VERIFIED"}
        metadata_path.write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
        result=compare.run_comparison(repo_root,name,candidate,metadata_path)
        s=result["summary"]; numerical_counts=s["outcome_counts"]
        s["numerical_fail_records"]=s["fail_records"]
        s["numerical_review_records"]=s["review_records"]
        s["numerical_not_evaluable_records"]=s["not_evaluable_records"]
        evidence={"host_mock":"MOCK_VERIFIED","wokwi_simulation":"WOKWI_SIMULATION_ONLY"}.get(source.get("execution_kind"),"TARGET_EVIDENCE_NOT_VERIFIED")
        s["numerical_outcome_counts"]=numerical_counts; s["verdict"]=evidence; s["is_c_parity_evidence"]=False
        s["execution_kind"]=source.get("execution_kind","NOT_AVAILABLE")
        s["session_scope"]=source.get("session_scope","full_session"); s["initial_rx_sequence"]=source.get("initial_rx_sequence",0)
        s["full_session_evidence"]=s["session_scope"]=="full_session"
        s["transport_status"]=transport["transport_status"]; s["target_evidence_status"]=evidence
        result["summary"]=s
        dest=Path(out_dir)/name; dest.mkdir(parents=True,exist_ok=True)
        result["rows"].to_csv(dest/"comparison_rows.csv",index=False,lineterminator="\n")
        (dest/"comparison_summary.json").write_text(json.dumps(s,indent=2,ensure_ascii=False,default=compare._json_default)+"\n",encoding="utf-8")
        (dest/"comparison_report.md").write_text(compare.markdown_report(result,f"ESP32 target comparator — {name}"),encoding="utf-8")
        results.append(result)
    return {"verdict":results[0]["summary"]["verdict"] if all(r["summary"]["verdict"]==results[0]["summary"]["verdict"] for r in results) else "TARGET_EVIDENCE_NOT_VERIFIED",
            "comparisons":[r["summary"] for r in results]}


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Chuyển capture ESP32 sang interchange và so với golden; không xác thực phần cứng.")
    parser.add_argument("--capture",type=Path,required=True); parser.add_argument("--suite",choices=("synthetic","real","all"),default="synthetic")
    parser.add_argument("--out",type=Path); args=parser.parse_args(argv)
    try:
        meta=_read_json(args.capture/"metadata.json"); run_id=meta.get("run_id","unknown")
        out=args.out or OUTPUT_ROOT/f"esp32_b2_{run_id}"
        result=compare_capture(args.capture,args.suite,out)
        print(json.dumps(result,indent=2,ensure_ascii=False,default=compare._json_default))
        return 1 if any(s["numerical_fail_records"] for s in result["comparisons"]) else 0
    except (CaptureError,OSError,ValueError) as exc:
        print(f"FAIL_CAPTURE: {exc}"); return 2


if __name__=="__main__": raise SystemExit(main())
