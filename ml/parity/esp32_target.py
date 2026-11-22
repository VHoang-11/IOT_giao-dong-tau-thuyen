"""Serial v1 transport and transaction state machine for the HV01-A target."""
from __future__ import annotations

import math, re, struct, time, zlib
from dataclasses import dataclass

from ml.parity.contract import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, SCHEMA_VERSION, SEMANTIC_CONTRACT_VERSION, VALIDITY_POLICY_VERSION

VERSION, MAX_PAYLOAD = 1, 384
MAX_BATCH, MAX_CASES, MAX_SAMPLES, MAX_ENDPOINTS = 32, 64, 4096, 32
TYPES = {1:"RUN_BEGIN",2:"CASE_BEGIN",3:"SAMPLES",4:"CASE_END",5:"RUN_END",
         128:"HELLO",129:"ACK",130:"RESULT",131:"CASE_DONE",132:"RUN_DONE",143:"ERROR"}
ORDER_CRC = zlib.crc32(b"".join(n.encode()+b"\0" for n in FEATURE_ORDER)) & 0xffffffff
ID = re.compile(r"^[A-Za-z0-9_.-]+$")

class ProtocolError(RuntimeError):
    """Invalid frame, response, or transaction state; reconnect/reset before reuse."""

@dataclass(frozen=True)
class Frame:
    version: int
    kind: int
    seq: int
    payload: bytes

def encode_frame(kind: int, seq: int, payload: bytes = b"") -> bytes:
    if len(payload)>MAX_PAYLOAD or not 0<=seq<=0xffffffff or kind not in TYPES:
        raise ProtocolError("type, sequence hoặc payload vượt giới hạn")
    body=struct.pack("<BBIH",VERSION,kind,seq,len(payload))+payload
    return b"\x53\x56"+body+struct.pack("<I",zlib.crc32(body)&0xffffffff)

def decode_frame(raw: bytes, expected_seq: int | None = None) -> Frame:
    if len(raw)<14 or raw[:2]!=b"\x53\x56": raise ProtocolError("sync/frame sai hoặc quá ngắn")
    ver,kind,seq,n=struct.unpack_from("<BBIH",raw,2)
    if ver!=VERSION or kind not in TYPES or n>MAX_PAYLOAD or len(raw)!=n+14:
        raise ProtocolError("version/type/length frame sai")
    if zlib.crc32(raw[2:-4])&0xffffffff!=struct.unpack_from("<I",raw,len(raw)-4)[0]:
        raise ProtocolError("CRC32/ISO-HDLC sai")
    if expected_seq is not None and seq!=expected_seq: raise ProtocolError(f"sequence sai: {seq}, cần {expected_seq}")
    return Frame(ver,kind,seq,raw[10:-4])

def _text(p: bytes, at: int) -> tuple[str,int]:
    if at>=len(p) or at+1+p[at]>len(p): raise ProtocolError("payload string thiếu/truncated")
    n=p[at]
    try: return p[at+1:at+1+n].decode("utf-8"),at+1+n
    except UnicodeDecodeError as e: raise ProtocolError("string UTF-8 sai") from e

def parse_hello(p: bytes) -> dict:
    if len(p)<10: raise ProtocolError("HELLO quá ngắn")
    version,count,order=struct.unpack_from("<BBI",p); strings=[]; pos=6
    for _ in range(9):
        value,pos=_text(p,pos); strings.append(value)
    if pos+4!=len(p): raise ProtocolError("HELLO length sai")
    rev,cpu=struct.unpack_from("<HH",p,pos)
    m=dict(protocol_version=version,feature_count=count,feature_order_crc32=order,
           feature_schema=strings[0],semantic_version=strings[1],validity_version=strings[2],
           parity_schema=strings[3],harness=strings[4],build_flags=strings[5],compiler=strings[6],
           sdk=strings[7],chip=strings[8],chip_revision=rev,cpu_mhz=cpu)
    want=(VERSION,23,ORDER_CRC,FEATURE_SCHEMA_VERSION,SEMANTIC_CONTRACT_VERSION,VALIDITY_POLICY_VERSION,SCHEMA_VERSION)
    got=(version,count,order,m["feature_schema"],m["semantic_version"],m["validity_version"],m["parity_schema"])
    if got!=want: raise ProtocolError(f"HELLO contract mismatch: {got!r}")
    return m

def parse_ack(p: bytes) -> dict:
    if len(p)!=9: raise ProtocolError("ACK length phải 9 byte")
    seq,code,samples=struct.unpack("<IBI",p); return dict(acknowledged_host_seq=seq,code=code,samples_received=samples)

def parse_result(p: bytes) -> dict:
    if not p: raise ProtocolError("RESULT rỗng")
    n=p[0]
    if not n or n+151!=len(p): raise ProtocolError("RESULT length sai")
    try: cid=p[1:1+n].decode("ascii")
    except UnicodeDecodeError as e: raise ProtocolError("RESULT case_id không ASCII") from e
    pos=1+n; endpoint,sha,elapsed,mask,flags=struct.unpack_from("<I32sIIB",p,pos); pos+=45
    n60,n180,consec=struct.unpack_from("<HHH",p,pos); pos+=6
    quality=struct.unpack_from("<f",p,pos)[0]; pos+=4
    status,reason,count=p[pos:pos+3]; pos+=3
    if count!=23 or mask>>23 or flags&~3 or not math.isfinite(quality) or not 0<=quality<=100:
        raise ProtocolError("RESULT metadata/quality sai")
    values=[]
    for i,bits in enumerate(struct.unpack_from("<23I",p,pos)):
        value=struct.unpack("<f",struct.pack("<I",bits))[0]
        if mask>>i&1:
            if not math.isfinite(value): raise ProtocolError("feature VALID không hữu hạn")
        elif bits!=0x7fc00000: raise ProtocolError("feature INVALID không phải canonical qNaN")
        values.append(value)
    return dict(case_id=cid,endpoint_index=endpoint,input_csv_sha256=sha.hex(),elapsed_us=elapsed,
                valid_mask=mask,ready_short=bool(flags&1),ready_long=bool(flags&2),n_valid_60=n60,
                n_valid_180=n180,consec_invalid=consec,data_quality_pct=quality,
                quality_status=status,quality_reason_bits=reason,values=values)

def parse_case_done(p: bytes) -> dict:
    if not p: raise ProtocolError("CASE_DONE rỗng")
    n=p[0]
    if not n or len(p)!=n+11: raise ProtocolError("CASE_DONE length sai")
    try: cid=p[1:1+n].decode("ascii")
    except UnicodeDecodeError as e: raise ProtocolError("CASE_DONE ID sai") from e
    samples,endpoints,checksum,status=struct.unpack_from("<IBIB",p,1+n)
    return dict(case_id=cid,samples_received=samples,endpoints_emitted=endpoints,samples_crc32=checksum,status=status)

def parse_run_done(p: bytes) -> dict:
    if not p: raise ProtocolError("RUN_DONE rỗng")
    n=p[0]
    if not n or len(p)!=n+36: raise ProtocolError("RUN_DONE length sai")
    try: rid=p[1:1+n].decode("ascii")
    except UnicodeDecodeError as e: raise ProtocolError("RUN_DONE ID sai") from e
    count,sha,status=struct.unpack_from("<H32sB",p,1+n)
    return dict(run_id=rid,cases_completed=count,manifest_sha256=sha.hex(),status=status)

def parse_error(p: bytes) -> dict:
    if len(p)!=2 or p[1]!=1: raise ProtocolError("ERROR payload sai/nonfatal")
    return dict(code=p[0],fatal=True)

class TargetSession:
    """Transport transactions only; fixture loading, CLI, and parity comparison live outside B1a."""
    def __init__(self, serial, timeout: float=8.0):
        self.serial,self.timeout=serial,timeout
        self.tx_seq=self.rx_seq=0; self.state="WAIT_HELLO"; self.hello=None
        self.run_id=None; self.manifest_sha=None; self.expected_cases=0; self.completed_cases=0; self.seen_case_ids=set()
        self.case=None; self.results=[]; self.transport_complete=False

    def _read(self,n: int) -> bytes:
        deadline=time.monotonic()+self.timeout; data=bytearray()
        while len(data)<n:
            if time.monotonic()>=deadline: raise ProtocolError("timeout chờ frame/terminal completion")
            part=self.serial.read(n-len(data))
            if part: data.extend(part)
        return bytes(data)

    def receive(self) -> tuple[Frame,dict]:
        sync=self._read(2)
        if sync!=b"\x53\x56": raise ProtocolError("sync sai")
        h=self._read(8); ver,kind,seq,n=struct.unpack("<BBIH",h)
        if n>MAX_PAYLOAD: raise ProtocolError("payload vượt 384 byte")
        f=decode_frame(sync+h+self._read(n+4),self.rx_seq); self.rx_seq+=1
        parsers={128:parse_hello,129:parse_ack,130:parse_result,131:parse_case_done,132:parse_run_done,143:parse_error}
        if f.kind not in parsers: raise ProtocolError(f"unexpected target message {f.kind}")
        value=parsers[f.kind](f.payload)
        if f.kind==128: self.hello=value
        return f,value

    def send(self,kind: int,payload: bytes=b"") -> int:
        wire=encode_frame(kind,self.tx_seq,payload)
        try:
            n=self.serial.write(wire)
            if n is not None and n!=len(wire): raise ProtocolError("serial write ngắn")
            if hasattr(self.serial,"flush"): self.serial.flush()
        except Exception as e:
            self.state="FAILED"; raise ProtocolError("serial write lỗi; reset target") from e
        seq=self.tx_seq; self.tx_seq+=1; return seq

    def wait_hello(self) -> dict:
        if self.state!="WAIT_HELLO": raise ProtocolError("HELLO ngoài state đầu")
        try:
            while True:
                f,m=self.receive()
                if f.kind!=128: raise ProtocolError("chưa nhận HELLO")
                self.hello=m; self.state="WAIT_RUN"; return m
        except ProtocolError:
            self.state="FAILED"; raise

    def _exchange(self,kind: int,payload: bytes,samples: int,expected_results=()) -> list[dict]:
        seq=self.send(kind,payload); got=[]
        try:
            while True:
                f,m=self.receive()
                if f.kind==128 and kind==1 and self.state=="WAIT_RUN": continue
                if f.kind==143: raise ProtocolError(f"target ERROR {m['code']}; reset target")
                if f.kind==130:
                    c=self.case
                    if c is None or m["case_id"]!=c["case_id"] or m["input_csv_sha256"]!=c["input_sha"]:
                        raise ProtocolError("RESULT case/input SHA mismatch")
                    at=len(got)
                    if at>=len(expected_results) or m["endpoint_index"]!=expected_results[at]:
                        raise ProtocolError("RESULT endpoint thiếu/thừa/trùng/sai thứ tự")
                    got.append(m); self.results.append(m); continue
                if f.kind!=129: raise ProtocolError("response không phải ACK/RESULT/ERROR")
                ack=m
                if ack["acknowledged_host_seq"]!=seq or ack["code"]!=0:
                    raise ProtocolError(f"NACK/ACK sai seq hoặc code={ack['code']}; reset target")
                if ack["samples_received"]!=samples: raise ProtocolError("ACK samples_received không khớp")
                if len(got)!=len(expected_results): raise ProtocolError("ACK trước hoặc thiếu RESULT")
                return got
        except ProtocolError:
            self.state="FAILED"; raise

    def _terminal(self,kind: int) -> dict:
        try: f,m=self.receive()
        except ProtocolError:
            self.state="FAILED"; raise
        if f.kind==143:
            self.state="FAILED"; raise ProtocolError(f"target ERROR {m['code']}; reset target")
        if f.kind!=kind:
            self.state="FAILED"; raise ProtocolError(f"thiếu {TYPES[kind]}")
        return m

    def begin_run(self,run_id: str,case_count: int,manifest_sha256: str) -> None:
        if self.state=="WAIT_HELLO": self.wait_hello()
        if self.state!="WAIT_RUN" or not ID.fullmatch(run_id) or len(run_id.encode("ascii"))>32 or not 1<=case_count<=MAX_CASES:
            raise ProtocolError("RUN_BEGIN state/ID/count sai")
        try: sha=bytes.fromhex(manifest_sha256)
        except ValueError as e: raise ProtocolError("manifest SHA256 sai") from e
        if len(sha)!=32: raise ProtocolError("manifest SHA256 cần 32 byte")
        raw=run_id.encode("ascii"); self.run_id=run_id; self.manifest_sha=sha.hex(); self.expected_cases=case_count
        self._exchange(1,bytes([len(raw)])+raw+struct.pack("<H",case_count)+sha,0); self.state="IN_RUN"

    def begin_case(self,case_id: str,sample_count: int,endpoints: list[int],input_sha256: str,samples_crc32: int) -> None:
        if (self.state!="IN_RUN" or self.completed_cases>=self.expected_cases or
                case_id in self.seen_case_ids or not ID.fullmatch(case_id) or
                len(case_id.encode("ascii"))>48):
            raise ProtocolError("CASE_BEGIN state/ID sai")
        if not 0<sample_count<=MAX_SAMPLES or not 0<len(endpoints)<=MAX_ENDPOINTS or endpoints!=sorted(set(endpoints)) or endpoints[-1]>=sample_count:
            raise ProtocolError("CASE_BEGIN sample/endpoint sai")
        try: sha=bytes.fromhex(input_sha256)
        except ValueError as e: raise ProtocolError("input SHA256 sai") from e
        if len(sha)!=32 or not 0<=samples_crc32<=0xffffffff: raise ProtocolError("case checksum sai")
        raw=case_id.encode("ascii"); self.case=dict(case_id=case_id,sample_count=sample_count,endpoints=endpoints,
            input_sha=sha.hex(),samples_crc=samples_crc32,samples_received=0,crc=0,seen=[])
        payload=(bytes([len(raw)])+raw+struct.pack("<IB",sample_count,len(endpoints))+
                 struct.pack("<"+"I"*len(endpoints),*endpoints)+sha+struct.pack("<I",samples_crc32))
        self._exchange(2,payload,0); self.state="IN_CASE"

    def send_samples(self,first_index: int,records: bytes) -> list[dict]:
        c=self.case
        if self.state!="IN_CASE" or c is None or len(records)%10 or not 0<len(records)//10<=MAX_BATCH:
            raise ProtocolError("SAMPLES state/count sai")
        count=len(records)//10; end=first_index+count
        if first_index!=c["samples_received"] or end>c["sample_count"]: raise ProtocolError("SAMPLES index/count sai")
        for i in range(count):
            nraw,valid=records[i*10+8:i*10+10]
            if nraw>2 or valid>1: raise ProtocolError("SAMPLES nraw/valid sai")
        wanted=[e for e in c["endpoints"] if first_index<=e<end]
        payload=struct.pack("<IB",first_index,count)+records
        result=self._exchange(3,payload,end,wanted)
        c["seen"].extend(r["endpoint_index"] for r in result); c["samples_received"]=end
        c["crc"]=zlib.crc32(records,c["crc"])&0xffffffff
        return result

    def end_case(self) -> dict:
        c=self.case
        if self.state!="IN_CASE" or c is None: raise ProtocolError("CASE_END state sai")
        if c["samples_received"]!=c["sample_count"] or c["seen"]!=c["endpoints"]: raise ProtocolError("case sample/endpoint incomplete")
        if c["crc"]!=c["samples_crc"]: self.state="FAILED"; raise ProtocolError("case sample CRC sai; reset target")
        self._exchange(4,b"",c["sample_count"]); m=self._terminal(131)
        actual=(m["case_id"],m["samples_received"],m["endpoints_emitted"],m["samples_crc32"],m["status"])
        expected=(c["case_id"],c["sample_count"],len(c["endpoints"]),c["samples_crc"],0)
        if actual!=expected:
            self.state="FAILED"; raise ProtocolError("CASE_DONE thiếu hoặc không khớp")
        self._last_count=c["sample_count"]; self.seen_case_ids.add(c["case_id"]); self.completed_cases+=1; self.case=None; self.state="IN_RUN"; return m

    def end_run(self) -> dict:
        if self.state!="IN_RUN" or self.case is not None or self.completed_cases!=self.expected_cases:
            raise ProtocolError("RUN_END trước khi mọi case hoàn tất")
        self._exchange(5,b"",self._last_count); m=self._terminal(132)
        if (m["run_id"],m["cases_completed"],m["manifest_sha256"],m["status"])!=(self.run_id,self.expected_cases,self.manifest_sha,0):
            self.state="FAILED"; raise ProtocolError("RUN_DONE thiếu hoặc không khớp")
        self.state="COMPLETE"; self.transport_complete=True; return m
