from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .audit_hohai import audit_hohai
from .audit_seafar import audit_seafar
from .audit_southampton import audit_southampton


ROOT = Path(__file__).resolve().parents[2]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _feature_candidates(inventory: dict) -> list[dict]:
    # No canonical 30-item list is present in repository docs. This clearly marked
    # working inventory follows only the requested signal families and needs team approval.
    candidates = [
        ("roll_mean_60s", "roll", "60s", "mean roll"), ("roll_std_60s", "roll", "60s", "std roll"),
        ("roll_rms_60s", "roll", "60s", "RMS roll"), ("roll_p95_abs_60s", "roll", "60s", "p95 |roll|"),
        ("roll_max_abs_60s", "roll", "60s", "max |roll|"), ("roll_zero_crossing_rate_60s", "roll", "60s", "zero crossings"),
        ("pitch_mean_60s", "pitch", "60s", "mean pitch"), ("pitch_std_60s", "pitch", "60s", "std pitch"),
        ("pitch_rms_60s", "pitch", "60s", "RMS pitch"), ("pitch_p95_abs_60s", "pitch", "60s", "p95 |pitch|"),
        ("pitch_max_abs_60s", "pitch", "60s", "max |pitch|"), ("pitch_zero_crossing_rate_60s", "pitch", "60s", "zero crossings"),
        ("roll_rate_mean_60s", "gyro_roll", "60s", "mean measured roll angular rate"),
        ("roll_rate_std_60s", "gyro_roll", "60s", "std measured roll angular rate"),
        ("roll_rate_rms_60s", "gyro_roll", "60s", "RMS measured roll angular rate"),
        ("pitch_rate_mean_60s", "gyro_pitch", "60s", "mean measured pitch angular rate"),
        ("pitch_rate_std_60s", "gyro_pitch", "60s", "std measured pitch angular rate"),
        ("pitch_rate_rms_60s", "gyro_pitch", "60s", "RMS measured pitch angular rate"),
        ("accel_x_rms_60s", "accel_x", "60s", "RMS accelerometer X"),
        ("accel_y_rms_60s", "accel_y", "60s", "RMS accelerometer Y"),
        ("accel_z_rms_60s", "accel_z", "60s", "RMS accelerometer Z"),
        ("persistent_roll_offset_180s", "roll", "180s", "signed mean roll over persistent window; threshold undefined"),
        ("persistent_pitch_offset_180s", "pitch", "180s", "signed mean pitch over persistent window; threshold undefined"),
        ("roll_amplitude_growth_180s", "roll", "180s", "slope of windowed roll amplitude; estimator not specified"),
        ("pitch_amplitude_growth_180s", "pitch", "180s", "slope of windowed pitch amplitude; estimator not specified"),
        ("roll_oscillation_period_60s", "roll", "60s", "roll oscillation period"),
        ("pitch_oscillation_period_60s", "pitch", "60s", "pitch oscillation period"),
        ("roll_pitch_correlation_60s", "roll_pitch", "60s", "cross-axis correlation"),
        ("roll_angular_acceleration_60s", "gyro_roll", "60s", "derivative of measured angular rate"),
        ("pitch_angular_acceleration_60s", "gyro_pitch", "60s", "derivative of measured angular rate"),
    ]
    signals = {
        "seafar": {"roll": {"roll_degrees"}, "pitch": {"pitch_degrees"},
            "gyro_roll": {"roll_rate_rad_min"}, "gyro_pitch": {"pitch_rate_rad_min"},
            "accel_x": {"accel_x_ms2"}, "accel_y": {"accel_y_ms2"}, "accel_z": {"accel_z_ms2"}, "roll_pitch": {"roll_degrees", "pitch_degrees"}},
        "hohai": {"roll": {"Roll"}, "pitch": {"Pitch"}, "gyro_roll": set(), "gyro_pitch": set(),
            "accel_x": set(), "accel_y": set(), "accel_z": set(), "roll_pitch": {"Roll", "Pitch"}},
        "southampton": {"roll": {"Roll"}, "pitch": {"Pitch"}, "gyro_roll": {"Delta Angle X"},
            "gyro_pitch": {"Delta Angle Y"}, "accel_x": {"Accelerometer X"}, "accel_y": {"Accelerometer Y"},
            "accel_z": {"Accelerometer Z"}, "roll_pitch": {"Roll", "Pitch"}},
    }
    results = []
    for name, signal, window, definition in candidates:
        per_source = {}
        for source in ("seafar", "hohai", "southampton"):
            available = bool(signals[source][signal])
            if signal in ("gyro_roll", "gyro_pitch") and source == "southampton":
                detail = "Direct rate column exists; units row says degree/s although header calls it Delta Angle; verify semantics."
                status = "DERIVABLE_WITH_ASSUMPTIONS"
            elif signal in ("gyro_roll", "gyro_pitch") and source == "seafar":
                detail = "Direct rate column exists in rad/min; explicit calibration/provenance is absent."
                status = "DERIVABLE_WITH_ASSUMPTIONS"
            elif available and source == "hohai":
                status, detail = "DERIVABLE_WITH_ASSUMPTIONS", "Signal and supplied 50 Hz metadata exist, but there are no per-sample timestamps to validate continuity or dropped samples."
            elif available and window == "180s" and source == "southampton":
                status, detail = "AVAILABLE", "Signal and timestamp columns exist; only eligible uninterrupted runs can supply the window."
            elif available and window == "180s" and source == "seafar":
                status, detail = "AVAILABLE", "Signal and epoch timestamp exist; only eligible uninterrupted segments can supply the window."
            elif available and window == "60s" and source in ("seafar", "southampton"):
                status, detail = "AVAILABLE", "Signal and timestamp columns exist; only eligible uninterrupted sessions can supply the window."
            elif not available and signal in ("gyro_roll", "gyro_pitch") and source == "hohai":
                status, detail = "UNAVAILABLE", "No direct gyro measurement; angle differentiation would not be measured gyroscope data."
            else:
                status, detail = "UNAVAILABLE", "Required source signal is absent."
            if "amplitude_growth" in name or "oscillation_period" in name:
                if available:
                    status, detail = "DERIVABLE_WITH_ASSUMPTIONS", "Requires agreed detrending/filtering, estimator and validity rules; none defined in current contract."
            if "persistent_" in name:
                status, detail = "DERIVABLE_WITH_ASSUMPTIONS", "Mean is computable, but persistence/threshold definition and timebase must be agreed."
            if "angular_acceleration" in name and available:
                status, detail = "DERIVABLE_WITH_ASSUMPTIONS", "Computed by differentiating measured gyro rate; noise handling and units need agreement."
            if signal == "roll_pitch" and available and source == "hohai":
                status, detail = "DERIVABLE_WITH_ASSUMPTIONS", "Both angles exist, but windowed statistics need a verified sample interval."
            per_source[source] = {"status": status, "signals_found": sorted(signals[source][signal]), "detail": detail}
        results.append({"name": name, "required_raw_signal": signal, "window": window,
            "definition_intent": definition, "suitable_sources": [s for s in per_source if per_source[s]["status"] != "UNAVAILABLE"],
            "per_source": per_source})
    return results


def _make_report(inv: dict) -> str:
    sf, hh, so = inv["seafar"], inv["hohai"], inv["southampton"]
    sft = sf["time"]
    imu_runs = so["runs"]
    stats = lambda key: sf["angles_deg"][key]
    seafar_aux = "\n".join(f"| {k} | {v['min']:.6g} | {v['max']:.6g} | {v['mean']:.6g} | {v['std']:.6g} |"
        for k, v in {**sf["angular_rate_statistics"], **{k: sf["statistics"][k] for k in ("accel_x_ms2", "accel_y_ms2", "accel_z_ms2")}}.items())
    rows = []
    for r in imu_runs:
        t = r["time"] or {}
        rows.append(f"| Run {r['run_id']} | {r['sample_count']:,} | {t.get('duration_s', 0):.2f} | {t.get('sampling_hz', 0):.3f} | {r['window_eligibility']['60s']} | {r['window_eligibility']['180s']} | {t.get('gap_count', 0)} |")
    candidates = inv["feature_availability"]
    so_fields = ["Roll", "Pitch", "Accelerometer X", "Accelerometer Y", "Accelerometer Z",
                 "Delta Angle X", "Delta Angle Y", "Delta Angle Z"]
    southampton_aggregates = {}
    for field in so_fields:
        parts = [r["statistics"].get(field, {}) for r in imu_runs]
        n = sum(p.get("valid", 0) for p in parts)
        mean = sum(p.get("mean", 0) * p.get("valid", 0) for p in parts) / n if n else None
        second = sum((p.get("std", 0) ** 2 + p.get("mean", 0) ** 2) * p.get("valid", 0) for p in parts) / n if n else None
        southampton_aggregates[field] = {"valid": n, "min": min((p["min"] for p in parts if p.get("min") is not None), default=None),
            "max": max((p["max"] for p in parts if p.get("max") is not None), default=None),
            "mean": mean, "std": ((max(0, second - mean ** 2)) ** .5 if n else None),
            "missing": sum(r["missing_by_column"].get(field, 0) for r in imu_runs)}
    so_stats = "\n".join(f"| {k} | {v['valid']:,} | {v['missing']} | {v['min']:.6g} | {v['max']:.6g} | {v['mean']:.6g} | {v['std']:.6g} |"
                          for k, v in southampton_aggregates.items())
    hohai_angles = {}
    for angle in ("Roll", "Pitch"):
        parts = [s["statistics"][angle] for s in hh["sessions"]]
        n = sum(p["valid"] for p in parts)
        mean = sum(p["mean"] * p["valid"] for p in parts) / n if n else None
        second = sum((p["std"] ** 2 + p["mean"] ** 2) * p["valid"] for p in parts) / n if n else None
        hohai_angles[angle] = {"min": min(p["min"] for p in parts), "max": max(p["max"] for p in parts),
                               "mean": mean, "std": max(0, second - mean ** 2) ** .5 if n else None}
    feature_lines = ["| Feature ứng viên | Tín hiệu | Cửa sổ | Seafar | Hohai | Southampton |",
                     "|---|---|---:|---|---|---|"]
    for f in candidates:
        feature_lines.append("| `{}` | {} | {} | {} | {} | {} |".format(f["name"], f["required_raw_signal"], f["window"],
             *(f["per_source"][s]["status"] for s in ("seafar", "hohai", "southampton"))))
    return f'''# Real Dataset Audit — Smart Vessel Motion Guard

Ngày audit: {inv['audit_timestamp_utc']}. Đây là audit chất lượng dữ liệu chỉ đọc; không preprocessing, feature extraction, labeling hay training.

## 1. Tổng quan nguồn dữ liệu

| Nguồn | Phiên/run | Mẫu | Nhận xét |
|---|---:|---:|---|
| Seafar | 1 file/session | {sf['record_count']:,} | JSON có timestamp epoch ms, góc, angular rate và accelerometer. |
| Hohai | {hh['session_count']} sheet/session | {sum(s['sample_count'] for s in hh['sessions']):,} | Mỗi sheet là session riêng; sáu DOF, không có timestamp/gyro. |
| Southampton IMU | {so['imu_csv_count']} run | {sum(r['sample_count'] for r in imu_runs):,} | CSV có timestamp, roll/pitch, acceleration và ba cột Delta Angle. |

Repository hiện chỉ có feature contract **14 trường** ở `contracts/features.md` (0–13) và `FeatureVector` C ở `core/include/svmg_core.h`, cùng 14 trường. `ml/README.md` cũng nói 14 feature. Không tìm thấy danh sách 30 feature ứng viên đã được phê duyệt. Bảng 30 mục dưới đây là **working inventory tạm suy ra từ nhóm tín hiệu người dùng nêu**, không thay đổi hợp đồng/định nghĩa và cần nhóm xác nhận.

## 2. Seafar

- Số bản ghi: **{sf['record_count']:,}**; có 16 cột, tất cả parse được dưới dạng numeric; tên cột: {', '.join(sf['columns'])}.
- Timestamp: Unix epoch milliseconds; khoảng {datetime.fromtimestamp(sft['start_s'], timezone.utc).isoformat()}–{datetime.fromtimestamp(sft['end_s'], timezone.utc).isoformat()}; thời lượng quan sát {sft['duration_s']:.3f} s; median dt {sft['median_dt_s']:.6f} s, xấp xỉ {sft['sampling_hz']:.3f} Hz.
- Duplicate timestamp: {sft['duplicate_timestamps']}; bước không tăng: {sft['non_increasing_steps']}; time gap >1.5× median dt: {sft['gap_count']}; segment liên tục đủ 60 s: {sft['eligible_windows']['60s']}; đủ 180 s: {sft['eligible_windows']['180s']}.
- Roll (degree): min {stats('roll_degrees')['min']}, max {stats('roll_degrees')['max']}, mean {stats('roll_degrees')['mean']}, std {stats('roll_degrees')['std']}.
- Pitch (degree): min {stats('pitch_degrees')['min']}, max {stats('pitch_degrees')['max']}, mean {stats('pitch_degrees')['mean']}, std {stats('pitch_degrees')['std']}.
- Angular rate và accelerometer phân bố trên toàn session:

| Cột | Min | Max | Mean | Std |
|---|---:|---:|---:|---:|
{seafar_aux}
- Missing/non-finite theo cột: {json.dumps(sf['missing_by_column'], ensure_ascii=False)}.
- Tốc độ roll/pitch/yaw được ghi rad/min; có thêm yaw rate degree/min. Đơn vị gia tốc được gợi ý từ tên `*_ms2`, nhưng metadata không xác nhận. Cần rà soát mức gia tốc rất nhỏ/độ tin cậy hiệu chuẩn.

## 3. Hohai

- Workbook có **{hh['session_count']} sheet/session**, mỗi sheet 6 cột: `{', '.join(hh['sessions'][0]['columns'])}`; mẫu/sheet: {min(s['sample_count'] for s in hh['sessions']):,}–{max(s['sample_count'] for s in hh['sessions']):,}.
- Sáu cột giá trị đọc được dưới dạng numeric; unit của góc không thể xác nhận từ workbook.
- Workbook không có timestamp; sample interval được gán **0.02 s (50 Hz)** theo metadata do người dùng cung cấp từ tài liệu `ml/data/raw/hohai/Data Description Example.pdf`. PDF đúng tên/path và workbook đã được đối chiếu; môi trường thiếu `pypdf`, `PyPDF2`, `pdfminer`, `pdfplumber`, `fitz`, nên PDF **không được parse** trong lần audit này. Inventory ghi rõ nguồn xác nhận và giới hạn này.
- Metadata đơn vị: Roll/Pitch/Yaw = degree; Surge/Sway/Heave = meter. Đây là metadata tài liệu được cung cấp, không suy luận từ workbook.
- Thời lượng mỗi session tính theo `(N - 1) / 50 Hz`: {min(s['duration_s'] for s in hh['sessions']):.2f}–{max(s['duration_s'] for s in hh['sessions']):.2f} s. Sheet đủ 60 s: {sum(s['window_eligibility']['60s'] for s in hh['sessions'])}/{hh['session_count']}; đủ 180 s: {sum(s['window_eligibility']['180s'] for s in hh['sessions'])}/{hh['session_count']}.
- Số sheet có missing/non-finite cell theo scan: {sum(any(v > 0 for v in s['missing_by_column'].values()) for s in hh['sessions'])}/{hh['session_count']}.
- Roll/pitch thống kê gộp mô tả (độ): roll min/max/mean/std = {hohai_angles['Roll']['min']}/{hohai_angles['Roll']['max']}/{hohai_angles['Roll']['mean']}/{hohai_angles['Roll']['std']}; pitch = {hohai_angles['Pitch']['min']}/{hohai_angles['Pitch']['max']}/{hohai_angles['Pitch']['mean']}/{hohai_angles['Pitch']['std']}.
- Roll/pitch là góc nhưng workbook không ghi unit; không có gyro trực tiếp. Không xem đạo hàm góc là gyro đo.
- Phân bố roll/pitch theo sheet nằm trong `dataset_inventory.json` (min/max/mean/std/p05/p95); các sheet giữ tách biệt.

## 4. Southampton

- Quét được **{so['imu_csv_count']} IMU CSV**, {so['lasso_csv_count']} Lasso CSV. Test Plan: {so['test_plan'].get('rows_by_run_id', 0)} Run ID.
- Số run đủ uninterrupted 60 s: **{len(so['eligible_60s_run_ids'])}**; đủ 180 s: **{len(so['eligible_180s_run_ids'])}**. Run IDs 60s: {so['eligible_60s_run_ids']}; 180s: {so['eligible_180s_run_ids']}.
- Timestamp gap, missing count và thống kê mỗi cột/run được ghi trong inventory chi tiết. Mỗi CSV là một run độc lập, không ghép run.
- Delta Angle unit row ghi `°.s^-1` (degree/s), dù tên cột có thể gợi ý delta angle. Đây là angular-rate column trực tiếp theo metadata của CSV, nhưng cần xác nhận ý nghĩa/định hướng trục và hiệu chuẩn.
- Khả năng matching IMU↔Lasso hiện chỉ theo run ID: {len(so['run_id_matching']['matching_ids'])} ID chung; chưa merge và chưa xác minh đồng bộ timestamp.
- Điều kiện sóng theo Test Plan có wave frequency/amplitude cho run numbers: {so['test_plan']['wave_test_run_numbers']}. Có file IMU tương ứng: {so['test_plan']['wave_test_run_numbers_with_imu']}; đủ 60s: {so['test_plan']['wave_test_run_numbers_with_eligible_60s']}; đủ 180s: {so['test_plan']['wave_test_run_numbers_with_eligible_180s']}. Đây chỉ là điều kiện thí nghiệm, không diễn giải thành nhãn ML.
- Tổng hợp roll/pitch/accelerometer/angular-rate trên 47 CSV (gộp thống kê để mô tả, không tạo chuỗi dữ liệu chung):

| Cột | Mẫu hợp lệ | Missing | Min | Max | Mean | Std |
|---|---:|---:|---:|---:|---:|---:|
{so_stats}
- Missing/non-finite tổng trên các cột: {sum(sum(r['missing_by_column'].values()) for r in imu_runs)}; timestamp gaps tổng: {sum(r['time']['gap_count'] for r in imu_runs)}.

### Tóm tắt từng run IMU

| Run | Mẫu | Thời lượng (s) | Hz | Đủ 60s | Đủ 180s | Gap |
|---:|---:|---:|---:|:---:|:---:|---:|
{chr(10).join(rows)}

## 5. Feature Availability Audit

Phân loại theo nguồn: `AVAILABLE` = tín hiệu/cadence cần thiết sẵn có cho phép tính trên segment đủ cửa sổ; `DERIVABLE_WITH_ASSUMPTIONS` = thiếu định nghĩa/đơn vị/tần số đã xác nhận; `UNAVAILABLE` = thiếu tín hiệu bắt buộc. Tên feature và cách tính vẫn chỉ là đề xuất kiểm kê, không phải định nghĩa được duyệt.

{chr(10).join(feature_lines)}

Tổng feature ứng viên tạm thời: **{len(candidates)}**. Trong đó các mục period, amplitude growth, persistence và angular acceleration cần quyết định thuật toán/ngưỡng/chất lượng; không thể gán số giả hay coi rate suy ra là gyro.

## 6. Vấn đề chất lượng, đồng bộ và đơn vị

- Hohai tần số và đơn vị dùng metadata tài liệu do người dùng cung cấp; vì không có per-sample timestamp, continuity/dropout không thể kiểm tra riêng cho từng sheet. PDF không được parse do thiếu dependency trong môi trường.
- Seafar rate dùng rad/min, Southampton degree/s; chuẩn hóa đơn vị chỉ nên diễn ra sau khi nhóm thống nhất trục/quy ước và xác minh nguồn. Seafar accel có giá trị rất nhỏ so với Southampton (xấp xỉ trọng lực ở trục Z), cần làm rõ scale/calibration/đơn vị.
- Southampton time stamp bắt đầu ở mốc khác nhau giữa runs; so sánh thời gian tuyệt đối giữa các nguồn/run không có căn cứ. Lasso có matching ID không đồng nghĩa đồng bộ thời gian.
- Chỉ định nghĩa gap dùng kiểm toán: step >1.5× median positive step; đây là cờ phát hiện để review, không phải dữ liệu đã được sửa.
- Missing values: Seafar bảng đếm theo field trong inventory; Southampton theo cột/run; Hohai theo sheet/cột. Không nội suy hay thay bằng 0.

## 7. Khuyến nghị nguồn

Southampton phù hợp nhất để đánh giá thực nghiệm roll/pitch dynamics trên cửa sổ 60/180 s: có timestamp, accelerometer và rate columns, nhiều run và Test Plan mô tả điều kiện. Chỉ dùng các run qua kiểm tra continuity và xác nhận đơn vị Delta Angle. Seafar hữu ích cho dữ liệu thực với timestamp và nhiều trường IMU nhưng cần xác minh scale/đơn vị và tính chất liên tục. Hohai có thể cung cấp cửa sổ thời gian dựa trên cadence 50 Hz được cung cấp; do workbook thiếu timestamp nên không thể kiểm chứng dropout/gap trong mỗi session.

## 8. Quyết định cần nhóm xác nhận

1. Phê duyệt danh sách/tên/định nghĩa của 30 ứng viên; hiện repository có contract 14 mục, không có danh sách 30 chính thức.
2. Hohai: khi có PDF reader, đối chiếu trực tiếp metadata 50 Hz/units với tài liệu; do workbook không có timestamp nên xác nhận cách chấp nhận giới hạn kiểm tra dropout/gap.
3. Southampton: xác nhận ý nghĩa cột Delta Angle, trục/quy ước dấu, scale và đồng hồ đồng bộ với Lasso.
4. Seafar: xác nhận đơn vị/calibration của accelerometer, nguồn đo rate và tiêu chuẩn quality/gap.
5. Chốt cách tính oscillation period, amplitude growth, persistent offset (threshold/duration), angular acceleration, detrending/filtering, và quy tắc minimum valid samples.
6. Chốt dùng feature contract 14 hiện tại hay quy trình thay đổi contract sau khi audit; không sửa contract trong bước này.

## 9. Tệp audit

- `ml/audit/audit_seafar.py`, `audit_hohai.py`, `audit_southampton.py`, `audit_all.py`.
- `ml/audit/dataset_inventory.json`: metadata/statistics tổng hợp, không chứa raw samples.
- Chạy lại từ repository root: `python -m ml.audit.audit_all`; kiểm thử: `python -m unittest ml.audit.test_audit -v`.
- Tệp raw không được chỉnh sửa. Không preprocessing, merge, labeling hay training.
'''


def run() -> dict:
    raw = ROOT / "ml/data/raw"
    inventory = {
        "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "read-only real dataset quality audit",
        "seafar": audit_seafar(raw / "seafar/cleaned_imu_gps_data.json"),
        "hohai": audit_hohai(raw / "hohai/6-DOF ship motions Data.xlsx"),
        "southampton": audit_southampton(raw / "southampton"),
        "feature_contract": {"document": "contracts/features.md", "documented_feature_count": 14,
            "c_feature_vector_count": 14, "candidate_30_list_found": False},
    }
    inventory["feature_availability"] = _feature_candidates(inventory)
    out = ROOT / "ml/audit"
    write_json(out / "dataset_inventory.json", inventory)
    (out / "real_dataset_audit_report.md").write_text(_make_report(inventory), encoding="utf-8")
    return inventory


def main():
    inventory = run()
    print("Audit complete:", len(inventory["feature_availability"]), "provisional candidates;",
          len(inventory["southampton"]["eligible_60s_run_ids"]), "Southampton runs >=60s;",
          len(inventory["southampton"]["eligible_180s_run_ids"]), "runs >=180s")

if __name__ == "__main__": main()
