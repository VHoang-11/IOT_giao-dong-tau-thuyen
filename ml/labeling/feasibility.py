from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .schemas import ANGLE_ONLY_23, FEATURE_STATUS_VALUES


def load_eligible_windows(feature_root: Path, datasets: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    result = {}
    required_meta = {"window_id", "dataset_source", "session_id", "segment_id", "window_end_seconds", "validity_json"}
    for dataset in datasets:
        value_path = feature_root / dataset / "feature_values.parquet"
        meta_path = feature_root / dataset / "feature_metadata.parquet"
        if not value_path.is_file() or not meta_path.is_file():
            raise FileNotFoundError(f"Thiếu feature parquet cho {dataset}: {value_path} / {meta_path}")
        values = pd.read_parquet(value_path)
        metadata = pd.read_parquet(meta_path)
        if not required_meta.issubset(metadata.columns):
            raise ValueError(f"Schema metadata feature không đủ cột cho {dataset}.")
        missing_features = [name for name in ANGLE_ONLY_23 if name not in values.columns]
        if missing_features:
            raise ValueError(f"Thiếu feature thuộc baseline angle-only: {missing_features}")
        frame = metadata.merge(values, on="window_id", validate="one_to_one")
        if not frame["dataset_source"].eq(dataset).all():
            raise ValueError(f"dataset_source không khớp thư mục {dataset}.")
        parsed = [json.loads(item) for item in frame["validity_json"]]
        frame["_angle23_valid"] = [all(item.get(name, {}).get("status") == "VALID" for name in ANGLE_ONLY_23)
                                   for item in parsed]
        frame["_status_json"] = [json.dumps({name: item.get(name, {}).get("status", "INVALID_INPUT")
                                             for name in ANGLE_ONLY_23}, sort_keys=True)
                                 for item in parsed]
        eligible = frame.loc[frame["_angle23_valid"]].copy()
        eligible["window_start_seconds"] = eligible["window_end_seconds"].astype(float) - 180.0
        eligible = eligible.sort_values(["session_id", "segment_id", "window_end_seconds"], kind="stable")
        result[dataset] = eligible.reset_index(drop=True)
    return result


def feasibility_summary(dataset: str, eligible: pd.DataFrame, all_feature_rows: int,
                        session_feature_rows: pd.DataFrame) -> dict:
    sessions = sorted(eligible["session_id"].astype(str).unique().tolist())
    def stats(column: str) -> dict:
        values = pd.to_numeric(eligible[column], errors="coerce").to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if not len(values):
            return {key: None for key in ("mean", "std_population", "min", "p05", "p50", "p95", "max")}
        return {"mean": float(np.mean(values)), "std_population": float(np.std(values, ddof=0)),
                "min": float(np.min(values)), "p05": float(np.quantile(values, .05)),
                "p50": float(np.quantile(values, .5)), "p95": float(np.quantile(values, .95)),
                "max": float(np.max(values))}
    per_session = []
    for session, group in eligible.groupby("session_id", sort=True):
        per_session.append({"session_id": str(session), "eligible_windows": int(len(group)),
                            "segments": int(group["segment_id"].nunique()),
                            "roll_std_60_p50_deg": float(group["roll_std_60"].median()),
                            "abs_roll_mean_180_p50_deg": float(group["roll_mean_180"].abs().median()),
                            "roll_rms_slope_180_p50_deg_per_min": float(group["roll_rms_slope_180"].median())})
    # Feature table includes only 60s endpoints; distinguish row count from 180s eligible windows.
    return {"dataset_source": dataset, "feature_candidate_rows_60s": int(all_feature_rows),
            "eligible_windows_180s_angle23": int(len(eligible)), "sessions_with_eligible_windows": len(sessions),
            "session_ids": sessions, "segment_count": int(eligible["segment_id"].nunique()),
            "overlapping_stride_seconds": 10, "window_seconds": 180,
            "feature_validity_values": list(FEATURE_STATUS_VALUES),
            "metrics": {"roll_mean_180_deg": stats("roll_mean_180"),
                        "roll_rms_60_deg": stats("roll_rms_60"),
                        "roll_std_60_deg": stats("roll_std_60"),
                        "roll_peak_to_peak_60_deg": stats("roll_peak_to_peak_60"),
                        "roll_abs_p95_60_deg": stats("roll_abs_p95_60"),
                        "roll_rms_slope_180_deg_per_min": stats("roll_rms_slope_180"),
                        "roll_rms_trend_r2_180": stats("roll_rms_trend_r2_180"),
                        "pitch_rms_60_deg": stats("pitch_rms_60")},
            "per_session": per_session,
            "class_evidence": {name: {"credible_labeled_windows": 0, "supporting_sessions": 0,
                                      "status": "NOT_ESTABLISHED"}
                               for name in ("NORMAL", "HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")},
            "ground_truth_annotations_found": 0, "human_review_decisions": 0,
            "note_vi": "Cửa sổ chồng lấn; số lượng cửa sổ không phải số quan sát độc lập. Không có ngưỡng được phê duyệt để biến thống kê mô tả thành nhãn."}


def source_evidence_notes() -> dict:
    return {
        "seafar": ["Nguồn tàu thực; audit không ghi nhận event/ground-truth annotation.",
                   "Roll có offset trung bình dương; không lấy zero-centered làm NORMAL.",
                   "Chỉ một session, nhiều segment do timestamp trùng/gap; không có xác nhận sự kiện vận hành."],
        "hohai": ["21 sheet là 21 session thực nghiệm riêng; roll/pitch degree, sample rate 50 Hz theo tài liệu được cung cấp.",
                  "Không có gyro đo trực tiếp và workbook không có timestamp để kiểm tra dropout.",
                  "Tên loại/thử nghiệm không được coi là nhãn nguy hiểm; PDF nguồn đã được báo cáo là không parse được trong audit."],
        "southampton": ["Dữ liệu mô hình KCS quy mô phòng thí nghiệm; Test Plan là ngữ cảnh sóng/thử nghiệm, không phải hazard label.",
                        "47 IMU runs, chỉ Run 14 đủ 180 giây theo audit.",
                        "Điều kiện tần số/biên độ sóng không được chuyển trực tiếp thành nhãn; không ghép IMU với Lasso.",
                        "Không có human review hoặc reference label được cung cấp."],
    }
