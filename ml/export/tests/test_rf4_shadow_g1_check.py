"""Test cong cu G1 (log Serial gia lap, khong can Wokwi): doc [MODEL], phan doan kich ban/cua so sach, cac kiem tra G1,
va doi chieu offline voi mo hinh dong bang (bo qua neu chua co mo hinh M2-R6a cuc bo)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from ml.export import rf4_freeze_m2r6b as F
from ml.export import rf4_shadow_g1_check as G

MODEL = ("[MODEL] status=AVAILABLE version=svmg-rf-four-class-m2r6a-0.1.0 kind=generated features=23 schema=svmg-angle-23-v1 "
         "schema_ok=yes preprocessing=imu-cf-bw4-20to10-v1 preprocessing_ok=yes requested=BASELINE_B active=BASELINE_B")


def f_line(t, values, mask="0x7fffff", mode="SIM"):
    vals = ",".join("nan" if math.isnan(v) else f"{v:.6g}" for v in values)
    return f"F,{t:.1f},{mode},1,0,0x00,{mask},23,1,1,600,1800,0,100.0,{vals}"


def m_line(t, rf, b="NORMAL", primary=None, calls=1, us=600, mode="SIM"):
    return f"M,{t:.1f},{mode},{rf},{b},{primary or b},0,{us},{us},{calls}"


def test_parse_segments_and_checks_without_model():
    v = [0.5] * 23
    log = "\n".join([MODEL, "[CFG] mac dinh model=BASELINE_B", "[MODE] SIMULATION", "[SCN] S1 sea=1",
                     f_line(200.0, v), m_line(200.0, "HIGH ROLL", calls=1),
                     f_line(400.0, v), m_line(400.0, "HIGH ROLL", calls=2),
                     "G,400.0,0,0,0,0,50,60,1,25,0,300,320,0,4"])
    s = G.summarize(G.parse(log), parity=None)
    assert s["checks"]["model_available_and_versioned"] and s["checks"]["baseline_b_is_active_model"]
    assert s["checks"]["primary_always_baseline_b"] and s["checks"]["rf_inference_ran"] and s["checks"]["rf_returned_a_class"]
    seg = s["segments"]["SIM:S1"]
    assert seg["updates"] == 2 and seg["clean_updates"] == 1 and seg["rf_clean"] == {"HIGH_ROLL": 1}   # 200 s: chua sach
    assert s["result"] == "G1_PASS"


def test_rf_as_primary_or_slow_inference_fails_g1():
    v = [0.5] * 23
    log = "\n".join([MODEL, f_line(10.0, v), m_line(10.0, "NORMAL", b="OFFSET", primary="NORMAL", us=1500)])
    c = G.summarize(G.parse(log), parity=None)["checks"]
    assert not c["primary_always_baseline_b"] and not c["latency_within_1ms"]


def test_missing_model_line_is_reported_not_assumed():
    s = G.summarize(G.parse(m_line(10.0, "NORMAL")), parity=None)
    assert not s["checks"]["model_line_seen"] and s["result"] == "G1_INCOMPLETE"


@pytest.mark.skipif(not (F.MODEL_DIR / "model.joblib").exists(), reason="cần mô hình M2-R6a cục bộ")
def test_offline_parity_uses_frozen_model_on_device_printed_features():
    from ml.train import rf_four_class_m2r6 as R
    frame = R.load(R.DATASETS["v0.3"][0])
    val = frame[frame.subset.eq("CORE") & frame.split.eq(R.VAL)]
    model, _ = F.load_frozen()
    picks, lines = [], [MODEL, "[MODE] SIMULATION"]
    for i, (_, row) in enumerate(val.head(40).iterrows()):
        x = R.matrix(val.loc[[row.name]])[0]
        p = model.predict_proba(np.array([x], dtype=np.float32))[0]
        rf = R.CLASSES[int(p.argmax())] if p.max() >= 0.5 else "UNKNOWN"
        short = {v: k for k, v in G.SHORT.items()}[rf]
        lines += [f_line(10.0 * i, list(x)), m_line(10.0 * i, short, calls=i + 1)]
        picks.append(rf)
    par = G.offline_parity(G.parse("\n".join(lines)))
    assert par["compared"] == 40 and par["agree"] + par["mismatch_near_threshold"] == 40 and not par["mismatch_other"]
    assert 0.25 <= par["conf"]["min"] <= 1.0
