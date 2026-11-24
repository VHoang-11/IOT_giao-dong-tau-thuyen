"""M2-R5c: bộ dữ liệu SIMULATION bốn lớp thử nghiệm v0.2 theo `ml/docs/M2_R5c_four_class_dataset_contract.md`.

Dùng lại nguyên quy tắc nhãn điểm cuối của pilot M2-R5 (`four_class_pilot_dataset.window_label`), ngưỡng labeling-v2
candidate đóng băng (D2) và đường Core C; không sửa pilot `svmg-four-class-pilot-0.1.0`. Bổ sung: độ phủ nhãn đích trong
lịch sử 180 s cho mỗi cửa sổ (D3), tập challenge S0b, thêm session S3 ở Train/Validation, Test-G1 giữ nguyên đúng các session
của pilot, và kiểm toán độ đa dạng seed (D4). Không huấn luyện mô hình.

    .venv/bin/python -m ml.train.four_class_experimental_dataset
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from ml.train import four_class_pilot_dataset as pilot
from ml.train.g1_simulation_dataset import ROOT, _core_rows, _features, _sha
from simulation.calibration.validate_labeling_v2_independent import CANDIDATE_PATH
from simulation.generator.config import DatasetSplit, LabelingVersion, ScenarioCode

DATASET_VERSION = "svmg-four-class-exp-0.2.0"
CONTRACT_VERSION = "svmg-four-class-label-contract-0.2.0"
LABEL_POLICY = "endpoint-phenotype-180s-history-0.2.0-APPROVED-EXPERIMENTAL"
FROZEN_CANDIDATE_SHA256 = "c57194eac3df5823165e63cd79f38fbbc50b099aabfb8acfc3528e235a959e9d"
OUT = ROOT / "ml/data/simulation_four_class_exp_v02"
REPORT = ROOT / "ml/reports/ml/m2_r5c_dataset_quality_report.md"
TARGET = {**pilot.TARGET, ScenarioCode.S0B: "NORMAL"}
SUBSET = {ScenarioCode.S0B: "CHALLENGE_S0B"}   # còn lại: CORE
# Kế hoạch khai báo trước (Train, Validation). S3 tăng gấp 3 so với pilot vì chỉ ~1/2 session S3 có growth quan sát được.
PLAN = {ScenarioCode.S0: (6, 3), ScenarioCode.S1: (6, 3), ScenarioCode.S2: (6, 3), ScenarioCode.S3: (24, 12),
        ScenarioCode.S0B: (4, 2)}
COVERAGE_THRESHOLDS = (0.0, 0.25, 0.5, 0.75, 1.0)
G1_SEED_BASE, G1_PER_SCENARIO = 2026112300, 9


def session_seed(index: int) -> int:
    """Seed SHA-256 ổn định cho session Train/Validation mới (D4); không đổi PRNG xorshift32 của bộ mô phỏng."""
    return int.from_bytes(hashlib.sha256(f"{DATASET_VERSION}|{index}".encode()).digest()[:4], "little") or 1


def pilot_test_g1_sessions() -> list[tuple[ScenarioCode, int]]:
    """Đúng các session Test-G1 của pilot (cùng thứ tự chỉ số và seed băm của pilot), không chỉnh theo kết quả."""
    out, index = [], 0
    for scenario, counts in pilot.PLAN.items():
        for split, count in zip(pilot.SPLITS, counts):
            for _ in range(count):
                if split is DatasetSplit.TEST_G1:
                    out.append((scenario, pilot.session_seed(index)))
                index += 1
    return out


def target_coverage(result, end_s: float, target: str) -> float | None:
    """Tỉ lệ mẫu 20 Hz trong lịch sử (end-180 s, end] có nhãn v2 bằng lớp đích; None nếu lịch sử chưa đủ/còn khởi động."""
    dt = result.timestamps_s[1] - result.timestamps_s[0]
    end = int(round(end_s / dt))
    start = end - int(round(pilot.WINDOW_S / dt)) + 1
    labels = result.labels_v2[max(start, 0):end + 1]
    if start < 0 or any(label is None for label in labels):
        return None
    return sum(label == target for label in labels) / len(labels)


def generate_session(runner, scenario: ScenarioCode, split: DatasetSplit, seed: int, origin: str) -> tuple[list[dict], dict]:
    result = runner.generate(scenario, seed=seed, dataset_split=split, labeling_version=LabelingVersion.V2)
    target, names, subset = TARGET[scenario], _features(), SUBSET.get(scenario, "CORE")
    session_id = f"{scenario.value}-seed-{seed:010d}"
    rows = []
    for raw in _core_rows(result.imu_samples):
        end_s, mask, vector = float(raw[0]), int(raw[1]), raw[7:]
        label, reason, agree_all = pilot.window_label(result, end_s, target)
        if not (bool(raw[2]) and bool(raw[3]) and int(raw[4]) >= 570 and int(raw[5]) >= 1710
                and mask == (1 << 23) - 1 and all(map(math.isfinite, vector))):
            label, reason = None, "CORE_FEATURE_INVALID"
        coverage = target_coverage(result, end_s, target)
        rows.append({"dataset_source": "SIMULATION", "dataset_version": DATASET_VERSION, "contract_version": CONTRACT_VERSION,
                     "label_source": pilot.LABEL_SOURCE, "label_policy": LABEL_POLICY, "subset": subset,
                     "session_id": session_id, "seed": seed, "scenario": scenario.value, "split": split.value,
                     "label": label or "ABSTAIN", "class_id": pilot.CLASSES[label] if label else "", "exclusion_reason": reason,
                     "target_coverage_180": "" if coverage is None else round(coverage, 6), "window_all_samples_agree": agree_all,
                     "window_start_seconds": end_s - pilot.WINDOW_S, "window_end_seconds": end_s, "feature_valid_mask": mask,
                     "n_valid_60": int(raw[4]), "n_valid_180": int(raw[5]), "data_quality_pct": float(raw[6]),
                     **{n: (float(v) if math.isfinite(v) else "") for n, v in zip(names, vector)}})
    meta = result.metadata
    return rows, {"session_id": session_id, "seed": seed, "seed_origin": origin, "scenario": scenario.value, "split": split.value,
                  "subset": subset, "target": target, "sampled_parameters": meta["sampled_parameters"], "events": result.events,
                  "eligible_windows": sum(r["label"] != "ABSTAIN" for r in rows), "windows": len(rows)}


def _diversity(per_session: list[int]) -> dict:
    n = [x for x in per_session if x > 0]
    total = sum(n)
    return {"windows": total, "sessions": len(n), "effective_sessions": round(total * total / sum(x * x for x in n), 2) if n else 0.0,
            "max_session_share": round(max(n) / total, 3) if n else None}


def audit(rows: list[dict], sessions: list[dict]) -> dict:
    eligible = [r for r in rows if r["label"] != "ABSTAIN"]
    by = {}
    for r in eligible:
        by.setdefault((r["subset"], r["split"], r["label"]), []).append(r)
    classes = {}
    for (subset, split, label), group in sorted(by.items()):
        per_session = Counter(r["session_id"] for r in group)
        cov = sorted(float(r["target_coverage_180"]) for r in group)
        q = lambda p: cov[min(len(cov) - 1, int(p * (len(cov) - 1) + 0.5))]  # noqa: E731
        classes[f"{subset}|{split}|{label}"] = {
            **_diversity(list(per_session.values())),
            "coverage": {"min": cov[0], "p25": q(.25), "median": q(.5), "mean": round(sum(cov) / len(cov), 4), "max": cov[-1]},
            "sensitivity": {str(t): {"windows": sum(c >= t for c in cov),
                                     "sessions": len({r["session_id"] for r in group if float(r["target_coverage_180"]) >= t})}
                            for t in COVERAGE_THRESHOLDS}}
    core = {tuple(k.split("|")[1:]) for k in classes if k.startswith("CORE|")}
    gates = {"all_classes_in_train_and_validation": all((s, c) in core for s in ("Train", "Validation") for c in pilot.CLASSES),
             "no_nan_in_eligible_features": all(r[n] != "" for r in eligible for n in _features()),
             "coverage_recorded_for_all_eligible": all(r["target_coverage_180"] != "" for r in eligible)}
    reasons = Counter((r["scenario"], r["exclusion_reason"]) for r in rows if r["label"] == "ABSTAIN")
    return {"classes": classes, "quality_gates": gates,
            "abstain_reasons": {f"{s}|{k}": v for (s, k), v in sorted(reasons.items())}, "seed_diversity": seed_diversity(sessions)}


def seed_diversity(sessions: list[dict]) -> dict:
    out = {}
    for scenario in sorted({s["scenario"] for s in sessions}):
        group = [s["sampled_parameters"] for s in sessions if s["scenario"] == scenario]
        t0 = [p["t0_s"] for p in group if p["t0_s"] is not None]
        out[scenario] = {"sessions": len(group), "distinct_t0": len({round(t) for t in t0}), "events": len(t0),
                         "baseline_sea_states": dict(sorted(Counter(p["baseline_sea_state"] for p in group).items()))}
    return out


def g1_seed_audit(runner) -> dict:
    """Kiểm toán G1 chỉ đọc: tái dựng seed tuần tự của G1 (không ghi lại artifact G1) và đo độ đa dạng t0/sea state."""
    sessions, index = [], 0
    for scenario in (ScenarioCode.S0, ScenarioCode.S1, ScenarioCode.S2, ScenarioCode.S3):
        for k in range(G1_PER_SCENARIO):
            split = DatasetSplit.TRAIN if k < 4 else DatasetSplit.VALIDATION if k < 6 else DatasetSplit.TEST_G1
            index += 1
            meta = runner.generate(scenario, seed=G1_SEED_BASE + index, dataset_split=split, labeling_version=LabelingVersion.V2).metadata
            sessions.append({"scenario": scenario.value, "seed": G1_SEED_BASE + index, "sampled_parameters": meta["sampled_parameters"]})
    manifest = ROOT / "ml/data/simulation_rf_g1/manifest.json"
    seeds_match = ([s["seed"] for s in json.loads(manifest.read_text())["sessions"]] == [s["seed"] for s in sessions]
                   if manifest.exists() else None)
    return {"seed_scheme": "seed_base+n (sequential)", "seeds_match_g1_manifest": seeds_match, **seed_diversity(sessions)}


def build_dataset(output_dir: Path = OUT, plan: dict = PLAN, report: Path | None = REPORT, include_test: bool = True) -> dict:
    if _sha(CANDIDATE_PATH) != FROZEN_CANDIDATE_SHA256:
        raise RuntimeError("labeling_v2_candidate.json khác bản đã đóng băng (D2); dừng.")
    runner, _ = pilot.make_runner()
    rows, sessions, index = [], [], 0
    jobs = [(sc, sp, None) for sc, counts in plan.items() for sp, n in zip((DatasetSplit.TRAIN, DatasetSplit.VALIDATION), counts)
            for _ in range(n)]
    jobs += [(sc, DatasetSplit.TEST_G1, seed) for sc, seed in pilot_test_g1_sessions()] if include_test else []
    for scenario, split, seed in jobs:
        origin = "pilot-0.1.0-test-g1" if seed else "exp-0.2.0-sha256"
        if seed is None:
            seed, index = session_seed(index), index + 1
        session_rows, session = generate_session(runner, scenario, split, seed, origin)
        rows.extend(session_rows)
        sessions.append(session)
    if len({s["seed"] for s in sessions}) != len(sessions):
        raise RuntimeError("Trùng seed giữa các session.")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "windows.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    contract = json.loads((ROOT / "contracts/features23.json").read_text())
    manifest = {"dataset_version": DATASET_VERSION, "contract_version": CONTRACT_VERSION, "label_policy": LABEL_POLICY,
                "label_source": pilot.LABEL_SOURCE, "dataset_source": "SIMULATION",
                "labeling_v2_candidate_sha256": FROZEN_CANDIDATE_SHA256, "class_mapping": pilot.CLASSES,
                "scenario_targets": {s.value: t for s, t in TARGET.items()}, "subsets": {s.value: SUBSET.get(s, "CORE") for s in TARGET},
                "feature_schema_version": contract["feature_schema_version"], "preprocessing_version": contract["preprocessing_version"],
                "feature_names": list(_features()), "plan_train_validation": {s.value: list(c) for s, c in plan.items()},
                "test_g1": "pilot svmg-four-class-pilot-0.1.0 Test-G1 sessions, unchanged", "coverage_thresholds": list(COVERAGE_THRESHOLDS),
                "session_count": len(sessions), "window_count": len(rows), "eligible_count": sum(r["label"] != "ABSTAIN" for r in rows),
                **audit(rows, sessions), "g1_seed_audit": g1_seed_audit(runner), "dataset_sha256": _sha(csv_path), "sessions": sessions,
                "sources_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in (
                    ROOT / "simulation/generator/scenarios.py", ROOT / "simulation/generator/config.py", ROOT / "simulation/generator/rng.py",
                    ROOT / "simulation/generator/imu_simulator.py", ROOT / "core/src/filter.c", ROOT / "core/src/features.c",
                    ROOT / "ml/train/g1_core_feature_runner.c", ROOT / "contracts/features23.json", CANDIDATE_PATH,
                    ROOT / "ml/train/four_class_pilot_dataset.py", Path(__file__).resolve())}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str, ensure_ascii=False) + "\n")
    if report:
        write_report(manifest, report)
    return manifest


def write_report(m: dict, path: Path) -> None:
    rows = [f"| {k.replace('|', ' | ')} | {v['windows']} | {v['sessions']} | {v['effective_sessions']} | {v['max_session_share']} | "
            f"{v['coverage']['median']:.3f} | {v['coverage']['min']:.3f} | "
            + " | ".join(f"{v['sensitivity'][str(t)]['windows']}/{v['sensitivity'][str(t)]['sessions']}" for t in (0.5, 0.75, 1.0)) + " |"
            for k, v in m["classes"].items()]
    seed = lambda d: "; ".join(f"{s}: " + (f"t0 khác nhau {v['distinct_t0']}/{v['events']}" if v["events"] else "không có sự kiện")  # noqa: E731
                               + f", sea state {v['baseline_sea_states']}"
                               for s, v in d.items() if isinstance(v, dict))
    lines = [f"# Báo cáo chất lượng bộ dữ liệu bốn lớp thử nghiệm M2-R5c (`{m['dataset_version']}`)", "",
             f"> Hợp đồng `{m['contract_version']}` (`ml/docs/M2_R5c_four_class_dataset_contract.md`), chính sách `{m['label_policy']}`. "
             "Nhãn là proxy mô phỏng theo kịch bản + ngưỡng labeling-v2 candidate đóng băng, không phải ground truth nguy hiểm ngoài "
             "thực tế. Báo cáo sinh tự động bởi `python -m ml.train.four_class_experimental_dataset`; dữ liệu gitignored tại "
             "`ml/data/simulation_four_class_exp_v02/`. Không huấn luyện hay đánh giá RF.", "",
             f"Session: {m['session_count']}; cửa sổ: {m['window_count']}; đủ điều kiện: {m['eligible_count']}. Cổng chất lượng: "
             + ", ".join(f"{k}={v}" for k, v in m["quality_gates"].items()) + ".", "",
             "## Phân bố lớp, độ đa dạng session và độ phủ nhãn đích trong lịch sử 180 s", "",
             "Cột: cửa sổ, session đóng góp, session hiệu dụng (Σn)²/Σn², tỉ phần lớn nhất của một session, trung vị và nhỏ nhất của "
             "`target_coverage_180`, rồi số cửa sổ/session còn lại nếu yêu cầu độ phủ ≥ 0,5 / 0,75 / 1,0 (chỉ là phân tích độ nhạy; "
             "chính sách chính không đổi).", "",
             "| Tập | Split | Lớp | Cửa sổ | Session | Session hiệu dụng | Tỉ phần lớn nhất | Phủ trung vị | Phủ nhỏ nhất | ≥0,5 | ≥0,75 | =1,0 |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|", *rows, "",
             "## Lý do ABSTAIN theo kịch bản", "", "; ".join(f"{k.replace('|', ' ')} {v}" for k, v in m["abstain_reasons"].items()) + ".", "",
             "## Kiểm toán độ đa dạng seed", "", f"- Bộ dữ liệu này (seed SHA-256; Test-G1 lấy nguyên từ pilot): {seed(m['seed_diversity'])}.",
             f"- G1 (seed tuần tự, chỉ đọc; khớp manifest G1: {m['g1_seed_audit']['seeds_match_g1_manifest']}): {seed(m['g1_seed_audit'])}. "
             "Artifact G1 không bị ghi lại.", "",
             "## Giới hạn", "",
             "- Nhãn và đặc trưng cùng sinh từ một bộ mô phỏng; ngưỡng candidate hiệu chỉnh trên chính bộ mô phỏng đó (D2).",
             "- Nhãn mô tả phenotype tại thời điểm dự đoán; lịch sử 180 s có thể trộn trạng thái (D1, D3) — xem độ phủ ở trên.",
             "- Chưa có pitch và nhiễu IMU (D5, PR riêng); ba đặc trưng pitch bằng 0. Chưa có Test-G2. S0b là tập challenge, không "
             "mặc định là dữ liệu huấn luyện NORMAL.", "", f"SHA-256 dataset: `{m['dataset_sha256']}`.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh bộ dữ liệu SIMULATION bốn lớp thử nghiệm M2-R5c (v0.2).")
    parser.add_argument("--output", type=Path, default=OUT)
    m = build_dataset(parser.parse_args().output)
    print(json.dumps({k: m[k] for k in ("dataset_version", "session_count", "eligible_count", "quality_gates", "dataset_sha256")},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
