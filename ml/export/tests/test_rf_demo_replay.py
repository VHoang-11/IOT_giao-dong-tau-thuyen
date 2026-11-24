"""Test host protocol M2-R2 với target giả lập theo luật framing của firmware/target_rf_demo (không cần ESP32)."""

import struct
import zlib

import numpy as np
import pandas as pd
import pytest

from ml.export import rf_demo_replay as r
from ml.train.rf_poc import FEATURE_ORDER


def fake_model(x: np.ndarray) -> tuple[int, int, float]:
    if len(x) != 23 or not np.all(np.isfinite(x)):
        return (-2 if len(x) != 23 else -3), -1, -1.0
    score = float(np.float32(min(1.0, abs(float(x[1])) / 4)))
    return 0, int(score >= 0.5), score


class FakeTarget:
    def __init__(self, drop_ids=(), score_offset=0.0, hello=b""):
        self.out, self.drop_ids, self.score_offset, self.hello = bytearray(), set(drop_ids), score_offset, hello

    def write(self, raw: bytes):
        version, kind, n = struct.unpack_from("<BBH", raw, 2)
        p, reply = raw[6:6 + n], None
        if zlib.crc32(raw[2:6 + n]) != struct.unpack_from("<I", raw, 6 + n)[0] or version != r.VERSION:
            reply = (r.ERROR, b"\x02" if version == r.VERSION else b"\x03")
        elif kind != r.PREDICT:
            reply = (r.HELLO, self.hello) if kind == r.HELLO_REQ else (r.ERROR, b"\x07")
        elif n < 5 or n != 5 + 4 * p[4]:
            reply = (r.ERROR, b"\x05")
        elif (sid := struct.unpack_from("<I", p)[0]) not in self.drop_ids:
            status, pred, score = fake_model(np.frombuffer(p[5:], "<f4"))
            reply = (r.RESULT, struct.pack("<IbbfI", sid, status, pred, score + self.score_offset, 17))
        self.out += r.encode_frame(*reply) if reply else b""

    def read(self, n):
        chunk, self.out[:n] = bytes(self.out[:n]), b""
        return chunk

    def reset_input_buffer(self):
        self.out.clear()


def _run(target, monkeypatch, n=12):
    monkeypatch.setattr(r.time, "sleep", lambda _: None)
    X = np.random.default_rng(1).uniform(0, 3, size=(n, 23)).astype(np.float32)
    ref = [fake_model(x) for x in X]
    vectors = pd.DataFrame({"window_id": range(n), "proxy_status": "NEG", "python_pred": [p for _, p, _ in ref],
                            "python_score": [s for _, _, s in ref], **dict(zip(FEATURE_ORDER, X.T))})
    link = r.Link(target, timeout=0.05)
    return r.summarize(r.replay(link, vectors), r.invalid_input_checks(link, X[0]), "host_mock")


def test_bad_crc_oversized_request_and_wrong_model_rejected():
    target = FakeTarget()
    raw = r.encode_frame(r.RESULT, struct.pack("<IbbfI", 5, 0, 1, 0.75, 3))
    target.out += raw[:-1] + bytes([raw[-1] ^ 1])
    with pytest.raises(r.ProtocolError):
        r.Link(target, 0.05).receive()
    with pytest.raises(r.ProtocolError):
        r.predict_payload(0, np.zeros(33))
    hello = bytes([1, 23, 25, 209, 0]) + b"".join(bytes([len(v)]) + v for v in (b"v", b"x" * 64, b"y", b"t", b"c")) + b"\xf0\x00"
    with pytest.raises(r.ProtocolError):
        r.handshake(r.Link(FakeTarget(hello=hello), 0.05), "a" * 64)


def test_clean_replay_and_all_invalid_inputs_pass(monkeypatch):
    s = _run(FakeTarget(), monkeypatch)
    assert s["result"] == "HOST_MOCK_PASS" and s["vectors"] == 12 and s["invalid_inputs_passed"] == s["invalid_inputs_total"] == 9


def test_dropped_response_and_score_error_are_reported_not_skipped(monkeypatch):
    s = _run(FakeTarget(drop_ids={3}), monkeypatch)
    assert s["result"] == "FAIL" and s["transport_failures"] == 1 and s["vectors"] == 12
    s = _run(FakeTarget(score_offset=1e-3), monkeypatch)
    assert s["result"] == "FAIL" and s["score_mismatches"] == 12
