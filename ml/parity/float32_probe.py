"""Mô phỏng số học float32 kiểu C để HIỆU CHỈNH dung sai và kiểm tra khả năng phát hiện lỗi của harness.

ĐÂY KHÔNG PHẢI KẾT QUẢ C/C++ VÀ KHÔNG PHẢI THƯ VIỆN FEATURE PRODUCTION.
- Kết quả được gắn ``producer.kind = python_float32_emulation``; harness gán nhãn FLOAT32_EMULATION_*, không bao giờ C_PARITY_*.
- Không dùng để sinh golden: golden luôn do ``ml.features.extractor`` tạo.
- Chỉ số cửa sổ/block và validity của CỬA SỔ (coverage, gap, warmup) lấy từ golden; probe chỉ mô phỏng phần số học
  (cộng dồn tuần tự float32, std hai lượt, sắp xếp + Type-7, OLS 3 điểm) và các quyết định phụ thuộc làm tròn
  (epsilon của ratio, ngưỡng SST của R², tỷ lệ dấu) để đo rủi ro C02/C03.

``mutation`` tái hiện các lỗi hiện thực C điển hình; golden + dung sai phải bắt được từng lỗi.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from ml.parity.contract import FEATURE_ORDER, SCHEMA_VERSION, feature_settings
from ml.parity.golden import read_inputs

F32 = np.float32
MUTATIONS = {
    "sample_std_ddof1": "std mẫu (chia n-1) thay vì std quần thể",
    "quantile_nearest_rank": "phân vị nearest-rank thay vì Type-7",
    "quantile_type6": "phân vị Type-6 h=(n+1)p thay vì Type-7",
    "window_includes_lower_bound": "cửa sổ [t-W, t) (lệch 1 mẫu) thay vì (t-W, t]",
    "radians_input": "dùng Roll/Pitch theo radian",
    "diff_per_second": "roll_diff_rms_60 chia cho dt (deg/s) thay vì deg/mẫu",
    "slope_per_second": "slope không nhân 60 (deg/s thay vì deg/phút)",
    "p95_without_abs": "P95 trên x thay vì |x|",
    "centered_rms": "RMS quanh mean (thực chất là std) thay vì RMS gồm offset",
    "swap_roll_pitch_rms": "đảo vị trí roll_rms_60 (0) và pitch_rms_60 (20)",
    "invalid_as_zero": "feature không VALID được xuất VALID = 0",
    "sign_ratio_counts_zero_as_positive": "đếm số 0 tuyệt đối là dương",
    "one_pass_variance": "phương sai một lượt E[x²]-E[x]² trong float32 (không ổn định)",
    "ratio_without_epsilon": "roll_rms_ratio_180 chỉ kiểm tra rms_early > 0, bỏ epsilon 1e-9",
    "r2_zero_when_undefined": "R² = 0 VALID khi SST <= ngưỡng thay vì UNDEFINED",
}


def seqsum(x: np.ndarray) -> np.float32:
    """Cộng tuần tự trong float32 như vòng for đơn giản của C (không pairwise, không compensated)."""
    if len(x) == 0:
        return F32(0.0)
    return np.cumsum(np.asarray(x, dtype=F32), dtype=F32)[-1]


def mean32(x):
    return F32(seqsum(x) / F32(len(x)))


def rms32(x):
    x = np.asarray(x, dtype=F32)
    return F32(np.sqrt(seqsum(x * x) / F32(len(x))))


def std32(x, ddof: int = 0, one_pass: bool = False):
    x = np.asarray(x, dtype=F32)
    n = len(x)
    if one_pass:
        var = F32(seqsum(x * x) / F32(n)) - F32(mean32(x) * mean32(x))
        var = F32(var * F32(n) / F32(n - ddof))
    else:
        d = x - mean32(x)
        var = F32(seqsum(d * d) / F32(n - ddof))
    return F32(np.sqrt(max(F32(0.0), var)))


def quantile32(x, p: float, method: str = "type7"):
    z = np.sort(np.asarray(x, dtype=F32), kind="stable")
    n = len(z)
    if method == "nearest_rank":
        return z[max(0, min(n - 1, math.ceil(p * n) - 1))]
    h = F32(F32(n - 1) * F32(p)) if method == "type7" else F32(F32(n + 1) * F32(p) - F32(1.0))
    h = min(max(h, F32(0.0)), F32(n - 1))
    j = int(math.floor(h))
    g = F32(h - F32(j))
    k = min(j + 1, n - 1)
    return F32(z[j] + g * F32(z[k] - z[j]))


def ols_slope_r2(r: np.ndarray, r2_tolerance: float):
    u = np.array([30.0, 90.0, 150.0], dtype=F32)
    r = np.asarray(r, dtype=F32)
    ub, rb = mean32(u), mean32(r)
    du, dr = u - ub, r - rb
    slope = F32(seqsum(du * dr) / seqsum(du * du))
    sst = seqsum(dr * dr)
    if not sst > F32(r2_tolerance):
        return slope, None
    fitted = rb + slope * du
    sse = seqsum((r - fitted) * (r - fitted))
    score = F32(F32(1.0) - sse / sst)
    if F32(-1e-12) <= score < F32(0.0):
        score = F32(0.0)
    if F32(1.0) < score <= F32(1.0 + 1e-12):
        score = F32(1.0)
    return slope, score


def _finite(x):
    return x[np.isfinite(x)]


def emulate_endpoint(roll, pitch, t, ep: dict, golden_status: list[str], settings: dict, mutation: str | None = None):
    """Trả (values, statuses) 23 phần tử cho một endpoint."""
    eps, r2_tol = float(settings["numeric_zero_epsilon_deg"]), float(settings["r_squared_zero_tolerance"])
    shift = 1 if mutation == "window_includes_lower_bound" else 0
    lo60, hi60 = ep["windows"]["roll_pitch_60s"]
    lo180, hi180 = ep["windows"]["roll_180s"]
    sl60, sl180 = slice(max(0, lo60 - shift), hi60 + 1 - shift), slice(max(0, lo180 - shift), hi180 + 1 - shift)
    blocks = [slice(max(0, lo - shift), hi + 1 - shift) for lo, hi in ep["windows"]["blocks_60s"]]
    q = {"quantile_nearest_rank": "nearest_rank", "quantile_type6": "type6"}.get(mutation, "type7")
    ddof = 1 if mutation == "sample_std_ddof1" else 0
    one_pass = mutation == "one_pass_variance"

    def _abs(v):
        return v if mutation == "p95_without_abs" else np.abs(v)

    def _rms(v):
        return std32(v) if mutation == "centered_rms" else rms32(v)

    values: dict[str, float | None] = {}
    status = dict(zip(FEATURE_ORDER, golden_status))
    r60, r180, p60 = _finite(roll[sl60]), _finite(roll[sl180]), _finite(pitch[sl60])
    if len(r60) >= 2:
        values.update({"roll_rms_60": _rms(r60), "roll_std_60": std32(r60, ddof, one_pass), "roll_mean_60": mean32(r60),
                       "roll_peak_to_peak_60": F32(r60.max() - r60.min()), "roll_abs_p95_60": quantile32(_abs(r60), 0.95, q),
                       "roll_abs_max_60": F32(np.abs(r60).max()),
                       "roll_iqr_60": F32(quantile32(r60, 0.75, q) - quantile32(r60, 0.25, q))})
        x, tt = roll[sl60].astype(F32), t[sl60]
        ok = np.isfinite(x[:-1]) & np.isfinite(x[1:]) & (np.abs(np.diff(tt) - 0.1) <= 1e-6)
        d = (x[1:] - x[:-1])[ok]
        if len(d):
            values["roll_diff_rms_60"] = F32(rms32(d) / F32(0.1)) if mutation == "diff_per_second" else rms32(d)
    if len(p60) >= 2:
        values.update({"pitch_rms_60": _rms(p60), "pitch_std_60": std32(p60, ddof, one_pass),
                       "pitch_peak_to_peak_60": F32(p60.max() - p60.min())})
    if len(r180) >= 2:
        npos = int(np.count_nonzero(r180 >= 0)) if mutation == "sign_ratio_counts_zero_as_positive" else int(np.count_nonzero(r180 > 0))
        nneg = int(np.count_nonzero(r180 < 0))
        values.update({"roll_mean_180": mean32(r180), "roll_median_180": quantile32(r180, 0.5, q),
                       "roll_mean_abs_180": mean32(np.abs(r180))})
        if npos + nneg:
            values["roll_dominant_sign_ratio_180"] = F32(F32(max(npos, nneg)) / F32(npos + nneg))
            if status["roll_dominant_sign_ratio_180"] == "UNDEFINED_MATHEMATICALLY":
                status["roll_dominant_sign_ratio_180"] = "VALID"
        elif status["roll_dominant_sign_ratio_180"] == "VALID":
            status["roll_dominant_sign_ratio_180"] = "UNDEFINED_MATHEMATICALLY"
        bx = [_finite(roll[b]) for b in blocks]
        if all(len(b) >= 2 for b in bx):
            means = np.array([mean32(b) for b in bx], dtype=F32)
            brms = np.array([_rms(b) for b in bx], dtype=F32)
            bp95 = np.array([quantile32(_abs(b), 0.95, q) for b in bx], dtype=F32)
            factor = F32(1.0) if mutation == "slope_per_second" else F32(60.0)
            slope, r2 = ols_slope_r2(brms, r2_tol)
            if r2 is None and mutation == "r2_zero_when_undefined":
                r2 = F32(0.0)
            p95_slope, _ = ols_slope_r2(bp95, r2_tol)
            values.update({"roll_segment_mean_std_180": std32(means, ddof, one_pass), "roll_mean_shift_180": F32(means[2] - means[0]),
                           "roll_rms_early_60": brms[0], "roll_rms_late_60": brms[2],
                           "roll_rms_slope_180": F32(slope * factor), "roll_p95_trend_slope_180": F32(p95_slope * factor)})
            if brms[0] > F32(0.0 if mutation == "ratio_without_epsilon" else eps):
                values["roll_rms_ratio_180"] = F32(brms[2] / brms[0])
                if status["roll_rms_ratio_180"] == "UNDEFINED_MATHEMATICALLY":
                    status["roll_rms_ratio_180"] = "VALID"
            elif status["roll_rms_ratio_180"] == "VALID":
                status["roll_rms_ratio_180"] = "UNDEFINED_MATHEMATICALLY"
            if r2 is not None:
                values["roll_rms_trend_r2_180"] = r2
                if status["roll_rms_trend_r2_180"] == "UNDEFINED_MATHEMATICALLY":
                    status["roll_rms_trend_r2_180"] = "VALID"
            elif status["roll_rms_trend_r2_180"] == "VALID":
                status["roll_rms_trend_r2_180"] = "UNDEFINED_MATHEMATICALLY"
    out_values, out_status = [], []
    for name in FEATURE_ORDER:
        st = status[name]
        v = values.get(name)
        if st == "VALID" and v is None:
            st = "UNDEFINED_MATHEMATICALLY"
        if st != "VALID":
            out_values.append(0.0 if mutation == "invalid_as_zero" else None)
            out_status.append("VALID" if mutation == "invalid_as_zero" else st)
        else:
            out_values.append(float(v))
            out_status.append(st)
    if mutation == "swap_roll_pitch_rms":
        a, b = FEATURE_ORDER.index("roll_rms_60"), FEATURE_ORDER.index("pitch_rms_60")
        out_values[a], out_values[b] = out_values[b], out_values[a]
        out_status[a], out_status[b] = out_status[b], out_status[a]
    return out_values, out_status


def emulate_suite(repo_root: Path, suite_dir: Path, mutation: str | None = None) -> list[dict]:
    """Bản ghi theo định dạng trao đổi cho cả suite (dùng golden expected để lấy status cửa sổ)."""
    import pandas as pd

    repo_root = Path(repo_root)
    settings = feature_settings(repo_root)
    cases = json.loads((repo_root / suite_dir / "cases.json").read_text(encoding="utf-8"))["cases"]
    expected = pd.read_csv(repo_root / suite_dir / "expected_features.csv", dtype=str, keep_default_na=False)
    status_by = {k: g.sort_values("feature_index", key=lambda s: s.astype(int)).status.tolist()
                 for k, g in expected.groupby(["case_id", "endpoint_index"])}
    records = []
    for case in cases:
        inputs = read_inputs(repo_root / case["input_file"])
        t = inputs.time_seconds.to_numpy(float)
        roll = inputs.roll_deg.to_numpy(np.float64).astype(F32)
        pitch = inputs.pitch_deg.to_numpy(np.float64).astype(F32)
        if mutation == "radians_input":
            roll, pitch = np.deg2rad(roll).astype(F32), np.deg2rad(pitch).astype(F32)
        for ep in case["endpoints"]:
            golden_status = status_by[(case["case_id"], str(ep["endpoint_index"]))]
            values, statuses = emulate_endpoint(roll, pitch, t, ep, golden_status, settings, mutation)
            for i, name in enumerate(FEATURE_ORDER):
                records.append({"schema_version": SCHEMA_VERSION, "case_id": case["case_id"], "input_sha256": case["input_sha256"],
                                "endpoint_index": ep["endpoint_index"], "endpoint_time_seconds": ep["endpoint_time_seconds"],
                                "feature_index": i, "feature_name": name, "status": statuses[i], "reason_code": "",
                                "value": values[i]})
    return records


def emulation_metadata(mutation: str | None) -> dict:
    return {"interchange_schema": "svmg-parity-output-v1", "schema_version": SCHEMA_VERSION,
            "producer": {"kind": "python_float32_emulation", "name": "ml.parity.float32_probe",
                         "mutation": mutation, "float_type": "float32", "accumulator_type": "float32 (cộng tuần tự)",
                         "note": "Mô phỏng Python, KHÔNG phải mã C; chỉ dùng hiệu chỉnh dung sai/kiểm tra harness."}}
