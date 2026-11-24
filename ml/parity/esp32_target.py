"""Serial v1 transport and transaction state machine for the HV01-A target."""
from __future__ import annotations

import argparse, csv, hashlib, json, math, re, struct, subprocess, sys, time, zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ml.parity.contract import FEATURE_ORDER, FEATURE_SCHEMA_VERSION, SCHEMA_VERSION, SEMANTIC_CONTRACT_VERSION, VALIDITY_POLICY_VERSION

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "ml/parity/fixtures"
MANIFEST_PATH = FIXTURES / "manifest.json"
SYNTHETIC_CASES = FIXTURES / "synthetic/cases.json"
REAL_CASES = ROOT / "ml/data/parity/real/cases.json"

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
    def __init__(self, serial, timeout: float=8.0, transcript_path: Path | None=None,
                 execution_kind: str="host_mock", allow_initial_rx_sequence: bool=False):
        self.serial,self.timeout=serial,timeout
        self.tx_seq=self.rx_seq=0; self.state="WAIT_HELLO"; self.hello=None
        self.run_id=None; self.manifest_sha=None; self.expected_cases=0; self.completed_cases=0; self.seen_case_ids=set()
        self.case=None; self.results=[]; self.raw_results=[]; self.transport_complete=False
        self.transcript=[]; self.transcript_path=Path(transcript_path) if transcript_path else None
        self.execution_kind=execution_kind; self.transcript_complete=False; self.transcript_integrity=True
        self.allow_initial_rx_sequence=allow_initial_rx_sequence; self.initial_rx_sequence=None

    def _record(self, direction: str, raw: bytes, status: str="OK", detail: str | None=None) -> None:
        kind=seq=declared=None
        if len(raw)>=4: kind=raw[3]
        if len(raw)>=8: seq=struct.unpack_from("<I",raw,4)[0]
        if len(raw)>=10: declared=struct.unpack_from("<H",raw,8)[0]
        event=dict(event_index=len(self.transcript),direction=direction,frame_type=TYPES.get(kind),
            type_id=kind,sequence=seq,timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            monotonic_ns=time.monotonic_ns(),frame_length=len(raw),declared_payload_length=declared,
            expected_frame_length=declared+14 if declared is not None else None,
            raw_frame_hex=raw.hex(),frame_complete=status=="OK",status=status,detail=detail)
        self.transcript.append(event)
        if status!="OK": self.transcript_integrity=False
        if self.transcript_path is not None:
            try:
                self.transcript_path.parent.mkdir(parents=True,exist_ok=True)
                with self.transcript_path.open("a",encoding="utf-8") as stream:
                    stream.write(json.dumps(event,allow_nan=False,separators=(",",":"))+"\n")
            except OSError as exc:
                self.transcript_integrity=False
                raise ProtocolError(f"Không ghi được serial transcript: {exc}") from exc

    def _read(self,n: int, capture: bytearray | None=None) -> bytes:
        deadline=time.monotonic()+self.timeout; data=bytearray()
        while len(data)<n:
            if time.monotonic()>=deadline: raise ProtocolError("timeout chờ frame/terminal completion")
            part=self.serial.read(n-len(data))
            if part:
                data.extend(part)
                if capture is not None: capture.extend(part)
        return bytes(data)

    def receive(self) -> tuple[Frame,dict]:
        raw=bytearray()
        try:
            sync=self._read(2,raw)
            if sync!=b"\x53\x56": raise ProtocolError("sync sai")
            h=self._read(8,raw); _,kind,_,n=struct.unpack("<BBIH",h)
            if n>MAX_PAYLOAD: raise ProtocolError("payload vượt 384 byte")
            tail=self._read(n+4,raw); f=decode_frame(sync+h+tail)
            if self.initial_rx_sequence is None:
                if self.allow_initial_rx_sequence:
                    if f.kind!=128: raise ProtocolError("attach yêu cầu HELLO đầu tiên")
                    self.rx_seq=f.seq
                self.initial_rx_sequence=self.rx_seq
            if f.seq!=self.rx_seq: raise ProtocolError(f"sequence sai: {f.seq}, cần {self.rx_seq}")
            parsers={128:parse_hello,129:parse_ack,130:parse_result,131:parse_case_done,132:parse_run_done,143:parse_error}
            if f.kind not in parsers: raise ProtocolError(f"unexpected target message {f.kind}")
            value=parsers[f.kind](f.payload)
        except ProtocolError as exc:
            self._record("RX",bytes(raw),"FRAME_ERROR" if raw else "TIMEOUT",str(exc))
            raise
        except Exception as exc:
            self._record("RX",bytes(raw),"READ_ERROR",str(exc))
            raise ProtocolError("serial read lỗi") from exc
        self._record("RX",bytes(raw))
        self.rx_seq+=1
        if f.kind==128: self.hello=value
        return f,value

    def send(self,kind: int,payload: bytes=b"") -> int:
        wire=encode_frame(kind,self.tx_seq,payload)
        raw=b""
        try:
            n=self.serial.write(wire)
            if n is None:
                raw=wire
                self._record("TX",raw,"WRITE_COUNT_UNKNOWN","Serial.write không trả byte count")
            elif isinstance(n,int) and 0<=n<=len(wire):
                raw=wire[:n]
                if n!=len(wire):
                    self._record("TX",raw,"PARTIAL_WRITE",f"{n}/{len(wire)} byte")
                    raise ProtocolError("serial write lỗi: ghi thiếu byte")
            else:
                self._record("TX",b"","WRITE_COUNT_INVALID",f"byte count không hợp lệ: {n!r}")
                raise ProtocolError("serial write trả byte count không hợp lệ")
            if hasattr(self.serial,"flush"): self.serial.flush()
        except ProtocolError:
            self.state="FAILED"; raise
        except Exception as e:
            self._record("TX",raw,"WRITE_ERROR",str(e))
            self.state="FAILED"; raise ProtocolError("serial write lỗi; reset target") from e
        if n is not None: self._record("TX",raw)
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
                    self.raw_results.append(dict(seq=f.seq,payload_hex=f.payload.hex(),
                        wire_hex=encode_frame(f.kind,f.seq,f.payload).hex(),decoded=m))
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
        self.state="COMPLETE"; self.transport_complete=True
        self.transcript_complete=self.transcript_integrity
        return m


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_suite(suite: str="synthetic") -> tuple[list[dict],str]:
    """Load and verify canonical golden inputs without regenerating fixtures."""
    manifest_raw=MANIFEST_PATH.read_bytes(); manifest=json.loads(manifest_raw)
    paths={"synthetic":SYNTHETIC_CASES,"real":REAL_CASES}
    selected=list(paths) if suite=="all" else [suite]
    if any(name not in paths or not paths[name].is_file() for name in selected):
        raise FileNotFoundError(f"suite {suite!r}: NOT_AVAILABLE; fixture cases.json không tồn tại")
    definitions=[]
    for name in selected:
        cases_path=paths[name]; cases_raw=cases_path.read_bytes(); cases_meta=json.loads(cases_raw)
        entry=manifest.get("files",{}).get(cases_path.relative_to(ROOT).as_posix())
        if (not entry or entry.get("sha256")!=_sha(cases_raw)
                or entry.get("bytes")!=len(cases_raw)): raise ProtocolError(f"SHA/size manifest cases {name} không khớp")
        if cases_meta.get("suite")!=name or cases_meta.get("feature_order")!=list(FEATURE_ORDER):
            raise ProtocolError(f"metadata suite/feature order {name} không khớp contract")
        if cases_meta.get("schema_version")!=SCHEMA_VERSION or cases_meta.get("schema_sha256")!=manifest.get("schema_sha256"):
            raise ProtocolError(f"metadata schema {name} không khớp manifest/contract")
        definitions.extend((name,case) for case in cases_meta["cases"])
    if not definitions or len(definitions)>MAX_CASES: raise ProtocolError("suite rỗng hoặc vượt 64 case")
    from ml.parity.golden import read_inputs
    loaded=[]; ids=set()
    for source_suite,meta in definitions:
        cid=meta["case_id"]; rel=meta["input_file"]
        if cid in ids or not ID.fullmatch(cid) or len(cid.encode("ascii"))>48: raise ProtocolError("case ID trùng hoặc sai")
        ids.add(cid); path=ROOT / rel; raw=path.read_bytes()
        file_entry=manifest.get("files",{}).get(rel)
        digest=_sha(raw)
        if digest!=meta["input_sha256"] or not file_entry or digest!=file_entry.get("sha256") or len(raw)!=file_entry.get("bytes"):
            raise ProtocolError(f"CSV SHA/manifest không khớp: {rel}")
        header=next(csv.reader([raw.splitlines()[0].decode("ascii")]),[])
        if header!=["sample_index","time_seconds","roll_deg","pitch_deg","source_sample_index"]:
            raise ProtocolError(f"CSV columns sai: {rel}")
        frame=read_inputs(path)
        indexes=frame.sample_index.tolist()
        if indexes!=list(range(len(indexes))) or len(indexes)!=meta["n_samples"] or not indexes or len(indexes)>MAX_SAMPLES:
            raise ProtocolError(f"sample_index/count không liên tục: {cid}")
        endpoints=[int(e["endpoint_index"]) for e in meta["endpoints"]]
        if (len(endpoints)!=meta["endpoint_count"] or not endpoints or len(endpoints)>MAX_ENDPOINTS
                or endpoints!=sorted(set(endpoints)) or endpoints[-1]>=len(indexes)):
            raise ProtocolError(f"endpoint metadata sai: {cid}")
        records=b"".join(struct.pack("<ffBB",float(r),float(p),2,1)
                         for r,p in zip(frame.roll_deg,frame.pitch_deg))
        loaded.append(dict(case_id=cid,input_sha256=digest,sample_count=len(indexes),
                           endpoints=endpoints,source_sample_index=frame.source_sample_index.tolist(),
                           records=records,samples_crc32=zlib.crc32(records)&0xffffffff,
                           provenance="SIMULATION" if source_suite=="synthetic" else "SENSOR"))
    return loaded,_sha(manifest_raw)


def run_suite(session: TargetSession, cases: list[dict], run_id: str, manifest_sha: str) -> dict:
    """Stream verified fixtures using the B1a transaction state machine."""
    session.wait_hello(); session.begin_run(run_id,len(cases),manifest_sha); completed=[]
    for case in cases:
        session.begin_case(case["case_id"],case["sample_count"],case["endpoints"],
                           case["input_sha256"],case["samples_crc32"])
        records=case["records"]
        for first in range(0,len(records)//10,MAX_BATCH):
            block=records[first*10:min(first+MAX_BATCH,len(records)//10)*10]
            session.send_samples(first,block)
        session.end_case(); completed.append(case["case_id"])
    done=session.end_run()
    return dict(run_done=done,completed_case_ids=completed,transport_status="TRANSPORT_COMPLETE",
                numerical_parity="NUMERICAL_PARITY_NOT_RUN")


def _safe_result(result: dict) -> dict:
    row=dict(result); mask=row["valid_mask"]
    row["values"]=[float(v) if mask>>i&1 else None for i,v in enumerate(row["values"])]
    return row


def _source_metadata() -> dict:
    try: commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
    except (OSError,subprocess.CalledProcessError): commit="NOT_AVAILABLE"
    try: dirty=bool(subprocess.check_output(["git","-C",str(ROOT),"status","--porcelain"],text=True).strip())
    except (OSError,subprocess.CalledProcessError): dirty=None
    return dict(source_commit=commit,source_worktree_dirty=dirty)

def _open_serial(serial_module,port: str,baud: int,timeout: float):
    if port.startswith("rfc2217://"):
        return serial_module.serial_for_url(port,baudrate=baud,timeout=timeout)
    return serial_module.Serial(port,baudrate=baud,timeout=timeout,write_timeout=timeout)


def save_capture(output: Path, run_id: str, suite: str, manifest_sha: str,
                 cases: list[dict], session: TargetSession, status: str,
                 firmware_bin: Path | None=None, error: str | None=None) -> None:
    output.mkdir(parents=True,exist_ok=True)
    transcript_path=output/"serial_transcript.jsonl"
    if session.transcript_path is not None:
        source=session.transcript_path
        if source.resolve()!=transcript_path.resolve():
            with transcript_path.open("xb") as stream: stream.write(source.read_bytes())
        elif not transcript_path.exists():
            with transcript_path.open("xb") as stream:
                for event in session.transcript:
                    stream.write((json.dumps(event,allow_nan=False,separators=(",",":"))+"\n").encode())
    elif not transcript_path.exists():
        with transcript_path.open("xb") as stream:
            for event in session.transcript:
                stream.write((json.dumps(event,allow_nan=False,separators=(",",":"))+"\n").encode())
    transcript_raw=transcript_path.read_bytes()
    transcript_sha=_sha(transcript_raw)
    transcript_complete=bool(status=="TRANSPORT_COMPLETE" and session.transcript_complete
                             and session.transcript_integrity)
    firmware_sha=_sha(firmware_bin.read_bytes()) if firmware_bin else "NOT_AVAILABLE"
    rows=[]
    for raw in session.raw_results:
        rows.append(dict(raw_frame_hex=raw["wire_hex"],payload_hex=raw["payload_hex"],
                         result=_safe_result(raw["decoded"]),provisional=status!="TRANSPORT_COMPLETE"))
    with (output/"raw_results.jsonl").open("x",encoding="utf-8") as stream:
        stream.write("".join(json.dumps(r,allow_nan=False,sort_keys=True)+"\n" for r in rows))
    has_serial_bytes=any(e["direction"] in ("TX","RX") and e["raw_frame_hex"] for e in session.transcript)
    scope="attached_partial_boot" if session.initial_rx_sequence not in (None,0) else "full_session"
    capture_status=("HOST_MOCK_VERIFIED" if session.execution_kind=="host_mock" else
        "WOKWI_SIMULATION_CAPTURED" if session.execution_kind=="wokwi_simulation" and has_serial_bytes else
        "WOKWI_SIMULATION_NOT_CAPTURED" if session.execution_kind=="wokwi_simulation" else
        "TARGET_CAPTURE_COLLECTED" if has_serial_bytes else "TARGET_EVIDENCE_NOT_VERIFIED")
    evidence_status="WOKWI_SIMULATION_ONLY" if session.execution_kind=="wokwi_simulation" else "TARGET_EVIDENCE_NOT_VERIFIED"
    metadata=dict(run_id=run_id,suite=suite,**_source_metadata(),manifest_sha256=manifest_sha,
        protocol_version=VERSION,feature_schema_version=FEATURE_SCHEMA_VERSION,
        semantic_contract_version=SEMANTIC_CONTRACT_VERSION,validity_policy_version=VALIDITY_POLICY_VERSION,
        parity_schema_version=SCHEMA_VERSION,firmware_sha256=firmware_sha,
        firmware_sha256_source="host_file" if firmware_bin else "NOT_AVAILABLE",
        firmware_sha256_scope="host file only; not attestation of the binary running on the device" if firmware_bin else "NOT_AVAILABLE",
        execution_kind=session.execution_kind,session_scope=scope,initial_rx_sequence=session.initial_rx_sequence,
        capture_status=capture_status,target_evidence_status=evidence_status,
        numerical_parity="NUMERICAL_PARITY_NOT_RUN",
        serial_transcript_sha256=transcript_sha,serial_transcript_complete=transcript_complete,
        serial_transcript_event_count=len(session.transcript),
        device_hello=session.hello,cases=[{k:c[k] for k in ("case_id","input_sha256","sample_count","endpoints","source_sample_index","provenance")} for c in cases])
    summary=dict(transport_status=status,numerical_parity="NUMERICAL_PARITY_NOT_RUN",
        cases_expected=len(cases),cases_completed=session.completed_cases,
        result_count=len(session.raw_results),error=error,reset_target_before_retry=status!="TRANSPORT_COMPLETE",
        serial_transcript_sha256=transcript_sha,serial_transcript_complete=transcript_complete,
        capture_status=capture_status,target_evidence_status=evidence_status)
    with (output/"metadata.json").open("x",encoding="utf-8") as stream:
        stream.write(json.dumps(metadata,allow_nan=False,indent=2,sort_keys=True)+"\n")
    with (output/"transport_summary.json").open("x",encoding="utf-8") as stream:
        stream.write(json.dumps(summary,allow_nan=False,indent=2,sort_keys=True)+"\n")


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Gửi golden fixture tới ESP32 HV01 target; không thực hiện numerical parity comparison.")
    parser.add_argument("--port",required=True); parser.add_argument("--baud",type=int,default=115200)
    parser.add_argument("--suite",choices=("synthetic","real","all"),default="synthetic")
    parser.add_argument("--run-id",required=True); parser.add_argument("--output",type=Path)
    parser.add_argument("--firmware-bin",type=Path); parser.add_argument("--timeout",type=float,default=8.0)
    parser.add_argument("--attach-running-target",action="store_true",help="neo sequence tại HELLO đầu; transcript không bao phủ boot trước đó")
    args=parser.parse_args(argv)
    if not ID.fullmatch(args.run_id) or args.run_id in (".","..") or len(args.run_id)>32 or args.baud<=0 or args.timeout<=0:
        parser.error("run-id, baud hoặc timeout không hợp lệ")
    if args.attach_running_target and not args.port.startswith("rfc2217://"):
        parser.error("--attach-running-target hiện chỉ dành cho endpoint RFC2217/Wokwi")
    output=args.output or ROOT/"ml/data/parity/esp32_target"/args.run_id
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error(f"thư mục output đã có dữ liệu, không ghi đè: {output}")
    output.mkdir(parents=True,exist_ok=True)
    cases=[]; session=None
    try:
        cases,manifest_sha=load_suite(args.suite)
        if args.firmware_bin and not args.firmware_bin.is_file(): raise FileNotFoundError(args.firmware_bin)
        try: import serial
        except ImportError as e: raise RuntimeError("Thiếu pyserial; cài bằng: python -m pip install pyserial") from e
        execution_kind="wokwi_simulation" if args.port.startswith("rfc2217://") else "serial_target"
        with _open_serial(serial,args.port,args.baud,args.timeout) as port:
            session=TargetSession(port,args.timeout,output/"serial_transcript.jsonl",execution_kind,
                                  allow_initial_rx_sequence=args.attach_running_target)
            run_suite(session,cases,args.run_id,manifest_sha)
        save_capture(output,args.run_id,args.suite,manifest_sha,cases,session,"TRANSPORT_COMPLETE",args.firmware_bin)
        print(f"TRANSPORT_COMPLETE; NUMERICAL_PARITY_NOT_RUN; capture: {output}"); return 0
    except Exception as exc:
        if session is None:
            kind="wokwi_simulation" if args.port.startswith("rfc2217://") else "serial_target"
            session=TargetSession(type("NoSerial",(),{})(),transcript_path=output/"serial_transcript.jsonl",
                                  execution_kind=kind,allow_initial_rx_sequence=args.attach_running_target)
        try:
            save_capture(output,args.run_id,args.suite,locals().get("manifest_sha","NOT_AVAILABLE"),
                         cases,session,"FAIL_TRANSPORT",args.firmware_bin,str(exc))
        except Exception as capture_error: print(f"Không lưu được diagnostic capture: {capture_error}",file=sys.stderr)
        print(f"FAIL_TRANSPORT: {exc}. Reset target trước lần chạy tiếp theo.",file=sys.stderr); return 2


if __name__=="__main__":
    raise SystemExit(main())
