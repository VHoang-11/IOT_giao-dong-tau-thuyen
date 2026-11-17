"""Dựng proxy-label dataset tái lập (PoC). Chạy từ repository root::

    python -m ml.labeling.proxy_dataset --spec ml/labeling/proxy_spec.yaml

Output lớn nằm trong ``ml/data/labels/proxy_v1/`` (gitignored). Tóm tắt nhỏ, đường dẫn tương đối,
được ghi vào ``ml/reports/ml/proxy_dataset_summary.json``. Module không ghi vào human-review ledger,
audit history, bảng verified hay bảng gợi ý AI; checksum được kiểm tra trước và sau khi chạy.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ml.labeling.ai_assisted_review import protected_checksums
from ml.labeling.human_review_workflow import ANGLE_FEATURES
from ml.labeling.proxy_rules import (ABSTAIN, NEG, POS, TARGETS, apply_rules, fit_calibration, load_spec,
                                     spec_sha256, supporting_measurements, window_statistics)
from ml.train.grouping import experiment_group, leave_one_group_out, session_cross_correlation

DATASETS = ("hohai", "seafar", "southampton")
SUMMARY_PATH = Path("ml/reports/ml/proxy_dataset_summary.json")
EXTRA_PROTECTED = (Path("ml/data/labels/ai_assisted_review/pilot_29_ai_suggestions.csv"),)


def _protected(repo_root: Path) -> dict:
    checks = protected_checksums(repo_root)
    for path in EXTRA_PROTECTED:
        full = repo_root / path
        if full.is_file():
            import hashlib
            checks[path.as_posix()] = hashlib.sha256(full.read_bytes()).hexdigest()
    return checks


def build_measurements(repo_root: Path, spec: dict) -> pd.DataFrame:
    """Một dòng cho mỗi window endpoint trong feature table (mọi nguồn), kèm thống kê nhân quả."""
    frames = []
    for dataset in DATASETS:
        base = repo_root / spec["paths"]["feature_root"] / dataset
        values = pd.read_parquet(base / "feature_values.parquet")
        meta = pd.read_parquet(base / "feature_metadata.parquet")
        table = meta.merge(values, on="window_id", how="inner", validate="one_to_one")
        rows = []
        for (session, segment), group in table.groupby(["session_id", "segment_id"], sort=True):
            path = repo_root / spec["paths"]["processed_root"] / dataset / session / segment / "timeseries.parquet"
            frame = pd.read_parquet(path, columns=["dataset_source", "session_id", "segment_id", "time_seconds", "roll_deg"])
            if {frame.dataset_source.iloc[0], frame.session_id.iloc[0], frame.segment_id.iloc[0]} != {dataset, session, segment}:
                raise ValueError(f"Định danh processed không khớp: {path}")
            t = frame.time_seconds.to_numpy(float)
            roll = frame.roll_deg.to_numpy(float)
            for record in group.itertuples(index=False):
                validity = json.loads(record.validity_json)
                source = json.loads(record.source_metadata_json)
                complete = all(validity[name]["status"] == "VALID" for name in ANGLE_FEATURES)
                stats = window_statistics(t, roll, float(record.window_end_seconds), float(t[0]), float(t[-1]), spec)
                row = {
                    "window_id": record.window_id, "dataset_source": dataset, "session_id": session,
                    "segment_id": segment, "window_start_seconds": float(record.window_end_seconds) - spec["window"]["window_seconds"],
                    "window_end_seconds": float(record.window_end_seconds),
                    "experiment_group": experiment_group(dataset, session), "angle23_complete": bool(complete),
                    "invalid_features_json": json.dumps(sorted(k for k, v in validity.items() if v["status"] != "VALID")),
                    "quality_flags_json": json.dumps([*source.get("warnings", []), "WINDOWS_OVERLAP_180S_STRIDE_10S"], ensure_ascii=False),
                    "source_class": source.get("source_class"), "raw_reference": source.get("raw_reference"),
                    "timestamp_source": source.get("timestamp_source"),
                    "filter_applied": bool(source.get("filter", {}).get("applied")),
                    "preprocessing_configuration_sha256": record.preprocessing_configuration_sha256,
                    "feature_spec_version": record.feature_spec_version,
                    "feature_extractor_version": record.feature_extractor_version,
                    "processed_path": path.relative_to(repo_root).as_posix(),
                    **{name: (float(getattr(record, name)) if getattr(record, name) is not None
                              and not pd.isna(getattr(record, name)) else math.nan) for name in ANGLE_FEATURES},
                    **stats,
                }
                if not row["statistics_valid"]:
                    for key in ("roll_mean_180_stat", "roll_centered_std_180", "roll_dominant_sign_ratio_180_stat",
                                "offset_to_oscillation_ratio", "centered_std_ratio", "log_centered_std_ratio",
                                "raw_rms_ratio", "context_fraction", "context_max_sub_std", "sub_std_lag1_autocorr",
                                "half_cycle_amplitude_lag1"):
                        row.setdefault(key, math.nan)
                    for key in ("block_mean_json", "block_centered_std_json", "block_raw_rms_json", "sub_block_std_json",
                                "sub_block_mean_sign_pattern"):
                        row.setdefault(key, "")
                    for key in ("monotonic_centered_blocks", "context_coverage_ok", "context_all_same_sign",
                                "late_block_exceeds_context"):
                        row.setdefault(key, False)
                    row.setdefault("sub_block_mean_sign_changes", -1)
                    row.setdefault("mann_kendall_S_sub_std", 0)
                rows.append(row)
        frames.append(pd.DataFrame(rows))
    measurements = pd.concat(frames, ignore_index=True)
    if measurements.window_id.duplicated().any():
        raise ValueError("window_id trùng trong measurement table.")
    return measurements.sort_values(["dataset_source", "session_id", "segment_id", "window_end_seconds"], ignore_index=True)


def out_of_fold_labels(measurements: pd.DataFrame, spec: dict, overrides: dict | None = None) -> tuple[pd.DataFrame, list[dict], pd.DataFrame]:
    """Nhãn mỗi cửa sổ Hohai dùng hiệu chuẩn fit trên các nhóm KHÁC nhóm của nó (out-of-fold)."""
    hohai_groups = measurements.loc[measurements.dataset_source.eq("hohai"), "experiment_group"]
    folds = leave_one_group_out(hohai_groups)
    by_fold, calibrations, oof = [], [], []
    for fold in folds:
        calibration = fit_calibration(measurements, fold["train_groups"], spec, overrides)
        calibrations.append({"fold": fold["fold"], **calibration, "test_groups": fold["test_groups"]})
        labels = apply_rules(measurements, calibration, spec)
        labels.insert(0, "fold", fold["fold"])
        labels["split_role"] = np.where(measurements.experiment_group.isin(fold["test_groups"]), "test",
                                        np.where(measurements.experiment_group.isin(fold["train_groups"]), "train", "outside_domain"))
        by_fold.append(labels)
        selected = labels.loc[labels.split_role.eq("test")]
        oof.append(selected)
        if fold["fold"] == 0:
            oof.append(labels.loc[labels.split_role.eq("outside_domain")])
    oof_frame = pd.concat(oof, ignore_index=True).drop(columns=["fold", "split_role"])
    if len(oof_frame) != len(measurements) or oof_frame.window_id.duplicated().any():
        raise RuntimeError("Nhãn out-of-fold không phủ đúng một lần mỗi cửa sổ.")
    return oof_frame, calibrations, pd.concat(by_fold, ignore_index=True)


def readiness(measurements: pd.DataFrame, labels: pd.DataFrame, spec: dict) -> dict:
    data = measurements.merge(labels, on="window_id", validate="one_to_one")
    gate = spec["readiness"]
    result = {}
    for dataset in DATASETS:
        subset = data.loc[data.dataset_source.eq(dataset)]
        # Chỉ nhóm có cửa sổ đủ 23 feature mới đóng góp quan sát độc lập.
        n_groups = subset.loc[subset.angle23_complete, "experiment_group"].nunique()
        per_target = {}
        for target in TARGETS:
            status = subset[f"{target}_status"]
            pos, neg = subset.loc[status.eq(POS)], subset.loc[status.eq(NEG)]
            info = {"positive_windows": int(len(pos)), "negative_windows": int(len(neg)),
                    "abstain_windows": int(status.eq(ABSTAIN).sum()),
                    "positive_groups": int(pos.experiment_group.nunique()), "negative_groups": int(neg.experiment_group.nunique()),
                    "positive_sessions": int(pos.session_id.nunique()), "negative_sessions": int(neg.session_id.nunique()),
                    "positive_groups_list": sorted(pos.experiment_group.unique().tolist())}
            blockers = []
            if n_groups < gate["minimum_domain_groups"]:
                blockers.append(f"DOMAIN_HAS_{n_groups}_INDEPENDENT_GROUP(S)")
            if info["positive_groups"] < gate["minimum_positive_groups"]:
                blockers.append(f"POSITIVE_GROUPS_{info['positive_groups']}<{gate['minimum_positive_groups']}")
            if info["negative_groups"] < gate["minimum_negative_groups"]:
                blockers.append(f"NEGATIVE_GROUPS_{info['negative_groups']}<{gate['minimum_negative_groups']}")
            if info["positive_sessions"] < gate["minimum_positive_sessions"]:
                blockers.append(f"POSITIVE_SESSIONS_{info['positive_sessions']}<{gate['minimum_positive_sessions']}")
            if info["positive_windows"] < gate["minimum_positive_windows"]:
                blockers.append(f"POSITIVE_WINDOWS_{info['positive_windows']}<{gate['minimum_positive_windows']}")
            info["decision"] = "TRAINABLE" if not blockers else "NOT_TRAINABLE"
            info["blockers"] = blockers
            per_target[target] = info
        complete = subset.loc[subset.angle23_complete]
        result[dataset] = {"independent_groups": int(n_groups), "sessions_with_complete_windows": int(complete.session_id.nunique()),
                           "windows": int(len(subset)), "complete_windows": int(len(complete)), "targets": per_target}
    return result


def distribution(measurements: pd.DataFrame, labels: pd.DataFrame) -> dict:
    data = measurements.merge(labels, on="window_id", validate="one_to_one")
    out = {}
    for dataset, subset in data.groupby("dataset_source"):
        entry = {"windows": int(len(subset)), "angle23_complete": int(subset.angle23_complete.sum()),
                 "window_status": subset.proxy_window_status.value_counts().to_dict(),
                 "targets": {t: subset[f"{t}_status"].value_counts().to_dict() for t in TARGETS},
                 "reasons": {t: subset[f"{t}_reason"].value_counts().to_dict() for t in TARGETS},
                 "phenotype_combinations": subset.proxy_phenotypes.value_counts().to_dict(),
                 "multi_label_windows": int(subset.multi_label.sum()),
                 "near_segment_end_audit_positive": {t: int((subset[f"{t}_status"].eq(POS) & subset.near_segment_end_audit).sum())
                                                     for t in TARGETS}}
        entry["by_group"] = {g: {t: grp[f"{t}_status"].value_counts().to_dict() for t in TARGETS} | {"windows": int(len(grp))}
                             for g, grp in subset.groupby("experiment_group")}
        out[dataset] = entry
    return out


def sensitivity(measurements: pd.DataFrame, spec: dict, default_labels: pd.DataFrame) -> dict:
    results = {}
    hohai = measurements.dataset_source.eq("hohai")
    base = default_labels.set_index("window_id")
    for target, variants in spec["sensitivity"].items():
        rows = []
        default_pos = set(base.index[base[f"{target}_status"].eq(POS)]) & set(measurements.window_id[hohai])
        for q_pos, q_neg in variants:
            labels, _, _ = out_of_fold_labels(measurements, spec, {target: (q_pos, q_neg)})
            merged = measurements.loc[hohai, ["window_id", "experiment_group", "session_id"]].merge(labels, on="window_id")
            status = merged[f"{target}_status"]
            pos = set(merged.window_id[status.eq(POS)])
            union = pos | default_pos
            rows.append({"positive_quantile": q_pos, "negative_quantile": q_neg,
                         "positive": int(status.eq(POS).sum()), "negative": int(status.eq(NEG).sum()),
                         "abstain": int(status.eq(ABSTAIN).sum()),
                         "positive_groups": int(merged.loc[status.eq(POS), "experiment_group"].nunique()),
                         "positive_sessions": int(merged.loc[status.eq(POS), "session_id"].nunique()),
                         "jaccard_vs_default_positive_set": (len(pos & default_pos) / len(union)) if union else None})
        results[target] = rows
    return results


def threshold_stability(calibrations: list[dict]) -> dict:
    out = {}
    for target in ("RELATIVE_HIGH_ROLL", "AMPLITUDE_GROWTH"):
        values = {k: [c["domains"]["hohai"][target][k] for c in calibrations]
                  for k in ("positive_threshold", "negative_threshold")}
        out[target] = {k: {"min": float(np.min(v)), "max": float(np.max(v)), "median": float(np.median(v)),
                           "per_fold": [float(x) for x in v]} for k, v in values.items()}
    return out


def assumption_checks(measurements: pd.DataFrame) -> dict:
    """Kiểm tra giả định độc lập của kiểm định xu hướng trên std 20 s (lý do không dùng p-value)."""
    data = measurements.loc[measurements.angle23_complete & measurements.statistics_valid]
    out = {}
    for dataset, subset in data.groupby("dataset_source"):
        lag1 = subset.sub_std_lag1_autocorr.dropna()
        amp = subset.half_cycle_amplitude_lag1.dropna()
        ratio_gap = (subset.centered_std_ratio - subset.raw_rms_ratio).abs()
        out[dataset] = {"sub_std_lag1_median": float(lag1.median()) if len(lag1) else None,
                        "half_cycle_amplitude_lag1_median": float(amp.median()) if len(amp) else None,
                        "half_cycle_amplitude_lag1_share_above_0_5": float((amp > 0.5).mean()) if len(amp) else None,
                        "median_offset_to_oscillation_ratio": float(subset.offset_to_oscillation_ratio.median()),
                        "max_abs_centered_minus_raw_ratio": float(ratio_gap.max()),
                        "windows_where_centered_ratio_exceeds_raw_by_1_5x": int((subset.centered_std_ratio > 1.5 * subset.raw_rms_ratio).sum())}
    return out


def run(repo_root: Path, spec_path: Path) -> dict:
    repo_root = repo_root.resolve()
    before = _protected(repo_root)
    spec = load_spec(repo_root / spec_path)
    measurements = build_measurements(repo_root, spec)
    oof_labels, calibrations, by_fold = out_of_fold_labels(measurements, spec)
    all_groups = sorted(measurements.loc[measurements.dataset_source.eq("hohai"), "experiment_group"].unique())
    final_calibration = fit_calibration(measurements, all_groups, spec)
    final_labels = apply_rules(measurements, final_calibration, spec)

    calibration_lookup = {c["fold"]: c for c in calibrations}
    test_fold = {g: c["fold"] for c in calibrations for g in c["test_groups"]}
    groups = measurements.set_index("window_id").experiment_group
    oof_labels["calibration_fold"] = oof_labels.window_id.map(groups).map(test_fold).fillna(0).astype(int)
    records = measurements.set_index("window_id", drop=False).to_dict("index")
    oof_labels["supporting_measurements_json"] = [
        supporting_measurements(records[w], calibration_lookup[f])
        for w, f in zip(oof_labels.window_id, oof_labels.calibration_fold)]

    output = repo_root / spec["paths"]["output_root"]
    output.mkdir(parents=True, exist_ok=True)
    measurements.to_parquet(output / "measurements.parquet", index=False)
    oof_labels.to_parquet(output / "proxy_labels_oof.parquet", index=False)
    by_fold.to_parquet(output / "proxy_labels_by_fold.parquet", index=False)
    final_labels.to_parquet(output / "proxy_labels_final_calibration.parquet", index=False)
    (output / "calibrations.json").write_text(json.dumps({"folds": calibrations, "final_all_hohai_groups": final_calibration},
                                                         indent=1, default=float), encoding="utf-8")

    hohai_sessions = sorted(measurements.loc[measurements.dataset_source.eq("hohai"), "session_id"].unique())
    xcorr = session_cross_correlation(repo_root / spec["paths"]["processed_root"], hohai_sessions)
    xcorr.to_csv(output / "hohai_session_xcorr.csv", index=False)
    summary = {
        "rule_version": spec["rule_version"], "spec_path": spec_path.as_posix(), "spec_sha256": spec_sha256(repo_root / spec_path),
        "output_root": spec["paths"]["output_root"],
        "inventory": {"windows_total": int(len(measurements)), "angle23_complete": int(measurements.angle23_complete.sum()),
                      "statistics_valid_and_complete": int((measurements.angle23_complete & measurements.statistics_valid).sum()),
                      "sessions_with_complete_windows": int(measurements.loc[measurements.angle23_complete, ["dataset_source", "session_id"]].drop_duplicates().shape[0]),
                      "experiment_groups_with_complete_windows": int(measurements.loc[measurements.angle23_complete, "experiment_group"].nunique())},
        "grouping_evidence": {
            "same_condition_max_abs_xcorr": xcorr.loc[xcorr.same_condition, "max_abs_xcorr"].describe().to_dict(),
            "different_condition_max_abs_xcorr": xcorr.loc[~xcorr.same_condition, "max_abs_xcorr"].describe().to_dict(),
            "same_condition_different_berth_max_abs_xcorr": xcorr.loc[xcorr.same_condition & ~xcorr.same_berth, "max_abs_xcorr"].describe().to_dict()},
        "distribution_oof": distribution(measurements, oof_labels.drop(columns=["supporting_measurements_json", "calibration_fold"])),
        "readiness": readiness(measurements, oof_labels, spec),
        "sensitivity": sensitivity(measurements, spec, oof_labels),
        "threshold_stability": threshold_stability(calibrations),
        "final_calibration": final_calibration,
        "assumption_checks": assumption_checks(measurements),
    }
    after = _protected(repo_root)
    if after != before:
        raise RuntimeError("Tệp human-review/verified/AI bị thay đổi trong khi dựng proxy dataset; dừng lại.")
    summary["protected_files_unchanged"] = True
    summary["protected_files"] = {k: v[:16] for k, v in after.items()}
    (repo_root / SUMMARY_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / SUMMARY_PATH).write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    (output / "proxy_dataset_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Dựng proxy-label dataset v1 (PoC, không phải ground truth).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--spec", type=Path, default=Path("ml/labeling/proxy_spec.yaml"))
    args = parser.parse_args()
    summary = run(args.repo_root, args.spec)
    print(json.dumps({"inventory": summary["inventory"],
                      "readiness": {d: {t: v["decision"] for t, v in r["targets"].items()} for d, r in summary["readiness"].items()}},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
