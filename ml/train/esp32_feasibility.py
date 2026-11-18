"""Phân tích khả thi ESP32 cho schema 23 angle feature (đề xuất cho M1; KHÔNG sửa contract/firmware).

Chạy từ repository root sau ``ml.train.rf_poc``::

    python -m ml.train.esp32_feasibility

Ghi ``ml/docs/feature_contract_23_v0.1.json`` (đề xuất contract, máy đọc được) và
``ml/reports/ml/esp32_feasibility.json`` (ước lượng + thí nghiệm mô phỏng chuỗi lọc firmware hiện tại).
Mọi con số RAM/flash/latency ở đây là ƯỚC LƯỢNG trên desktop, chưa đo trên thiết bị.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal

from ml.features.calculations import population_std
from ml.labeling.human_review_workflow import ANGLE_FEATURES

CONTRACT_PATH = Path("ml/docs/feature_contract_23_v0.1.json")
OUTPUT_PATH = Path("ml/reports/ml/esp32_feasibility.json")
FS = 10.0

# (spec_id trong feature_specification_30.md, tín hiệu, cửa sổ s, đơn vị, định nghĩa ngắn, chiến lược nhúng)
CONTRACT = {
    "roll_rms_60": (0, "roll", 60, "deg", "sqrt(mean(x^2)) trên (t-60,t]", "O(1) tổng bình phương trượt"),
    "roll_std_60": (1, "roll", 60, "deg", "độ lệch chuẩn quần thể (mẫu số n)", "O(1) moment trượt ổn định"),
    "roll_mean_60": (2, "roll", 60, "deg", "mean(x)", "O(1) tổng trượt"),
    "roll_peak_to_peak_60": (3, "roll", 60, "deg", "max(x)-min(x)", "O(1) khấu hao bằng deque đơn điệu"),
    "roll_abs_p95_60": (4, "roll", 60, "deg", "phân vị Type-7 0.95 của |x|", "sắp xếp 600 phần tử/lần cập nhật"),
    "roll_abs_max_60": (5, "roll", 60, "deg", "max(|x|)", "O(1) khấu hao bằng deque"),
    "roll_iqr_60": (6, "roll", 60, "deg", "Q0.75-Q0.25 Type-7", "sắp xếp 600 phần tử"),
    "roll_diff_rms_60": (7, "roll", 60, "deg/sample @10 Hz", "RMS sai phân bậc 1 giữa mẫu kề đúng chu kỳ 0.1 s", "O(1); PHỤ THUỘC tần số lấy mẫu"),
    "roll_mean_180": (11, "roll", 180, "deg", "mean(x)", "O(1) tổng trượt"),
    "roll_median_180": (12, "roll", 180, "deg", "Q0.50 Type-7", "sắp xếp 1800 phần tử"),
    "roll_mean_abs_180": (13, "roll", 180, "deg", "mean(|x|)", "O(1) tổng trượt"),
    "roll_dominant_sign_ratio_180": (14, "roll", 180, "1", "max(n+,n-)/(n++n-), bỏ số 0 tuyệt đối", "O(1) bộ đếm dấu"),
    "roll_segment_mean_std_180": (15, "roll", 180, "deg", "std quần thể của 3 mean block 60 s", "O(1) sau tổng block"),
    "roll_mean_shift_180": (16, "roll", 180, "deg", "mean(block 3) - mean(block 1)", "O(1) sau tổng block"),
    "roll_rms_early_60": (17, "roll", 180, "deg", "RMS block 60 s cũ nhất", "O(1) sau tổng block"),
    "roll_rms_late_60": (18, "roll", 180, "deg", "RMS block 60 s mới nhất (trùng số học với roll_rms_60)", "O(1)"),
    "roll_rms_ratio_180": (19, "roll", 180, "1", "rms_late/rms_early; không xác định nếu rms_early <= 1e-9", "O(1)"),
    "roll_rms_slope_180": (20, "roll", 180, "deg/min", "độ dốc OLS của 3 RMS block theo tâm [30,90,150] s, x60", "O(1)"),
    "roll_rms_trend_r2_180": (21, "roll", 180, "1", "R^2 của hồi quy 3 điểm; không xác định nếu SST=0", "O(1)"),
    "roll_p95_trend_slope_180": (22, "roll", 180, "deg/min", "độ dốc OLS của P95|x| 3 block, x60", "sắp xếp 3x600 phần tử"),
    "pitch_rms_60": (26, "pitch", 60, "deg", "sqrt(mean(p^2))", "O(1)"),
    "pitch_std_60": (27, "pitch", 60, "deg", "độ lệch chuẩn quần thể", "O(1)"),
    "pitch_peak_to_peak_60": (28, "pitch", 60, "deg", "max(p)-min(p)", "O(1) deque"),
}


def build_contract() -> dict:
    if tuple(CONTRACT) != tuple(ANGLE_FEATURES):
        raise AssertionError("Thứ tự contract đề xuất phải trùng ANGLE_FEATURES.")
    return {
        "contract_id": "svmg-angle23", "version": "0.1.0-proposal", "status": "PROPOSAL_PENDING_M1_REVIEW",
        "supersedes": None, "legacy_contract_untouched": ["contracts/features.md", "core/include/svmg_core.h",
                                                          "core/include/svmg_features.h"],
        "source_of_truth_formulas": "ml/docs/feature_specification_30.md + ml/features/extractor.py (feature_extractor_version 0.1.0)",
        "sampling_hz": FS, "endpoint_convention": "(t-W, t]", "update_stride_seconds": 10.0,
        "window_seconds": [60, 180], "blocks_180": "3 block 60 s không chồng lấn, cũ -> mới, (lower, upper]",
        "minimum_valid_fraction": 0.95, "maximum_gap_factor": 1.5, "dtype": "float32 trên ESP32; tham chiếu float64 Python",
        "invalid_policy": "Không thay bằng 0; mỗi feature có cờ validity; vector thiếu -> ABSTAIN/UNKNOWN, không NORMAL",
        "features": [{"index": i, "name": name, "spec_id": spec[0], "signal": spec[1], "window_seconds": spec[2],
                      "unit": spec[3], "definition": spec[4], "embedded_strategy": spec[5]}
                     for i, (name, spec) in enumerate(CONTRACT.items())],
        "parity_tolerance_proposal": {"absolute_deg": 1e-3, "relative": 1e-4,
                                      "note": "Đề xuất ban đầu cho float32 vs float64; cần M1/M2 chốt sau khi chạy golden vectors."},
    }


def memory_estimate(model_cards: dict) -> dict:
    roll_ring = int(180 * FS * 4)
    pitch_ring = int(60 * FS * 4)
    valid_bits = int(math.ceil(180 * FS / 8) + math.ceil(60 * FS / 8))
    scratch = int(180 * FS * 4)
    outputs = 23 * 4 + 23
    total = roll_ring + pitch_ring + valid_bits + scratch + outputs
    sort_ops = 180 * FS * math.log2(180 * FS) + 5 * 60 * FS * math.log2(60 * FS)
    models = {}
    for target, card in model_cards.items():
        stats = card["tree_statistics"]
        models[target] = {"estimated_c_array_bytes": stats["estimated_c_array_bytes"],
                          "total_nodes": stats["total_nodes"], "n_estimators": stats["n_estimators"],
                          "max_depth": stats["max_depth"],
                          "mean_comparisons_per_inference": stats["mean_comparisons_per_inference"],
                          "max_comparisons_per_inference": stats["max_comparisons_per_inference"],
                          "latency_estimate_us_at_240MHz_20_cycles_per_comparison":
                              stats["max_comparisons_per_inference"] * 20 / 240.0}
    return {"feature_ram_bytes": {"roll_ring_180s_float32": roll_ring, "pitch_ring_60s_float32": pitch_ring,
                                  "validity_bits": valid_bits, "quantile_scratch_1800_float32": scratch,
                                  "outputs_and_flags": outputs, "total": total},
            "existing_core_engine_bytes_documented": 3336, "free_ram_documented_bytes_approx": 270000,
            "flash_budget_documented_bytes_approx": 1900000,
            "documented_source": "firmware/docs/M1-08_resource_table.md (đo với stub, ngày 12/11/2026)",
            "sort_comparisons_per_update_estimate": int(sort_ops),
            "models": models,
            "status": "ESTIMATE_NOT_MEASURED_ON_DEVICE"}


def firmware_chain_emulation(repo_root: Path, measurements: pd.DataFrame, calibration: dict) -> dict:
    """Ước lượng ảnh hưởng của chuỗi hiện tại (Butterworth bậc 2 fc=0.5 Hz, ra 2 Hz) lên roll_std_60 Hohai.

    Xấp xỉ: lọc trên tín hiệu 10 Hz đã xử lý (firmware lọc ở 20 Hz trước khi giảm mẫu), không mô phỏng gia tốc kế.
    """
    sos = signal.butter(2, 0.5, btype="low", fs=FS, output="sos")
    thresholds = calibration["domains"]["hohai"]["RELATIVE_HIGH_ROLL"]
    rows = []
    hohai = measurements.loc[measurements.dataset_source.eq("hohai") & measurements.angle23_complete]
    for session, group in hohai.groupby("session_id"):
        frame = pd.read_parquet(repo_root / "ml/data/processed/hohai" / session / "segment_000" / "timeseries.parquet",
                                columns=["time_seconds", "roll_deg"])
        t, x = frame.time_seconds.to_numpy(float), frame.roll_deg.to_numpy(float)
        zi = signal.sosfilt_zi(sos) * x[0]
        y, _ = signal.sosfilt(sos, x, zi=zi)
        decim_t, decim_y = t[4::5], y[4::5]
        for end, original in zip(group.window_end_seconds, group.roll_std_60):
            seg = decim_y[(decim_t > end - 60) & (decim_t <= end)]
            rows.append({"session_id": session, "window_end_seconds": end, "roll_std_60_10hz": original,
                         "roll_std_60_fw_chain_2hz": population_std(seg), "n_2hz": len(seg)})
    table = pd.DataFrame(rows)
    table["ratio"] = table.roll_std_60_fw_chain_2hz / table.roll_std_60_10hz

    def decide(v):
        return np.where(v >= thresholds["positive_threshold"], "POS", np.where(v < thresholds["negative_threshold"], "NEG", "ABSTAIN"))
    original, emulated = decide(table.roll_std_60_10hz), decide(table.roll_std_60_fw_chain_2hz)
    freqs = {"hohai_dominant_roll_hz_approx": 1 / 1.8, "southampton_test_plan_wave_hz": 0.7976,
             "southampton_late_window_roll_hz_approx": 1 / 0.70}
    gains = {k: float(1 / math.sqrt(1 + (f / 0.5) ** 4)) for k, f in freqs.items()}
    return {"windows": int(len(table)), "std_ratio_median": float(table.ratio.median()),
            "std_ratio_p05": float(table.ratio.quantile(0.05)), "std_ratio_p95": float(table.ratio.quantile(0.95)),
            "samples_per_60s_window_2hz": int(table.n_2hz.median()),
            "proxy_decisions_original": pd.Series(original).value_counts().to_dict(),
            "proxy_decisions_emulated": pd.Series(emulated).value_counts().to_dict(),
            "decisions_changed": int((original != emulated).sum()),
            "original_pos_now_not_pos": int(((original == "POS") & (emulated != "POS")).sum()),
            "butterworth2_0p5hz_gain_at": gains, "nyquist_2hz_output_hz": 1.0,
            "approximation": "Lọc 0.5 Hz trên chuỗi 10 Hz rồi lấy mỗi mẫu thứ 5; không mô phỏng bộ lọc bù/gia tốc kế."}


def filtered_feature_model_shift(repo_root: Path, measurements: pd.DataFrame) -> dict:
    """Trích lại đủ 23 feature bằng extractor thật trên Roll/Pitch lọc Butterworth bậc 2 0.5 Hz (giữ 10 Hz)
    rồi dự đoán bằng mô hình cuối. Cô lập ảnh hưởng bộ lọc (không mô phỏng giảm mẫu hay gia tốc kế)."""
    import yaml
    from ml.features.extractor import extract_segment
    from ml.train.predict import load_model, predict_frame
    card_path = repo_root / "ml/data/models/rf_poc_v1/relative_high_roll_model_card.json"
    if not card_path.is_file():
        return {"status": "SKIPPED_NO_MODEL"}
    model, card = load_model(card_path, repo_root)
    settings = yaml.safe_load((repo_root / "ml/features/config.yaml").read_text(encoding="utf-8"))["features"]
    sos = signal.butter(2, 0.5, btype="low", fs=FS, output="sos")
    filtered = []
    for session in sorted(measurements.loc[measurements.dataset_source.eq("hohai"), "session_id"].unique()):
        segment = repo_root / "ml/data/processed/hohai" / session / "segment_000"
        frame = pd.read_parquet(segment / "timeseries.parquet")
        provenance = json.loads((segment / "provenance.json").read_text(encoding="utf-8"))
        for column in ("roll_deg", "pitch_deg"):
            x = frame[column].to_numpy(float)
            frame[column] = signal.sosfilt(sos, x, zi=signal.sosfilt_zi(sos) * x[0])[0]
        values, meta, _ = extract_segment(frame, provenance, settings, "hohai")
        ok = meta.validity_json.map(lambda s: all(json.loads(s)[f]["status"] == "VALID" for f in ANGLE_FEATURES)).to_numpy()
        filtered.append(values[ok].assign(dataset_source="hohai"))
    filtered = pd.concat(filtered, ignore_index=True)
    original = measurements.loc[measurements.dataset_source.eq("hohai") & measurements.angle23_complete]
    p_orig, p_filt = predict_frame(model, card, original), predict_frame(model, card, filtered)
    merged = original[["window_id", "roll_std_60"]].merge(filtered[["window_id", "roll_std_60"]], on="window_id", suffixes=("_orig", "_filt"))
    return {"windows_original": int(len(original)), "windows_filtered_complete": int(len(filtered)),
            "predictions_original": p_orig.proxy_prediction.value_counts().to_dict(),
            "predictions_filtered": p_filt.proxy_prediction.value_counts().to_dict(),
            "abstain_reasons_filtered": p_filt.loc[p_filt.status.eq("ABSTAIN"), "abstain_reason"].value_counts().to_dict(),
            "roll_std_60_ratio_median": float((merged.roll_std_60_filt / merged.roll_std_60_orig).median()),
            "approximation": "Butterworth bậc 2 fc=0.5 Hz nhân quả trên chuỗi 10 Hz đã xử lý; extractor 0.1.0; không giảm mẫu, không mô phỏng gia tốc kế."}


def southampton_accel_roll_check(repo_root: Path) -> dict:
    """So sánh Roll của dataset với Roll suy từ gia tốc kế (atan2) — quy ước trục chọn thực nghiệm, chưa xác minh."""
    frame = pd.read_parquet(repo_root / "ml/data/processed/southampton/southampton_run_14/segment_000/timeseries.parquet",
                            columns=["roll_deg", "accel_y_m_s2", "accel_z_m_s2"]).dropna()
    acc_roll = np.degrees(np.arctan2(-frame.accel_y_m_s2.to_numpy(), -frame.accel_z_m_s2.to_numpy()))
    roll = frame.roll_deg.to_numpy()
    return {"samples": int(len(frame)), "convention": "atan2(-ay, -az) (chọn để khớp dấu; chưa xác minh)",
            "dataset_roll_mean_deg": float(roll.mean()), "accel_roll_mean_deg": float(acc_roll.mean()),
            "dataset_roll_std_deg": float(roll.std()), "accel_roll_std_deg": float(acc_roll.std()),
            "pearson_r": float(np.corrcoef(roll, acc_roll)[0, 1]),
            "rms_difference_deg": float(np.sqrt(np.mean((roll - acc_roll) ** 2)))}


def run(repo_root: Path) -> dict:
    repo_root = repo_root.resolve()
    contract = build_contract()
    (repo_root / CONTRACT_PATH).write_text(json.dumps(contract, indent=1, ensure_ascii=False), encoding="utf-8")
    measurements = pd.read_parquet(repo_root / "ml/data/labels/proxy_v1/measurements.parquet")
    calibration = json.loads((repo_root / "ml/data/labels/proxy_v1/calibrations.json").read_text())["final_all_hohai_groups"]
    cards_path = repo_root / "ml/reports/ml/rf_poc_model_card.json"
    cards = json.loads(cards_path.read_text()) if cards_path.is_file() else {}
    results_path = repo_root / "ml/reports/ml/rf_poc_results.json"
    compact = {}
    if results_path.is_file():
        results = json.loads(results_path.read_text())
        compact = {t: {"f1": r["compact_model"]["pooled"]["f1"], "params": r["compact_model"]["params"],
                       "median_estimated_c_array_bytes": r["compact_model"]["tree_statistics_fold_median_bytes"]}
                   for t, r in results.get("targets", {}).items()}
    output = {"contract_path": CONTRACT_PATH.as_posix(), "memory": memory_estimate(cards), "compact_models": compact,
              "firmware_chain_emulation": firmware_chain_emulation(repo_root, measurements, calibration),
              "filtered_feature_model_shift": filtered_feature_model_shift(repo_root, measurements),
              "southampton_accel_roll_check": southampton_accel_roll_check(repo_root),
              "current_firmware_chain": {"input_hz": 20, "complementary_filter_tau_s": 7.5, "lowpass": "Butterworth bậc 2, 0.5 Hz",
                                         "output_hz": 2, "short_window_samples": 120, "long_window_samples": 360,
                                         "update_every_samples": 10, "source": "core/include/svmg_filter.h, core/src/filter.c, core/include/svmg_features.h"},
              "deployable": False,
              "deployable_blockers": ["Chưa đo RAM/flash/latency trên ESP32 với model thật",
                                      "Chưa có cài đặt C 23 feature và golden-vector parity",
                                      "Chuỗi firmware hiện tại 2 Hz + lọc 0.5 Hz khác chuỗi 10 Hz của dataset",
                                      "Roll ESP32 từ bộ lọc bù MPU6050 khác nguồn đo của dataset; chưa có hiệu chuẩn chéo",
                                      "Mô hình học trên Hohai model-scale (chu kỳ ~1.8 s), không đại diện tàu full-scale",
                                      "Nhãn là proxy tương đối, không phải hazard đã xác minh"]}
    (repo_root / OUTPUT_PATH).write_text(json.dumps(output, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Ước lượng khả thi ESP32 cho schema 23 feature (đề xuất, không sửa firmware).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    out = run(args.repo_root)
    print(json.dumps({"memory_total_bytes": out["memory"]["feature_ram_bytes"]["total"],
                      "fw_chain_std_ratio_median": out["firmware_chain_emulation"]["std_ratio_median"],
                      "fw_chain_decisions_changed": out["firmware_chain_emulation"]["decisions_changed"],
                      "southampton_accel_roll": out["southampton_accel_roll_check"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
