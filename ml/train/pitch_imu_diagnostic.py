"""M2-R5c-2: mẫu chẩn đoán NHỎ cho mở rộng mô phỏng pitch/IMU (`svmg-sim-pitch-imu-0.1.0`). Không phải dataset huấn luyện.

8 session miền Train (2 mỗi lớp S0–S3, seed SHA-256 riêng; không dùng Test-G1) × 3 cấu hình ROLL_ONLY / PITCH_ONLY /
PITCH_MPU6050_RESIDUAL, qua đúng đường Core C 23 đặc trưng và quy tắc nhãn điểm cuối của pilot (nhãn lấy từ roll thật).

    .venv/bin/python -m ml.train.pitch_imu_diagnostic
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics as st

from ml.train import four_class_pilot_dataset as pilot
from ml.train.g1_simulation_dataset import ROOT, _core_rows, _features
from simulation.generator import pitch_imu as P
from simulation.generator.config import DatasetSplit, LabelingVersion

OUT = ROOT / "ml/data/simulation_pitch_imu_diag"
REPORT = ROOT / "ml/reports/ml/m2_r5c2_pitch_imu_diagnostic.md"
CONFIGS = {"ROLL_ONLY": P.ROLL_ONLY, "PITCH_ONLY": P.PITCH_ONLY, "PITCH_MPU6050_RESIDUAL": P.PITCH_MPU6050_RESIDUAL}
PITCH = ("pitch_rms_60", "pitch_std_60", "pitch_peak_to_peak_60")
ROLL = ("roll_std_60", "roll_mean_60", "roll_rms_slope_180")


def diag_seed(index: int) -> int:
    return int.from_bytes(hashlib.sha256(f"svmg-sim-pitch-imu-diag|{index}".encode()).digest()[:4], "little") or 1


def windows(result, imu, target: str) -> list[dict]:
    names, out = _features(), []
    for raw in _core_rows(imu):
        label, reason, _ = pilot.window_label(result, float(raw[0]), target)
        full = bool(raw[3]) and int(raw[1]) == (1 << 23) - 1 and all(map(math.isfinite, raw[7:]))
        ok = full and bool(raw[2]) and int(raw[4]) >= 570 and int(raw[5]) >= 1710
        out.append({"end": float(raw[0]), "ready_long": bool(raw[3]), "full23": full, "label": label if ok else None,
                    **dict(zip(names, raw[7:]))})
    return out


def q(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))] if s else math.nan


def run() -> dict:
    runner, _ = pilot.make_runner()
    per = {name: {"windows": [], "pitch_rms_deg": [], "residual": {"accel_x": [], "gyro_y": []}, "meta": []} for name in CONFIGS}
    for index, scenario in enumerate([s for s in pilot.TARGET for _ in range(2)]):
        seed = diag_seed(index)
        result = runner.generate(scenario, seed=seed, dataset_split=DatasetSplit.TRAIN, labeling_version=LabelingVersion.V2)
        clean = None
        for name, config in CONFIGS.items():
            imu, meta = P.synthesize(result, config, seed)
            for w in windows(result, imu, pilot.TARGET[scenario]):
                per[name]["windows"].append({"session": index, **w})
            theta = meta["pitch_rad"]
            per[name]["pitch_rms_deg"].append(math.degrees(math.sqrt(sum(x * x for x in theta) / len(theta))))
            per[name]["meta"].append({k: meta.get(k) for k in ("pitch_period_s", "pitch_damping_ratio", "accel_bias_m_s2", "gyro_bias_rad_s")})
            if name == "PITCH_ONLY":
                clean = imu
            if name == "PITCH_MPU6050_RESIDUAL":
                per[name]["residual"]["accel_x"].append([a.ax - b.ax for a, b in zip(imu, clean)])
                per[name]["residual"]["gyro_y"].append([a.gy - b.gy for a, b in zip(imu, clean)])
    base = {(w["session"], w["end"]): w for w in per["ROLL_ONLY"]["windows"]}
    summary = {"version": P.SIM_EXTENSION_VERSION, "sessions": 8, "split_domain": "Train", "configs": {}}
    for name, data in per.items():
        ws, ready = data["windows"], [w for w in data["windows"] if w["ready_long"]]
        eligible = [w for w in ws if w["label"]]
        both = [(w, base[(w["session"], w["end"])]) for w in eligible if base[(w["session"], w["end"])]["label"]]
        res = data["residual"]
        summary["configs"][name] = {
            "pitch_rms_deg": {"min": round(min(data["pitch_rms_deg"]), 3), "median": round(st.median(data["pitch_rms_deg"]), 3),
                              "max": round(max(data["pitch_rms_deg"]), 3)},
            "pitch_period_s": sorted(round(m["pitch_period_s"], 2) for m in data["meta"] if m["pitch_period_s"]),
            "full23_fraction_of_ready_windows": round(sum(w["full23"] for w in ready) / len(ready), 4),
            "eligible_by_class": {c: sum(w["label"] == c for w in eligible) for c in pilot.CLASSES},
            "label_agreement_with_roll_only": round(sum(w["label"] == b["label"] for w, b in both) / len(both), 4) if both else None,
            "pitch_features": {f: {k: round(q([w[f] for w in eligible], p), 4) for k, p in (("p5", .05), ("median", .5), ("p95", .95))}
                               for f in PITCH},
            "roll_feature_median_abs_diff_vs_roll_only": {f: round(st.median(abs(w[f] - b[f]) for w, b in both), 5) for f in ROLL} if both else {},
            "noise_residual": {k: {"within_session_std_median": round(st.median(st.pstdev(x) for x in v), 6),
                                   "between_session_bias_std": round(st.pstdev([st.fmean(x) for x in v]), 6)} for k, v in res.items() if v}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    write_report(summary)
    return summary


def write_report(s: dict) -> None:
    c = s["configs"]
    head = "| Chỉ số | " + " | ".join(c) + " |"
    row = lambda label, fn: f"| {label} | " + " | ".join(str(fn(v)) for v in c.values()) + " |"  # noqa: E731
    lines = [f"# Chẩn đoán mô phỏng pitch/IMU M2-R5c-2 (`{s['version']}`)", "",
             "> Mẫu chẩn đoán nhỏ (8 session miền Train, 2 mỗi lớp S0–S3; không dùng Test-G1), không phải dataset huấn luyện. "
             "Nhãn vẫn lấy từ roll thật theo quy tắc điểm cuối của pilot; ngưỡng/công thức không đổi. Sinh bởi "
             "`python -m ml.train.pitch_imu_diagnostic`; số liệu đầy đủ tại `ml/data/simulation_pitch_imu_diag/summary.json` (gitignored). "
             "Giả định và giới hạn: `ml/docs/M2_R5c2_pitch_imu_simulation.md`.", "", head, "|---|" + "---:|" * len(c),
             row("RMS pitch thật [độ] min/trung vị/max", lambda v: f"{v['pitch_rms_deg']['min']}/{v['pitch_rms_deg']['median']}/{v['pitch_rms_deg']['max']}"),
             row("Tỉ lệ cửa sổ đủ 23/23 khi đã sẵn sàng 180 s", lambda v: v["full23_fraction_of_ready_windows"]),
             row("Cửa sổ đủ điều kiện N/H/P/G", lambda v: "/".join(str(x) for x in v["eligible_by_class"].values())),
             row("Nhãn trùng roll-only", lambda v: v["label_agreement_with_roll_only"])]
    for f in PITCH:
        lines.append(row(f"`{f}` p5/trung vị/p95 [độ]", lambda v, f=f: f"{v['pitch_features'][f]['p5']}/{v['pitch_features'][f]['median']}/{v['pitch_features'][f]['p95']}"))
    for f in ROLL:
        lines.append(row(f"Trung vị |Δ`{f}`| so với roll-only", lambda v, f=f: v["roll_feature_median_abs_diff_vs_roll_only"].get(f)))
    noise = c["PITCH_MPU6050_RESIDUAL"]["noise_residual"]
    lines += ["", f"Chu kỳ pitch đã rút (s): {c['PITCH_ONLY']['pitch_period_s']}. Phần dư nhiễu đo được (cấu hình MPU6050 dư): "
              f"độ lệch chuẩn nhiễu trong session (trung vị) accel X {noise['accel_x']['within_session_std_median']} m/s² (cấu hình 0,02), "
              f"gyro Y {noise['gyro_y']['within_session_std_median']} rad/s (cấu hình ≈ 0,000524); độ phân tán bias giữa 8 session "
              f"accel X {noise['accel_x']['between_session_bias_std']} m/s² (cấu hình 0,01), gyro Y {noise['gyro_y']['between_session_bias_std']} "
              "rad/s (cấu hình ≈ 0,000873; ước lượng thô vì chỉ 8 session).", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(run()["configs"], indent=1, ensure_ascii=False))
