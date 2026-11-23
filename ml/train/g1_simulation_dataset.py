"""Deterministic G1 coursework dataset using the production Core C path."""
from __future__ import annotations

import argparse
import ctypes as ct
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from functools import lru_cache

from simulation.generator.config import DatasetSplit, ScenarioCode, SimulationConfig
from simulation.generator.scenarios import ScenarioRunner

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ml/data/simulation_rf_g1"
SCENARIOS = ((ScenarioCode.S0, "NORMAL", 0), (ScenarioCode.S1, "HIGH_ROLL", 1),
             (ScenarioCode.S2, "PERSISTENT_OFFSET", 2),
             (ScenarioCode.S3, "AMPLITUDE_GROWTH", 3))
SPLITS = (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST_G1)
ROW_WIDTH = 30
RAW_PER_FEATURE = 200
LABEL_SOURCE = "SIMULATION_SCENARIO_PROXY"


class MotionSample(ct.Structure):
    _fields_ = [(name, ct.c_float) for name in ("ax", "ay", "az", "gx", "gy", "gz", "t")]
    _fields_ += [("source_mode", ct.c_uint8), ("valid", ct.c_uint8)]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _features() -> tuple[str, ...]:
    contract = json.loads((ROOT / "contracts/features23.json").read_text())
    names = tuple(item["name"] for item in contract["features"])
    if len(names) != 23 or [item["index"] for item in contract["features"]] != list(range(23)):
        raise ValueError("Contract features23 không có đúng 23 vị trí liên tục.")
    return names


@lru_cache(maxsize=1)
def _core_runner() -> ct.CDLL:
    build_dir = Path(tempfile.mkdtemp(prefix="svmg-g1-core-"))
    library = build_dir / "libsvmg_g1.so"
    subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-shared", "-fPIC",
                    "-I", str(ROOT / "core/include"),
                    str(ROOT / "core/src/filter.c"), str(ROOT / "core/src/features.c"),
                    str(ROOT / "ml/train/g1_core_feature_runner.c"), "-lm", "-o", str(library)],
                   check=True, cwd=ROOT)
    lib = ct.CDLL(str(library))
    lib.svmg_g1_extract.argtypes = [ct.POINTER(MotionSample), ct.c_size_t,
                                    ct.POINTER(ct.c_float), ct.c_size_t]
    lib.svmg_g1_extract.restype = ct.c_int
    c_names = (ct.c_char_p * 23).in_dll(lib, "SVMG_FEATURE_NAMES")
    if tuple(item.decode() for item in c_names) != _features():
        raise ValueError("Tên/thứ tự feature từ Core C lệch contracts/features23.json.")
    return lib


def _core_rows(samples) -> list[list[float]]:
    input_rows = (MotionSample * len(samples))()
    for i, sample in enumerate(samples):
        input_rows[i] = MotionSample(sample.ax, sample.ay, sample.az, sample.gx,
                                     sample.gy, sample.gz, sample.t, 1, sample.valid)
    capacity = len(samples) // RAW_PER_FEATURE + 1
    output = (ct.c_float * (capacity * ROW_WIDTH))()
    count = _core_runner().svmg_g1_extract(input_rows, len(samples), output, capacity)
    if count < 0:
        raise RuntimeError(f"Core C G1 runner lỗi: {count}")
    return [list(output[i * ROW_WIDTH:(i + 1) * ROW_WIDTH]) for i in range(count)]


def _window_evidence(result, end_s: float, target: str) -> tuple[bool, str]:
    lower = end_s - 180.0
    indexes = [i for i, t in enumerate(result.timestamps_s) if lower < t <= end_s]
    if not indexes:
        return False, "NO_WINDOW_SAMPLES"
    if any(result.transition_flags[i] for i in indexes):
        return False, "TRANSITION_IN_WINDOW"
    labels = [result.labels_v1[i] for i in indexes]
    if any(label is None for label in labels):
        return False, "LABEL_WARMUP"
    if any(label != target for label in labels):
        return False, "PRIMARY_LABEL_DISAGREEMENT"
    other_flags = {"NORMAL": (), "HIGH_ROLL": ("persistent_offset_active", "observed_amplitude_growth"),
                   "PERSISTENT_OFFSET": ("high_roll_active", "observed_amplitude_growth"),
                   "AMPLITUDE_GROWTH": ("high_roll_active", "persistent_offset_active")}[target]
    for i in indexes:
        flags = result.phenotype_flags_v2[i]
        if any(getattr(flags, name) is True for name in other_flags):
            return False, "KNOWN_PHENOTYPE_OVERLAP"
    return True, ""


def generate_session(scenario: ScenarioCode, split: DatasetSplit, seed: int,
                     config: SimulationConfig | None = None) -> list[dict]:
    config = config or SimulationConfig()
    result = ScenarioRunner(config).generate(scenario, seed=seed, dataset_split=split)
    target, class_id = next((label, cid) for code, label, cid in SCENARIOS if code is scenario)
    names = _features()
    rows = []
    for raw in _core_rows(result.imu_samples):
        end_s = float(raw[0])
        eligible, reason = _window_evidence(result, end_s, target)
        mask, short, long = int(raw[1]), bool(raw[2]), bool(raw[3])
        valid_counts = int(raw[4]) >= 570 and int(raw[5]) >= 1710
        vector = raw[7:]
        if not short or not long or not valid_counts or mask != (1 << 23) - 1 or not all(map(math.isfinite, vector)):
            eligible, reason = False, "CORE_FEATURE_INVALID"
        lower = end_s - 180.0
        rows.append({"dataset_source": "SIMULATION", "session_id": f"{scenario.value}-seed-{seed:010d}",
            "seed": seed, "scenario": scenario.value, "split": split.value,
            "label_source": LABEL_SOURCE, "proxy_label": target if eligible else "UNLABELED",
            "class_id": class_id if eligible else "", "window_start_seconds": lower,
            "window_end_seconds": end_s, "feature_valid_mask": mask,
            "ready_short": short, "ready_long": long, "n_valid_60": int(raw[4]),
            "n_valid_180": int(raw[5]), "data_quality_pct": float(raw[6]),
            "eligible": eligible, "exclusion_reason": reason,
            **{name: (float(value) if math.isfinite(value) else "")
               for name, value in zip(names, vector)}})
    return rows


def _write_report(manifest: dict, report_path: Path) -> None:
    lines = ["# Kiểm toán dataset mô phỏng G1 cho coursework RF", "",
        "> Nhãn là `SIMULATION_SCENARIO_PROXY`, không phải ground truth/hazard. Chưa huấn luyện RF; không đánh giá Test-G2.", "",
        f"- Phiên: {manifest['session_count']} (mỗi scenario: {manifest['sessions_per_scenario']}); tổng cửa sổ: {manifest['window_count']}; đủ điều kiện: {manifest['eligible_count']}.",
        f"- Feature: {manifest['feature_schema_version']}, đúng {len(manifest['feature_names'])} tên/thứ tự; preprocessing: `{manifest['preprocessing_version']}`.",
        f"- CSV SHA-256: `{manifest['dataset_sha256']}`. Pitch chỉ từ IMU/filter thực tế của simulator roll-only, không sinh thêm pitch motion.", "",
        "| Split | Scenario | Session groups có mẫu đủ điều kiện | Cửa sổ đủ điều kiện | Cửa sổ loại |", "|---|---|---:|---:|---:|"]
    for item in manifest["coverage"]:
        lines.append(f"| {item['split']} | {item['scenario']} | {item['groups_with_eligible_windows']}/{item['sessions']} | {item['eligible_windows']} | {item['excluded_windows']} |")
    lines += ["", "### Eligible windows per independent session", "", "| Session ID | Split | Scenario proxy | Eligible | Excluded |", "|---|---|---|---:|---:|"]
    for session in manifest["sessions"]:
        lines.append(f"| `{session['session_id']}` | {session['split']} | {session['proxy_target']} | {session['eligible_windows']} | {session['excluded_windows']} |")
    lines += ["", "## Kết luận", "", f"Training readiness: **{manifest['training_readiness']}**. Dataset phù hợp để kiểm tra plumbing/proxy theo G1, nhưng lớp thiếu coverage ở Train/Validation thì chưa train được. Chưa đủ cơ sở gọi là mô hình phenotype/hazard đã xác minh. Session/seed là group split; không chia cửa sổ ngẫu nhiên. Nhãn v1 đồng nhất, transition và overlap đã biết chỉ là bộ lọc proxy coursework, không phê duyệt ontology B2a.", ""]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_dataset(sessions_per_scenario: int = 9, seed_base: int = 2026112300,
                  output_dir: Path = OUT) -> dict:
    if sessions_per_scenario < 3:
        raise ValueError("Cần tối thiểu 3 session/scenario để có đủ Train/Validation/Test-G1.")
    config = SimulationConfig()
    rows, sessions = [], []
    for scenario, _, _ in SCENARIOS:
        train_count = max(1, sessions_per_scenario - 5) if sessions_per_scenario >= 6 else 1
        validation_count = 2 if sessions_per_scenario >= 6 else 1
        for index in range(sessions_per_scenario):
            split = (DatasetSplit.TRAIN if index < train_count else
                     DatasetSplit.VALIDATION if index < train_count + validation_count else
                     DatasetSplit.TEST_G1)
            seed = seed_base + len(sessions) + 1
            session_rows = generate_session(scenario, split, seed, config)
            rows.extend(session_rows)
            eligible_count = sum(bool(row["eligible"]) for row in session_rows)
            sessions.append({"session_id": f"{scenario.value}-seed-{seed:010d}", "seed": seed,
                             "scenario": scenario.value, "split": split.value,
                             "generator_version": config.generator_version,
                             "sample_count_20hz": config.time.sample_count,
                             "proxy_target": next(label for code, label, _ in SCENARIOS if code is scenario),
                             "eligible_windows": eligible_count,
                             "excluded_windows": len(session_rows) - eligible_count})
    names = _features()
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "g1_windows.csv"
    columns = ["dataset_source", "session_id", "seed", "scenario", "split", "label_source", "proxy_label",
        "class_id", "window_start_seconds", "window_end_seconds", "feature_valid_mask", "ready_short",
        "ready_long", "n_valid_60", "n_valid_180", "data_quality_pct", "eligible", "exclusion_reason", *names]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    coverage = []
    for split in SPLITS:
        for scenario, _, _ in SCENARIOS:
            subset = [r for r in rows if r["split"] == split.value and r["scenario"] == scenario.value]
            coverage.append({"split": split.value, "scenario": scenario.value,
                "sessions": sum(s["split"] == split.value and s["scenario"] == scenario.value for s in sessions),
                "groups_with_eligible_windows": sum(s["split"] == split.value and s["scenario"] == scenario.value and s["eligible_windows"] > 0 for s in sessions),
                "eligible_windows": sum(bool(r["eligible"]) for r in subset),
                "excluded_windows": sum(not bool(r["eligible"]) for r in subset)})
    contract = json.loads((ROOT / "contracts/features23.json").read_text())
    ready = all(item["groups_with_eligible_windows"] >= (2 if item["split"] != "Train" else 2)
                for item in coverage)
    manifest = {"dataset_version": "svmg-g1-coursework-0.1.0", "dataset_source": "SIMULATION",
        "label_source": LABEL_SOURCE, "session_count": len(sessions), "sessions_per_scenario": sessions_per_scenario,
        "window_count": len(rows), "eligible_count": sum(bool(r["eligible"]) for r in rows),
        "training_readiness": "COURSEWORK_READY" if ready else "BLOCKED_MISSING_CLASS_GROUP_COVERAGE",
        "feature_schema_version": contract["feature_schema_version"],
        "preprocessing_version": contract["preprocessing_version"], "feature_names": list(names),
        "sampling_hz": 10, "raw_imu_sampling_hz": 20, "update_interval_s": 10,
        "window_endpoint": contract["window_endpoint"], "generator_version": config.generator_version,
        "class_mapping": {label: class_id for _, label, class_id in SCENARIOS},
        "seed_base": seed_base, "sessions": sessions, "coverage": coverage,
        "dataset_sha256": _sha(csv_path), "sources_sha256": {
            str(p.relative_to(ROOT)): _sha(p) for p in (
                ROOT / "simulation/generator/scenarios.py", ROOT / "simulation/generator/config.py",
                ROOT / "core/src/filter.c", ROOT / "core/src/features.c",
                ROOT / "ml/train/g1_core_feature_runner.c", ROOT / "contracts/features23.json")}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _write_report(manifest, ROOT / "ml/reports/ml/g1_coursework_dataset_audit.md")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo dataset G1 proxy từ generator và Core C production.")
    parser.add_argument("--sessions-per-scenario", type=int, default=9)
    parser.add_argument("--seed-base", type=int, default=2026112300)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.sessions_per_scenario, args.seed_base, args.output), indent=2))


if __name__ == "__main__":
    main()
