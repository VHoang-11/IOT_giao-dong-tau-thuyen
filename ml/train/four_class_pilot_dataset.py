"""M2-R5 pilot: bộ dữ liệu SIMULATION bốn lớp, nhỏ và tái lập được, phục vụ lập kế hoạch M2-R6 (không huấn luyện ở đây).

Dùng lại bộ mô phỏng có sẵn (ScenarioRunner, kích động G1, tổng hợp IMU), ngưỡng labeling-v2 *candidate* đã đóng băng
và đường lọc/đặc trưng Core C của production (ml/train/g1_core_feature_runner.c). Nhãn là proxy theo kịch bản, được
labeler v2 nhân quả xác nhận; KHÔNG phải ground truth nguy hiểm ngoài thực tế.
Chính sách gán nhãn cửa sổ bên dưới đang ở trạng thái PROPOSED, cần M1/M2 duyệt (xem báo cáo M2-R5).

    .venv/bin/python -m ml.train.four_class_pilot_dataset
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

from ml.train.g1_simulation_dataset import ROOT, _core_rows, _features, _sha
from simulation.calibration.validate_labeling_v2_independent import CANDIDATE_PATH, load_frozen_candidate
from simulation.generator.config import DatasetSplit, LabelingVersion, ScenarioCode, SimulationConfig
from simulation.generator.scenarios import ScenarioRunner

DATASET_VERSION = "svmg-four-class-pilot-0.1.0"
LABEL_SOURCE = "SIMULATION_SCENARIO_V2_CANDIDATE"
LABEL_POLICY = "scenario-target+v2-endpoint-single-phenotype-0.1.0-PROPOSED"
OUT = ROOT / "ml/data/simulation_four_class_pilot"
REPORT = ROOT / "ml/reports/ml/m2_r5_four_class_pilot_report.md"
CLASSES = {"NORMAL": 0, "HIGH_ROLL": 1, "PERSISTENT_OFFSET": 2, "AMPLITUDE_GROWTH": 3}   # = svmg_class_t 0..3
TARGET = {ScenarioCode.S0: "NORMAL", ScenarioCode.S1: "HIGH_ROLL", ScenarioCode.S2: "PERSISTENT_OFFSET",
          ScenarioCode.S3: "AMPLITUDE_GROWTH"}
SPLITS = (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST_G1)
# Số session mỗi split (Train, Validation, Test-G1). S3 gấp đôi: chỉ khoảng một nửa session S3 có tăng biên độ quan sát được.
PLAN = {ScenarioCode.S0: (4, 2, 2), ScenarioCode.S1: (4, 2, 2), ScenarioCode.S2: (4, 2, 2), ScenarioCode.S3: (8, 4, 4)}
SEED_BASE = 2026120100
FLAGS = {"HIGH_ROLL": "high_roll_active", "PERSISTENT_OFFSET": "persistent_offset_active",
         "AMPLITUDE_GROWTH": "observed_amplitude_growth"}
WINDOW_S = 180.0
SEED_SCHEME = "sha256(dataset_version|seed_base|index)[:4] little-endian uint32"


def session_seed(index: int, seed_base: int = SEED_BASE) -> int:
    """Seed băm cho từng session: seed xorshift32 liên tiếp cho các lần rút đầu gần như trùng nhau (t0, sea state)."""
    digest = hashlib.sha256(f"{DATASET_VERSION}|{seed_base}|{index}".encode()).digest()
    return int.from_bytes(digest[:4], "little") or 1


def make_runner() -> tuple[ScenarioRunner, dict]:
    candidate, document = load_frozen_candidate()
    return ScenarioRunner(replace(SimulationConfig(), labeling=candidate)), document


def window_label(result, end_s: float, target: str) -> tuple[str | None, str, bool]:
    """Nhãn cho cửa sổ nhân quả (end-180 s, end]; trả (nhãn hoặc None, lý do loại, mọi mẫu trong cửa sổ cùng nhãn)."""
    dt = result.timestamps_s[1] - result.timestamps_s[0]
    end = int(round(end_s / dt))
    start = end - int(round(WINDOW_S / dt)) + 1
    if start < 0 or abs(result.timestamps_s[end] - end_s) > dt / 2:
        return None, "NO_FULL_WINDOW", False
    t0 = result.events[0]["t0_s"] if result.events else None
    if t0 is not None and end_s < t0:
        return None, "PRE_EVENT", False
    if any(result.transition_flags[start:end + 1]):
        return None, "TRANSITION_IN_WINDOW", False
    labels = result.labels_v2[start:end + 1]
    if any(label is None for label in labels):
        return None, "LABEL_WARMUP", False
    agree_all = all(label == target for label in labels)
    if labels[-1] != target:
        return None, "ENDPOINT_LABEL_MISMATCH", agree_all
    flags = result.phenotype_flags_v2[end]
    active = {name for name, attr in FLAGS.items() if getattr(flags, attr) is True}
    if active != (set() if target == "NORMAL" else {target}):
        return None, "PHENOTYPE_OVERLAP", agree_all
    return target, "", agree_all


def generate_session(runner: ScenarioRunner, scenario: ScenarioCode, split: DatasetSplit, seed: int) -> tuple[list[dict], dict]:
    result = runner.generate(scenario, seed=seed, dataset_split=split, labeling_version=LabelingVersion.V2)
    target, names = TARGET[scenario], _features()
    session_id = f"{scenario.value}-seed-{seed:010d}"
    rows = []
    for raw in _core_rows(result.imu_samples):
        end_s, mask, vector = float(raw[0]), int(raw[1]), raw[7:]
        label, reason, agree_all = window_label(result, end_s, target)
        core_ok = (bool(raw[2]) and bool(raw[3]) and int(raw[4]) >= 570 and int(raw[5]) >= 1710
                   and mask == (1 << 23) - 1 and all(map(math.isfinite, vector)))
        if not core_ok:
            label, reason = None, "CORE_FEATURE_INVALID"
        rows.append({"dataset_source": "SIMULATION", "dataset_version": DATASET_VERSION, "label_source": LABEL_SOURCE,
                     "label_policy": LABEL_POLICY, "session_id": session_id, "seed": seed, "scenario": scenario.value,
                     "split": split.value, "label": label or "ABSTAIN", "class_id": CLASSES[label] if label else "",
                     "exclusion_reason": reason, "window_all_samples_agree": agree_all,
                     "window_start_seconds": end_s - WINDOW_S, "window_end_seconds": end_s, "feature_valid_mask": mask,
                     "n_valid_60": int(raw[4]), "n_valid_180": int(raw[5]), "data_quality_pct": float(raw[6]),
                     **{n: (float(v) if math.isfinite(v) else "") for n, v in zip(names, vector)}})
    meta = result.metadata
    session = {"session_id": session_id, "seed": seed, "scenario": scenario.value, "split": split.value, "target": target,
               "child_seeds": meta["child_seeds"], "sampled_parameters": meta["sampled_parameters"], "events": result.events,
               "eligible_windows": sum(r["label"] != "ABSTAIN" for r in rows), "windows": len(rows)}
    return rows, session


def build_dataset(output_dir: Path = OUT, plan: dict = PLAN, seed_base: int = SEED_BASE, report: Path | None = REPORT) -> dict:
    runner, candidate_doc = make_runner()
    rows, sessions = [], []
    for scenario, counts in plan.items():
        for split, count in zip(SPLITS, counts):
            for _ in range(count):
                session_rows, session = generate_session(runner, scenario, split, session_seed(len(sessions), seed_base))
                rows.extend(session_rows)
                sessions.append(session)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "windows.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts = {split.value: {label: {"windows": sum(r["split"] == split.value and r["label"] == label for r in rows),
                                    "sessions": len({r["session_id"] for r in rows if r["split"] == split.value and r["label"] == label})}
                            for label in CLASSES} for split in SPLITS}
    reasons: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["label"] == "ABSTAIN":
            reasons.setdefault(r["scenario"], {}).setdefault(r["exclusion_reason"], 0)
            reasons[r["scenario"]][r["exclusion_reason"]] += 1
    strict = {label: sum(r["label"] == label and r["window_all_samples_agree"] for r in rows) for label in CLASSES}
    complete = all(c["windows"] > 0 for split in counts.values() for c in split.values())
    contract = json.loads((ROOT / "contracts/features23.json").read_text())
    manifest = {
        "dataset_version": DATASET_VERSION, "dataset_source": "SIMULATION", "label_source": LABEL_SOURCE,
        "label_policy": LABEL_POLICY, "label_policy_status": "PROPOSED_PENDING_M1_M2_REVIEW",
        "labeling_v2_candidate": {"path": str(CANDIDATE_PATH.relative_to(ROOT)), "sha256": _sha(CANDIDATE_PATH),
                                  "calibration_status": candidate_doc["recommended_thresholds"]["calibration_status"]},
        "class_mapping": CLASSES, "scenario_targets": {s.value: t for s, t in TARGET.items()},
        "excluded_scenarios": {"S0b": "đối chứng âm, chưa đưa vào pilot", "H1": "kịch bản kết hợp, chưa có chính sách chồng lấn"},
        "feature_schema_version": contract["feature_schema_version"], "preprocessing_version": contract["preprocessing_version"],
        "feature_names": list(_features()), "raw_imu_sampling_hz": 20, "feature_sampling_hz": 10, "update_interval_s": 10,
        "window_s": [60, 180], "seed_base": seed_base, "seed_scheme": SEED_SCHEME, "plan": {s.value: dict(zip((x.value for x in SPLITS), c)) for s, c in plan.items()},
        "session_count": len(sessions), "window_count": len(rows), "eligible_count": sum(r["label"] != "ABSTAIN" for r in rows),
        "counts": counts, "strict_all_window_agreement_counts": strict, "abstain_reasons_by_scenario": reasons,
        "coverage_status": "ALL_CLASSES_IN_ALL_SPLITS" if complete else "MISSING_CLASS_IN_SOME_SPLIT",
        "dataset_sha256": _sha(csv_path), "sessions": sessions,
        "sources_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in (
            ROOT / "simulation/generator/scenarios.py", ROOT / "simulation/generator/config.py",
            ROOT / "simulation/generator/imu_simulator.py", ROOT / "core/src/filter.c", ROOT / "core/src/features.c",
            ROOT / "ml/train/g1_core_feature_runner.c", ROOT / "contracts/features23.json", Path(__file__).resolve())}}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, default=str) + "\n")
    if report:
        write_report(manifest, report)
    return manifest


def write_report(m: dict, path: Path) -> None:
    lines = [f"# Bộ dữ liệu pilot mô phỏng bốn lớp M2-R5 (`{m['dataset_version']}`)", "",
             "> Nhãn là **proxy theo kịch bản mô phỏng**, được xác nhận bằng ngưỡng labeling-v2 *candidate* đã đóng băng "
             "(`calibration_status=candidate`). Đây không phải ground truth nguy hiểm ngoài thực tế; chính sách gán nhãn cửa sổ "
             "đang **PROPOSED** (chờ M1/M2 duyệt) và không mô hình nào được huấn luyện. Báo cáo sinh tự động bởi "
             "`python -m ml.train.four_class_pilot_dataset` (dữ liệu gitignored tại `ml/data/simulation_four_class_pilot/`).", "",
             "## Phương pháp", "",
             "- Nguồn: `ScenarioRunner` có sẵn (dao động tử roll phi tuyến bậc hai 1 bậc tự do, kích động tương quan G1, tổng hợp "
             "IMU hệ FRD ở 20 Hz; gia tốc kế = lực riêng từ cùng góc roll, con quay gx = cùng tốc độ roll). Kịch bản S0→NORMAL, "
             "S1→HIGH_ROLL, S2→PERSISTENT_OFFSET, S3→AMPLITUDE_GROWTH; S0b và H1 không đưa vào pilot.",
             f"- Đặc trưng: bộ lọc Core C production + `features.c` qua `g1_core_feature_runner.c` (đổi hệ FRD→cảm biến, 20→10 Hz, "
             f"bỏ 20 output khởi động). Schema `{m['feature_schema_version']}`, preprocessing `{m['preprocessing_version']}`, 23 "
             "đặc trưng đúng thứ tự contract, một cửa sổ nhân quả (t-180 s, t] mỗi 10 s.",
             "- Một cửa sổ chỉ được gán lớp khi thỏa mọi điều kiện: Core C sẵn sàng 60/180 s, 23/23 hợp lệ và hữu hạn, "
             "n60 ≥ 570, n180 ≥ 1710; cửa sổ kết thúc sau thời điểm sự kiện t0; trong cửa sổ không có mẫu chuyển tiếp của bộ "
             "mô phỏng (t0..t0+90 s) và không có mẫu khởi động v2; nhãn v2 nhân quả tại điểm cuối cửa sổ bằng nhãn đích của "
             "kịch bản; và chỉ đúng cờ phenotype đích đang bật (NORMAL: không cờ nào). Ngược lại cửa sổ là `ABSTAIN` kèm lý do. "
             "NaN không bao giờ được thay bằng 0.",
             f"- Chia tập theo session, dùng các miền tham số đã thống nhất. Seed session = {m['seed_scheme']} "
             f"(seed_base {m['seed_base']}), tách biệt với seed của G1 và của các lần hiệu chỉnh/xác nhận labeling-v2. Lần sinh "
             "đầu dùng seed tuần tự (seed_base+n) chỉ cho bốn thời điểm sự kiện khác nhau (330-341 s) và không có baseline SS0, "
             "vì lần rút đầu của xorshift32 gần như trùng nhau với các seed liên tiếp; G1 và các lần hiệu chỉnh v2 cũng dùng seed "
             "tuần tự nên cần kiểm toán lại độ đa dạng tham số (bộ mô phỏng không bị sửa ở đây).", "",
             "## Số lượng (cửa sổ đủ điều kiện / số session đóng góp)", "",
             "| Split | " + " | ".join(m["class_mapping"]) + " |", "|---|" + "---:|" * len(m["class_mapping"])]
    for split, by_label in m["counts"].items():
        lines.append(f"| {split} | " + " | ".join(f"{c['windows']} / {c['sessions']}" for c in by_label.values()) + " |")
    lines += ["", f"Số session: {m['session_count']}; số cửa sổ: {m['window_count']}; đủ điều kiện: {m['eligible_count']}; "
              f"độ phủ: **{m['coverage_status']}**. Theo quy tắc chặt kiểu G1 (mọi mẫu trong cửa sổ 180 s mang nhãn đích), "
              "số cửa sổ đủ điều kiện sẽ là: "
              + ", ".join(f"{k} {v}" for k, v in m["strict_all_window_agreement_counts"].items()) + ".", "",
              "Lý do ABSTAIN theo kịch bản: " + "; ".join(f"{s}: " + ", ".join(f"{k} {v}" for k, v in sorted(r.items()))
                                                        for s, r in sorted(m["abstain_reasons_by_scenario"].items())) + ".", "",
              "## Giới hạn", "",
              "- Nhãn và đặc trưng cùng sinh ra từ một chuỗi roll mô phỏng; nhãn dạng quy tắc có thể làm việc phân lớp trông dễ "
              "(xem M2-R3). Ngưỡng là candidate được hiệu chỉnh trên chính bộ mô phỏng này.",
              "- AMPLITUDE_GROWTH ngắn ngủi và thưa: tăng biên độ tham số không xuất hiện ở mọi session S3 và nhanh chóng "
              "chuyển thành HIGH_ROLL, nên ít cửa sổ đạt điều kiện.",
              "- Bộ mô phỏng chỉ có roll, nhiễu/bias IMU chưa đặt (None): ba đặc trưng pitch bằng đúng 0 ở mọi cửa sổ (cột hằng, "
              "không mang thông tin) và MPU6050 thật sẽ khác (lệch miền). Test-G2 (G2/JONSWAP) chưa được triển khai nên chỉ có "
              "Train/Validation/Test-G1. Profile sea state chưa được hiệu chỉnh với sóng thật.",
              "- Cỡ pilot nhỏ hơn rất nhiều so với 605 session theo kế hoạch; số lượng không phù hợp cho metric cuối cùng.", "",
              "## Kiểm chứng", "",
              "`pytest ml/train/tests/test_four_class_pilot_dataset.py` kiểm tra tính tất định, class id so với `svmg_class_t`, "
              "loại cửa sổ trước sự kiện/chuyển tiếp, cô lập split theo session và seed không trùng, thứ tự 23 đặc trưng và tính "
              "hữu hạn (không impute bằng 0), tính nhân quả (đặc trưng từ 600 s đầu bằng đặc trưng của cả session) và sự nhất quán "
              "manifest/CSV. Parity đặc trưng Core C so với Python M2 do `tests/firmware/tools/check_features23.py` đảm nhận; "
              "sinh lại phải tái tạo đúng SHA-256 bên dưới.", "",
              "## Mức sẵn sàng cho M2-R6", "",
              "Chỉ dùng được để phát triển pipeline và thử nghiệm RF theo nhóm đầu tiên sau khi M1/M2 duyệt chính sách gán nhãn "
              "cửa sổ, cách xử lý chồng lấn/ABSTAIN và việc dùng ngưỡng candidate. Không dùng để tuyên bố độ chính xác ngoài thực tế.",
              f"SHA-256 của dataset: `{m['dataset_sha256']}`.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh bộ dữ liệu pilot SIMULATION bốn lớp M2-R5.")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    m = build_dataset(args.output)
    print(json.dumps({k: m[k] for k in ("dataset_version", "session_count", "window_count", "eligible_count",
                                        "coverage_status", "counts", "dataset_sha256")}, indent=1))


if __name__ == "__main__":
    main()
