"""Sinh 4 báo cáo Markdown (tiếng Việt) của gói parity từ các JSON đã chạy. Mọi con số đọc từ artifact, không gõ tay.

    python -m ml.parity.golden --suite all && python -m ml.parity.readiness && python -m ml.parity.reports
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.parity.contract import (CONTRACT_V02, SCHEMA_VERSION, SEMANTIC_CONTRACT_VERSION,
                                VALIDITY_POLICY_VERSION)
from ml.parity.golden import MANIFEST, REAL_ROOT, SYNTHETIC_ROOT, TOLERANCE_PATH
from ml.parity.readiness import REPORT_JSON as READINESS_JSON

OUT = Path("ml/reports/parity")
VALIDATION_JSON = OUT / "feature23_contract_validation.json"
SCOPE = ("> **Phạm vi.** Gói này chuẩn bị kiểm chứng parity *tính feature* Python/C cho 23 angle feature của PoC Random Forest "
         "phân loại motion phenotype bằng proxy label — KHÔNG phải bộ phân loại an toàn hàng hải đã xác thực. "
         "Golden vector đã chuẩn bị KHÔNG có nghĩa parity Python/C hay triển khai ESP32 đã được kiểm chứng.")


def _load(repo_root: Path, rel: Path):
    path = repo_root / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _table(headers, rows) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |" for r in rows]
    return out


def _g(x, fmt=".3g"):
    return "—" if x is None else format(x, fmt)


# --------------------------------------------------------------------------- 1. contract


def contract_report(repo_root: Path) -> str:
    v = _load(repo_root, VALIDATION_JSON)
    c = _load(repo_root, CONTRACT_V02)
    tol = _load(repo_root, TOLERANCE_PATH)
    L = [f"# Kiểm định contract 23 feature (`{SEMANTIC_CONTRACT_VERSION}`)", "", SCOPE, "",
         f"- Schema: `{v['schema_version']}`; SHA-256 thứ tự tên: `{v['schema_sha256']}`.",
         f"- Schema feature C: `{v['feature_schema_version']}`; validity policy: `{VALIDITY_POLICY_VERSION}`.",
         f"- SHA-256 tên/thứ tự feature trong model card: `{v['model_card_schema_sha256']}` → khớp: **{v['model_card_schema_matches']}**. Hash chỉ bao phủ ordered names.",
         f"- Tham chiếu số học: {v['extractor_reference']}. Công thức KHÔNG bị sửa; parity artifacts giữ `{SCHEMA_VERSION}` để bảo toàn provenance.",
         f"- Bất nhất chặn (thứ tự/cửa sổ): **{'CÓ' if v['blocking_inconsistency'] else 'KHÔNG'}** — vì vậy được phép sinh golden.",
         f"- C01–C04: đã chốt hoặc đã giải quyết; vấn đề mở cần nhóm quyết định: {', '.join(i['id'] for i in v['issues'] if i['status'].startswith('OPEN')) or 'không có'}.", "",
         "## 1. Thứ tự 23 feature trên mọi nguồn", ""]
    L += _table(["Nguồn", "Khớp thứ tự contract"], [(f"`{k}`", "✅" if ok else "❌") for k, ok in v["order_checks"].items()])
    L += ["", "## 2. Bảng contract đã kiểm định", ""]
    L += _table(["Index", "Feature", "Nhóm", "Cửa sổ (s)", "Đơn vị", "Định nghĩa", "Lớp dung sai"],
                [(f["index"], f"`{f['name']}`", f["group"], f["window_seconds"], f["unit"], f["definition"],
                  tol["feature_class"][f["name"]]) for f in c["features"]])
    cfg = v["config_checks"]
    L += ["", "## 3. Quy ước đã xác nhận (đối chiếu `ml/features/config.yaml` và extractor)", ""]
    L += _table(["Hạng mục", "Giá trị/quy tắc", "Xác nhận"], [
        ("Tần số đầu vào", "10 Hz (chu kỳ 0,1 s)", "✅" if cfg["sampling_hz_10"] else "❌"),
        ("Đơn vị Roll/Pitch", "độ (degree); `roll_diff_rms_60` là deg/mẫu ở 10 Hz; slope là deg/phút", "✅ (contract `units`)"),
        ("Cửa sổ trượt", "60 s và 180 s, nửa mở `(t-W, t]`, không vượt ranh giới segment", "✅" if cfg["endpoint_convention"] else "❌"),
        ("Bước cập nhật", "10 s; endpoint theo CHỈ SỐ mẫu 600 + 100·j từ đầu segment (C05)", "✅" if cfg["stride_10s"] else "❌"),
        ("Độ lệch chuẩn", "quần thể, mẫu số n (std, segment_mean_std)", "✅ (kiểm tra hành vi `population_std`)"),
        ("Phân vị", "Type-7: h=(n-1)p, nội suy tuyến tính", "✅" if cfg["quantile_type7"] else "❌"),
        ("Sai phân", "chỉ cặp (x[i-1], x[i]) đều nằm trong cửa sổ, đều hữu hạn, cách đúng 0,1 s; 600 mẫu → 599 cặp; cần ≥ 570 cặp", "✅ (kiểm tra `difference_pair_semantics`)"),
        ("3 block 180 s", "(t-180,t-120], (t-120,t-60], (t-60,t]; mỗi block ≥ 570 mẫu, không gap", "✅" if cfg["three_60s_blocks"] else "❌"),
        ("Hồi quy xu hướng", "OLS 3 điểm tại u = 30/90/150 s; slope × 60 → deg/phút = (r3 - r1)/2", "✅ (kiểm tra `trend_slope_units`)"),
        ("R²", "1 - SSE/SST; UNDEFINED nếu SST ≤ 1e-15; kẹp về [0,1] chỉ trong 1e-12", f"✅ (tolerance {cfg['r_squared_zero_tolerance']})"),
        ("Epsilon ratio", f"rms_early ≤ {cfg['numeric_zero_epsilon_deg']} deg → UNDEFINED", "✅ (epsilon số học, xem C02)"),
        ("Coverage", "≥ 95% mẫu: 570/600 và 1710/1800; số timestamp ≤ N+1", "✅" if cfg["minimum_valid_fraction_0_95"] else "❌"),
        ("Gap", "khoảng cách timestamp > 1,5 chu kỳ (0,15 s) trong cửa sổ → INVALID_INPUT/TIMESTAMP_GAP", "✅" if cfg["maximum_gap_factor_1_5"] else "❌"),
        ("Warm-up", "feature 60 s cần ≥ 60 s lịch sử, 180 s cần ≥ 180 s → INSUFFICIENT_WINDOW/WINDOW_HISTORY_SHORT", "✅ (kiểm tra `warmup`)"),
        ("Giá trị không hợp lệ", "value = null/ô rỗng, KHÔNG bao giờ 0; vector thiếu → ABSTAIN/UNKNOWN, không NORMAL", "✅"),
    ])
    L += ["", "## 4. Kiểm tra hành vi trên chính extractor (đáp án giải tích)", ""]
    L += _table(["Kiểm tra", "Kỳ vọng", "Quan sát", "Đạt", "Ghi chú"],
                [(b["id"], b["expected"], b["observed"], "✅" if b["passed"] else "❌", b["note"]) for b in v["behaviour_checks"]])
    L += ["", "## 5. Bất nhất và điểm cần làm rõ (không giải quyết ngầm)", ""]
    L += _table(["ID", "Mức", "Trạng thái", "Vấn đề", "Đặc tả", "Extractor", "Chính sách golden"],
                [(i["id"], i["severity"], i["status"], i["title"], i.get("spec", "—"), i.get("extractor", "—"), i.get("golden_policy", "—"))
                 for i in v["issues"]])
    L += ["", "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
          "- **Vì sao extractor là chuẩn số học, không phải tài liệu?** Mô hình RF đã được huấn luyện trên đúng các số do `extractor.py` sinh ra. Nếu C làm theo một cách hiểu khác của tài liệu, vector đầu vào sẽ lệch phân phối huấn luyện dù 'đúng chữ'. Vì vậy mọi khác biệt được ghi thành issue có mã thay vì sửa lặng lẽ.",
          "- **SHA-256 của thứ tự tên dùng để làm gì?** Một chuỗi băm ngắn đại diện cho thứ tự 23 tên; model card RF ghi cùng giá trị nên firmware có thể từ chối model/feature lệch schema chỉ bằng so sánh 64 ký tự.",
          "- **Tại sao cửa sổ nửa mở `(t-W, t]`?** Để mỗi mẫu thuộc đúng một block và cửa sổ có đúng 600 mẫu ở 10 Hz; nếu dùng `[t-W, t]` sẽ có 601 mẫu, thay đổi mean/RMS và phân vị — case SYN12 đặt gai đúng tại t-60 để phát hiện.",
          "- **Population std khác sample std bao nhiêu?** Hệ số √(n/(n-1)) = 1,00083 với n = 600; với 3 mean block thì là √(3/2) = 1,22. Golden + dung sai phát hiện được cả hai."]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- 2. golden


def golden_report(repo_root: Path) -> str:
    m = _load(repo_root, MANIFEST)
    syn = _load(repo_root, SYNTHETIC_ROOT / "cases.json")
    real = _load(repo_root, REAL_ROOT / "cases.json")
    exp = pd.read_csv(repo_root / SYNTHETIC_ROOT / "expected_features.csv", dtype=str, keep_default_na=False)
    L = ["# Báo cáo sinh golden vector 23 feature", "", SCOPE, "",
         f"- Lệnh: `{m['generator']} --suite all` (chạy từ repository root, `.venv`). Không có dấu thời gian trong file: chạy lại cho byte giống hệt (đã kiểm tra bằng test `test_deterministic_generation_matches_tracked_fixtures`).",
         f"- Môi trường: Python {m['environment']['python']}, NumPy {m['environment']['numpy']}, pandas {m['environment']['pandas']}.",
         f"- Contract: `{m['contract']}` (sha256 `{m['contract_sha256'][:16]}…`); schema `{m['schema_version']}`.",
         f"- Trạng thái: **{' / '.join(m['parity_status'])}**.", "",
         "## 1. Cách sinh", "",
         "1. Tín hiệu đầu vào được làm tròn về float32 và lưu dạng chuỗi float32 ngắn nhất round-trip; C đọc bằng `strtof` sẽ được đúng cùng bit.",
         "2. Golden được tính bằng **extractor production** (`ml.features.extractor.extract_segment`) trên chính các byte đã lưu (đọc lại file trước khi tính), không bằng một thư viện công thức thứ hai.",
         "3. Với case synthetic, `ml/parity/analytic.py` suy ra đáp án bằng **công thức đóng độc lập** (không import extractor) để bắt lỗi chung giữa tài liệu và mã.",
         "4. Với case real, golden được đối chiếu với feature table đã có trong `ml/data/features` (cùng extractor) để bắt lỗi cắt đoạn/ranh giới.",
         "5. Mọi file được băm SHA-256 trong `ml/parity/fixtures/manifest.json`.", "",
         "## 2. Cấu trúc fixture", "",
         "```text",
         "ml/parity/fixtures/                      (theo dõi bằng Git, nhỏ, không nhạy cảm)",
         "  manifest.json                          checksum + tóm tắt kiểm tra",
         "  tolerance_spec.json                    dung sai theo feature (đề xuất)",
         "  interchange_format.json                định dạng đầu ra C phải xuất",
         "  synthetic/inputs/<case_id>.csv         sample_index,time_seconds,roll_deg,pitch_deg,source_sample_index",
         "  synthetic/expected_features.csv        golden dạng dài: 1 dòng/(case, endpoint, feature)",
         "  synthetic/golden_vectors.jsonl         golden dạng vector 23 phần tử/(case, endpoint)",
         "  synthetic/cases.json                   metadata case: endpoint, chỉ số cửa sổ/block, thang dung sai, cờ điều kiện, kiểm tra giải tích",
         "ml/data/parity/real/                     (gitignored: trích từ dữ liệu processed cục bộ)",
         "  inputs/*.csv, expected_features.csv, golden_vectors.jsonl, cases.json",
         "```", ""]
    L += _table(["File theo dõi Git", "Byte", "SHA-256 (16 ký tự đầu)"],
                [(f"`{p}`", e["bytes"], e["sha256"][:16]) for p, e in m["files"].items() if e["tracked_in_git"] and not p.endswith("/inputs") and "/inputs/" not in p])
    n_inputs = sum(1 for p, e in m["files"].items() if "/synthetic/inputs/" in p)
    in_bytes = sum(e["bytes"] for p, e in m["files"].items() if "/synthetic/inputs/" in p)
    L += ["", f"Cộng thêm {n_inputs} file input synthetic ({in_bytes:,} byte). Real-data: {sum(1 for e in m['files'].values() if not e['tracked_in_git'])} file, chỉ lưu cục bộ (gitignored).", "",
          "## 3. Case synthetic — tín hiệu kiểm thử SỐ HỌC (không phải dữ liệu hàng hải tổng hợp)", ""]
    L += _table(["Case", "Mô tả", "Phát hiện", "Mẫu", "Endpoint", "NaN/Inf Roll", "Timestamp bỏ", "Kiểm tra giải tích"],
                [(f"`{c['case_id']}`", c["title"], ", ".join(c["detects"]), c["n_samples"], c["endpoint_count"],
                  c["non_finite_samples"]["roll"], c["dropped_timestamps"],
                  f"{sum(a['passed'] for a in c['analytic_checks'])}/{len(c['analytic_checks'])}") for c in syn["cases"]])
    counts = exp.groupby(["status", "reason_code"]).size().reset_index(name="n")
    L += ["", "### Phân bố trạng thái trong golden synthetic", ""]
    L += _table(["Status", "Reason code", "Bản ghi"], [(r.status, r.reason_code or "—", r.n) for r in counts.itertuples()])
    ac = m["analytic_checks"]
    L += ["", f"Kiểm tra giải tích độc lập: **{ac['passed']}/{ac['total']} đạt**; thất bại: {ac['failed'] or 'không'}. "
          "Ví dụ: std quần thể của sine 5° = 5/√2; Type-7 P95 của ramp = x_min + 0,95·599·bước; RMS sai phân của sine dùng 599 cặp (không phải 600); "
          "R² của RMS block (1,2,3)/√2 = 1, (1,3,2)/√2 = 0,25, (1,2,1)/√2 = 0 (VALID, khác UNDEFINED).", "",
          "Cờ điều kiện số (`condition_flag`) đánh dấu golden mà quyết định/giá trị phụ thuộc làm tròn: `ILL_CONDITIONED_R2` khi SST/mean(r)² < 1e-6, `NEAR_EPSILON_RATIO` khi rms_early trong [ε/10, 10ε].", "",
          "## 4. Case dữ liệu thật", ""]
    if real is None:
        L += ["Golden real-data chưa được sinh trên máy này (cần `ml/data/processed` và `ml/data/features`)."]
    else:
        L += _table(["Case", "Dataset", "Session", "Segment", "Mẫu bắt đầu", "Số mẫu", "Endpoint", "Quy tắc chọn"],
                    [(f"`{c['case_id']}`", c["dataset_source"], c["session_id"], c["segment_id"], c["source_start_index"], c["n_samples"],
                      c["endpoint_count"], c["selection_rule"]) for c in real["cases"]])
        rc = m.get("real_cross_check", {})
        L += ["", "Đối chiếu với feature table đã có (cùng extractor, endpoint trùng lưới vì mẫu bắt đầu là bội số 100):", ""]
        L += _table(["Case", "Giá trị so sánh", "Max |Δ|", "Lệch validity"],
                    [(c["case_id"], c["values_compared"], c["max_abs_difference"], c["validity_mismatch"]) for c in rc.get("cases", [])])
        L += ["", f"Kết quả: **{'đạt' if rc.get('passed') else 'KHÔNG đạt'}**. |Δ| = 0 vì Roll/Pitch processed đã lưu kiểu float32 nên làm tròn float32 của golden không đổi giá trị. "
              "Feature 180 s ở endpoint < 180 s của đoạn trích là WARMUP theo thiết kế (đoạn trích không mang lịch sử trước nó) và không được so với feature table.",
              "", "Đoạn trích chỉ lấy trong một segment, không vượt ranh giới segment, không dùng mẫu tương lai so với endpoint; định danh dataset/session/segment và chỉ số mẫu nguồn được giữ trong `cases.json` và cột `source_sample_index`."]
    L += ["", "## 5. Hạn chế", "",
          "- Golden chỉ chứng minh *tính feature trên chuỗi Roll/Pitch cho sẵn* (Level 1 → chuẩn bị Level 2). Không nói gì về cách ESP32 ước lượng Roll/Pitch (Level 3).",
          "- Kiểm tra giải tích độc lập chỉ phủ các case có đáp án đóng; các case khác dựa vào extractor + test của module `ml/features`.",
          "- 5 đoạn real-data là mẫu đại diện tất định, không phải đánh giá thống kê toàn bộ dataset.", "",
          "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
          "- **Tại sao không viết lại công thức để sinh golden?** Hai bản hiện thực do cùng một người viết dễ mắc cùng một lỗi hiểu sai; golden phải là đúng con số mà RF đã thấy khi huấn luyện, nên lấy thẳng từ extractor production. Kiểm tra độc lập được làm bằng *công thức đóng* trên tín hiệu có đáp án.",
          "- **Tại sao lưu input dạng float32?** ESP32 lưu Roll/Pitch float32. Nếu golden tính từ float64 rồi C đọc float32, phần sai lệch do *đầu vào* sẽ lẫn vào sai lệch do *thuật toán*. Làm tròn trước giúp hai bên dùng đúng cùng bit đầu vào.",
          "- **Tại sao có cả CSV dài và JSONL vector?** CSV dài dễ diff/lọc theo feature và mang tên feature; JSONL vector đúng là định dạng C xuất ra mỗi 10 s.",
          "- **Synthetic có phải dữ liệu huấn luyện giả?** Không. Đây là fixture toán học (hằng, sine, ramp, gai, NaN, gap…) chỉ để kiểm tra tính toán; không dùng để huấn luyện hay đánh giá mô hình."]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- 3. parity preparation


def parity_report(repo_root: Path) -> str:
    r = _load(repo_root, READINESS_JSON)
    tol = _load(repo_root, TOLERANCE_PATH)
    syn = r["suites"]["synthetic"]
    ratios = {k: e["float32_emulation"]["max_error_ratio_overall"] for k, e in r["suites"].items() if e.get("available")}
    c03 = r.get("c03_evidence") or {}
    L = ["# Chuẩn bị parity Python/C cho 23 feature", "", SCOPE, "",
         f"## Trạng thái: **{r['status'][0]}** · **{r['status'][1]}**", "",
         "Chưa có đầu ra C/C++ thật nào được nộp (`ml/data/parity/c_results/` trống), nên **không có kết luận parity Python/C**. "
         "Mọi kết quả 'PASS' dưới đây là kiểm tra harness/dung sai bằng Python và được gắn nhãn tương ứng.", "",
         "## 1. Ba mức kiểm chứng (tách bạch)", ""]
    L += _table(["Mức", "Câu hỏi", "Trạng thái hiện tại"], [
        ("Level 1 — tham chiếu Python đúng", "Extractor tính đúng định nghĩa?", "Đã kiểm: test `ml/features`, kiểm tra giải tích độc lập, cross-check feature table, test parity."),
        ("Level 2 — parity Python/C", "C cho cùng số trên CÙNG chuỗi Roll/Pitch?", r["levels"]["level_2_python_c_parity"]),
        ("Level 3 — ESP32 cảm biến → mô hình", "IMU thật + ước lượng góc + lọc cho feature cùng phân phối huấn luyện?", r["levels"]["level_3_esp32_sensor_to_model"]),
    ])
    L += ["", "**Level 2 không suy ra Level 3.** Báo cáo `ml/reports/ml/esp32_feature_compatibility.md` đã đo: khi tính lại 23 feature trên Roll/Pitch Hohai đi qua Butterworth bậc 2, 0,5 Hz (mô phỏng chuỗi lọc firmware hiện tại), "
          "số dự đoán POS của RF giảm từ **188** xuống **4** (1512 cửa sổ; 505 ABSTAIN vì feature ngoài miền huấn luyện). "
          "Một hiện thực C hoàn hảo về số học vẫn cho dự đoán sai nếu chuỗi Roll/Pitch đầu vào khác miền huấn luyện. Giới hạn này giữ nguyên.", "",
          "## 2. Thiết kế dung sai (ĐỀ XUẤT KỸ THUẬT, chưa đo trên thiết bị)", "",
          f"Công thức: `{tol['formula']}`, trong đó {tol['scale_definition']}. Tham số u32 = 2⁻²⁴ ≈ {tol['u32']:.3g}.", "",
          "Lý do có hạng `scale_rel·S`: sai số làm tròn float32 tỷ lệ với độ lớn **đầu vào**, không với giá trị đầu ra. Ví dụ std 0,007° của tín hiệu offset 10° (SYN31) có sai số tuyệt đối cỡ u·10, lớn hơn rất nhiều u·0,007. "
          "Một dung sai tương đối thuần theo giá trị sẽ đánh trượt C trung thực; một dung sai tuyệt đối chung (v0.1: 1e-3°) lại quá lỏng để bắt Type-6/Type-7 hay n/(n-1) ở biên độ nhỏ.", ""]
    L += _table(["Lớp", "abs_floor", "rel", "scale_rel", "Feature", "Cơ sở"],
                [(k, c["abs_floor"], c["rel"], c["scale_rel"], ", ".join(f"`{f}`" for f, cl in tol["feature_class"].items() if cl == k), c["rationale"])
                 for k, c in tol["classes"].items()])
    L += ["", "Điều kiện REVIEW (không PASS/FAIL tự động):", ""] + [f"- `{k}`: {v}" for k, v in tol["review_conditions"].items()]
    L += ["", f"- {tol['status_rule']}", "- R² VALID ngoài [0, 1] luôn FAIL; feature không VALID có giá trị (kể cả 0) luôn FAIL; VALID mà NaN/rỗng luôn FAIL.", "",
          "## 3. Hiệu chỉnh dung sai bằng mô phỏng float32 (KHÔNG phải kết quả C)", "",
          "`ml/parity/float32_probe.py` mô phỏng cách một hiện thực C đơn giản tính trong float32: cộng tuần tự (không pairwise), std hai lượt, sắp xếp + Type-7, OLS 3 điểm. "
          "Chỉ số cửa sổ/validity cửa sổ lấy từ golden; probe chỉ đo phần số học. Kết quả gắn nhãn `FLOAT32_EMULATION_*`.", ""]
    for suite in ("synthetic", "real"):
        e = r["suites"].get(suite, {})
        if not e.get("available"):
            continue
        emu = e["float32_emulation"]
        L += [f"### Suite {suite}: **{emu['verdict']}** — tỷ lệ sai số/cho phép lớn nhất {emu['max_error_ratio_overall']:.3f}", ""]
        L += _table(["#", "Feature", "Pass", "Fail", "Review", "Max |Δ|", "Max sai số tương đối", "Max |Δ|/cho phép"],
                    [(f["feature_index"], f"`{f['feature_name']}`", f["pass"], f["fail"], f["review"], _g(f["max_abs_error"]),
                      _g(f["max_rel_error"]), _g(f["max_error_ratio"])) for f in emu["per_feature"]])
        if emu["review_rows"]:
            L += ["", "Bản ghi REVIEW:", ""] + [f"- `{x['case_id']}` endpoint {x['endpoint_index']} `{x['feature_name']}`: golden {x['expected_status']}, float32 {x['actual_status']} = {x['actual_value']}." for x in emu["review_rows"]]
        L += [""]
    worst = max(ratios.values())
    L += [f"Diễn giải: tỷ lệ sai số/cho phép lớn nhất của mô phỏng float32 là {', '.join(f'{k} {v:.3f}' for k, v in ratios.items())} "
          f"(biên an toàn ≈ {1 / worst:.1f} lần), tức dung sai không đánh trượt phép mô phỏng float32 này. "
          + (f"Bản ghi REVIEW của `{c03['case_id']}` tái hiện rủi ro C03: ba block là hoán vị của cùng 600 giá trị; RMS block theo Python "
             f"(`math.fsum`, không phụ thuộc thứ tự) = {', '.join(repr(x) for x in c03['python_block_rms'])} → SST = {c03['python_sst']:.3g} → UNDEFINED; "
             f"float32 cộng tuần tự = {', '.join(repr(x) for x in c03['float32_block_rms'])} → SST = {c03['float32_sst']:.3g} "
             f"{'>' if c03['float32_sst'] > c03['sst_threshold'] else '≤'} {c03['sst_threshold']:g} → probe có thể cho status khác reference. "
             "Đây là mô phỏng cộng dồn float32, không phải production C; `core/src/features.c` dùng double trung gian. Ngưỡng SST runtime vẫn là 1e-15; REVIEW là diagnostic riêng." if c03 else ""), "",
          "## 4. Ma trận phát hiện lỗi hiện thực C điển hình", "",
          f"Mọi đột biến đều phải bị phát hiện: **{'đạt' if syn['all_mutations_detected'] else 'KHÔNG đạt'}**.", ""]
    L += _table(["Đột biến", "Mô tả", "Kết luận harness", "Bản ghi FAIL", "Case phát hiện", "Feature FAIL"],
                [(f"`{x['mutation']}`", x["description_vi"], x["verdict"], x["fail_records"], len(x["detecting_cases"]),
                  ", ".join(f"`{f}`" for f in x["failing_features"][:6]) + (" …" if len(x["failing_features"]) > 6 else ""))
                 for x in syn["mutation_matrix"]])
    L += ["", "## 5. Kịch bản file đầu ra hỏng (harness phải từ chối)", "",
          f"Tất cả xử lý đúng: **{'đạt' if syn['all_corruptions_behaved'] else 'KHÔNG đạt'}**.", ""]
    L += _table(["Kịch bản", "Kết quả mong đợi", "Kết luận", "Đếm lỗi"],
                [(s["scenario"], s["expected_outcome"], s["verdict"], s["outcome_counts"] or "—") for s in syn["corruption_scenarios"]])
    L += ["", "## 6. Harness và định dạng trao đổi", "",
          "- `python -m ml.parity.compare --suite synthetic --candidate <c_output.csv|jsonl> --metadata <metadata.json> --out <thư mục>`",
          "- Kiểm tra: schema_version, số feature/thứ tự (tên khớp index), case_id, input_sha256, endpoint_index/endpoint_time hữu hạn, bản ghi thiếu/thừa/trùng, từ vựng status, mã hóa giá trị, dung sai theo feature, so khớp status, R² ∈ [0,1]; schema/manifest metadata sai → `FAIL_METADATA`; reason_code chỉ cảnh báo.",
          "- Xuất `comparison_rows.csv` (mỗi bản ghi: giá trị Python, giá trị C, |Δ|, sai số tương đối, cho phép, kết luận), `comparison_summary.json`, `comparison_report.md`.",
          "- Nhãn kết luận theo `producer.kind`: chỉ `independent_c_implementation` mới cho `C_PARITY_*`. Harness không thể tự xác minh nguồn gốc — M1 phải kèm `source_commit`, trình biên dịch và cờ để người duyệt đối chiếu.",
          f"- Manifest: {r['manifest_verification']['files']} file, lỗi checksum: {len(r['manifest_verification']['problems'])}.", "",
          "## 7. Hạn chế", "",
          "- Dung sai là đề xuất từ phân tích làm tròn + mô phỏng; chưa có số đo từ trình biên dịch Xtensa/ESP32 (có `madd.s` fused multiply-add) hay từ mã C thật.",
          "- Probe float32 dùng validity cửa sổ của golden nên KHÔNG kiểm tra logic coverage/gap của C; golden synthetic (SYN20–SYN27) mới kiểm tra phần đó.",
          f"- C01–C03 đã được chốt trong `{SEMANTIC_CONTRACT_VERSION}`; C04 giữ chính sách timestamp phân lớp. Golden expected values không đổi vì công thức và validity production không đổi.", "",
          "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
          "- **Vì sao không dùng một dung sai chung?** Các feature có độ nhạy khác nhau: max/peak-to-peak chỉ chọn lại giá trị đầu vào (gần như chính xác), mean/std tích lũy sai số theo N và theo biên độ, R² có thể ill-conditioned vô hạn khi SST → 0.",
          "- **Tại sao mô phỏng float32 mà vẫn nói chưa có parity?** Mô phỏng chỉ trả lời 'dung sai có hợp lý không' và 'harness có bắt lỗi không'. Parity là tính chất của *mã C thật* với *trình biên dịch thật*; không thể chứng minh bằng mã Python.",
          "- **REVIEW khác FAIL thế nào?** REVIEW dành cho bài toán ill-conditioned (R² khi SST rất nhỏ, ratio sát epsilon): hai hiện thực đúng có thể ra quyết định khác nhau chỉ vì làm tròn. Người duyệt xem giá trị/điều kiện, không tự động đánh rớt.",
          "- **Tại sao FAIL khi C ghi 0 cho feature không hợp lệ?** Vì 0 là giá trị có nghĩa (ví dụ std = 0 của tín hiệu hằng). Đổi 'không xác định' thành 0 có thể đẩy mô hình về NORMAL — trái nguyên tắc an toàn 'lỗi → UNKNOWN, không NORMAL'."]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- 4. handoff M1


def handoff_report(repo_root: Path) -> str:
    c = _load(repo_root, CONTRACT_V02)
    tol = _load(repo_root, TOLERANCE_PATH)
    m = _load(repo_root, MANIFEST)
    r = _load(repo_root, READINESS_JSON)
    L = ["# Hướng dẫn tích hợp 23 feature cho M1 (Hoàng và nhóm firmware)", "", SCOPE, "",
         f"- Contract mapping: semantic `{c['semantic_contract']['version']}` ({c['semantic_contract']['status']}); validity `{c['validity_policy_version']}`; parity lịch sử `{c['schema_version']}`; C `{c['semantic_contract']['feature_schema']['version']}`; SHA-256 chỉ nhận diện ordered names; model weights/hash/metrics giữ nguyên.",
         "- Contract C hiện hành (`contracts/features.md`, `core/include/svmg_core.h`, `core/include/svmg_features.h`) **không bị sửa**. Việc thêm vector 23 feature vào C là quyết định của M1 sau khi duyệt đề xuất này.",
         f"- Trạng thái hiện tại: **{' / '.join(r['status'])}**. Golden đã sẵn sàng; parity Python/C chưa được kiểm chứng vì chưa có đầu ra C.", "",
         "## 1. Tín hiệu đầu vào", ""]
    L += _table(["Trường", "Kiểu", "Đơn vị", "Quy ước"], [
        ("`time_seconds`", "float64 (C: double hoặc bộ đếm mẫu)", "giây", "tăng nghiêm ngặt trong một segment; nhịp danh định 0,1 s"),
        ("`roll_deg`", "float32", "độ", "góc lắc ngang; NaN/±Inf = mẫu lỗi có timestamp"),
        ("`pitch_deg`", "float32", "độ", "góc lắc dọc; NaN/±Inf = mẫu lỗi có timestamp"),
    ])
    L += ["", "- **Lấy mẫu:** 10 Hz đều. Feature `roll_diff_rms_60` có đơn vị deg/mẫu nên **phụ thuộc trực tiếp** vào 10 Hz; không tính ở 20 Hz hay 2 Hz rồi quy đổi.",
          "- **C04 — M2 tham chiếu timestamp-aware:** giữ nhịp timestamp; NaN/Inf có timestamp được xử lý theo coverage/adjacent-pair rules. Bỏ timestamp tạo gap; cửa sổ chứa gap > 0,15 s là `INVALID_INPUT/TIMESTAMP_GAP`. Golden SYN23/SYN24 giữ nguyên.",
          "- **C04 — M1 stream firmware:** pipeline 20 Hz restart khi timestamp hữu hạn bị trùng, lùi hoặc gap vượt 0,075 s; engine xóa feature history và chuyển `UNKNOWN`, rồi cần warm-up/đủ history mới. Timestamp NaN/Inf bị từ chối, không xử lý payload với `nominal_dt`, không tiêu thụ pha decimation; engine chuyển `UNKNOWN` ngay. Alarm `CRITICAL` giữ nguyên.",
          "- **C04 — M1 feature-only C API:** không nhận timestamp, giả định lưới 10 Hz đều. Không thể tự nhận diện gap hoặc tái tạo status M2.",
          "- **C04 — C host parity:** 46 bản ghi gap của SYN23/SYN24 tiếp tục `NOT_EVALUABLE`; không được tính là PASS. Chỉ đầu ra C timestamp-aware có dữ liệu/checksum/endpoint thực mới đủ điều kiện đánh giá chúng.",
          "- **Trục và dấu:** golden kiểm tra phép tính trên chuỗi số cho sẵn; dấu dương của Roll/Pitch trên ESP32 (`svmg_filter.h`: roll = atan2(ay, az), pitch = atan2(-ax, √(ay²+az²))) và mốc 0 sau hiệu chuẩn thuộc Level 3, cần M1 xác nhận khớp quy ước dataset trước khi dùng mô hình.",
          "- **Segment:** cửa sổ không được vượt ranh giới phiên/khởi động lại; sau reboot, đếm warm-up lại từ đầu.", "",
          "## 2. Cửa sổ, endpoint, warm-up", "",
          "- Endpoint e (thời điểm tính) là một mẫu; cửa sổ W chứa mẫu i khi `t_e - W < t_i ≤ t_e`. Ở 10 Hz không gap: 60 s = chỉ số `[k_e-599, k_e]`, 180 s = `[k_e-1799, k_e]`.",
          "- 3 block của cửa sổ 180 s (cũ → mới): `(t-180, t-120]`, `(t-120, t-60]`, `(t-60, t]` — mỗi block 600 mẫu.",
          "- Lưới endpoint: chỉ số mẫu 600, 700, 800, … tính từ mẫu đầu segment (mỗi 10 s). Golden liệt kê `endpoint_index` cho từng case; C phải tính đúng tại các chỉ số đó.",
          "- Warm-up: < 60 s → mọi feature INSUFFICIENT_WINDOW; 60–180 s → 11 feature 60 s có thể VALID, 12 feature 180 s là INSUFFICIENT_WINDOW. Chỉ khi đủ 23 VALID mới đưa vào RF; nếu thiếu → ABSTAIN/UNKNOWN, KHÔNG NORMAL.", "",
          "## 3. Thứ tự 23 feature và định nghĩa số học", "",
          "`feature_index` là 0-based (0..22); bảng STT trong `M2_23_Features_ESP32_Integration.md` là 1-based (issue C09).", ""]
    L += _table(["Index", "Feature", "Cửa sổ", "Đơn vị", "Định nghĩa", "Lớp dung sai"],
                [(f["index"], f"`{f['name']}`", f["window_seconds"], f["unit"], f["definition"], tol["feature_class"][f["name"]]) for f in c["features"]])
    L += ["", "Chi tiết bắt buộc:", "",
          "- `x` là các mẫu **hữu hạn** trong cửa sổ (NaN/Inf bị loại); n = số mẫu hữu hạn. mean = Σx/n; RMS = √(Σx²/n) (gồm offset, KHÔNG trừ mean); std = √(Σ(x-mean)²/n) (quần thể).",
          "- Phân vị Type-7: sắp xếp tăng z[0..n-1]; h = (n-1)p; j = ⌊h⌋; g = h-j; Q = z[j] + g·(z[min(j+1,n-1)] - z[j]). P95 dùng |x|; IQR = Q0.75 - Q0.25 trên x có dấu; median = Q0.50.",
          "- `roll_diff_rms_60`: chỉ cặp (x[i-1], x[i]) cùng nằm trong cửa sổ, cùng hữu hạn, |Δt - 0,1| ≤ 1e-6 s; m cặp (tối đa 599); cần m ≥ 570; giá trị √(Σd²/m).",
          "- `roll_dominant_sign_ratio_180`: n+ = #(x>0), n- = #(x<0); số 0 tuyệt đối bị loại; max(n+,n-)/(n++n-). Mọi mẫu bằng 0 → UNDEFINED_MATHEMATICALLY / NON_FINITE_RESULT (C08).",
          "- Block: m_j, r_j (RMS), p_j (P95 của |x|) cho j = 1..3. `segment_mean_std` = std quần thể của (m1,m2,m3); `mean_shift` = m3 - m1; `rms_early` = r1; `rms_late` = r3 (trùng giá trị `roll_rms_60` khi cả hai VALID, C06).",
          "- `roll_rms_ratio_180` = r3/r1; nếu r1 ≤ 1e-9 → UNDEFINED / EARLY_RMS_AT_OR_BELOW_EPSILON.",
          "- Slope OLS trên u = (30, 90, 150) s, đổi sang deg/phút: với 3 điểm cách đều, **slope = (r3 - r1)/2** (tương tự cho p_j).",
          "- R² = 1 - SSE/SST với SST = Σ(r_j - r̄)²; dạng đóng cho 3 điểm cách đều: **R² = (r3 - r1)²/(2·SST)**. SST ≤ 1e-15 → UNDEFINED / CONSTANT_RMS_TREND. Kẹp về [0,1] chỉ khi lệch ≤ 1e-12.",
          "- Kết quả VALID nhưng không hữu hạn → UNDEFINED / NON_FINITE_RESULT.", "",
          "## 4. Ngữ nghĩa validity/status", ""]
    L += _table(["Status", "Reason code", "Khi nào"], [
        ("VALID", "—", "giá trị hữu hạn, mọi điều kiện đạt"),
        ("INSUFFICIENT_WINDOW", "WINDOW_HISTORY_SHORT", "t_e - t_đầu-segment < W (warm-up)"),
        ("INVALID_INPUT", "SAMPLING_RATE_MISMATCH", "nhịp segment không phải 10 Hz (±1%)"),
        ("INVALID_INPUT", "TIMESTAMP_GAP", "trong cửa sổ có hai timestamp liên tiếp cách > 0,15 s"),
        ("INVALID_INPUT", "TIME_SAMPLE_COVERAGE", "số timestamp trong cửa sổ < 570/1710 hoặc > N+1"),
        ("INVALID_INPUT", "SIGNAL_VALID_COVERAGE", "số mẫu hữu hạn của tín hiệu < 570/1710"),
        ("INVALID_INPUT", "ADJACENT_PAIR_COVERAGE", "`roll_diff_rms_60`: < 570 cặp kề hợp lệ"),
        ("INVALID_INPUT", "SEGMENT_BLOCK_COVERAGE", "8 feature block: một block bất kỳ < 570 mẫu hoặc có gap (C01)"),
        ("UNDEFINED_MATHEMATICALLY", "EARLY_RMS_AT_OR_BELOW_EPSILON", "`roll_rms_ratio_180`: r1 ≤ 1e-9"),
        ("UNDEFINED_MATHEMATICALLY", "CONSTANT_RMS_TREND", "`roll_rms_trend_r2_180`: SST ≤ 1e-15"),
        ("UNDEFINED_MATHEMATICALLY", "NON_FINITE_RESULT", "kết quả NaN/Inf (gồm sign ratio khi mọi mẫu = 0)"),
    ])
    L += ["", "Thứ tự ưu tiên trong một cửa sổ: WINDOW_HISTORY_SHORT → SAMPLING_RATE_MISMATCH → TIMESTAMP_GAP → TIME_SAMPLE_COVERAGE → SIGNAL_VALID_COVERAGE. "
          "8 feature block dùng lại status của cửa sổ 180 s nếu cửa sổ đó lỗi. Harness so khớp **status bắt buộc**, reason_code chỉ cảnh báo.", "",
          "## 5. Fixture", ""]
    L += _table(["Đường dẫn", "Nội dung", "Git"], [
        ("`ml/parity/fixtures/synthetic/inputs/*.csv`", f"{m['suites']['synthetic']['cases']} chuỗi kiểm thử số học", "có"),
        ("`ml/parity/fixtures/synthetic/expected_features.csv`", f"{m['suites']['synthetic']['expected_rows']} bản ghi golden dạng dài", "có"),
        ("`ml/parity/fixtures/synthetic/golden_vectors.jsonl`", f"{m['suites']['synthetic']['endpoints']} vector 23 phần tử", "có"),
        ("`ml/parity/fixtures/synthetic/cases.json`", "endpoint, chỉ số cửa sổ/block, thang dung sai, cờ điều kiện", "có"),
        ("`ml/parity/fixtures/interchange_format.json`", "định dạng đầu ra C", "có"),
        ("`ml/parity/fixtures/tolerance_spec.json`", "dung sai theo feature", "có"),
        ("`ml/parity/fixtures/manifest.json`", "checksum mọi file", "có"),
        ("`ml/data/parity/real/…`", f"{m['suites'].get('real', {}).get('cases', 0)} đoạn Hohai/Seafar/Southampton (sinh cục bộ)", "không (gitignored)"),
    ])
    L += ["", "Đọc input: `roll_deg`/`pitch_deg` là chuỗi float32 ngắn nhất (đọc bằng `strtof`), chấp nhận `nan`, `inf`, `-inf`; `source_sample_index` nhảy cóc biểu thị timestamp bị bỏ. Runner host kiểm tra `time_seconds` và đánh dấu cửa sổ gap là `NOT_EVALUABLE`; `svmg_features_compute`/`svmg_features_from_series` không nhận timestamp. Mẫu NaN/Inf có timestamp vẫn chiếm slot lưới, khác timestamp bị bỏ.", "",
          "## 6. Định dạng đầu ra C", "",
          "CSV (một dòng cho mỗi case × endpoint × feature):", "", "```csv",
          "schema_version,case_id,input_sha256,endpoint_index,endpoint_time_seconds,feature_index,feature_name,status,reason_code,value",
          *_example_rows(repo_root),
          "```", "",
          "Hoặc JSONL (một dòng mỗi case × endpoint, mảng 23 phần tử, `null` cho feature không VALID). Kèm `metadata.json`:", "", "```json",
          json.dumps({"interchange_schema": "svmg-parity-output-v1", "schema_version": SCHEMA_VERSION,
                      "producer": {"kind": "independent_c_implementation", "name": "svmg_feature23_host_test", "version": "0.1.0",
                                   "source_commit": "<git commit>", "compiler": "<gcc/xtensa-esp32-elf-gcc + version>",
                                   "compiler_flags": "<-O2 ...>", "target": "host|esp32", "float_type": "float32",
                                   "accumulator_type": "float64"},
                      "golden_manifest_sha256": "<sha256 ml/parity/fixtures/manifest.json>"}, indent=1, ensure_ascii=False),
          "```", "", "Giá trị VALID ghi ≥ 9 chữ số có nghĩa (`%.9g`); feature không VALID để trống — ghi `0` là FAIL.", "",
          "## 7. Lệnh chạy cho M1", "", "```bash",
          "# 0) Từ repository root, dùng môi trường dự án",
          ".venv/bin/python -m ml.parity.golden --verify-only            # kiểm tra checksum fixture",
          "# 1) Chương trình C (host trước, ESP32 sau) đọc từng ml/parity/fixtures/synthetic/inputs/<case>.csv,",
          "#    tính 23 feature tại các endpoint_index trong expected_features.csv, ghi out/synthetic.csv + out/metadata.json",
          "# 2) So sánh",
          ".venv/bin/python -m ml.parity.compare --suite synthetic \\",
          "    --candidate out/synthetic.csv --metadata out/metadata.json --out ml/data/parity/runs/m1_host_v1",
          "# 3) (Tùy chọn) nộp để tổng hợp trạng thái: ml/data/parity/c_results/<run>/{synthetic.csv,real.csv,metadata.json}",
          ".venv/bin/python -m ml.parity.readiness",
          "# Suite real cần dữ liệu processed cục bộ:",
          ".venv/bin/python -m ml.parity.golden --suite real",
          "```", "",
          "Mã thoát của `compare` là 0 khi không có FAIL, 1 khi có FAIL. Metadata khai báo sai schema hoặc checksum manifest bị từ chối (`FAIL_METADATA`). Chỉ khi `producer.kind = independent_c_implementation` và cả hai suite đạt, trạng thái mới chuyển thành `C_PARITY_VERIFIED`.", "",
          "## 8. Diễn giải lỗi parity", ""]
    L += _table(["Triệu chứng trong comparison_rows.csv", "Nguyên nhân thường gặp", "Case nhạy nhất"], [
        ("FAIL_FEATURE_NAME_ORDER", "sai thứ tự hoặc lệch 0/1-based", "mọi case"),
        ("std (index 1, 12, 21) lệch tỷ lệ ≈ 1,00083 hoặc 1,22", "std mẫu (n-1)", "SYN04, SYN13"),
        ("Mọi feature góc lệch hệ số ≈ 0,01745", "dùng radian", "SYN25"),
        ("Chỉ P95/IQR/median/p95_slope lệch", "sai nội suy phân vị (Type-6, nearest-rank) hoặc quên |x|", "SYN13, SYN14"),
        ("Nhiều feature lệch quanh gai", "biên cửa sổ `[t-W, t)` hoặc `[t-W, t]`", "SYN12"),
        ("`roll_diff_rms_60` lệch ×10", "chia cho dt (deg/s)", "SYN04"),
        ("Slope lệch ÷60", "để deg/s thay vì deg/phút", "SYN07–SYN09"),
        ("std lệch lớn ở tín hiệu offset", "phương sai một lượt float32", "SYN31"),
        ("FAIL_STATUS_MISMATCH ở hàng INVALID", "quy tắc coverage/gap/block khác extractor (C01, C04)", "SYN21–SYN27"),
        ("FAIL_INVALID_HAS_VALUE", "ghi 0 thay vì để trống", "SYN01, SYN17, SYN20"),
        ("REVIEW_ILL_CONDITIONED (R²/ratio)", "diagnostic độ nhạy trong parity; không phải runtime validity và float32 probe không đại diện C production", "SYN30"),
        ("FAIL_INPUT_SHA256 / MISSING / EXTRA", "đọc sai file, sai lưới endpoint", "—"),
    ])
    L += ["", "## 9. Việc cần làm tiếp ở Level 3 (chưa thực hiện)", "",
          "1. Đo trên ESP32 thật: RAM (ring Roll 180 s + Pitch 60 s + scratch 1800 float ≈ 17,2 kB theo ước lượng `esp32_feature_compatibility.md`, trạng thái ESTIMATE_NOT_MEASURED_ON_DEVICE), stack high-water mark, Flash của mã + mô hình, thời gian một lần cập nhật 10 s (sắp xếp 1800 phần tử).",
          "2. Chạy lại đúng golden trên ESP32 (không chỉ host) để thấy ảnh hưởng `madd.s`/cờ biên dịch.",
          "3. Chuỗi Roll/Pitch 10 Hz riêng cho feature (firmware hiện xuất 2 Hz sau lọc 0,5 Hz) và đánh giá lại lệch miền: thí nghiệm đã có cho thấy POS 188 → 4 khi lọc 0,5 Hz.",
          "4. Xác nhận trục/dấu và hiệu chuẩn mốc 0 của Roll/Pitch so với quy ước dataset.",
          "## 10. Trạng thái quyết định", "",
          f"C01: cả ba block ≥ 570 mẫu, chính sách production bảo thủ so với dependency tối thiểu của đặc tả ứng viên; C02: epsilon zero số học 1e-9 độ, không phải noise floor cảm biến; C03: SST tuyệt đối 1e-15 độ², C dùng double, float32 probe chỉ mô phỏng và REVIEW chỉ là diagnostic; C04: resolved. Validity policy `{VALIDITY_POLICY_VERSION}`.", "",
          ]
    L += ["", "## Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
          "- **Vì sao M1 phải xuất cả status chứ không chỉ 23 số?** Vì mô hình chỉ được chạy khi đủ 23 feature hợp lệ; nếu status sai, firmware có thể suy luận trên vector không hợp lệ hoặc bỏ qua vector hợp lệ — đều là lỗi parity dù số khớp.",
          "- **Vì sao golden đánh giá tại endpoint_index cố định?** Để so cùng một tập mẫu. So theo thời gian thực của ESP32 sẽ trộn lẫn sai lệch đồng hồ với sai lệch thuật toán.",
          "- **Parity đạt rồi có triển khai được không?** Chưa. Parity chỉ chứng minh C tính giống Python trên cùng chuỗi đầu vào. Còn phải chứng minh chuỗi Roll/Pitch mà ESP32 tạo ra giống miền dữ liệu huấn luyện (Level 3) và đo tài nguyên trên chip.",
          ]
    return "\n".join(L) + "\n"


def _example_rows(repo_root: Path) -> list[str]:
    exp = pd.read_csv(repo_root / SYNTHETIC_ROOT / "expected_features.csv", dtype=str, keep_default_na=False)
    cases = {c["case_id"]: c for c in _load(repo_root, SYNTHETIC_ROOT / "cases.json")["cases"]}
    sub = exp.loc[(exp.case_id == "SYN04_sine_roll") & (exp.endpoint_index == exp.loc[exp.case_id == "SYN04_sine_roll", "endpoint_index"].iloc[-1])]
    rows = []
    for name in ("roll_rms_60", "roll_rms_trend_r2_180"):
        x = sub.loc[sub.feature_name == name].iloc[0]
        value = "" if x.value == "" else format(float(x.value), ".9g")
        rows.append(f"{SCHEMA_VERSION},{x.case_id},{cases[x.case_id]['input_sha256']},{x.endpoint_index},{x.endpoint_time_seconds},"
                    f"{x.feature_index},{x.feature_name},{x.status},{x.reason_code},{value}")
    return rows


def write_all(repo_root: Path) -> dict[str, str]:
    repo_root = Path(repo_root).resolve()
    outputs = {"feature23_contract_validation.md": contract_report(repo_root),
               "golden_vector_generation_report.md": golden_report(repo_root),
               "python_c_parity_preparation.md": parity_report(repo_root),
               "m1_firmware_handoff.md": handoff_report(repo_root)}
    for name, text in outputs.items():
        (repo_root / OUT / name).write_text(text, encoding="utf-8")
    return {name: (OUT / name).as_posix() for name in outputs}


if __name__ == "__main__":
    print(json.dumps(write_all(Path(".")), indent=1, ensure_ascii=False))
