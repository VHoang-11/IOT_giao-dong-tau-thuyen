"""M2-R5d: bộ dữ liệu SIMULATION bốn lớp thử nghiệm v0.3 = v0.2 + pitch và nhiễu/bias IMU (`PITCH_MPU6050_RESIDUAL`).

Dùng lại nguyên `four_class_experimental_dataset` (v0.2: nhãn điểm cuối, ngưỡng đóng băng, ABSTAIN, độ phủ, kiểm toán) và
`simulation/generator/pitch_imu.py` (`svmg-sim-pitch-imu-0.1.0`). Cùng session/seed với v0.2 (kể cả Test-G1); chỉ thay mẫu IMU
20 Hz đưa vào Core C, roll thật và nhãn v2 giữ nguyên. Không sửa pilot/v0.2, không huấn luyện mô hình.

    .venv/bin/python -m ml.train.four_class_v03_dataset
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

from ml.train import four_class_experimental_dataset as v02
from ml.train import four_class_pilot_dataset as pilot
from ml.train.g1_simulation_dataset import ROOT, _features, _sha
from simulation.calibration.validate_labeling_v2_independent import CANDIDATE_PATH
from simulation.generator import pitch_imu as P
from simulation.generator.config import DatasetSplit

DATASET_VERSION = "svmg-four-class-exp-0.3.0"
IMU_CONFIG_NAME, IMU_CONFIG = "PITCH_MPU6050_RESIDUAL", P.PITCH_MPU6050_RESIDUAL
OUT = ROOT / "ml/data/simulation_four_class_exp_v03"
REPORT = ROOT / "ml/reports/ml/m2_r5d_dataset_v03_quality_report.md"
V02_CSV = v02.OUT / "windows.csv"
PITCH = ("pitch_rms_60", "pitch_std_60", "pitch_peak_to_peak_60")
ROLL = ("roll_mean_60", "roll_std_60", "roll_rms_slope_180")


class PitchIMURunner:
    """Bọc ScenarioRunner: thay `imu_samples` bằng IMU có pitch + nhiễu (seed = seed session); nhãn và roll thật không đổi."""

    def __init__(self, runner, config: P.PitchIMUConfig = IMU_CONFIG):
        self.runner, self.config, self.meta = runner, config, {}

    def generate(self, scenario, *, seed: int, **kwargs):
        result = self.runner.generate(scenario, seed=seed, **kwargs)
        imu, self.meta[seed] = P.synthesize(result, self.config, seed)
        return replace(result, imu_samples=imu)


def jobs(plan: dict = v02.PLAN, include_test: bool = True) -> list[tuple]:
    """Đúng thứ tự và seed session của v0.2: Train/Validation seed SHA-256 v0.2, Test-G1 = các session Test-G1 của pilot."""
    out, index = [], 0
    for scenario, counts in plan.items():
        for split, n in zip((DatasetSplit.TRAIN, DatasetSplit.VALIDATION), counts):
            for _ in range(n):
                out.append((scenario, split, v02.session_seed(index), "exp-0.2.0-sha256"))
                index += 1
    return out + ([(sc, DatasetSplit.TEST_G1, seed, "pilot-0.1.0-test-g1") for sc, seed in v02.pilot_test_g1_sessions()]
                  if include_test else [])


def generate_session(runner: PitchIMURunner, scenario, split, seed: int, origin: str) -> tuple[list[dict], dict]:
    rows, session = v02.generate_session(runner, scenario, split, seed, origin)
    meta = runner.meta.pop(seed)
    rows = [{"sim_extension_version": P.SIM_EXTENSION_VERSION, "imu_config": IMU_CONFIG_NAME, **r,
             "dataset_version": DATASET_VERSION} for r in rows]
    theta = meta["pitch_rad"]
    session.update(sim_extension_version=P.SIM_EXTENSION_VERSION, pitch_period_s=meta["pitch_period_s"],
                   pitch_damping_ratio=meta["pitch_damping_ratio"], accel_bias_m_s2=meta["accel_bias_m_s2"],
                   gyro_bias_rad_s=meta["gyro_bias_rad_s"],
                   true_pitch_rms_deg=round(math.degrees(math.sqrt(sum(x * x for x in theta) / len(theta))), 6))
    return rows, session


def _q(values: list[float]) -> dict:
    v = sorted(values)
    pick = lambda p: round(v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))], 4)  # noqa: E731
    return {"p5": pick(.05), "median": pick(.5), "p95": pick(.95), "zero_fraction": round(sum(x == 0 for x in v) / len(v), 4)}


def summarize(rows: list[dict]) -> dict:
    """Phân bố cửa sổ/session theo tập-split-nhãn, tỉ lệ ABSTAIN, phân bố pitch trên cửa sổ có nhãn."""
    by, total = {}, Counter((r["subset"], r["split"]) for r in rows)
    for r in rows:
        by.setdefault(f"{r['subset']}|{r['split']}|{r['label']}", set()).add(r["session_id"])
    windows = Counter(f"{r['subset']}|{r['split']}|{r['label']}" for r in rows)
    eligible = [r for r in rows if r["label"] != "ABSTAIN"]
    return {"windows_sessions": {k: [windows[k], len(by[k])] for k in sorted(by)},
            "abstain_rate": {f"{s}|{p}": round(windows[f"{s}|{p}|ABSTAIN"] / n, 4) for (s, p), n in sorted(total.items())},
            "abstain_reasons": dict(sorted(Counter(r["exclusion_reason"] for r in rows if r["label"] == "ABSTAIN").items())),
            "pitch": {n: _q([float(r[n]) for r in eligible]) for n in PITCH}}


def compare(rows: list[dict], v02_csv: Path = V02_CSV) -> dict | None:
    """So sánh với CSV v0.2 cục bộ theo (session_id, window_end_seconds); None nếu chưa sinh v0.2."""
    if not v02_csv.exists():
        return None
    with v02_csv.open(encoding="utf-8") as f:
        old_rows = list(csv.DictReader(f))
    old = {(r["session_id"], r["window_end_seconds"]): r for r in old_rows}
    pairs = [(old.get((r["session_id"], str(r["window_end_seconds"]))), r) for r in rows]
    both = [(o, n) for o, n in pairs if o and o["label"] != "ABSTAIN" and n["label"] != "ABSTAIN"]
    return {"v02_sha256": _sha(v02_csv), "windows_v02": len(old_rows), "windows_matched": sum(o is not None for o, _ in pairs),
            "label_agreement": round(sum(bool(o) and o["label"] == n["label"] for o, n in pairs) / len(pairs), 6),
            "exclusion_reason_agreement": round(sum(bool(o) and o["exclusion_reason"] == n["exclusion_reason"] for o, n in pairs)
                                                / len(pairs), 6),
            "label_changes": dict(Counter(f"{o['label']}->{n['label']}" for o, n in pairs if o and o["label"] != n["label"])),
            "v02": summarize(old_rows),
            "roll_abs_delta": {k: _q([abs(float(n[k]) - float(o[k])) for o, n in both]) for k in ROLL}}


def build_dataset(output_dir: Path = OUT, plan: dict = v02.PLAN, report: Path | None = REPORT, include_test: bool = True,
                  v02_csv: Path = V02_CSV) -> dict:
    if _sha(CANDIDATE_PATH) != v02.FROZEN_CANDIDATE_SHA256:
        raise RuntimeError("labeling_v2_candidate.json khác bản đã đóng băng (D2); dừng.")
    runner = PitchIMURunner(pilot.make_runner()[0])
    rows, sessions = [], []
    for scenario, split, seed, origin in jobs(plan, include_test):
        session_rows, session = generate_session(runner, scenario, split, seed, origin)
        rows.extend(session_rows)
        sessions.append(session)
    if len({s["seed"] for s in sessions}) != len(sessions):
        raise RuntimeError("Trùng seed giữa các session/split.")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "windows.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    contract = json.loads((ROOT / "contracts/features23.json").read_text())
    contract_names = [f["name"] for f in sorted(contract["features"], key=lambda f: f["index"])]
    audit, summary, comparison = v02.audit(rows, sessions), summarize(rows), compare(rows, v02_csv)
    audit["quality_gates"].update(
        feature_columns_match_contract_order=[k for k in rows[0] if k in contract_names] == contract_names == list(_features()),
        unique_session_seeds_across_splits=True,
        pitch_features_not_identically_zero=all(v["zero_fraction"] < 1.0 for v in summary["pitch"].values()),
        labels_match_v02=None if comparison is None else comparison["label_agreement"] == 1.0)
    manifest = {"dataset_version": DATASET_VERSION, "base_dataset_version": v02.DATASET_VERSION,
                "contract_version": v02.CONTRACT_VERSION, "label_policy": v02.LABEL_POLICY, "label_source": pilot.LABEL_SOURCE,
                "dataset_source": "SIMULATION", "sim_extension_version": P.SIM_EXTENSION_VERSION,
                "imu_config_name": IMU_CONFIG_NAME, "imu_config": asdict(IMU_CONFIG),
                "labeling_v2_candidate_sha256": v02.FROZEN_CANDIDATE_SHA256, "class_mapping": pilot.CLASSES,
                "scenario_targets": {s.value: t for s, t in v02.TARGET.items()},
                "feature_schema_version": contract["feature_schema_version"], "preprocessing_version": contract["preprocessing_version"],
                "feature_names": list(_features()), "plan_train_validation": {s.value: list(c) for s, c in plan.items()},
                "test_g1": "pilot svmg-four-class-pilot-0.1.0 Test-G1 sessions = v0.2 Test-G1, unchanged",
                "session_count": len(sessions), "window_count": len(rows), "eligible_count": sum(r["label"] != "ABSTAIN" for r in rows),
                **audit, "summary": summary, "comparison_v02": comparison, "dataset_sha256": _sha(csv_path), "sessions": sessions,
                "sources_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in (
                    ROOT / "simulation/generator/scenarios.py", ROOT / "simulation/generator/config.py", ROOT / "simulation/generator/rng.py",
                    ROOT / "simulation/generator/imu_simulator.py", ROOT / "simulation/generator/pitch_imu.py",
                    ROOT / "simulation/generator/roll_dynamics.py", ROOT / "simulation/generator/wave_generator.py",
                    ROOT / "core/src/filter.c", ROOT / "core/src/features.c", ROOT / "ml/train/g1_core_feature_runner.c",
                    ROOT / "contracts/features23.json", CANDIDATE_PATH, ROOT / "ml/train/four_class_pilot_dataset.py",
                    ROOT / "ml/train/four_class_experimental_dataset.py", Path(__file__).resolve())}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str, ensure_ascii=False) + "\n")
    if report:
        write_report(manifest, report)
    return manifest


def write_report(m: dict, path: Path) -> None:
    c, s = m["comparison_v02"], m["summary"]
    old = c["v02"] if c else {"windows_sessions": {}, "abstain_rate": {}, "pitch": {}}
    cell = lambda d, k: "/".join(map(str, d.get(k, ["–"])))  # noqa: E731
    dist = [f"| {k.replace('|', ' | ')} | {cell(old['windows_sessions'], k)} | {cell(s['windows_sessions'], k)} | "
            f"{m['classes'][k]['effective_sessions']} | {m['classes'][k]['coverage']['median']:.3f} |"
            for k in s["windows_sessions"] if not k.endswith("ABSTAIN")]
    pq = lambda d: f"{d['p5']} / {d['median']} / {d['p95']} (0: {d['zero_fraction']})" if d else "–"  # noqa: E731
    lines = [f"# Báo cáo chất lượng bộ dữ liệu bốn lớp thử nghiệm M2-R5d (`{m['dataset_version']}`)", "",
             f"> `{m['base_dataset_version']}` + pitch/nhiễu IMU `{m['sim_extension_version']}` cấu hình `{m['imu_config_name']}`. "
             f"Cùng session/seed, nhãn, ngưỡng đóng băng và chính sách `{m['label_policy']}` như v0.2; Test-G1 giữ nguyên. Nguồn "
             "`SIMULATION`, nhãn là proxy mô phỏng, không phải ground truth nguy hiểm. Sinh bởi `python -m ml.train.four_class_v03_dataset`; "
             "dữ liệu và manifest gitignored tại `ml/data/simulation_four_class_exp_v03/`. Không huấn luyện/đánh giá RF.", "",
             f"Session: {m['session_count']}; cửa sổ: {m['window_count']}; có nhãn: {m['eligible_count']}. Cổng chất lượng: "
             + ", ".join(f"{k}={v}" for k, v in m["quality_gates"].items()) + ".", "",
             "## Phân bố lớp theo split (cửa sổ/session), v0.2 so với v0.3", "",
             "| Tập | Split | Lớp | v0.2 | v0.3 | Session hiệu dụng v0.3 | Phủ trung vị v0.3 |", "|---|---|---|---:|---:|---:|---:|", *dist, "",
             "## So sánh v0.2 và v0.3", "",
             f"- Khớp cửa sổ: {c['windows_matched']}/{c['windows_v02']}; trùng nhãn {c['label_agreement']}; trùng lý do loại "
             f"{c['exclusion_reason_agreement']}; nhãn đổi: {c['label_changes'] or 'không'}. SHA v0.2 `{c['v02_sha256'][:12]}…` không đổi."
             if c else "- Chưa có CSV v0.2 cục bộ nên không so sánh.",
             "- Tỉ lệ ABSTAIN (v0.2 → v0.3): " + "; ".join(f"{k.replace('|', ' ')} {old['abstain_rate'].get(k, '–')} → {v}"
                                                         for k, v in s["abstain_rate"].items()) + ".",
             "- Lý do ABSTAIN v0.3: " + ", ".join(f"{k} {v}" for k, v in s["abstain_reasons"].items()) + ".",
             "- Đặc trưng pitch trên cửa sổ có nhãn, p5 / trung vị / p95 (độ), kèm tỉ lệ bằng 0: "
             + "; ".join(f"`{n}` {pq(old['pitch'].get(n))} → {pq(d)}" for n, d in s["pitch"].items()) + ".",
             "- |Δ| đặc trưng roll trên cửa sổ có nhãn ở cả hai bản (p5 / trung vị / p95): "
             + ("; ".join(f"`{k}` {v['p5']} / {v['median']} / {v['p95']}" for k, v in c["roll_abs_delta"].items()) if c else "–") + ".",
             "- AMPLITUDE_GROWTH (cửa sổ/session hiệu dụng/phủ trung vị): " + "; ".join(
                 f"{k.split('|')[1]} {v['windows']}/{v['effective_sessions']}/{v['coverage']['median']:.3f}"
                 for k, v in m["classes"].items() if k.endswith("AMPLITUDE_GROWTH")) + ".", "",
             "## Giới hạn", "",
             "- Pitch, sea state và nhiễu là giả định mô phỏng chưa hiệu chỉnh với tàu/MPU6050 thật; chưa có gia tốc tịnh tiến, yaw, "
             "lượng tử hóa, trôi nhiệt, lệch trục (xem `ml/docs/M2_R5c2_pitch_imu_simulation.md`).",
             "- Nhãn lấy từ roll thật nên pitch/nhiễu không đổi nhãn; AMPLITUDE_GROWTH Validation vẫn mỏng. Chưa có Test-G2.", "",
             f"SHA-256 dataset: `{m['dataset_sha256']}`.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh bộ dữ liệu SIMULATION bốn lớp thử nghiệm M2-R5d (v0.3).")
    parser.add_argument("--output", type=Path, default=OUT)
    m = build_dataset(parser.parse_args().output)
    print(json.dumps({k: m[k] for k in ("dataset_version", "session_count", "eligible_count", "quality_gates", "dataset_sha256")},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
