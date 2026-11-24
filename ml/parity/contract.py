"""Kiểm định contract 23 angle feature so với extractor Python (tham chiếu số học hiện hành).

Không sửa công thức. Mọi khác biệt giữa đặc tả, contract đề xuất và hành vi extractor được ghi thành
``issues`` có mã, mức độ và trạng thái; không giải quyết ngầm.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ml.features.extractor import extract_segment
from ml.features.spec import FEATURE_NAMES, PRACTICAL_SUBSETS, WINDOW_SECONDS

CONTRACT_V01 = Path("ml/docs/feature_contract_23_v0.1.json")
CONTRACT_V02 = Path("ml/docs/feature_contract_23_v0.2.json")
FEATURE_CONFIG = Path("ml/features/config.yaml")
M1_DOC = Path("ml/docs/M2_23_Features_ESP32_Integration.md")
MODEL_CARD = Path("ml/reports/ml/rf_poc_model_card.json")
CONTRACT_VERSION = "0.2.0-proposal"
SCHEMA_VERSION = f"svmg-angle23-{CONTRACT_VERSION}"
FEATURE_SCHEMA_VERSION = "svmg-angle-23-v1"
SEMANTIC_CONTRACT_VERSION = "svmg-angle23-semantics-1.0.0"
VALIDITY_POLICY_VERSION = "svmg-angle23-validity-1.0.0"

# Danh sách kỳ vọng do milestone cung cấp (nhóm A, C, D, F); contract trong repository vẫn là chuẩn.
EXPECTED_SELECTION = (
    "roll_rms_60", "roll_std_60", "roll_mean_60", "roll_peak_to_peak_60", "roll_abs_p95_60", "roll_abs_max_60",
    "roll_iqr_60", "roll_diff_rms_60",
    "roll_mean_180", "roll_median_180", "roll_mean_abs_180", "roll_dominant_sign_ratio_180",
    "roll_segment_mean_std_180", "roll_mean_shift_180",
    "roll_rms_early_60", "roll_rms_late_60", "roll_rms_ratio_180", "roll_rms_slope_180", "roll_rms_trend_r2_180",
    "roll_p95_trend_slope_180",
    "pitch_rms_60", "pitch_std_60", "pitch_peak_to_peak_60",
)
FEATURE_ORDER = tuple(PRACTICAL_SUBSETS["angle_only_23_without_gyro_or_period"])
GROUPS = {name: ("A_roll_60" if i < 8 else "C_roll_offset_180" if i < 14 else "D_roll_growth_180" if i < 20 else "F_pitch_60")
          for i, name in enumerate(FEATURE_ORDER)}
STATUS_VOCABULARY = ("VALID", "INSUFFICIENT_WINDOW", "INVALID_INPUT", "UNDEFINED_MATHEMATICALLY")
REASON_CODES = ("WINDOW_HISTORY_SHORT", "SAMPLING_RATE_MISMATCH", "TIMESTAMP_GAP", "TIME_SAMPLE_COVERAGE",
                "SIGNAL_VALID_COVERAGE", "ADJACENT_PAIR_COVERAGE", "SEGMENT_BLOCK_COVERAGE",
                "EARLY_RMS_AT_OR_BELOW_EPSILON", "CONSTANT_RMS_TREND", "NON_FINITE_RESULT")


def feature_settings(repo_root: Path) -> dict:
    return yaml.safe_load((repo_root / FEATURE_CONFIG).read_text(encoding="utf-8"))["features"]


def schema_sha256(names=FEATURE_ORDER) -> str:
    return hashlib.sha256("\n".join(names).encode()).hexdigest()


def run_extractor(times, roll, pitch, settings: dict, case_id: str = "probe"):
    n = len(times)
    frame = pd.DataFrame({"dataset_source": "golden", "session_id": case_id, "segment_id": "segment_000",
                          "time_seconds": np.asarray(times, float), "roll_deg": np.asarray(roll, float),
                          "pitch_deg": np.asarray(pitch, float), "gyro_x_rad_s": np.full(n, np.nan),
                          "gyro_y_rad_s": np.full(n, np.nan)})
    return extract_segment(frame, {"target_sampling_hz_effective": settings["target_sampling_hz"]}, settings, "golden")


def _doc_order(repo_root: Path) -> list[str]:
    text = (repo_root / M1_DOC).read_text(encoding="utf-8")
    return [name for _, name in re.findall(r"^\|\s*(\d+)\s*\|\s*`?([a-z0-9_]+)`?\s*\|", text, re.M)]


def _behaviour_checks(settings: dict) -> list[dict]:
    """Kiểm tra hành vi trên chính extractor bằng tín hiệu có đáp án giải tích."""
    checks = []
    t = np.arange(2101) / 10.0

    def last(values, metadata, name):
        status = json.loads(metadata.iloc[-1].validity_json)[name]
        return values.iloc[-1][name], status["status"], status["reason_code"]

    sine = np.sin(2 * np.pi * 0.1 * t + 0.3)
    v, m, _ = run_extractor(t, sine, np.zeros_like(t), settings)
    std, _, _ = last(v, m, "roll_std_60")
    checks.append({"id": "population_std", "expected": math.sqrt(0.5), "observed": float(std),
                   "passed": abs(std - math.sqrt(0.5)) < 1e-12,
                   "note": "Sine biên độ 1, số chu kỳ nguyên: std quần thể = 1/sqrt(2); std mẫu (n-1) sẽ lớn hơn 0,083%."})
    ramp = 0.5 + 0.004 * np.arange(2101)
    v, m, _ = run_extractor(t, ramp, np.zeros_like(t), settings)
    p95, _, _ = last(v, m, "roll_abs_p95_60")
    lo = ramp[2101 - 600]
    expected = lo + 0.95 * 599 * 0.004
    checks.append({"id": "type7_quantile", "expected": expected, "observed": float(p95), "passed": abs(p95 - expected) < 1e-9,
                   "note": "Cấp số cộng 600 giá trị: Q_0.95 Type-7 = x_min + 0.95*(n-1)*bước."})
    spike = np.zeros_like(t)
    spike[1500] = 10.0  # t = 150.0 = endpoint 210 - 60: KHÔNG thuộc (150, 210]
    v, m, _ = run_extractor(t, spike, np.zeros_like(t), settings)
    amax, _, _ = last(v, m, "roll_abs_max_60")
    mean180, _, _ = last(v, m, "roll_mean_180")
    checks.append({"id": "half_open_window", "expected": 0.0, "observed": float(amax), "passed": amax == 0.0 and mean180 > 0,
                   "note": "Mẫu tại đúng t-60 bị loại khỏi cửa sổ 60 s nhưng thuộc cửa sổ 180 s."})
    v, m, _ = run_extractor(t, np.zeros_like(t), np.zeros_like(t), settings)
    _, ratio_status, ratio_reason = last(v, m, "roll_rms_ratio_180")
    _, r2_status, r2_reason = last(v, m, "roll_rms_trend_r2_180")
    _, sign_status, _ = last(v, m, "roll_dominant_sign_ratio_180")
    checks.append({"id": "zero_signal_undefined", "expected": "UNDEFINED_MATHEMATICALLY x3",
                   "observed": [ratio_status, ratio_reason, r2_status, r2_reason, sign_status],
                   "passed": ratio_status == r2_status == sign_status == "UNDEFINED_MATHEMATICALLY",
                   "note": "Tín hiệu 0: ratio (rms_early <= epsilon), R² (SST = 0), sign ratio (không có mẫu khác 0) đều không xác định, không bằng 0."})
    v, m, _ = run_extractor(t[:1501], sine[:1501], np.zeros(1501), settings)
    _, st180, reason180 = last(v, m, "roll_mean_180")
    _, st60, _ = last(v, m, "roll_rms_60")
    checks.append({"id": "warmup", "expected": "60 s VALID, 180 s INSUFFICIENT_WINDOW", "observed": [st60, st180, reason180],
                   "passed": st60 == "VALID" and st180 == "INSUFFICIENT_WINDOW",
                   "note": "150 s lịch sử: feature 180 s chưa được tính (WARMUP)."})
    growth = np.where(t <= 90, 1.0, np.where(t <= 150, 2.0, 3.0)) * np.sin(2 * np.pi * 0.1 * t + 0.3)
    v, m, _ = run_extractor(t, growth, np.zeros_like(t), settings)
    slope, _, _ = last(v, m, "roll_rms_slope_180")
    expected_slope = (3 - 1) / math.sqrt(2) / 2.0
    checks.append({"id": "trend_slope_units", "expected": expected_slope, "observed": float(slope),
                   "passed": abs(slope - expected_slope) < 1e-9,
                   "note": "RMS block 1/√2, 2/√2, 3/√2 tại tâm 30/90/150 s: slope = (r3-r1)/120 s × 60 = deg/phút."})
    holes = sine.copy()
    holes[np.arange(1520, 2100, 29)[:20]] = np.nan
    v, m, _ = run_extractor(t, holes, np.zeros_like(t), settings)
    _, diff_status, diff_reason = last(v, m, "roll_diff_rms_60")
    _, rms_status, _ = last(v, m, "roll_rms_60")
    checks.append({"id": "difference_pair_semantics", "expected": "rms VALID, diff_rms INVALID_INPUT/ADJACENT_PAIR_COVERAGE",
                   "observed": [rms_status, diff_status, diff_reason],
                   "passed": rms_status == "VALID" and diff_status == "INVALID_INPUT" and diff_reason == "ADJACENT_PAIR_COVERAGE",
                   "note": "20 NaN rời rạc (3,3%) giữ feature pointwise hợp lệ nhưng xóa 40 cặp kề nhau: 559 < 570 cặp."})
    return checks


def validate_contract(repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    settings = feature_settings(repo_root)
    v01 = json.loads((repo_root / CONTRACT_V01).read_text(encoding="utf-8"))
    from ml.labeling.human_review_workflow import ANGLE_FEATURES
    from ml.train.rf_poc import FEATURE_ORDER as RF_ORDER
    sources = {"milestone_expected_selection": list(EXPECTED_SELECTION),
               "ml.features.spec.PRACTICAL_SUBSETS": list(FEATURE_ORDER),
               "ml.labeling.human_review_workflow.ANGLE_FEATURES": list(ANGLE_FEATURES),
               "ml.train.rf_poc.FEATURE_ORDER": list(RF_ORDER),
               "feature_contract_23_v0.1.json": [f["name"] for f in v01["features"]],
               "M2_23_Features_ESP32_Integration.md": _doc_order(repo_root)}
    card_sha = None
    if (repo_root / MODEL_CARD).is_file():
        card = json.loads((repo_root / MODEL_CARD).read_text(encoding="utf-8"))
        card_sha = next(iter(card.values()))["feature_schema"]["sha256"]
    order_checks = {name: order == list(FEATURE_ORDER) for name, order in sources.items()}
    window_checks = {f["name"]: {"contract": f["window_seconds"], "spec": WINDOW_SECONDS[f["name"]],
                                 "match": f["window_seconds"] == WINDOW_SECONDS[f["name"]]} for f in v01["features"]}
    config_checks = {
        "sampling_hz_10": settings["target_sampling_hz"] == 10.0 == v01["sampling_hz"],
        "stride_10s": settings["window_stride_seconds"] == 10.0 == v01["update_stride_seconds"],
        "minimum_valid_fraction_0_95": settings["minimum_valid_fraction"] == 0.95 == v01["minimum_valid_fraction"],
        "maximum_gap_factor_1_5": settings["maximum_gap_factor"] == 1.5 == v01["maximum_gap_factor"],
        "quantile_type7": settings["quantile_method"] == "type7",
        "endpoint_convention": settings["endpoint_convention"] == "(t-W,t]",
        "three_60s_blocks": settings["long_window_segments_seconds"] == [60.0, 60.0, 60.0],
        "numeric_zero_epsilon_deg": settings["numeric_zero_epsilon_deg"],
        "r_squared_zero_tolerance": settings["r_squared_zero_tolerance"],
    }
    behaviour = _behaviour_checks(settings)
    issues = [
        {"id": "C01", "severity": "MATERIAL", "status": "RESOLVED_CONSERVATIVE_ALL_THREE_BLOCKS",
         "title": "Điều kiện hợp lệ của feature block 180 s",
         "spec": "Đặc tả 30 ứng viên mô tả dependency toán học tối thiểu theo feature.",
         "extractor": "Chính sách production đã duyệt: cửa sổ 180 s phải hợp lệ và cả 3 block 60 s phải có ít nhất 570 mẫu; nếu một block không đạt thì cả 8 feature chia block INVALID_INPUT/SEGMENT_BLOCK_COVERAGE.",
         "golden_policy": "Giữ nguyên SYN22/SYN27. Đây là validity gate bảo thủ production, không phải dependency tối thiểu của từng công thức trong đặc tả 30 ứng viên.",
         "verification_evidence": ["ml/features/extractor.py", "core/src/features.c", "SYN22_nan_excess", "SYN27_block_coverage_rule", "tests/firmware/test/test_features/test_features.c"]},
        {"id": "C02", "severity": "MATERIAL", "status": "RESOLVED_NUMERICAL_ZERO_EPSILON",
         "title": "Epsilon mẫu số của roll_rms_ratio_180",
         "spec": "Epsilon là ngưỡng zero số học, không phải độ phân giải hay noise floor cảm biến đã hiệu chuẩn.",
         "extractor": f"rms_early <= {settings['numeric_zero_epsilon_deg']} degree -> UNDEFINED_MATHEMATICALLY; tỷ số hữu hạn lớn vẫn hợp lệ.",
         "golden_policy": "Giữ nguyên SYN17/SYN18/SYN19; không thêm ngưỡng miền model hoặc thay đổi RF.",
         "verification_evidence": ["ml/features/config.yaml", "ml/features/extractor.py", "core/include/svmg_features.h", "SYN17_zero_early_block", "SYN18_epsilon_below", "SYN19_epsilon_above"]},
        {"id": "C03", "severity": "MATERIAL", "status": "RESOLVED_ABSOLUTE_SST_DOUBLE_ACCUMULATION",
         "title": "Ngưỡng SST tuyệt đối và độ nhạy tích lũy R-squared",
         "spec": "R² không xác định nếu SST = 0; production policy dùng ngưỡng tuyệt đối đã chốt.",
         "extractor": f"SST <= {settings['r_squared_zero_tolerance']} deg² -> UNDEFINED_MATHEMATICALLY. Production C tích lũy RMS, SST và SSE bằng double; float32_probe chỉ mô phỏng, không phải production algorithm.",
         "golden_policy": "Giữ SYN29 (R²=0 VALID) và SYN30 theo Python reference. Parity REVIEW_ILL_CONDITIONED là diagnostic riêng, không đổi runtime validity.",
         "verification_evidence": ["ml/features/calculations.py", "core/src/features.c", "ml/parity/float32_probe.py", "SYN29_block_step_symmetric", "SYN30_permuted_blocks"]},
        {"id": "C04", "severity": "MATERIAL", "status": "RESOLVED_LAYERED_TIMESTAMP_BOUNDARY",
         "title": "Biểu diễn mẫu thiếu: NaN có timestamp khác với timestamp bị bỏ",
         "spec": "≥ 95% mẫu hợp lệ; gap > 1,5 chu kỳ làm cửa sổ không hợp lệ.",
         "extractor": "Mẫu NaN có timestamp được bỏ qua trong thống kê pointwise (≤ 5%); một timestamp bị bỏ (khoảng cách 0,2 s > 0,15 s) làm MỌI cửa sổ chứa nó INVALID_INPUT/TIMESTAMP_GAP.",
         "firmware_policy": "Pipeline M1 xử lý gap timestamp hữu hạn bằng restart, xóa feature history và đưa decision về UNKNOWN; timestamp NaN/Inf bị loại khỏi filter/decimation và engine chuyển UNKNOWN ngay cả khi chưa phát output 10 Hz. Active CRITICAL được giữ nguyên.",
         "numerical_api_policy": "C feature-only API không nhận timestamp và chỉ áp dụng trên lưới 10 Hz đều; API này không tự đánh giá TIMESTAMP_GAP.",
         "golden_policy": "Giữ nguyên SYN23/SYN24 timestamp-aware expected outputs. C host feature-only tiếp tục NOT_EVALUABLE cho 46 bản ghi gap; không đổi sang PASS khi chưa có C timestamp-aware output."},
        {"id": "C05", "severity": "CLARIFICATION", "status": "DOCUMENTED_IN_V0_2",
         "title": "Neo lưới endpoint",
         "extractor": "Endpoint theo CHỈ SỐ mẫu: mẫu thứ 600, 700, … tính từ mẫu đầu segment; mẫu đầu tiên không bao giờ thuộc cửa sổ 60 s đầu. Sau một timestamp bị bỏ, thời điểm endpoint lệch theo chỉ số.",
         "golden_policy": "Golden ghi rõ endpoint (chỉ số và thời gian) cho từng case; C đánh giá đúng tại các endpoint đó."},
        {"id": "C06", "severity": "CLARIFICATION", "status": "DOCUMENTED_IN_V0_2",
         "title": "roll_rms_late_60 trùng giá trị nhưng khác validity với roll_rms_60",
         "extractor": "Cùng mẫu (t-60, t] nên cùng giá trị khi cả hai hợp lệ; rms_late chỉ hợp lệ khi đủ 180 s và đủ 3 block."},
        {"id": "C08", "severity": "CLARIFICATION", "status": "DOCUMENTED_IN_V0_2",
         "title": "Mã lý do của roll_dominant_sign_ratio_180 khi mọi mẫu bằng 0",
         "spec": "Không xác định nếu mọi giá trị đúng bằng 0.",
         "extractor": "dominant_sign_ratio trả NaN, _valid() đổi thành UNDEFINED_MATHEMATICALLY với reason_code NON_FINITE_RESULT (không có mã riêng như NO_NONZERO_SAMPLES).",
         "golden_policy": "Status được so khớp bắt buộc; reason_code chỉ so như cảnh báo. M1 nên xuất NON_FINITE_RESULT để trùng golden."},
        {"id": "C09", "severity": "CLARIFICATION", "status": "DOCUMENTED_IN_V0_2",
         "title": "Chỉ số 0-based của contract và STT 1-based trong tài liệu M1",
         "spec": "M2_23_Features_ESP32_Integration.md đánh STT 1..23; contract JSON và golden dùng feature_index 0..22.",
         "golden_policy": "Interchange dùng feature_index 0-based; harness kiểm tra feature_name khớp index để bắt lệch 1 vị trí."},
        {"id": "C07", "severity": "MATERIAL", "status": "SUPERSEDED_IN_V0_2",
         "title": "Dung sai parity một giá trị chung trong v0.1",
         "spec": "v0.1 đề xuất tuyệt đối 1e-3°, tương đối 1e-4 cho mọi feature.",
         "golden_policy": "v0.2 thay bằng dung sai theo nhóm feature có hạng tỷ lệ theo biên độ đầu vào (ml/parity/fixtures/tolerance_spec.json)."},
    ]
    inconsistent_orders = [k for k, ok in order_checks.items() if not ok]
    return {"schema_version": SCHEMA_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
            "validity_policy_version": VALIDITY_POLICY_VERSION,
            "feature_count": len(FEATURE_ORDER), "feature_order": list(FEATURE_ORDER),
            "schema_sha256": schema_sha256(), "model_card_schema_sha256": card_sha,
            "model_card_schema_matches": card_sha == schema_sha256() if card_sha else None,
            "order_checks": order_checks, "inconsistent_orders": inconsistent_orders,
            "window_checks": window_checks, "all_windows_match": all(v["match"] for v in window_checks.values()),
            "config_checks": config_checks, "behaviour_checks": behaviour,
            "all_behaviour_checks_passed": all(c["passed"] for c in behaviour),
            "issues": issues, "blocking_inconsistency": bool(inconsistent_orders) or not all(v["match"] for v in window_checks.values()),
            "extractor_reference": "ml/features/extractor.py (feature_extractor_version 0.1.0, feature_spec_version candidate-30-v1)"}


def build_contract_v02(repo_root: Path, validation: dict) -> dict:
    """Giữ định danh v0.2 của parity artifacts và gắn semantic contract đã được duyệt."""
    v01 = json.loads((repo_root / CONTRACT_V01).read_text(encoding="utf-8"))
    settings = feature_settings(repo_root)
    contract = {k: v for k, v in v01.items() if k not in ("features", "parity_tolerance_proposal", "version")}
    contract.update({
        "version": CONTRACT_VERSION, "schema_version": SCHEMA_VERSION, "supersedes": "0.1.0-proposal",
        "status": "FINALIZED_SEMANTICS", "schema_sha256": schema_sha256(),
        "semantic_contract": {
            "version": SEMANTIC_CONTRACT_VERSION,
            "status": "FINAL",
            "validity_policy_version": VALIDITY_POLICY_VERSION,
            "feature_schema": {"version": FEATURE_SCHEMA_VERSION, "sha256_scope": "ordered feature names only",
                               "sha256": schema_sha256()},
            "parity_schema_mapping": {
                "schema_version": SCHEMA_VERSION,
                "status": "HISTORICAL_ARTIFACT_SCHEMA_PRESERVED",
                "note": "Golden và host parity metadata giữ định danh producer đã phát hành; không ghi lại fixture như thể được sinh dưới schema version mới."
            },
            "validity_policy": {
                "C01": "Cửa sổ 180 s hợp lệ và cả ba block 60 s đều có ít nhất 570 mẫu; nếu một block không đạt, cả tám feature block INVALID_INPUT/SEGMENT_BLOCK_COVERAGE.",
                "C02": "rms_early <= 1e-9 degree -> UNDEFINED_MATHEMATICALLY; ngưỡng zero số học, không phải noise floor cảm biến.",
                "C03": "SST <= 1e-15 degree^2 -> UNDEFINED_MATHEMATICALLY; parity REVIEW chỉ là diagnostic."
            },
            "model_compatibility_metadata": _model_compatibility(repo_root)
        },
        "units": {"roll_deg": "degree", "pitch_deg": "degree", "time_seconds": "second"},
        "window_membership": "Mẫu i thuộc cửa sổ W tại endpoint e khi t_e - W < t_i <= t_e. Với nhịp 10 Hz không gap, tương đương chỉ số (k_e - 10W, k_e].",
        "endpoint_grid": "Chỉ số mẫu 600 + 100·j tính từ mẫu đầu segment (endpoint đầu tại t0 + 60 s). Golden liệt kê endpoint tường minh.",
        "warmup": "Feature 60 s: cần t_e - t0 >= 60 s; feature 180 s: cần >= 180 s. Thiếu lịch sử -> INSUFFICIENT_WINDOW/WINDOW_HISTORY_SHORT (WARMUP).",
        "coverage": {"pointwise_minimum_finite_samples_60s": 570, "pointwise_minimum_finite_samples_180s": 1710,
                     "diff_minimum_adjacent_pairs_60s": 570, "block_minimum_samples": 570,
                     "maximum_gap_seconds": settings["maximum_gap_factor"] / settings["target_sampling_hz"],
                     "maximum_timestamps_in_window": "N_expected + 1"},
        "missing_value_semantics": "M2: NaN/Inf có timestamp bỏ khỏi thống kê pointwise; cặp sai phân chỉ dùng hai mẫu hữu hạn kề nhau đúng 0,1 s. Timestamp vắng mặt tạo gap và cửa sổ chứa gap vượt ngưỡng là INVALID_INPUT/TIMESTAMP_GAP. M1 stream: gap timestamp hữu hạn restart pipeline/window và đưa decision UNKNOWN; timestamp NaN/Inf bị từ chối, không lọc payload bằng nominal_dt, engine UNKNOWN tức thì. C feature-only API giả định lưới 10 Hz đều và không biểu diễn gap.",
        "timestamp_gap_policy": {
            "m2_timestamp_aware_reference": "Giữ nguyên semantics và golden SYN23/SYN24: cửa sổ chứa gap vượt 0,15 s là INVALID_INPUT/TIMESTAMP_GAP.",
            "m1_end_to_end_stream": "Gap hữu hạn restart filter và xóa feature history; timestamp không hữu hạn bị loại khỏi decimation và làm engine UNKNOWN ngay; active CRITICAL không bị xóa.",
            "m1_feature_only_api": "Giữ nguyên API số học không timestamp; yêu cầu chuỗi 10 Hz đều.",
            "host_c_parity": "46 bản ghi SYN23/SYN24 vẫn NOT_EVALUABLE đối với API không timestamp; chỉ implementation timestamp-aware có đầu ra thật mới có thể được so sánh."
        },
        "block_rule_as_implemented": "Chính sách validity production bảo thủ đã duyệt: cả 8 feature dựa trên block (segment_mean_std, mean_shift, rms_early, rms_late, rms_ratio, rms_slope, trend_r2, p95_trend_slope) cần cửa sổ 180 s hợp lệ VÀ cả 3 block đạt ít nhất 570 mẫu. Quy tắc này chặt hơn dependency toán học tối thiểu của một số công thức trong đặc tả 30 ứng viên.",
        "statistics": {"std": "quần thể, mẫu số n", "quantile": "Type-7: h=(n-1)p, nội suy tuyến tính trên giá trị đã sắp xếp",
                       "regression": "OLS 3 điểm tại tâm block u=[30,90,150] s; slope × 60 -> deg/min",
                       "r_squared": f"1-SSE/SST; UNDEFINED nếu SST <= {settings['r_squared_zero_tolerance']}; kẹp [0,1] chỉ trong 1e-12",
                       "ratio_epsilon_deg": settings["numeric_zero_epsilon_deg"],
                       "sign_ratio": "max(n+,n-)/(n++n-); số 0 tuyệt đối bị loại; UNDEFINED nếu không có mẫu khác 0"},
        "status_vocabulary": list(STATUS_VOCABULARY), "reason_codes": list(REASON_CODES),
        "invalid_value_encoding": "Feature không VALID có value = null (JSON) hoặc ô rỗng (CSV); không bao giờ 0.",
        "input_representation": "Golden input là giá trị float32 (lưu dạng thập phân 9 chữ số, đọc lại chính xác vào float32).",
        "index_base": "feature_index 0-based (0..22); STT trong tài liệu M1 là 1-based (C09)",
        "reason_code_notes": {"roll_dominant_sign_ratio_180": "mọi mẫu hữu hạn bằng 0 -> UNDEFINED_MATHEMATICALLY / NON_FINITE_RESULT (C08)",
                              "block_features": "cửa sổ 180 s không hợp lệ -> dùng lại status/reason của cửa sổ 180 s; block thiếu -> INVALID_INPUT / SEGMENT_BLOCK_COVERAGE"},
        "interchange_format": "ml/parity/fixtures/interchange_format.json",
        "tolerance_spec": "ml/parity/fixtures/tolerance_spec.json",
        "golden_manifest": "ml/parity/fixtures/manifest.json",
        "open_issues": [i["id"] for i in validation["issues"] if i["status"].startswith("OPEN")],
        "validity_policy_version": VALIDITY_POLICY_VERSION,
        "changelog": ["Chốt C01-C03 thành semantic contract " + SEMANTIC_CONTRACT_VERSION + ".",
                      "Giữ nguyên numeric schema, feature formulas, tolerance, golden expected values và validity hiện tại.",
                      "Thay dung sai chung của v0.1 bằng dung sai theo feature (C07).",
                      "Giải quyết C04 bằng ranh giới validity timestamp-aware và restart end-to-end M1; giữ nguyên feature formulas và golden gap outputs.",
                      "Bổ sung ngữ nghĩa cửa sổ, endpoint, warmup, coverage, mẫu thiếu, mã trạng thái (C04-C06, C08, C09).",
                      "Công thức, tên, đơn vị, thứ tự 23 feature KHÔNG đổi so với v0.1."],
        "features": [dict(f, group=GROUPS[f["name"]]) for f in v01["features"]],
    })
    return contract


def write_validation(repo_root: Path) -> dict:
    validation = validate_contract(repo_root)
    if validation["blocking_inconsistency"]:
        (repo_root / "ml/reports/parity").mkdir(parents=True, exist_ok=True)
        (repo_root / "ml/reports/parity/feature23_contract_validation.json").write_text(
            json.dumps(validation, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        raise RuntimeError(f"Thứ tự/cửa sổ feature không nhất quán: {validation['inconsistent_orders']}; dừng trước khi sinh golden.")
    contract = build_contract_v02(repo_root, validation)
    (repo_root / CONTRACT_V02).write_text(json.dumps(contract, indent=1, ensure_ascii=False), encoding="utf-8")
    validation["contract_v02_path"] = CONTRACT_V02.as_posix()
    validation["contract_v02_sha256"] = hashlib.sha256((repo_root / CONTRACT_V02).read_bytes()).hexdigest()
    out = repo_root / "ml/reports/parity/feature23_contract_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(validation, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return validation


def _model_compatibility(repo_root: Path) -> dict:
    """Report compatibility without changing historical model metrics or artifacts."""
    card = json.loads((repo_root / MODEL_CARD).read_text(encoding="utf-8"))
    model_id, model = next(iter(card.items()))
    return {"model_id": model_id, "model_sha256": model["model_sha256"],
            "feature_schema_version": FEATURE_SCHEMA_VERSION, "feature_schema_sha256": schema_sha256(),
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION, "validity_policy_version": VALIDITY_POLICY_VERSION,
            "input_policy": "FULL_VECTOR_ONLY; training requires angle23_complete and inference rejects non-finite feature values",
            "historical_metrics_and_model_modified": False}


def finalize_generated_metadata(repo_root: Path) -> dict:
    """Regenerate semantic artifacts and manifest metadata without rebuilding golden rows."""
    repo_root = Path(repo_root).resolve()
    validation = write_validation(repo_root)
    manifest_path = repo_root / "ml/parity/fixtures/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract_path = repo_root / CONTRACT_V02
    issues = [i["id"] for i in validation["issues"] if i["status"].startswith("OPEN")]
    manifest.update({
        "contract": CONTRACT_V02.as_posix(),
        "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "contract_validation": {
            "blocking_inconsistency": validation["blocking_inconsistency"],
            "open_issues": issues
        }
    })
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True, default=float) + "\n",
                             encoding="utf-8")
    readiness_path = repo_root / "ml/reports/parity/parity_readiness.json"
    if readiness_path.is_file():
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        readiness["golden_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        readiness_path.write_text(json.dumps(readiness, indent=1, ensure_ascii=False, default=float) + "\n",
                                  encoding="utf-8")
    return {"contract_sha256": manifest["contract_sha256"], "contract_validation": manifest["contract_validation"]}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sinh contract metadata mà không tái sinh golden vectors.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(finalize_generated_metadata(args.repo_root), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
