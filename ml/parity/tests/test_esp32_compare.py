import hashlib
import json
import struct

import pytest

from ml.parity import compare, esp32_compare as ec, esp32_target as target, interchange
from ml.parity.contract import SCHEMA_VERSION
from ml.parity.golden import MANIFEST, read_inputs


def mock_capture(path, mutation=None):
    cases=json.loads((target.FIXTURES/"synthetic/cases.json").read_text())["cases"]
    manifest_sha=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(); cap_cases=[]; raw=[]; seq=0
    for case in cases:
        frame=read_inputs(ec.ROOT/case["input_file"])
        cap_cases.append(dict(case_id=case["case_id"],input_sha256=case["input_sha256"],
            sample_count=len(frame),endpoints=[e["endpoint_index"] for e in case["endpoints"]],
            source_sample_index=frame.source_sample_index.tolist(),provenance="SIMULATION"))
        for endpoint in cap_cases[-1]["endpoints"]:
            counts=ec._window_counts(frame,endpoint); mask=0; values=[0x7fc00000]*23
            if case["case_id"]=="SYN01_const_zero" and endpoint==600: mask|=1; values[0]=0
            if case["case_id"]=="SYN29_block_step_symmetric" and endpoint==2100: mask|=1<<18; values[18]=0
            if case["case_id"]=="SYN19_epsilon_above" and endpoint==2100: mask|=1<<16; values[16]=0x3f800000
            if mutation=="value" and case["case_id"]=="SYN01_const_zero" and endpoint==600:
                values[0]=struct.unpack("<I",struct.pack("<f",2.0))[0]
            payload=(bytes([len(case["case_id"])])+case["case_id"].encode()+
                struct.pack("<I32sIIB",endpoint,bytes.fromhex(case["input_sha256"]),20,mask,
                            int(counts["ready_short"])+2*int(counts["ready_long"]))+
                struct.pack("<HHHfBBB",counts["n_valid_60"],counts["n_valid_180"],counts["consec_invalid"],
                            100.0,0,0,23)+struct.pack("<23I",*values))
            decoded=dict(case_id=case["case_id"],endpoint_index=endpoint,input_csv_sha256=case["input_sha256"],
                valid_mask=mask,ready_short=counts["ready_short"],ready_long=counts["ready_long"],
                n_valid_60=counts["n_valid_60"],n_valid_180=counts["n_valid_180"],
                consec_invalid=counts["consec_invalid"],values=[struct.unpack("<f",struct.pack("<I",v))[0] if mask>>i&1 else None for i,v in enumerate(values)])
            if mutation=="value" and case["case_id"]=="SYN01_const_zero" and endpoint==600: decoded["values"][0]=2.0
            if mutation=="invalid_zero" and case["case_id"]=="SYN01_const_zero" and endpoint==600: decoded["values"][1]=0.0
            raw.append(dict(raw_frame_hex=target.encode_frame(130,seq,payload).hex(),payload_hex=payload.hex(),
                            result=decoded,provisional=False)); seq+=1
    meta=dict(run_id="b2_mock",suite="synthetic",manifest_sha256=manifest_sha,
        protocol_version=target.VERSION,parity_schema_version=SCHEMA_VERSION,
        feature_schema_version=target.FEATURE_SCHEMA_VERSION,semantic_contract_version=target.SEMANTIC_CONTRACT_VERSION,
        validity_policy_version=target.VALIDITY_POLICY_VERSION,source_commit="mock",execution_kind="host_mock",
        device_hello=dict(feature_count=23,feature_order_crc32=target.ORDER_CRC,
            feature_schema=target.FEATURE_SCHEMA_VERSION,semantic_version=target.SEMANTIC_CONTRACT_VERSION,
            validity_version=target.VALIDITY_POLICY_VERSION,parity_schema=SCHEMA_VERSION),cases=cap_cases)
    summary=dict(transport_status="TRANSPORT_COMPLETE",numerical_parity="NUMERICAL_PARITY_NOT_RUN",
        cases_expected=len(cases),cases_completed=len(cases),result_count=len(raw),error=None)
    path.mkdir(parents=True); (path/"metadata.json").write_text(json.dumps(meta))
    (path/"transport_summary.json").write_text(json.dumps(summary))
    (path/"raw_results.jsonl").write_text("".join(json.dumps(r)+"\n" for r in raw))
    return meta,summary,raw


@pytest.fixture
def capture(tmp_path):
    return tmp_path/"capture"


def test_mock_capture_adapts_status_and_keeps_c04_not_evaluable(capture):
    mock_capture(capture); records,_,_=ec.adapt_capture(capture,"synthetic")
    by_key={(r["case_id"],r["endpoint_index"],r["feature_index"]):r for r in records}
    ne=[r for r in records if r["status"]==compare.NOT_EVALUABLE_STATUS]
    assert len(ne)==46 and {r["case_id"] for r in ne}=={"SYN23_timestamp_gap","SYN24_single_dropped_sample"}
    assert by_key[("SYN01_const_zero",600,0)]["status"]=="VALID"
    assert by_key[("SYN29_block_step_symmetric",2100,18)]["value"]==0.0
    assert by_key[("SYN29_block_step_symmetric",2100,18)]["status"]=="VALID"


def test_status_adapter_preserves_c01_c02_c03_rules(capture):
    mock_capture(capture); rows,_,_=ec.adapt_capture(capture,"synthetic")
    keys={(r["case_id"],r["endpoint_index"],r["feature_index"]):r for r in rows}
    for cid in ("SYN22_nan_excess","SYN27_block_coverage_rule"):
        block=[r for r in rows if r["case_id"]==cid and r["feature_index"]==12 and r["endpoint_index"]>=1800]
        assert any(r["status"]=="INVALID_INPUT" and r["reason_code"]=="SEGMENT_BLOCK_COVERAGE" for r in block)
    ratio=keys[("SYN17_zero_early_block",2100,16)]
    assert ratio["status"]=="UNDEFINED_MATHEMATICALLY" and ratio["reason_code"]=="EARLY_RMS_AT_OR_BELOW_EPSILON"
    assert keys[("SYN18_epsilon_below",2100,16)]["reason_code"]=="EARLY_RMS_AT_OR_BELOW_EPSILON"
    assert keys[("SYN19_epsilon_above",2100,16)]["status"]=="VALID"
    assert keys[("SYN29_block_step_symmetric",2100,18)]["status"]=="VALID"
    assert keys[("SYN30_permuted_blocks",2100,18)]["reason_code"]=="CONSTANT_RMS_TREND"


def test_capture_rejects_incomplete_sha_schema_duplicate_and_missing(capture):
    meta,summary,raw=mock_capture(capture)
    summary["transport_status"]="FAIL_TRANSPORT"; (capture/"transport_summary.json").write_text(json.dumps(summary))
    with pytest.raises(ec.CaptureError,match="transport"): ec.adapt_capture(capture,"synthetic")
    summary["transport_status"]="TRANSPORT_COMPLETE"; (capture/"transport_summary.json").write_text(json.dumps(summary))
    meta["manifest_sha256"]="0"*64; (capture/"metadata.json").write_text(json.dumps(meta))
    with pytest.raises(ec.CaptureError,match="Manifest SHA"): ec.adapt_capture(capture,"synthetic")
    meta["manifest_sha256"]=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(); meta["feature_schema_version"]="wrong"
    (capture/"metadata.json").write_text(json.dumps(meta))
    with pytest.raises(ec.CaptureError,match="Version"): ec.adapt_capture(capture,"synthetic")
    meta["feature_schema_version"]=target.FEATURE_SCHEMA_VERSION; (capture/"metadata.json").write_text(json.dumps(meta))
    duplicate=dict(raw[0]); last=target.decode_frame(bytes.fromhex(raw[-1]["raw_frame_hex"]))
    duplicate["raw_frame_hex"]=target.encode_frame(130,last.seq+1,bytes.fromhex(duplicate["payload_hex"])).hex()
    raw.append(duplicate); summary["result_count"]+=1
    (capture/"transport_summary.json").write_text(json.dumps(summary)); (capture/"raw_results.jsonl").write_text("".join(json.dumps(r)+"\n" for r in raw))
    with pytest.raises(ec.CaptureError,match="duplicate"): ec.adapt_capture(capture,"synthetic")
    raw.pop(); summary["result_count"]-=1
    (capture/"transport_summary.json").write_text(json.dumps(summary)); (capture/"raw_results.jsonl").write_text("".join(json.dumps(r)+"\n" for r in raw[:-1]))
    summary["result_count"]-=1; (capture/"transport_summary.json").write_text(json.dumps(summary))
    with pytest.raises(ec.CaptureError,match="thiếu"): ec.adapt_capture(capture,"synthetic")


def test_capture_rejects_wrong_input_sha(capture):
    meta,_,raw=mock_capture(capture); raw[0]["result"]["input_csv_sha256"]="0"*64
    (capture/"raw_results.jsonl").write_text("".join(json.dumps(r)+"\n" for r in raw))
    with pytest.raises(ec.CaptureError,match="SHA/mask"): ec.adapt_capture(capture,"synthetic")


def test_invalid_zero_and_out_of_tolerance_are_comparator_failures(capture,tmp_path):
    mock_capture(capture,"invalid_zero")
    with pytest.raises(ec.CaptureError,match="invalid không được thành 0"):
        ec.adapt_capture(capture,"synthetic")
    expected,cases=compare.load_golden(ec.ROOT,"synthetic")
    record=dict(schema_version=SCHEMA_VERSION,case_id="SYN01_const_zero",
        input_sha256=cases["SYN01_const_zero"]["input_sha256"],endpoint_index=600,
        endpoint_time_seconds=60.0,feature_index=1,feature_name="roll_std_60",
        status="INVALID_INPUT",reason_code="SIGNAL_VALID_COVERAGE",value=0.0)
    candidate=interchange.from_records([record])
    result=compare.compare_frames(expected,candidate,cases)
    assert "FAIL_INVALID_HAS_VALUE" in set(result["rows"].outcome)


def test_mock_is_never_reported_as_target_parity(capture,tmp_path):
    mock_capture(capture)
    result=ec.compare_capture(capture,"synthetic",tmp_path/"out")
    assert result["verdict"]=="MOCK_VERIFIED"
    assert all(not summary["is_c_parity_evidence"] for summary in result["comparisons"])


def test_b1b_capture_without_independent_execution_evidence_is_unverified(capture,tmp_path):
    meta,_,_=mock_capture(capture); meta.pop("execution_kind")
    (capture/"metadata.json").write_text(json.dumps(meta))
    result=ec.compare_capture(capture,"synthetic",tmp_path/"out")
    assert result["verdict"]=="TARGET_EVIDENCE_NOT_VERIFIED"


def test_comparator_rejects_out_of_range_r2():
    expected,cases=compare.load_golden(ec.ROOT,"synthetic")
    record=dict(schema_version=SCHEMA_VERSION,case_id="SYN29_block_step_symmetric",
        input_sha256=cases["SYN29_block_step_symmetric"]["input_sha256"],endpoint_index=2100,
        endpoint_time_seconds=210.0,feature_index=18,feature_name="roll_rms_trend_r2_180",
        status="VALID",reason_code="",value=1.1)
    rows=compare.compare_frames(expected,interchange.from_records([record]),cases)["rows"]
    assert "FAIL_R2_OUT_OF_RANGE" in set(rows.outcome)


def test_capture_numeric_difference_uses_shared_tolerance(capture,tmp_path):
    mock_capture(capture,"value")
    result=ec.compare_capture(capture,"synthetic",tmp_path/"out")
    assert result["comparisons"][0]["numerical_outcome_counts"].get("FAIL_VALUE_TOLERANCE",0)>0
    assert result["verdict"]=="MOCK_VERIFIED" and not result["comparisons"][0]["is_c_parity_evidence"]
    assert (tmp_path/"out/synthetic/comparison_rows.csv").is_file()
