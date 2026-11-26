"""G1: nghiem thu Random Forest SHADOW tren Wokwi (env esp32dev_rf4_shadow). CHI DOC Serial; khong gui byte nao.

1) Ghi Serial TU LUC BOOT: chay lenh truoc, roi moi Start Wokwi; cong che doi toi khi RFC2217 mo.
   .venv/bin/python -m ml.export.rf4_shadow_g1_check capture --port rfc2217://localhost:4001 --seconds 1800 --run-id g1_01
2) Phan tich lai mot log da ghi:
   .venv/bin/python -m ml.export.rf4_shadow_g1_check analyze ml/data/parity/wokwi_mpu6050/g1_01/serial_raw.log

Kiem tra: dong [MODEL] (AVAILABLE, dung version/schema/preprocessing, active=BASELINE_B); primary luon = Baseline B;
warm-up + 23/23 dac trung; so lan suy luan; do tre; doi chieu OFFLINE: chay mo hinh dong bang tren dung 23 gia tri thiet bi
in o dong F (%.6g) -> do tin cay va lop ky vong (UNKNOWN neu conf < tau) so voi lop RF thiet bi bao o dong M cung thoi diem.
Ket qua RF tren STUB SIMULATION chi chung minh duong ong chay, KHONG phai do chinh xac.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "ml/data/parity/wokwi_mpu6050"   # gitignored
MODEL_VERSION = "svmg-rf-four-class-m2r6a-0.1.0"
FULL_MASK = (1 << 23) - 1
CLEAN_AFTER_S = 190.0          # cua so 180 s + 1 chu ky cap nhat sau khi doi kich ban/che do
LATENCY_MAX_US = 1000          # tieu chi G1 (roadmap): <= 1 ms moi lan suy luan
SHORT = {"NORMAL": "NORMAL", "HIGH ROLL": "HIGH_ROLL", "OFFSET": "PERSISTENT_OFFSET", "GROWTH": "AMPLITUDE_GROWTH",
         "UNKNOWN": "UNKNOWN", "FAULT": "FAULT"}   # class_short() trong firmware -> ten lop


def parse(text: str) -> dict:
    """Doc log Serial -> cac dong co cau truc, gan nhan doan (che do, kich ban) va 'sach' (du xa lan doi gan nhat)."""
    model = cfg = None
    mode, scn, seg_start, pending_change = "SENSOR", "S0", None, True
    feats, ms, gs = {}, [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[MODEL]"):
            model = dict(kv.split("=", 1) for kv in line[7:].split() if "=" in kv)
        elif line.startswith("[CFG]") and cfg is None:
            cfg = line
        elif line.startswith("[MODE]"):
            mode, pending_change = line.split()[1], True
        elif line.startswith("[SCN]"):
            scn, pending_change = line.split()[1], True
        elif line.startswith("F,"):
            f = line.split(",")
            if len(f) != 37:
                continue
            t = float(f[1])
            if pending_change:
                seg_start, pending_change = t - 10.0, False   # lan doi xay ra trong chu ky 10 s truoc dong F nay
            vals = [float("nan") if v == "nan" else float(v) for v in f[14:37]]
            feats[t] = {"t": t, "mode": f[2], "scenario": scn if f[2] == "SIM" else "-", "status": int(f[4]),
                        "mask": int(f[6], 16), "n_valid": int(f[7]), "ready_long": f[9] == "1", "values": vals,
                        "clean": seg_start is not None and t - seg_start >= CLEAN_AFTER_S}
        elif line.startswith("M,"):
            m = line.split(",")
            if len(m) == 10:
                ms.append({"t": float(m[1]), "mode": m[2], "rf": SHORT.get(m[3], m[3]), "b": SHORT.get(m[4], m[4]),
                           "primary": SHORT.get(m[5], m[5]), "status": int(m[6]), "infer_last_us": int(m[7]),
                           "infer_max_us": int(m[8]), "calls": int(m[9])})
        elif line.startswith("G,"):
            g = line.split(",")
            if len(g) in (13, 15):
                gs.append({"t": float(g[1]), "cnt_gap": int(g[2]), "acq_ovf": int(g[13]) if len(g) == 15 else 0,
                           "acq_qmax": int(g[14]) if len(g) == 15 else 0})
    return {"model": model, "cfg": cfg, "features": feats, "m": ms, "g": gs}


def offline_parity(p: dict) -> dict:
    """Chay mo hinh DONG BANG tren 23 gia tri thiet bi in ra (cung thoi diem voi dong M co RF duoc goi)."""
    import numpy as np

    from ml.export import rf4_freeze_m2r6b as F
    from ml.train import rf_four_class_m2r6 as R
    model, _ = F.load_frozen()                       # dung neu SHA model.joblib khac ban dong bang
    tau = json.loads(F.MANIFEST.read_text())["unknown_policy"]["tau_conf"]
    rows, prev_calls = [], 0
    for m in p["m"]:
        f = p["features"].get(m["t"])
        called = m["calls"] > prev_calls
        prev_calls = m["calls"]
        if not called or f is None or f["mask"] != FULL_MASK:
            continue
        proba = model.predict_proba(np.array([f["values"]], dtype=np.float32))[0]
        conf, k = float(proba.max()), int(proba.argmax())
        expect = R.CLASSES[k] if np.float32(conf) >= np.float32(tau) else "UNKNOWN"
        top2 = float(np.sort(proba)[-1] - np.sort(proba)[-2])
        rows.append({"t": m["t"], "mode": f["mode"], "scenario": f["scenario"], "clean": f["clean"], "device_rf": m["rf"],
                     "offline_rf": expect, "conf": round(conf, 4), "top2_margin": round(top2, 4),
                     "near_threshold": abs(conf - tau) < 1e-3 or top2 < 1e-3})
    agree = [r for r in rows if r["device_rf"] == r["offline_rf"]]
    mism = [r for r in rows if r["device_rf"] != r["offline_rf"]]
    return {"compared": len(rows), "agree": len(agree), "mismatch_near_threshold": sum(r["near_threshold"] for r in mism),
            "mismatch_other": [r for r in mism if not r["near_threshold"]][:10],
            "conf": {"min": min((r["conf"] for r in rows), default=None), "median": sorted(r["conf"] for r in rows)[len(rows) // 2] if rows else None},
            "rows": rows}


def summarize(p: dict, parity: dict | None) -> dict:
    ms, fs, gs = p["m"], list(p["features"].values()), p["g"]
    model = p["model"] or {}
    segs: dict[str, dict] = {}
    for m in ms:
        f = p["features"].get(m["t"])
        key = f"{m['mode']}:{f['scenario'] if f else '?'}"
        s = segs.setdefault(key, {"updates": 0, "clean_updates": 0, "rf_all": Counter(), "rf_clean": Counter(), "b_clean": Counter()})
        s["updates"] += 1
        s["rf_all"][m["rf"]] += 1
        if f and f["clean"]:
            s["clean_updates"] += 1
            s["rf_clean"][m["rf"]] += 1
            s["b_clean"][m["b"]] += 1
    full = [f for f in fs if f["mask"] == FULL_MASK]
    checks = {
        "model_line_seen": bool(model),
        "model_available_and_versioned": model.get("status") == "AVAILABLE" and model.get("version") == MODEL_VERSION
                                          and model.get("schema_ok") == "yes" and model.get("preprocessing_ok") == "yes",
        "baseline_b_is_active_model": model.get("active") == "BASELINE_B" and model.get("requested") == "BASELINE_B",
        "primary_always_baseline_b": bool(ms) and all(m["primary"] == m["b"] for m in ms),
        "warmup_reached_23_of_23": bool(full),
        "rf_inference_ran": bool(ms) and ms[-1]["calls"] > 0,
        "rf_returned_a_class": any(m["rf"] in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH") for m in ms),
        "latency_within_1ms": bool(ms) and max(m["infer_max_us"] for m in ms) <= LATENCY_MAX_US,
        "acq_queue_never_overflowed": all(g["acq_ovf"] == 0 for g in gs),
    }
    if parity is not None:
        checks["device_matches_offline_model"] = parity["compared"] > 0 and not parity["mismatch_other"]
    return {"checks": checks, "result": "G1_PASS" if all(checks.values()) else "G1_INCOMPLETE",
            "model_line": model, "cfg_line": p["cfg"],
            "first_full_23_t": full[0]["t"] if full else None, "feature_updates": len(fs), "full_23_updates": len(full),
            "m_updates": len(ms), "rf_calls_last": ms[-1]["calls"] if ms else 0,
            "infer_us_max": max((m["infer_max_us"] for m in ms), default=None),
            "cnt_gap_first_last": [gs[0]["cnt_gap"], gs[-1]["cnt_gap"]] if gs else None,
            "acq_queue_max": max((g["acq_qmax"] for g in gs), default=None),
            "segments": {k: {**{x: v[x] for x in ("updates", "clean_updates")}, "rf_all": dict(v["rf_all"]),
                             "rf_clean": dict(v["rf_clean"]), "baseline_b_clean": dict(v["b_clean"])} for k, v in segs.items()},
            "offline_parity": None if parity is None else {k: v for k, v in parity.items() if k != "rows"},
            "note": "SIMULATION dung STUB song sin cua M1 (khong phai bo sinh M2): lop RF chi chung minh duong ong, khong phai do chinh xac."}


def analyze(log: Path, with_parity: bool = True) -> dict:
    p = parse(log.read_text(encoding="utf-8", errors="replace"))
    parity = offline_parity(p) if with_parity else None
    s = summarize(p, parity)
    s["serial_raw_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
    (log.parent / "g1_summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    if parity is not None:
        (log.parent / "g1_parity_rows.json").write_text(json.dumps(parity["rows"], indent=1), encoding="utf-8")
    return s


def capture(port: str, seconds: float, run_id: str, wait_s: float) -> Path:
    import serial  # noqa: PLC0415  (pyserial, ghim trong ml/train/requirements.txt)
    u = urlparse(port)
    out = OUT_ROOT / run_id
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + wait_s
    while True:                                       # cho Wokwi mo cong (bat dau ghi truoc khi Start de bat dong [MODEL])
        try:
            socket.create_connection((u.hostname, u.port), timeout=1).close()
            break
        except OSError:
            if time.monotonic() > deadline:
                raise SystemExit(f"Cong {port} chua mo sau {wait_s:.0f} s")
            time.sleep(0.5)
    data, end = bytearray(), time.monotonic() + seconds
    with serial.serial_for_url(port, baudrate=115200, timeout=0.5) as sp:
        print(f"Dang ghi {seconds:.0f} s tu {port} -> {out}")
        while time.monotonic() < end:
            data += sp.read(4096)
    log = out / "serial_raw.log"
    log.write_bytes(bytes(data))
    return log


def main() -> None:
    ap = argparse.ArgumentParser(description="G1: nghiem thu RF shadow tren Wokwi (chi doc Serial).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--port", default="rfc2217://localhost:4001")
    c.add_argument("--seconds", type=float, default=1800)
    c.add_argument("--run-id", required=True)
    c.add_argument("--wait-s", type=float, default=600)
    a = sub.add_parser("analyze")
    a.add_argument("log", type=Path)
    a.add_argument("--no-parity", action="store_true")
    args = ap.parse_args()
    log = capture(args.port, args.seconds, args.run_id, args.wait_s) if args.cmd == "capture" else args.log
    s = analyze(log, with_parity=not getattr(args, "no_parity", False))
    print(json.dumps({k: s[k] for k in ("result", "checks", "first_full_23_t", "rf_calls_last", "infer_us_max", "segments",
                                        "offline_parity")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
