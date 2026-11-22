import math, struct, zlib

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
        self.rx=bytearray(); self.mode=mode; self.tx=0; self.rxseq=0; self.sent=[]
        self.run=""; self.manifest=b""; self.case=None; self.received=0
        self.push(128,hello("wrong" if mode=="bad_hello" else None))
        if mode=="repeat_hello": self.push(128,hello())

    def push(self,kind,payload=b""):
        self.rx.extend(p.encode_frame(kind,self.rxseq,payload)); self.rxseq+=1; self.sent.append(kind)

    def ack(self,f,count,code=0): self.push(129,struct.pack("<IBI",f.seq,code,count))

    def write(self,wire):
        if self.mode=="short_write": return len(wire)-1
        f=p.decode_frame(wire,self.tx); self.tx+=1
        if f.kind==1:
            n=f.payload[0]; self.run=f.payload[1:1+n].decode(); self.manifest=f.payload[3+n:35+n]
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
        elif f.kind==5:
            self.ack(f,self.received)
            if self.mode!="no_run_done":
                rid=self.run.encode(); self.push(132,bytes([len(rid)])+rid+struct.pack("<H32sB",1,self.manifest,0))
        return len(wire)

    def read(self,n):
        out=bytes(self.rx[:n]); del self.rx[:n]; return out

    def flush(self): pass

def ready(mode="ok",endpoints=(0,1)):
    io=MockSerial(mode); s=p.TargetSession(io,0.005); s.wait_hello()
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
