import hashlib, json, math, struct, zlib

import pytest

from ml.parity import esp32_target as p

def hello(schema=None):
    fields=("svmg-angle-23-v1","svmg-angle23-semantics-1.0.0","svmg-angle23-validity-1.0.0",
            schema or "svmg-angle23-0.2.0-proposal","hv01-a-1 / esp32dev / Arduino","flags","compiler","sdk","ESP32")
    return struct.pack("<BBI",1,23,p.ORDER_CRC)+b"".join(bytes([len(x)])+x.encode() for x in fields)+struct.pack("<HH",1,240)

def result(case,endpoint,sha=None):
    cid=case["id"].encode(); values=[0x3fa00000]+[0x7fc00000]*22
    return (bytes([len(cid)])+cid+struct.pack("<I32sIIB",endpoint,sha or case["sha"],25,1,3)+
            struct.pack("<HHHfBBB",600,1800,0,98.5,0,0,23)+struct.pack("<23I",*values))

class MockSerial:
    def __init__(self,mode="ok"):
        self.rx=bytearray(); self.mode=mode; self.tx=0; self.rxseq=0; self.sent=[]; self.written=[]
        self.rx_frames=[]; self.tx_frames=[]
        self.run=""; self.manifest=b""; self.case=None; self.received=0; self.expected_cases=1; self.completed=0
        self.push(128,hello("wrong" if mode=="bad_hello" else None))
        if mode=="repeat_hello": self.push(128,hello())

    def push(self,kind,payload=b""):
        raw=p.encode_frame(kind,self.rxseq,payload); self.rx.extend(raw); self.rx_frames.append(raw)
        self.rxseq+=1; self.sent.append(kind)

    def ack(self,f,count,code=0): self.push(129,struct.pack("<IBI",f.seq,code,count))

    def write(self,wire):
        if self.mode=="short_write": return len(wire)-1
        self.tx_frames.append(bytes(wire))
        f=p.decode_frame(wire,self.tx); self.tx+=1
        self.written.append(f.kind)
        if f.kind==1:
            n=f.payload[0]; self.run=f.payload[1:1+n].decode(); self.expected_cases=struct.unpack_from("<H",f.payload,1+n)[0]; self.manifest=f.payload[3+n:35+n]
            if self.mode=="error": self.push(143,b"\x07\x01")
            else: self.ack(f,0,1 if self.mode=="nack" else 0)
        elif f.kind==2:
            b=f.payload; n=b[0]; pos=1+n; count,ne=struct.unpack_from("<IB",b,pos); pos+=5
            eps=list(struct.unpack_from("<"+"I"*ne,b,pos)); pos+=4*ne
            self.case=dict(id=b[1:1+n].decode(),count=count,endpoints=eps,sha=b[pos:pos+32],crc=struct.unpack_from("<I",b,pos+32)[0])
            self.received=0; self.ack(f,0)
        elif f.kind==3:
            first,n=struct.unpack_from("<IB",f.payload); end=first+n; self.received=end
            for e in self.case["endpoints"]:
                if first<=e<end: self.push(130,result(self.case,e,b"0"*32 if self.mode=="wrong_sha" else None))
            self.ack(f,end+int(self.mode=="bad_count"))
        elif f.kind==4:
            self.ack(f,self.received)
            if self.mode!="no_case_done":
                c=self.case; cid=c["id"].encode()
                self.push(131,bytes([len(cid)])+cid+struct.pack("<IBIB",c["count"],len(c["endpoints"]),c["crc"],0))
            self.completed+=1
        elif f.kind==5:
            self.ack(f,self.received)
            if self.mode!="no_run_done":
                rid=self.run.encode(); self.push(132,bytes([len(rid)])+rid+struct.pack("<H32sB",self.completed,self.manifest,0))
        return len(wire)

    def read(self,n):
        out=bytes(self.rx[:n]); del self.rx[:n]; return out

    def flush(self): pass

def ready(mode="ok",endpoints=(0,1),transcript_path=None):
    io=MockSerial(mode); s=p.TargetSession(io,0.005,transcript_path=transcript_path); s.wait_hello()
    s.begin_run("run_1",1,"ab"*32)
    records=struct.pack("<ffBB",float("nan"),0.1,2,1)+struct.pack("<ffBB",1.0,-2.0,2,1)
    crc=zlib.crc32(records)&0xffffffff; sha="cd"*32
    s.begin_case("SYN01",len(records)//10,list(endpoints),sha,crc)
    return io,s,records,crc,sha

def test_frame_encode_decode_crc_and_little_endian():
    raw=p.encode_frame(3,0x1234,b"abc"); f=p.decode_frame(raw,0x1234)
    assert raw[:2]==b"SV" and raw[2:10]==struct.pack("<BBIH",1,3,0x1234,3) and f.payload==b"abc"
    with pytest.raises(p.ProtocolError,match="CRC32"): p.decode_frame(raw[:-1]+bytes([raw[-1]^1]))

def test_bad_sequence_version_length_and_payload_rejected():
    raw=p.encode_frame(1,2)
    with pytest.raises(p.ProtocolError,match="sequence"): p.decode_frame(raw,1)
    with pytest.raises(p.ProtocolError,match="payload"): p.encode_frame(1,0,b"x"*385)
    bad=bytearray(raw); struct.pack_into("<H",bad,8,385)
    with pytest.raises(p.ProtocolError,match="length"): p.decode_frame(bytes(bad))
    bad=bytearray(raw); bad[2]=2
    # Recompute CRC so the version check, rather than CRC, rejects this frame.
    bad[-4:]=struct.pack("<I",zlib.crc32(bad[2:-4])&0xffffffff)
    with pytest.raises(p.ProtocolError,match="version"): p.decode_frame(bytes(bad))

def test_hello_contract_and_repeated_hello_during_run_start():
    io=MockSerial("repeat_hello")
    s=p.TargetSession(io,.005); assert s.wait_hello()["feature_count"]==23
    s.begin_run("run_1",1,"ab"*32)
    assert s.state=="IN_RUN" and io.sent[:2]==[128,128]
    with pytest.raises(p.ProtocolError,match="contract mismatch"): p.parse_hello(hello("bad"))

def test_ack_result_terminal_and_error_payload_decoders():
    assert p.parse_ack(struct.pack("<IBI",3,0,99))["samples_received"]==99
    c={"id":"SYN01","sha":bytes.fromhex("cd"*32)}; r=p.parse_result(result(c,4))
    assert len(r["values"])==23 and r["values"][0]==1.25 and math.isnan(r["values"][1])
    done=p.parse_case_done(b"\x01x"+struct.pack("<IBIB",2,1,3,0))
    assert done["status"]==0 and p.parse_run_done(b"\x01r"+struct.pack("<H32sB",1,b"z"*32,0))["cases_completed"]==1
    assert p.parse_error(b"\x07\x01")["fatal"]

def test_nack_and_fatal_error_are_rejected():
    io=p.TargetSession(MockSerial("nack"),.005); io.wait_hello()
    with pytest.raises(p.ProtocolError,match="NACK"): io.begin_run("run_1",1,"ab"*32)
    io=p.TargetSession(MockSerial("error"),.005); io.wait_hello()
    with pytest.raises(p.ProtocolError,match="ERROR"): io.begin_run("run_1",1,"ab"*32)
    io=p.TargetSession(MockSerial("short_write"),.005); io.wait_hello()
    with pytest.raises(p.ProtocolError,match="write lỗi"): io.begin_run("run_1",1,"ab"*32)
    assert io.state=="FAILED"

def test_timeout_fails_transport():
    empty=type("Empty",(),{"read":lambda self,n:b""})()
    with pytest.raises(p.ProtocolError,match="timeout"): p.TargetSession(empty,.001).wait_hello()

def test_case_and_run_states_require_terminal_completion():
    io,s,records,_,_=ready("no_case_done")
    with pytest.raises(p.ProtocolError,match="incomplete"): s.end_case()
    with pytest.raises(p.ProtocolError,match="RUN_END"): s.end_run()
    s.send_samples(0,records)
    with pytest.raises(p.ProtocolError,match="timeout"): s.end_case()

def test_missing_run_done_is_not_transport_success():
    io,s,records,_,_=ready("no_run_done"); s.send_samples(0,records); s.end_case()
    with pytest.raises(p.ProtocolError,match="timeout"): s.end_run()
    assert not s.transport_complete and s.state=="FAILED"

def test_duplicate_endpoints_bad_sha_count_and_sample_crc_are_rejected():
    io=p.TargetSession(MockSerial(),.005); io.wait_hello(); io.begin_run("run_1",1,"ab"*32)
    with pytest.raises(p.ProtocolError,match="endpoint"): io.begin_case("SYN01",2,[1,1],"cd"*32,0)
    io,s,records,crc,sha=ready()
    with pytest.raises(p.ProtocolError,match="samples_received"): ready("bad_count")[1].send_samples(0,records)
    io,s,records,_,_=ready("wrong_sha")
    with pytest.raises(p.ProtocolError,match="case/input SHA"): s.send_samples(0,records)
    io,s,records,_,_=ready()
    s.case["samples_crc"]^=1; s.send_samples(0,records)
    with pytest.raises(p.ProtocolError,match="CRC"): s.end_case()

def test_happy_path_requires_case_done_and_run_done():
    io,s,records,_,_=ready(); got=s.send_samples(0,records)
    assert [r["endpoint_index"] for r in got]==[0,1]
    assert io.sent.index(130)<io.sent.index(129,io.sent.index(130))
    assert struct.unpack_from("<I",records)[0]==0x7fc00000
    assert s.end_case()["case_id"]=="SYN01"
    assert s.end_run()["run_id"]=="run_1" and s.transport_complete and s.state=="COMPLETE"


def test_canonical_loader_checks_fixture_hash_order_and_float32_bits():
    cases,manifest_sha=p.load_suite("synthetic")
    assert len(cases)==31 and len(manifest_sha)==64
    c=cases[0]
    assert c["case_id"]=="SYN01_const_zero" and c["endpoints"]==[e["endpoint_index"] for e in __import__("json").loads((p.SYNTHETIC_CASES).read_text())["cases"][0]["endpoints"]]
    assert len(c["records"])==c["sample_count"]*10 and len(c["source_sample_index"])==c["sample_count"]
    assert c["records"][:10]==struct.pack("<ffBB",0.0,0.0,2,1)
    nan_case=next(x for x in cases if x["case_id"]=="SYN21_isolated_nan")
    nan_record=next(nan_case["records"][i*10:i*10+10] for i in range(nan_case["sample_count"])
                    if math.isnan(struct.unpack_from("<f",nan_case["records"],i*10)[0]))
    assert struct.unpack_from("<I",nan_record)[0]==0x7fc00000 and nan_record[8:]==b"\x02\x01"
    inf_case=next(x for x in cases if x["case_id"]=="SYN26_infinite_values")
    assert any(struct.unpack_from("<I",inf_case["records"],i*10)[0]==0x7f800000
               for i in range(inf_case["sample_count"]))


def test_fixture_loader_rejects_unavailable_suite_and_float32_nan_bits():
    if p.REAL_CASES.is_file():
        real,_=p.load_suite("real"); both,_=p.load_suite("all")
        assert len(real)==5 and len(both)==36 and real[0]["provenance"]=="SENSOR"
    else:
        with pytest.raises(FileNotFoundError,match="NOT_AVAILABLE"): p.load_suite("real")
    rec=struct.pack("<ffBB",float("nan"),float("inf"),2,1)
    assert struct.unpack_from("<I",rec)[0]==0x7fc00000
    assert struct.unpack_from("<I",rec,4)[0]==0x7f800000 and rec[8:]==b"\x02\x01"


def test_fixture_loader_rejects_csv_sha_mismatch(tmp_path,monkeypatch):
    import hashlib, json
    root=tmp_path; base=root/"ml/parity/fixtures/synthetic"; base.mkdir(parents=True)
    csv_path=base/"tiny.csv"; csv_path.write_text("sample_index,time_seconds,roll_deg,pitch_deg,source_sample_index\n0,0,0.0,0.0,17\n")
    rel="ml/parity/fixtures/synthetic/tiny.csv"; digest=hashlib.sha256(csv_path.read_bytes()).hexdigest()
    cases={"suite":"synthetic","schema_version":p.SCHEMA_VERSION,"schema_sha256":"s",
        "feature_order":list(p.FEATURE_ORDER),"cases":[{"case_id":"SYN_TEST","input_file":rel,
        "input_sha256":digest,"n_samples":1,"endpoint_count":1,"endpoints":[{"endpoint_index":0}]}]}
    case_path=base/"cases.json"; case_path.write_text(json.dumps(cases)); case_rel="ml/parity/fixtures/synthetic/cases.json"
    manifest={"schema_sha256":"s","files":{case_rel:{"sha256":hashlib.sha256(case_path.read_bytes()).hexdigest(),"bytes":case_path.stat().st_size},
        rel:{"sha256":digest,"bytes":csv_path.stat().st_size}}}
    manifest_path=root/"ml/parity/fixtures/manifest.json"; manifest_path.parent.mkdir(parents=True,exist_ok=True)
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(p,"ROOT",root); monkeypatch.setattr(p,"SYNTHETIC_CASES",case_path); monkeypatch.setattr(p,"MANIFEST_PATH",manifest_path)
    loaded,_=p.load_suite(); assert loaded[0]["source_sample_index"]==[17]
    csv_path.write_text(csv_path.read_text().replace(",0.0,0.0,17",",1.0,0.0,17"))
    with pytest.raises(p.ProtocolError,match="SHA/manifest"): p.load_suite()


def test_real_synthetic_fixtures_stream_through_b1a_session_in_multiple_batches_and_cases(tmp_path):
    cases,manifest_sha=p.load_suite("synthetic"); cases=cases[:2]
    io=MockSerial(); session=p.TargetSession(io,.02)
    report=p.run_suite(session,cases,"fixture_run",manifest_sha)
    assert report["transport_status"]=="TRANSPORT_COMPLETE"
    assert report["numerical_parity"]=="NUMERICAL_PARITY_NOT_RUN"
    assert report["completed_case_ids"]==[c["case_id"] for c in cases]
    assert session.completed_cases==2 and len(session.results)==32
    assert io.written.count(3)>2 and session.transport_complete
    p.save_capture(tmp_path,"fixture_run","synthetic",manifest_sha,cases,session,"TRANSPORT_COMPLETE")
    import json
    meta=json.loads((tmp_path/"metadata.json").read_text())
    raw=[json.loads(x) for x in (tmp_path/"raw_results.jsonl").read_text().splitlines()]
    assert meta["cases"][0]["provenance"]=="SIMULATION" and meta["source_commit"]
    assert len(raw)==32 and raw[0]["result"]["values"][1] is None
    assert raw[0]["result"]["valid_mask"]==1 and not raw[0]["provisional"]


def test_incomplete_capture_is_never_marked_complete(tmp_path):
    io,s,records,_,_=ready("no_run_done"); s.send_samples(0,records); s.end_case()
    with pytest.raises(p.ProtocolError): s.end_run()
    p.save_capture(tmp_path,"run_1","synthetic","ab"*32,[],s,"FAIL_TRANSPORT",error="terminal missing")
    import json
    summary=json.loads((tmp_path/"transport_summary.json").read_text())
    raw=[json.loads(x) for x in (tmp_path/"raw_results.jsonl").read_text().splitlines()]
    assert summary["transport_status"]=="FAIL_TRANSPORT" and summary["numerical_parity"]=="NUMERICAL_PARITY_NOT_RUN"
    assert all(r["provisional"] for r in raw)
    transcript=(tmp_path/"serial_transcript.jsonl").read_bytes()
    assert summary["serial_transcript_complete"] is False
    assert summary["serial_transcript_sha256"]==hashlib.sha256(transcript).hexdigest()
    assert json.loads(transcript.splitlines()[-1])["status"]=="TIMEOUT"


def test_transcript_preserves_actual_tx_rx_bytes_and_result_before_ack(tmp_path):
    path=tmp_path/"serial_transcript.jsonl"
    io,s,records,_,_=ready("repeat_hello",transcript_path=path)
    s.send_samples(0,records); s.end_case(); s.end_run()
    # Events were collected from the exact mock serial read/write byte strings.
    events=s.transcript
    tx=[bytes.fromhex(e["raw_frame_hex"]) for e in events if e["direction"]=="TX"]
    rx=[bytes.fromhex(e["raw_frame_hex"]) for e in events if e["direction"]=="RX" and e["status"]=="OK"]
    assert tx==io.tx_frames and rx==io.rx_frames
    kinds=[e["frame_type"] for e in events]
    assert [e["frame_type"] for e in events if e["direction"]=="RX"][:2]==["HELLO","HELLO"]
    assert kinds.index("RESULT")<kinds.index("ACK",kinds.index("RESULT"))
    assert "CASE_DONE" in kinds and "RUN_DONE" in kinds
    assert s.transcript_complete
    p.save_capture(tmp_path,"run_1","synthetic","ab"*32,[],s,"TRANSPORT_COMPLETE")
    saved=(tmp_path/"serial_transcript.jsonl").read_bytes()
    metadata=json.loads((tmp_path/"metadata.json").read_text())
    assert hashlib.sha256(saved).hexdigest()==metadata["serial_transcript_sha256"]
    assert metadata["capture_status"]=="HOST_MOCK_VERIFIED"
    assert metadata["target_evidence_status"]=="TARGET_EVIDENCE_NOT_VERIFIED"
    assert metadata["numerical_parity"]=="NUMERICAL_PARITY_NOT_RUN"


def test_transcript_retains_nack_error_and_partial_frame_diagnostics():
    s=p.TargetSession(MockSerial("nack"),.005); s.wait_hello()
    with pytest.raises(p.ProtocolError,match="NACK"): s.begin_run("run_1",1,"ab"*32)
    assert [e["frame_type"] for e in s.transcript if e["direction"]=="RX"]==["HELLO","ACK"]
    assert s.transcript[-1]["raw_frame_hex"]
    s=p.TargetSession(MockSerial("error"),.005); s.wait_hello()
    with pytest.raises(p.ProtocolError,match="ERROR"): s.begin_run("run_1",1,"ab"*32)
    assert any(e["frame_type"]=="ERROR" and e["raw_frame_hex"] for e in s.transcript)


def test_transcript_artifacts_do_not_overwrite_existing_files(tmp_path):
    io,s,records,_,_=ready(); s.send_samples(0,records); s.end_case(); s.end_run()
    p.save_capture(tmp_path,"run_1","synthetic","ab"*32,[],s,"TRANSPORT_COMPLETE")
    original=(tmp_path/"serial_transcript.jsonl").read_bytes()
    with pytest.raises(FileExistsError):
        p.save_capture(tmp_path,"run_1","synthetic","ab"*32,[],s,"TRANSPORT_COMPLETE")
    assert (tmp_path/"serial_transcript.jsonl").read_bytes()==original


def test_cli_help_and_argument_errors_without_pyserial():
    with pytest.raises(SystemExit) as help_exit: p.main(["--help"])
    assert help_exit.value.code==0
    with pytest.raises(SystemExit): p.main(["--port","mock","--run-id","bad id"])


def test_cli_missing_pyserial_fails_closed(tmp_path,monkeypatch,capsys):
    import builtins
    original=builtins.__import__
    def no_serial(name,*args,**kwargs):
        if name=="serial": raise ImportError("mock missing pyserial")
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,"__import__",no_serial)
    code=p.main(["--port","mock","--run-id","no_serial","--output",str(tmp_path)])
    assert code==2 and "pip install pyserial" in capsys.readouterr().err
