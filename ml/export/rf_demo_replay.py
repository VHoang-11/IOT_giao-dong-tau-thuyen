"""M2-R2: replay vector held-out Hohai T9 (M2-R1) tới ESP32 RF demo cô lập; chỉ gửi 23 float32 feature, ESP32 tự chạy
model C99, host so với tham chiếu sklearn. Protocol + lệnh chạy: firmware/target_rf_demo/README.md."""

import argparse
import hashlib
import json
import struct
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from ml.train.rf_poc import FEATURE_ORDER

MODEL_DIR = Path(__file__).resolve().parents[2] / "ml/data/models/rf_demo_m2r1"
SYNC, VERSION, MAX_VALUES, MAX_RX_PAYLOAD, SCORE_TOL = b"RF", 1, 32, 240, 1e-6
PREDICT, HELLO_REQ, HELLO, RESULT, ERROR = 0x01, 0x02, 0x80, 0x81, 0x8F
ERRORS = {1: "BAD_SYNC", 2: "BAD_CRC", 3: "BAD_VERSION", 4: "BAD_LENGTH", 5: "BAD_PAYLOAD", 6: "TIMEOUT", 7: "BAD_TYPE"}
MISMATCH_KEYS = ("transport_failures", "target_errors_on_valid_vectors", "status_mismatches", "prediction_mismatches", "score_mismatches")


class ProtocolError(RuntimeError):
    """Frame/transaction sai; host phải resync."""


def encode_frame(kind: int, payload: bytes = b"", version: int = VERSION) -> bytes:
    body = struct.pack("<BBH", version, kind, len(payload)) + payload
    return SYNC + body + struct.pack("<I", zlib.crc32(body))


def predict_payload(sample_id: int, values) -> bytes:
    values = np.asarray(values, dtype="<f4")
    if len(values) > MAX_VALUES:
        raise ProtocolError("quá nhiều giá trị cho một frame")
    return struct.pack("<IB", sample_id, len(values)) + values.tobytes()


class Link:
    """Frame giới hạn độ dài + CRC32; mọi byte TX/RX (kể cả frame lỗi) được ghi vào transcript."""

    def __init__(self, serial, timeout: float = 3.0):
        self.serial, self.timeout, self.transcript = serial, timeout, []

    def _log(self, direction: str, raw: bytes, status: str = "OK") -> None:
        self.transcript.append({"i": len(self.transcript), "dir": direction, "t_ns": time.monotonic_ns(), "hex": raw.hex(), "status": status})

    def send(self, raw: bytes) -> None:
        self.serial.write(raw), self._log("TX", raw)

    def _read(self, n: int, buf: bytearray) -> None:
        deadline = time.monotonic() + self.timeout
        while len(buf) < n:
            if time.monotonic() > deadline:
                raise ProtocolError("TIMEOUT")
            buf.extend(self.serial.read(n - len(buf)))

    def receive(self) -> tuple[int, bytes]:
        raw = bytearray()
        try:
            self._read(2, raw)
            self._read(6 if raw == SYNC else 0, raw)
            if raw[:2] != SYNC or (n := struct.unpack_from("<H", raw, 4)[0]) > MAX_RX_PAYLOAD:
                raise ProtocolError(f"BAD_SYNC_OR_LENGTH:{bytes(raw[:2]).hex()}{'(HV01_target_parity_firmware)' if raw[:2] == b'SV' else ''}")
            self._read(10 + n, raw)
            if zlib.crc32(raw[2:6 + n]) != struct.unpack_from("<I", raw, 6 + n)[0] or raw[2] != VERSION:
                raise ProtocolError("BAD_CRC_OR_VERSION")
        except ProtocolError as exc:
            self._log("RX", bytes(raw), str(exc))
            raise
        self._log("RX", bytes(raw))
        return raw[3], bytes(raw[6:6 + n])

    def resync(self) -> None:
        time.sleep(0.3), self.serial.reset_input_buffer()


def parse_hello(p: bytes) -> dict:
    out, at = dict(zip(("protocol", "n_features", "n_trees"), p[:3]), n_nodes=struct.unpack_from("<H", p, 3)[0]), 5
    for key in ("model_version", "model_sha256", "feature_order_sha256", "target", "chip"):
        out[key], at = p[at + 1:at + 1 + p[at]].decode(), at + 1 + p[at]
    return {**out, "cpu_mhz": struct.unpack_from("<H", p, at)[0]}


def request(link: Link, sample_id: int, payload: bytes = b"", raw: bytes | None = None) -> dict:
    """Một PREDICT -> đúng một RESULT/ERROR. Lỗi transport được ghi lại rồi resync, không bỏ qua mẫu."""
    link.send(raw or encode_frame(PREDICT, payload))
    try:
        kind, p = link.receive()
    except ProtocolError as exc:
        return link.resync() or {"transport": f"FAIL_{exc}"}
    if kind == ERROR and len(p) == 1:
        return {"transport": "OK", "target_error": ERRORS.get(p[0], str(p[0]))}
    if kind != RESULT or len(p) != 14 or struct.unpack_from("<I", p)[0] != sample_id:
        return link.resync() or {"transport": "FAIL_UNEXPECTED_FRAME"}
    return dict(zip(("transport", "status", "pred", "score", "elapsed_us"), ("OK", *struct.unpack("<IbbfI", p)[1:])))


def handshake(link: Link, export_sha: str) -> dict:
    link.serial.reset_input_buffer(), link.send(encode_frame(HELLO_REQ))
    kind, p = link.receive()
    hello = parse_hello(p) if kind == HELLO else {}
    order_sha = hashlib.sha256("\n".join(FEATURE_ORDER).encode()).hexdigest()
    if (hello.get("model_sha256"), hello.get("feature_order_sha256"), hello.get("n_features")) != (export_sha, order_sha, 23):
        raise ProtocolError(f"Target không chạy đúng model/thứ tự feature M2-R1: {hello}")
    link.resync()  # bỏ HELLO boot/trùng lặp còn trong buffer trước khi replay
    return hello


def invalid_input_checks(link: Link, x: np.ndarray) -> dict:
    nan, inf, p, bad_crc = x.copy(), x.copy(), predict_payload, bytearray(encode_frame(PREDICT, predict_payload(9003, x)))
    nan[3], inf[20], bad_crc[-1] = np.nan, -np.inf, bad_crc[-1] ^ 0xFF
    rejected, nonfinite = {"status": -2, "pred": -1}, {"status": -3, "pred": -1}
    cases = {"count_22": (9000, p(9000, x[:22]), None, rejected), "count_24": (9001, p(9001, np.r_[x, 0]), None, rejected),
             "count_0": (9002, p(9002, x[:0]), None, rejected), "nan_feature": (9005, p(9005, nan), None, nonfinite),
             "neg_inf_feature": (9006, p(9006, inf), None, nonfinite),
             "bad_crc": (9003, b"", bytes(bad_crc), {"target_error": "BAD_CRC"}),
             "count_23_but_22_values": (9004, b"", encode_frame(PREDICT, p(9004, x)[:-4]), {"target_error": "BAD_PAYLOAD"}),
             "bad_version": (9007, b"", encode_frame(PREDICT, p(9007, x), version=9), {"target_error": "BAD_VERSION"}),
             "unknown_type": (9008, b"", encode_frame(0x7E), {"target_error": "BAD_TYPE"})}
    out = {name: {**request(link, sid, payload, raw), "expected": expect} for name, (sid, payload, raw, expect) in cases.items()}
    return {k: {**v, "passed": v["transport"] == "OK" and all(v.get(f) == x for f, x in v["expected"].items())} for k, v in out.items()}


def replay(link: Link, vectors: pd.DataFrame) -> pd.DataFrame:
    X, ref = vectors[list(FEATURE_ORDER)].to_numpy(np.float32), vectors[["window_id", "proxy_status", "python_pred", "python_score"]]
    return pd.DataFrame([{"sample_id": i, "window_id": w, "proxy_status": s, "ref_pred": int(rp), "ref_score": float(rs),
                          **request(link, i, predict_payload(i, X[i]))} for i, (w, s, rp, rs) in enumerate(ref.itertuples(index=False))])


def summarize(rows: pd.DataFrame, invalid: dict, kind: str) -> dict:
    rows = rows.reindex(columns=list(dict.fromkeys([*rows.columns, "status", "pred", "score", "elapsed_us"])))
    transport_ok = rows.transport.eq("OK")
    ok = transport_ok & rows.status.notna()
    diff, lat = (rows.score[ok] - rows.ref_score[ok]).abs(), rows.elapsed_us[ok]
    s = {"vectors": len(rows), "transport_failures": int((~transport_ok).sum()),
         "target_errors_on_valid_vectors": int((transport_ok & rows.status.isna()).sum()),
         "status_mismatches": int((rows.status[ok] != 0).sum()), "prediction_mismatches": int((rows.pred[ok] != rows.ref_pred[ok]).sum()),
         "score_max_abs_diff": float(diff.max()) if ok.any() else None, "score_tolerance": SCORE_TOL,
         "score_mismatches": int((diff > SCORE_TOL).sum()), "invalid_inputs_passed": sum(v["passed"] for v in invalid.values()),
         "invalid_inputs_total": len(invalid), "execution_kind": kind,
         "latency_us": {"median": float(lat.median()), "p95": float(lat.quantile(0.95)), "max": float(lat.max())} if ok.any() else None}
    clean = s["vectors"] > 0 and s["invalid_inputs_passed"] == s["invalid_inputs_total"] and not any(s[k] for k in MISMATCH_KEYS)
    s["result"] = ("WOKWI_PASS" if kind == "wokwi_simulation" else f"{kind.upper()}_PASS") if clean else "FAIL"
    return s


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay vector Hohai T9 tới ESP32 RF demo cô lập (M2-R2).")
    for flag, kw in (("--port", {"required": True}), ("--run-id", {"required": True}), ("--timeout", {"type": float, "default": 3.0})):
        parser.add_argument(flag, **kw)
    args = parser.parse_args(argv)
    import serial  # noqa: PLC0415  (pyserial chỉ cần khi chạy thật)
    from ml.parity.esp32_target import _open_serial  # noqa: PLC0415
    out, kind = MODEL_DIR / "esp32_replay" / args.run_id, "wokwi_simulation" if args.port.startswith("rfc2217://") else "serial_target"
    out.mkdir(parents=True, exist_ok=False)
    results, vectors = json.loads((MODEL_DIR / "results.json").read_text()), pd.read_csv(MODEL_DIR / "heldout_replay_vectors.csv")
    with _open_serial(serial, args.port, 115200, args.timeout) as port:
        link = Link(port, args.timeout)
        try:
            hello = handshake(link, results["demo_model"]["export"]["generated_sha256"])
            rows, invalid = replay(link, vectors), invalid_input_checks(link, vectors[list(FEATURE_ORDER)].to_numpy(np.float32)[0])
        finally:
            transcript = "".join(json.dumps(e) + "\n" for e in link.transcript)
            (out / "serial_transcript.jsonl").write_text(transcript, encoding="utf-8")
    rows.to_csv(out / "replay_results.csv", index=False, float_format="%.9g")
    summary = {**summarize(rows, invalid, kind), "hello": hello, "invalid_inputs": invalid, "model_metadata": results["metadata"],
               "serial_transcript_sha256": hashlib.sha256(transcript.encode()).hexdigest(), "serial_transcript_events": len(link.transcript)}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("invalid_inputs", "model_metadata")}, indent=1, default=float))
    return 0 if summary["result"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
