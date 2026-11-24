from __future__ import annotations

import math
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from ml.preprocessing.config import load_config as load_preprocessing_config
from ml.preprocessing.hohai import load_sessions as load_hohai
from ml.preprocessing.seafar import load_sessions as load_seafar
from ml.preprocessing.signal_processing import process_session
from ml.preprocessing.southampton import load_sessions as load_southampton

from .extractor import extract_segment
from .spec import FEATURE_NAMES


RAW_LOADERS = {"seafar": load_seafar, "hohai": load_hohai, "southampton": load_southampton}


def _pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 2 or np.std(left) == 0.0 or np.std(right) == 0.0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def run_filter_sensitivity(repo_root: Path, feature_root: Path, processed_root: Path,
                           feature_settings: dict, stability_settings: dict) -> dict:
    """Đối chiếu baseline với cutoff thay thế trong RAM; không ghi đè Parquet production."""
    output = {}
    pp_config = load_preprocessing_config(repo_root / "ml/preprocessing/config.yaml")
    baseline_pp_settings = pp_config["preprocessing"]
    alternative = dict(baseline_pp_settings)
    alternative["anti_alias_cutoff_hz"] = float(stability_settings["alternative_cutoff_hz"])

    for dataset in ("seafar", "hohai", "southampton"):
        parquet_files = sorted((processed_root / dataset).glob("**/timeseries.parquet"))
        if not parquet_files:
            output[dataset] = {"status": "NO_PROCESSED_SEGMENTS"}
            continue
        selected_path = max(parquet_files, key=lambda path: pq.ParquetFile(path).metadata.num_rows)
        baseline_frame = pd.read_parquet(selected_path)
        session_id = str(baseline_frame["session_id"].iloc[0])
        segment_id = str(baseline_frame["segment_id"].iloc[0])
        baseline_provenance = json.loads(selected_path.with_name("provenance.json").read_text(encoding="utf-8"))
        original_rate = baseline_provenance.get("original_sampling_hz")
        original_rate = float(original_rate) if original_rate is not None else 0.0
        if dataset == "seafar" or original_rate <= feature_settings["target_sampling_hz"]:
            output[dataset] = {"status": "NOT_APPLICABLE_NO_50_TO_10_FILTER",
                "session_id": session_id, "segment_id": segment_id,
                "original_sampling_hz": original_rate,
                "reason_vi": "Tần số nguồn không cao hơn tần số đích; không có bước giảm mẫu 50 xuống 10 Hz để so sánh cutoff."}
            continue

        raw_sessions = RAW_LOADERS[dataset](repo_root / "ml/data/raw")
        raw_session = next(session for session in raw_sessions if session.session_id == session_id)
        alternative_segments, _ = process_session(raw_session, alternative, repo_root)
        alternative_segment = next(item for item in alternative_segments if item.segment_id == segment_id)
        alternative_values, alternative_metadata, _ = extract_segment(
            alternative_segment.frame, alternative_segment.provenance, feature_settings, dataset)
        baseline_values_path = feature_root / dataset / "feature_values.parquet"
        baseline_meta_path = feature_root / dataset / "feature_metadata.parquet"
        baseline_values = pd.read_parquet(baseline_values_path)
        baseline_meta = pd.read_parquet(baseline_meta_path)
        selected_meta = baseline_meta[(baseline_meta.session_id == session_id)
                                      & (baseline_meta.segment_id == segment_id)].copy()
        selected_values = selected_meta[["window_id", "window_end_seconds", "validity_json"]].merge(
            baseline_values, on="window_id", how="inner", validate="one_to_one")
        alt_meta = alternative_metadata[["window_id", "window_end_seconds", "validity_json"]].copy()
        alt_values = alternative_values.copy()
        alt_join = alt_meta.merge(alt_values, on="window_id", how="inner", validate="one_to_one")
        selected_values["window_key"] = selected_values["window_end_seconds"].round(6)
        alt_join["window_key"] = alt_join["window_end_seconds"].round(6)
        joined = selected_values.merge(alt_join, on="window_key", suffixes=("_baseline", "_alternative"),
                                       how="inner", validate="one_to_one")
        feature_results = {}
        for feature in FEATURE_NAMES:
            pairs = []
            for _, row in joined.iterrows():
                base_status = json.loads(row["validity_json_baseline"])[feature]["status"]
                alt_status = json.loads(row["validity_json_alternative"])[feature]["status"]
                base_value = row.get(f"{feature}_baseline")
                alt_value = row.get(f"{feature}_alternative")
                if base_status == "VALID" and alt_status == "VALID" and pd.notna(base_value) and pd.notna(alt_value):
                    pairs.append((float(base_value), float(alt_value)))
            if not pairs:
                feature_results[feature] = {"matched_valid_windows": 0, "mean_absolute_difference": None,
                    "max_absolute_difference": None, "mean_relative_difference_percent": None,
                    "correlation": None, "mean_normalized_absolute_difference": None}
                continue
            base = np.asarray([pair[0] for pair in pairs], dtype=float)
            alt = np.asarray([pair[1] for pair in pairs], dtype=float)
            difference = np.abs(alt - base)
            relative = difference[np.abs(base) > 1e-12] / np.abs(base[np.abs(base) > 1e-12]) * 100.0
            denominator = float(np.median(np.abs(base)))
            feature_results[feature] = {
                "matched_valid_windows": int(len(pairs)),
                "mean_absolute_difference": float(np.mean(difference)),
                "max_absolute_difference": float(np.max(difference)),
                "mean_relative_difference_percent": float(np.mean(relative)) if len(relative) else None,
                "correlation": _pearson(base, alt),
                "mean_normalized_absolute_difference": float(np.mean(difference) / max(denominator, 1e-12)),
            }
        ranking = sorted(
            ((name, value["mean_normalized_absolute_difference"])
             for name, value in feature_results.items() if value["mean_normalized_absolute_difference"] is not None),
            key=lambda item: item[1], reverse=True)
        output[dataset] = {
            "status": "COMPARED",
            "representative_session_id": session_id,
            "representative_segment_id": segment_id,
            "raw_reference": _repository_reference(raw_session.raw_reference, repo_root),
            "baseline_cutoff_hz": float(baseline_pp_settings["anti_alias_cutoff_hz"]),
            "alternative_cutoff_hz": float(alternative["anti_alias_cutoff_hz"]),
            "original_sampling_hz": original_rate,
            "baseline_sampling_hz": float(feature_settings["target_sampling_hz"]),
            "matched_windows": int(len(joined)),
            "features": feature_results,
            "most_sensitive_features_by_normalized_difference": ranking[:10],
            "experiment_storage": "in-memory only; không ghi đè artifact baseline",
        }
    return output


def json_value(path: Path, key: str, default):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get(key, default)


def _repository_reference(reference: str, repo_root: Path) -> str:
    """Giữ nguồn raw ở dạng đường dẫn tương đối, kể cả Hohai có hậu tố sheet."""
    raw_path, separator, suffix = reference.partition("::")
    try:
        relative = Path(raw_path).resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        relative = Path(raw_path).name
    return relative + (separator + suffix if separator else "")
