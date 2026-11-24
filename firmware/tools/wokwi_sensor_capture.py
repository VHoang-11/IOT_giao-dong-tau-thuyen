"""M2-R4: ghi Serial của firmware `esp32dev_diag` trên Wokwi qua RFC2217 (CHỈ ĐỌC, không gửi byte nào) và tóm tắt bằng chứng
đường MPU6050 (I2C) -> roll/pitch -> Core C -> 23 đặc trưng. Nguồn là MPU6050 MÔ PHỎNG của Wokwi, không phải cảm biến vật lý.

    .venv/bin/python firmware/tools/wokwi_sensor_capture.py --port rfc2217://localhost:4000 --seconds 240 --run-id imu01
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "ml/data/parity/wokwi_mpu6050"   # gitignored


def summarize(text: str) -> dict:
    lines = text.splitlines()
    raw = [l.split(",") for l in lines if l.startswith("I,") and len(l.split(",")) == 14]
    rp = [l.split(",") for l in lines if l.startswith("R,") and len(l.split(",")) >= 4]
    feat = [l.split(",") for l in lines if l.startswith("F,") and len(l.split(",")) == 37]
    accel = {tuple(r[5:8]) for r in raw}
    gyro = {tuple(r[8:11]) for r in raw}
    rolls, pitches = [float(r[2]) for r in rp], [float(r[3]) for r in rp]
    masks = [int(f[6], 16) for f in feat]
    full = [f for f in feat if int(f[6], 16) == (1 << 23) - 1]
    s = {
        "lines": len(lines), "boot_i2c_scan": next((l for l in lines if l.startswith("[I2C] scan")), None),
        "boot_hw": next((l for l in lines if l.startswith("[HW]")), None),
        "diag_header_seen": any(l.startswith("[DIAG] M2-R4") for l in lines),
        "raw_lines": len(raw), "sensor_mode_raw_lines": sum(r[2] == "SENSOR" for r in raw),
        "who_am_i_ok_all": bool(raw) and all(r[3] == "1" for r in raw),
        "distinct_accel_register_tuples": len(accel), "distinct_gyro_register_tuples": len(gyro),
        "i2c_errors_last": int(raw[-1][11]) if raw else None, "saturation_last": int(raw[-1][13]) if raw else None,
        "roll_lines": len(rp), "roll_min": min(rolls, default=None), "roll_max": max(rolls, default=None),
        "pitch_min": min(pitches, default=None), "pitch_max": max(pitches, default=None),
        "feature_updates": len(feat), "max_valid_features": max((int(f[7]) for f in feat), default=0),
        "ready_long_seen": any(f[9] == "1" for f in feat), "all_23_valid_updates": len(full),
        "first_all_23_t": float(full[0][1]) if full else None,
        "distinct_valid_masks": sorted({f"0x{m:06x}" for m in masks}),
        "invalid_lists_seen": sorted({l for l in lines if l.startswith("[DIAG] invalid:")}),
    }
    checks = {
        "i2c_mpu_present": s["who_am_i_ok_all"] or bool(s["boot_hw"] and "MPU6050:ok" in s["boot_hw"]),
        "raw_registers_changed": s["distinct_accel_register_tuples"] >= 2 and s["sensor_mode_raw_lines"] > 0,
        "no_i2c_errors": s["i2c_errors_last"] == 0,
        "roll_or_pitch_changed": rp != [] and (max(rolls) - min(rolls) >= 1.0 or max(pitches) - min(pitches) >= 1.0),
        "features_ready_long": s["ready_long_seen"], "all_23_valid_observed": s["all_23_valid_updates"] > 0,
    }
    g = [l.split(",") for l in lines if l.startswith("G,") and len(l.split(",")) in (13, 15)]
    gaps = [dict(kv.split("=") for kv in l.split()[2:]) for l in lines if l.startswith("[DIAG] GAP ")]
    n60 = [int(f[10]) for f in feat]
    s["timing"] = {  # M2-R4: nhịp lấy mẫu; khoảng mẫu > 75 ms (max_gap_s) làm pipeline reset cửa sổ
        "feature_window_resets": sum(b < a for a, b in zip(n60, n60[1:])), "gap_events": len(gaps), "gap_details": gaps[:20],
        **({f"max_{k}_ms": max(float(r[i]) for r in g) for k, i in (("sample_dt", 6), ("loop_gap", 7), ("sampling", 8), ("lcd", 9),
                                                                     ("net", 10), ("feature_update", 12))} if g else {}),
        "cnt_gap_last": int(g[-1][2]) if g else None, "late_samples_last": int(g[-1][5]) if g else None,
        "loop_overruns_last": int(g[-1][4]) if g else None, "mqtt_error_lines": sum(l.startswith("E (") for l in lines),
        "acq_task": any(l.startswith("[ACQ]") for l in lines) or any(len(r) == 15 and (r[13] != "0" or r[14] != "0") for r in g),
        "acq_queue_overflow_last": int(g[-1][13]) if g and len(g[-1]) == 15 else None,
        "acq_queue_max": max((int(r[14]) for r in g if len(r) == 15), default=None)}
    m = [l.split(",") for l in lines if l.startswith("M,") and len(l.split(",")) == 10]   # M2-R7: RF bốn lớp shadow
    if m:
        model = next((l for l in lines if l.startswith("[MODEL]")), "")
        count = lambda i: dict(Counter(r[i] for r in m))  # noqa: E731
        s["rf_shadow"] = {"model_line": model, "updates": len(m), "rf": count(3), "baseline_b": count(4), "primary": count(5),
                          "infer_calls": int(m[-1][9]), "infer_last_us_max": max(int(r[7]) for r in m), "infer_max_us": int(m[-1][8])}
        checks.update(rf_model_available="status=AVAILABLE" in model and "svmg-rf-four-class-m2r6a-0.1.0" in model,
                      rf_shadow_only="active=BASELINE_B" in model and all(r[5] == r[4] for r in m),
                      rf_inference_ran=int(m[-1][9]) > 0)
    s["checks"] = checks
    s["result"] = "WOKWI_SENSOR_PASS" if all(checks.values()) else ("PARTIAL" if any(checks.values()) else "NO_EVIDENCE")
    return s


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ghi Serial Wokwi (chỉ đọc) và tóm tắt bằng chứng MPU6050 -> 23 đặc trưng.")
    parser.add_argument("--port", default="rfc2217://localhost:4000")
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    import serial  # noqa: PLC0415

    out = OUT_ROOT / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    data, deadline = bytearray(), time.monotonic() + args.seconds
    with serial.serial_for_url(args.port, baudrate=115200, timeout=0.5) as port:
        while time.monotonic() < deadline:
            data += port.read(4096)
    (out / "serial_raw.log").write_bytes(bytes(data))
    summary = {"source": "WOKWI_SIMULATED_MPU6050", "port": args.port, "capture_seconds": args.seconds,
               "serial_raw_sha256": hashlib.sha256(bytes(data)).hexdigest(), "bytes": len(data),
               **summarize(data.decode("utf-8", errors="replace"))}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if summary["result"] == "WOKWI_SENSOR_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
