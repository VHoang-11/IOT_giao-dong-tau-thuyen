from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow
import scipy
import yaml

from . import __version__
from .diagnostics import create_feature_figures
from .extractor import FeatureInputError, extract_segment, validate_segment
from .io import load_config, relative_path, write_json
from .reporting import build_reports
from .spec import FEATURE_NAMES, PRACTICAL_SUBSETS, VALIDITY_STATUSES
from .stability import run_filter_sensitivity


DATASETS = ("seafar", "hohai", "southampton")


def _run_tests(repo_root: Path) -> dict:
    command = [sys.executable, "-m", "pytest", "ml/features/tests", "-q"]
    process = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    output = (process.stdout + process.stderr).strip()
    print(output)
    import re
    matches = {key: int(re.search(rf"(\d+) {key}", output).group(1)) if re.search(rf"(\d+) {key}", output) else 0
               for key in ("passed", "failed", "skipped", "error", "xfailed", "xpassed")}
    return {"command": "python -m pytest ml/features/tests -q",
        "total": sum(matches.values()), "passed": matches["passed"],
        "failed": matches["failed"] + matches["error"], "skipped": matches["skipped"],
        "exit_code": int(process.returncode),
        "result_summary": output.splitlines()[-1] if output else "Không có output từ pytest."}


def _read_provenance(path: Path) -> dict:
    provenance_path = path.with_name("provenance.json")
    if not provenance_path.exists():
        raise FeatureInputError(f"Không tìm thấy provenance cạnh Parquet: {provenance_path}")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if not isinstance(provenance, dict):
        raise FeatureInputError(f"Provenance không phải object JSON: {provenance_path}")
    return provenance


def _aggregate_dataset(dataset: str, frames: list[pd.DataFrame], metadata_frames: list[pd.DataFrame],
                       segment_summaries: list[dict], elapsed: float, peak_memory_mb: float,
                       output_root: Path, repo_root: Path, settings: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame, list[dict]]:
    values = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["window_id", *FEATURE_NAMES])
    metadata = pd.concat(metadata_frames, ignore_index=True) if metadata_frames else pd.DataFrame()
    validity_records = [json.loads(value) for value in metadata.get("validity_json", [])]
    status_counts = {feature: {status: 0 for status in VALIDITY_STATUSES} for feature in FEATURE_NAMES}
    for validity in validity_records:
        for feature in FEATURE_NAMES:
            status_counts[feature][validity[feature]["status"]] += 1
    rows_any_valid = 0
    invalid_input_rows = 0
    complete_rows = 0
    partial_rows = 0
    subset_counts = {name: 0 for name in PRACTICAL_SUBSETS}
    for validity in validity_records:
        statuses = {feature: validity[feature]["status"] for feature in FEATURE_NAMES}
        valid_names = {feature for feature, status in statuses.items() if status == "VALID"}
        rows_any_valid += bool(valid_names)
        invalid_input_rows += any(status == "INVALID_INPUT" for status in statuses.values())
        complete = len(valid_names) == len(FEATURE_NAMES)
        complete_rows += complete
        partial_rows += bool(valid_names) and not complete
        for subset, feature_names in PRACTICAL_SUBSETS.items():
            subset_counts[subset] += all(statuses[name] == "VALID" for name in feature_names)

    statistics = {}
    for feature in FEATURE_NAMES:
        series = pd.to_numeric(values.get(feature, pd.Series(dtype=float)), errors="coerce").to_numpy(dtype=np.float64)
        finite = series[np.isfinite(series)]
        if len(finite):
            statistics[feature] = {"valid_count": int(len(finite)), "mean": float(np.mean(finite)),
                "std_population": float(np.std(finite, ddof=0)), "min": float(np.min(finite)),
                "max": float(np.max(finite)), "p05": float(np.quantile(finite, .05, method="linear")),
                "p50": float(np.quantile(finite, .50, method="linear")),
                "p95": float(np.quantile(finite, .95, method="linear"))}
        else:
            statistics[feature] = {"valid_count": 0, "mean": None, "std_population": None,
                "min": None, "max": None, "p05": None, "p50": None, "p95": None}
    result = {
        "dataset_source": dataset,
        "segments": len(segment_summaries),
        "sessions": len({item["session_id"] for item in segment_summaries}),
        "candidate_windows_60s": int(len(values)),
        "candidate_windows_180s": int(sum(item["candidate_windows_180s"] for item in segment_summaries)),
        "rows_with_any_valid_feature": int(rows_any_valid),
        "partial_validity_rows": int(partial_rows),
        "complete_30_feature_rows": int(complete_rows),
        "invalid_input_rows": int(invalid_input_rows),
        "complete_practical_subsets": {name: int(count) for name, count in subset_counts.items()},
        "feature_status_counts": status_counts,
        "feature_statistics": statistics,
        "elapsed_seconds": float(elapsed),
        "peak_traced_python_memory_mb": float(peak_memory_mb),
        "memory_measurement_note_vi": "Tracemalloc đo peak cấp phát Python; không đảm bảo bao gồm đầy đủ native buffer của NumPy/Arrow.",
        "feature_values_path": relative_path(output_root / dataset / "feature_values.parquet", repo_root),
        "feature_metadata_path": relative_path(output_root / dataset / "feature_metadata.parquet", repo_root),
        "feature_column_order": list(FEATURE_NAMES),
        "source_gyro_status": settings["source_gyro_status"].get(dataset, "MISSING_SOURCE_SIGNAL"),
    }
    return result, values, metadata, validity_records


def _clean_output_dataset(feature_root: Path, dataset: str, repo_root: Path) -> Path:
    target = (feature_root / dataset).resolve()
    base = feature_root.resolve()
    if base not in target.parents or repo_root.resolve() not in base.parents:
        raise ValueError("Đường dẫn feature output không nằm an toàn dưới repository feature root.")
    if target.exists():
        import shutil
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def run_pipeline(config_path: Path, dataset: str = "all", dry_run: bool = False,
                 skip_stability: bool = False) -> dict:
    config, repo_root = load_config(config_path)
    datasets = DATASETS if dataset == "all" else (dataset,)
    processed_root = config["paths"]["processed_root"]
    feature_root = config["paths"]["feature_root"]
    report_root = config["paths"]["report_root"]
    settings = config["features"]
    for name in datasets:
        if not (processed_root / name).is_dir():
            raise FileNotFoundError(f"Không tìm thấy processed dataset: {processed_root / name}")

    if dry_run:
        validation = {}
        for name in datasets:
            paths = sorted((processed_root / name).glob("**/timeseries.parquet"))
            segment_rows = []
            for path in paths:
                frame = pd.read_parquet(path)
                provenance = _read_provenance(path)
                source, session, segment, times = validate_segment(frame, name)
                segment_rows.append({"session_id": session, "segment_id": segment,
                    "rows": len(frame), "start_seconds": float(times[0]), "end_seconds": float(times[-1]),
                    "effective_sampling_hz": provenance.get("target_sampling_hz_effective")})
            validation[name] = {"segments": len(segment_rows), "rows": sum(x["rows"] for x in segment_rows),
                                "segment_checks": segment_rows}
        print(f"[THÔNG TIN] Kiểm tra schema hoàn tất: {sum(x['segments'] for x in validation.values())} segment; chưa ghi feature.")
        return {"dry_run": True, "datasets": validation}

    dataset_summaries = {}
    values_by_dataset = {}
    validity_by_dataset = {}
    for name in datasets:
        print(f"[THÔNG TIN] Đang trích xuất candidate features: {name}...")
        output_dir = _clean_output_dataset(feature_root, name, repo_root)
        paths = sorted((processed_root / name).glob("**/timeseries.parquet"))
        if not paths:
            raise FileNotFoundError(f"Không có timeseries.parquet trong {processed_root / name}")
        frames: list[pd.DataFrame] = []
        metadata_frames: list[pd.DataFrame] = []
        segment_summaries = []
        tracemalloc.start()
        before_current, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        started = time.perf_counter()
        for path in paths:
            frame = pd.read_parquet(path)
            provenance = _read_provenance(path)
            value_frame, metadata_frame, segment_summary = extract_segment(frame, provenance, settings, name)
            frames.append(value_frame)
            metadata_frames.append(metadata_frame)
            segment_summaries.append(segment_summary)
        elapsed = time.perf_counter() - started
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = max(0.0, peak - before_current) / (1024 * 1024)
        dataset_summary, value_table, metadata_table, validity_records = _aggregate_dataset(
            name, frames, metadata_frames, segment_summaries, elapsed, peak_mb,
            feature_root, repo_root, settings)
        # IDs are the join key; only candidate feature columns appear in the model-value table.
        value_table.to_parquet(output_dir / "feature_values.parquet", index=False,
                               compression=config["output"]["compression"], engine="pyarrow")
        metadata_table.to_parquet(output_dir / "feature_metadata.parquet", index=False,
                                  compression=config["output"]["compression"], engine="pyarrow")
        dataset_summaries[name] = dataset_summary
        values_by_dataset[name] = value_table
        validity_by_dataset[name] = validity_records
        print(f"[THÔNG TIN] {name}: {len(value_table):,} candidate rows; {dataset_summary['complete_30_feature_rows']:,} complete 30-feature rows.")

    stability = {}
    if config["stability"]["run"] and not skip_stability and set(datasets) == set(DATASETS):
        stability = run_filter_sensitivity(repo_root, feature_root, processed_root,
                                           settings, config["stability"])
    else:
        for name in datasets:
            stability[name] = {"status": "SKIPPED", "reason_vi": "Sensitivity study không được chạy theo tùy chọn CLI."}

    figure_records = create_feature_figures(values_by_dataset, validity_by_dataset,
        feature_root / "diagnostics", int(config["output"]["plot_dpi"]))
    for item in figure_records:
        item["path"] = relative_path(item["path"], repo_root)

    test_results = _run_tests(repo_root)
    versions = {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "pyarrow": pyarrow.__version__,
                "scipy": scipy.__version__, "pyyaml": yaml.__version__}
    summary = {
        "feature_extractor_version": __version__,
        "feature_spec_status": "CANDIDATE_OPERATIONAL_DEFINITIONS_PENDING_TEAM_APPROVAL",
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": ".", "configuration_path": relative_path(config_path.resolve(), repo_root),
        "configuration": settings, "environment": versions,
        "cli_command": "python -m ml.features.run --config ml/features/config.yaml --dataset all",
        "test_results": test_results,
        "datasets": dataset_summaries,
        "filter_stability": stability,
        "figures": figure_records,
        "feature_names_in_exact_order": list(FEATURE_NAMES),
        "metadata_excluded_from_feature_vector": ["window_id", "dataset_source", "session_id", "segment_id", "window_end_seconds", "validity_json", "source_metadata_json"],
        "scope": "feature extraction and validation only; no labels, no Random Forest, no C contract changes",
    }
    write_json(report_root / "feature_extraction_summary.json", summary)
    build_reports(summary, report_root)
    print(f"[THÔNG TIN] Hoàn tất trích xuất. Báo cáo: {report_root / 'feature_extraction_results.md'}")
    if test_results["exit_code"] != 0:
        raise RuntimeError("Feature tests thất bại; xem output pytest ở trên.")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trích xuất 30 candidate features SVMG từ Parquet processed.")
    parser.add_argument("--config", type=Path, default=Path("ml/features/config.yaml"), help="Cấu hình feature YAML.")
    parser.add_argument("--dataset", choices=["all", *DATASETS], default="all", help="Nguồn cần xử lý.")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra schema và metadata, không ghi feature.")
    parser.add_argument("--skip-stability", action="store_true", help="Bỏ so sánh cutoff thay thế.")
    args = parser.parse_args(argv)
    try:
        run_pipeline(args.config, args.dataset, args.dry_run, args.skip_stability)
    except Exception as error:
        print(f"[LỖI] Trích xuất feature dừng: {error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
