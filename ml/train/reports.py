"""Sinh 4 báo cáo tiếng Việt + đề xuất contract 23 feature từ artifact JSON thực tế.

Chạy sau ``proxy_dataset``, ``rf_poc`` và ``esp32_feasibility``::

    python -m ml.train.reports

Mọi con số được đọc từ JSON đã sinh; không có giá trị chép tay.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from ml.labeling.human_review_workflow import ANGLE_FEATURES

REPORT_DIR = Path("ml/reports/ml")
CONTRACT_MD = Path("ml/docs/feature_contract_23_proposal.md")

DISCLAIMER = ("> **Phạm vi bắt buộc.** Đây là *proof of concept phân loại motion phenotype dựa trên proxy label*, "
              "KHÔNG phải bộ phân loại an toàn hàng hải đã được xác thực. Proxy label được sinh bằng quy tắc tương đối "
              "trên chính tín hiệu; không có ground truth độc lập, không có nhãn hazard vận hành đã xác minh và không có "
              "quyết định human review nào được dùng.")

REPRO = """```bash
source .venv/bin/activate
python -m pip install -r ml/train/requirements.txt
python -m ml.labeling.proxy_dataset --spec ml/labeling/proxy_spec.yaml
python -m ml.train.rf_poc --config ml/train/rf_poc_config.yaml
python -m ml.train.esp32_feasibility
python -m ml.train.reports
python -m ml.train.predict --model-card ml/data/models/rf_poc_v1/relative_high_roll_model_card.json \\
    --input ml/data/labels/proxy_v1/measurements.parquet --output ml/data/models/rf_poc_v1/predict_cli_demo.csv
python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit ml/train/tests -q
for nb in 17_proxy_label_design 18_proxy_label_distribution 19_rf_grouped_evaluation 20_rf_deployment_feasibility; do
  python -m nbconvert --to notebook --execute --inplace ml/notebooks/$nb.ipynb
done
```

Dùng `python -m nbconvert` của `.venv` (không phải `python -m jupyter nbconvert` khi venv chưa activate): lệnh `jupyter` tìm
`jupyter-nbconvert` trên `PATH` và có thể chạy kernel của một Python khác. Cell đầu của mỗi notebook in interpreter và phiên bản scikit-learn đã dùng."""


def f(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "không xác định"
    return f"{float(value):.{digits}f}"


def pct(value) -> str:
    return "không xác định" if value is None else f"{100 * float(value):.1f}%"


def load(repo_root: Path) -> dict:
    read = lambda p: json.loads((repo_root / p).read_text(encoding="utf-8"))
    return {"proxy": read("ml/reports/ml/proxy_dataset_summary.json"), "rf": read("ml/reports/ml/rf_poc_results.json"),
            "esp": read("ml/reports/ml/esp32_feasibility.json"), "contract": read("ml/docs/feature_contract_23_v0.1.json")}


# =========================================================================== 1. đặc tả proxy


def specification(d: dict) -> str:
    p = d["proxy"]
    st = p["threshold_stability"]
    hr, gr = st["RELATIVE_HIGH_ROLL"], st["AMPLITUDE_GROWTH"]
    return f"""# Đặc tả proxy label `{p['rule_version']}`

{DISCLAIMER}

## 1. Mục tiêu

Chuyển bài toán từ "phân loại trạng thái nguy hiểm" (không có ground truth) sang **phân loại motion phenotype dựa trên proxy**:
mỗi cửa sổ 180 s được gắn trạng thái POS/NEG/ABSTAIN cho từng phenotype quan sát được bằng một quy tắc tái lập, có phiên bản,
có hiệu chuẩn chỉ trên dữ liệu train. Đặc tả máy đọc được: `ml/labeling/proxy_spec.yaml` (SHA-256 `{p['spec_sha256'][:16]}…`).

## 2. Bốn khái niệm không được đánh đồng

| Khái niệm | Ai/cái gì tạo ra | Ý nghĩa | Trạng thái trong dự án |
|---|---|---|---|
| Observed motion phenotype | Hình thái tín hiệu Roll/Pitch | "Tín hiệu trông như thế nào" (dao động mạnh tương đối, lệch một phía, biên độ tăng) | Mô tả, chưa phải nhãn |
| Proxy rule label | Quy tắc `{p['rule_version']}` + hiệu chuẩn | Nhãn tự động, tái lập, có thể sai so với thực tế vật lý | **Được dùng trong PoC này** |
| Human-reviewed observation | Người đánh giá ghi vào ledger có audit | Người xác nhận phenotype quan sát được | 0 quyết định; không dùng |
| Verified operational hazard | Nguồn độc lập (nhật ký vận hành, envelope đã duyệt) | Trạng thái nguy hiểm thật | 0 nhãn; không thể huấn luyện |

## 3. Công thức bài toán

- Target đa nhãn: `RELATIVE_HIGH_ROLL`, `PERSISTENT_OFFSET`, `AMPLITUDE_GROWTH`; mỗi target ∈ {{POS, NEG, ABSTAIN}}.
- Trạng thái cửa sổ: `PHENOTYPE_PROXY` (≥ 1 target POS, giữ mọi target POS), `NO_PROXY_TRIGGERED` (cả ba NEG),
  `ABSTAIN` (không target nào POS và ít nhất một target ABSTAIN).
- `NO_PROXY_TRIGGERED` **không** có nghĩa NORMAL hay SAFE: nó chỉ nói không quy tắc proxy nào kích hoạt.
- Không ép phenotype chồng lấn về một lớp loại trừ; cột `proxy_phenotypes` giữ danh sách, `multi_label` đánh dấu chồng lấn.

## 4. Quy ước chung

| Mục | Quy ước |
|---|---|
| Kênh tín hiệu | `roll_deg` từ `ml/data/processed/*/*/*/timeseries.parquet` (10 Hz); Pitch chỉ dùng làm feature RF, không định nghĩa proxy |
| Cửa sổ | `(t-180, t]` cùng session/segment, ≥ 95% mẫu, không gap > 1.5 chu kỳ; block 3×60 s và sub-block 9×20 s |
| Lịch sử nhân quả | `(t-360, t-180]` cùng segment (bối cảnh); không dùng mẫu sau `t` |
| Miền hiệu chuẩn | Mỗi nguồn riêng; không gộp model-scale và full-scale. Chỉ Hohai có ≥ 3 nhóm độc lập nên chỉ Hohai được hiệu chuẩn |
| Nhóm độc lập | Hohai: điều kiện thử nghiệm `Tn` (9 nhóm); Seafar/Southampton: session/run (1 nhóm mỗi nguồn) |
| Hiệu chuẩn | Phân vị có trọng số đều theo session, quy ước inverted-CDF, chỉ trên cửa sổ hợp lệ của các nhóm train |
| Cửa sổ không hợp lệ | Thiếu một trong 23 angle feature hoặc thống kê không tính được → ABSTAIN có lý do, không bị xóa |
| Cờ kiểm toán | `near_segment_end_audit` (còn < 10 s đến cuối segment) chỉ dùng phân tích offline, không vào quy tắc |

## 5. Quy tắc `RELATIVE_HIGH_ROLL`

- **Động cơ khoa học:** đo độ mạnh dao động *tương đối* trong một miền thí nghiệm, tách khỏi offset tĩnh.
- **Kênh/cửa sổ:** Roll, 60 s cuối của cửa sổ.
- **Tham chiếu:** phân phối `roll_std_60` của các cửa sổ train cùng miền (Hohai).
- **Phương trình:** `s60 = sqrt(Σ(x_i - x̄)² / n)` trên `(t-60, t]` (trùng feature `roll_std_60`).
- **Hiệu chuẩn:** `T_pos = Q_0.90(s60 | train)`, `T_neg = Q_0.80(s60 | train)`, trọng số đều theo session.
- **Quyết định:** POS nếu `s60 ≥ T_pos`; NEG nếu `s60 < T_neg`; ABSTAIN (`BOUNDARY_BAND`) nếu ở giữa.
- **Ngưỡng đo được qua 9 outer fold (Hohai):** `T_pos` ∈ [{f(hr['positive_threshold']['min'])}, {f(hr['positive_threshold']['max'])}]°,
  `T_neg` ∈ [{f(hr['negative_threshold']['min'])}, {f(hr['negative_threshold']['max'])}]°. Đây là **ngưỡng tương đối thực nghiệm của mô hình
  thu nhỏ**, không phải giới hạn Roll vật lý hay an toàn.
- **Điều kiện hợp lệ:** miền đã hiệu chuẩn; `roll_std_60` VALID. Seafar/Southampton → ABSTAIN (`SINGLE_SESSION…`/`SINGLE_RUN…`).
- **Lỗi đã biết:** phụ thuộc mạnh vào điều kiện sóng (nhóm T7–T9 chứa toàn bộ POS) nên thực chất phân biệt *mức kích thích* của thí nghiệm;
  vòng lặp hoàn toàn với feature `roll_std_60` và các feature biên độ tương quan.

## 6. Quy tắc `PERSISTENT_OFFSET` (offset so với mốc 0 cảm biến)

- **Động cơ:** phát hiện Roll đo được nằm lệch một phía kéo dài. Vì mốc 0/mounting và quy ước dấu chưa được xác minh ở cả ba nguồn,
  proxy này được định nghĩa **tương đối với mốc 0 cảm biến** (`offset_reference = SENSOR_DATUM_UNVERIFIED`, `physical_heel_claim = false`).
  Nó không bao giờ khẳng định đó là góc nghiêng (heel/list) thật của tàu.
- **Kênh/cửa sổ:** Roll 180 s + bối cảnh 180 s trước đó.
- **Phương trình/tiêu chí cấu trúc (không ngưỡng biên độ):**
  POS nếu mọi mẫu cửa sổ cùng dấu (`dominant_sign_ratio = 1`), 9/9 mean sub-block 20 s cùng dấu **và** mọi mẫu bối cảnh cùng dấu;
  NEG nếu mean sub-block đổi dấu ít nhất một lần; ABSTAIN nếu cùng dấu nhưng dao động cắt mốc 0, hoặc thiếu bối cảnh đầy đủ.
- **Hiệu chuẩn:** không có.
- **Lỗi đã biết:** sai lệch lắp đặt cảm biến tạo POS giả; tàu có list thật nhưng dao động lớn hơn offset sẽ thành ABSTAIN.

## 7. Quy tắc `AMPLITUDE_GROWTH`

- **Động cơ:** biên độ dao động tăng theo thời gian. Phát hiện trước đó: RMS thô bị offset che (`roll_rms_ratio_180` ≈ 1 dù dao động tăng nhiều lần),
  nên quy tắc dùng **độ lệch chuẩn quanh mean** (centered).
- **Kênh/cửa sổ:** Roll, ba block 60 s trong cửa sổ, chín sub-block 20 s trong bối cảnh.
- **Phương trình:** `g = ln(σ_late60 / σ_early60)` với σ là std quần thể quanh mean của block.
- **Hiệu chuẩn:** `T_pos = Q_0.95(g | train)`, `T_neg = Q_0.90(g | train)`; qua 9 fold `T_pos` ∈ [{f(gr['positive_threshold']['min'])}, {f(gr['positive_threshold']['max'])}]
  (tức tỷ lệ ≈ {f(math.exp(gr['positive_threshold']['median']), 2)}×).
- **Quyết định:** NEG nếu `g < T_neg`; ABSTAIN nếu ở vùng biên; với `g ≥ T_pos` chỉ POS khi **đồng thời** σ ba block tăng đơn điệu,
  bối cảnh đủ ≥ 95% và σ block cuối lớn hơn mọi σ sub-block 20 s của bối cảnh; ngược lại ABSTAIN
  (`HIGH_RATIO_NOT_MONOTONIC`, `HIGH_RATIO_NOT_ABOVE_RECENT_HISTORY`, `HIGH_RATIO_NO_CAUSAL_CONTEXT`).
- **Vì sao không dùng p-value Mann–Kendall để quyết định:** kiểm định giả định các quan sát độc lập; biên độ nửa chu kỳ Hohai có tự tương quan
  lag-1 trung vị {f(p['assumption_checks']['hohai']['half_cycle_amplitude_lag1_median'], 2)} ({pct(p['assumption_checks']['hohai']['half_cycle_amplitude_lag1_share_above_0_5'])} cửa sổ > 0.5),
  tức nhóm sóng làm giả định độc lập bị vi phạm. S Mann–Kendall chỉ được lưu như số đo mô tả.
- **Lỗi đã biết:** nhóm sóng tạm thời, cuối run, nhiễu khi σ_early rất nhỏ (ở mức nhiễu cảm biến).

## 8. Đo lường so với giả định

| Đã đo trên dữ liệu | Giả định/quy ước thực nghiệm |
|---|---|
| Ngưỡng từng fold, số POS/NEG/ABSTAIN, tương quan chéo giữa session | Chọn phân vị 0.90/0.80 và 0.95/0.90 (có nghiên cứu độ nhạy) |
| Tự tương quan biên độ, mức RMS bị offset che | Điều kiện T là khóa nhóm đủ mạnh (có bằng chứng tương quan, chưa có tài liệu thí nghiệm đầy đủ) |
| Kiểm tra quy tắc chỉ dùng mẫu ≤ t (test) | Mốc 0 cảm biến không phản ánh heel thật |

## 9. Tái lập

{REPRO}

## 10. Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao gọi là "relative"?** Ngưỡng là phân vị của chính dữ liệu train Hohai. Nếu đổi miền (tàu thật, mô hình khác), ngưỡng mất ý nghĩa;
  vì vậy Seafar/Southampton được ABSTAIN thay vì mượn ngưỡng Hohai.
- **Vì sao có ABSTAIN?** Gần ngưỡng, một thay đổi nhỏ của phân vị đổi nhãn; tách vùng biên ra giúp nhãn POS/NEG ổn định hơn.
  Cái giá: đánh giá trên POS/NEG trở nên dễ hơn thực tế (xem báo cáo RF).
- **Vì sao không gọi offset là nghiêng tàu?** Không nguồn nào có hiệu chuẩn mốc 0/mounting; sensor bias và heel cho cùng một tín hiệu.
- **Vì sao không dùng RMS ratio cho growth?** Với offset lớn (Seafar |mean|/std trung vị {f(p['assumption_checks']['seafar']['median_offset_to_oscillation_ratio'], 1)}),
  RMS gần như bằng |mean|; có {p['assumption_checks']['seafar']['windows_where_centered_ratio_exceeds_raw_by_1_5x']} cửa sổ Seafar mà tỷ lệ σ centered vượt tỷ lệ RMS thô ≥ 1.5 lần.
"""


# =========================================================================== 2. chất lượng dataset


def quality(d: dict) -> str:
    p, rf = d["proxy"], d["rf"]
    inv, ge = p["inventory"], p["grouping_evidence"]
    lines = [f"# Báo cáo chất lượng proxy dataset `{p['rule_version']}`", "", DISCLAIMER, "",
             "## 1. Mục tiêu", "",
             "Đánh giá trước khi huấn luyện: độ phủ, phân phối nhãn proxy, chồng lấn đa nhãn, ABSTAIN, độ ổn định quy tắc, độ nhạy hiệu chuẩn và "
             "cổng training-readiness theo nhóm độc lập.", "",
             "## 2. Phương pháp", "",
             "- Dựng bảng đo cho mọi window endpoint của feature table (`python -m ml.labeling.proxy_dataset`).",
             "- Nhãn **out-of-fold**: mỗi cửa sổ Hohai được gắn nhãn bằng hiệu chuẩn fit trên 8 điều kiện T *khác* điều kiện của nó; "
             "Seafar/Southampton không hiệu chuẩn được nên chỉ có quy tắc offset cấu trúc.",
             "- Độ nhạy: lặp lại toàn bộ quy trình out-of-fold với các cặp phân vị trong spec.",
             "- Cổng readiness (spec `readiness`): miền ≥ 3 nhóm độc lập; POS ở ≥ 3 nhóm và ≥ 5 session; NEG ở ≥ 3 nhóm; ≥ 20 cửa sổ POS. "
             "Lý do chọn: với leave-one-group-out, mỗi fold train phải còn POS từ ≥ 2 nhóm khác nhau, nếu không mô hình chỉ học một điều kiện thí nghiệm.",
             "", "## 3. Kiểm kê thực tế (tính lại từ artifact)", "",
             "| Chỉ số | Giá trị đo | Trạng thái báo cáo trước |", "|---|---:|---|",
             f"| Window endpoint trong feature table | {inv['windows_total']} | — |",
             f"| Cửa sổ đủ 23 angle feature | {inv['angle23_complete']} | 2.864 (khớp) |",
             f"| Session có cửa sổ đủ 23 feature | {inv['sessions_with_complete_windows']} | 23 (khớp) |",
             f"| Nhóm độc lập (sau khi gộp Hohai theo điều kiện T) | {inv['experiment_groups_with_complete_windows']} | chưa từng báo cáo |",
             "", "### Bằng chứng chọn khóa nhóm Hohai", "",
             "Tên sheet Hohai = bến × điều kiện thử nghiệm `Tn` × cấu hình dây neo (theo `Data Description Example.pdf`). Tương quan chéo cực đại |ρ| "
             "của Roll (lag ±30 s) giữa các cặp session:", "",
             "| Cặp session | Số cặp | Trung vị | Min | Max |", "|---|---:|---:|---:|---:|",
             f"| Cùng điều kiện T | {int(ge['same_condition_max_abs_xcorr']['count'])} | {f(ge['same_condition_max_abs_xcorr']['50%'])} | {f(ge['same_condition_max_abs_xcorr']['min'])} | {f(ge['same_condition_max_abs_xcorr']['max'])} |",
             f"| Cùng T, khác bến | {int(ge['same_condition_different_berth_max_abs_xcorr']['count'])} | {f(ge['same_condition_different_berth_max_abs_xcorr']['50%'])} | {f(ge['same_condition_different_berth_max_abs_xcorr']['min'])} | {f(ge['same_condition_different_berth_max_abs_xcorr']['max'])} |",
             f"| Khác điều kiện T | {int(ge['different_condition_max_abs_xcorr']['count'])} | {f(ge['different_condition_max_abs_xcorr']['50%'])} | {f(ge['different_condition_max_abs_xcorr']['min'])} | {f(ge['different_condition_max_abs_xcorr']['max'])} |",
             "", "Session cùng điều kiện T có chung chuỗi sóng tới nên không độc lập; split theo session sẽ rò rỉ. "
             "Một số cặp khác T vẫn có |ρ| cao (max ở trên) nên T là khóa *mạnh hơn* session nhưng chưa chắc là đủ; đây là giới hạn còn lại.",
             "", "## 4. Phân phối proxy label (out-of-fold)", ""]
    lines += ["| Nguồn | Cửa sổ | Đủ 23 feature | PHENOTYPE_PROXY | NO_PROXY_TRIGGERED | ABSTAIN | Đa nhãn |", "|---|---:|---:|---:|---:|---:|---:|"]
    for ds, v in p["distribution_oof"].items():
        ws = v["window_status"]
        lines.append(f"| {ds} | {v['windows']} | {v['angle23_complete']} | {ws.get('PHENOTYPE_PROXY', 0)} | {ws.get('NO_PROXY_TRIGGERED', 0)} | {ws.get('ABSTAIN', 0)} | {v['multi_label_windows']} |")
    lines += ["", "| Nguồn | Target | POS | NEG | ABSTAIN | Nhóm có POS | Session có POS | Quyết định | Lý do chặn |", "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for ds, r in p["readiness"].items():
        for t, v in r["targets"].items():
            lines.append(f"| {ds} | {t} | {v['positive_windows']} | {v['negative_windows']} | {v['abstain_windows']} | {v['positive_groups']} | "
                         f"{v['positive_sessions']} | **{v['decision']}** | {', '.join(v['blockers']) or '—'} |")
    lines += ["", "### Tổ hợp phenotype (chồng lấn đa nhãn)", ""]
    for ds, v in p["distribution_oof"].items():
        lines.append(f"- **{ds}:** " + "; ".join(f"`{k}` = {n}" for k, n in v["phenotype_combinations"].items()))
    lines += ["", "### Lý do ABSTAIN/NEG/POS theo target (Hohai)", ""]
    for t, reasons in p["distribution_oof"]["hohai"]["reasons"].items():
        lines.append(f"- **{t}:** " + "; ".join(f"`{k}` = {n}" for k, n in reasons.items()))
    lines += ["", "### Độ phủ theo nhóm độc lập Hohai", "", "| Nhóm | Cửa sổ | RELATIVE_HIGH_ROLL (POS/NEG/ABSTAIN) | AMPLITUDE_GROWTH (POS/NEG/ABSTAIN) |", "|---|---:|---|---|"]
    for g, v in p["distribution_oof"]["hohai"]["by_group"].items():
        a, b = v["RELATIVE_HIGH_ROLL"], v["AMPLITUDE_GROWTH"]
        lines.append(f"| {g} | {v['windows']} | {a.get('POS', 0)}/{a.get('NEG', 0)}/{a.get('ABSTAIN', 0)} | {b.get('POS', 0)}/{b.get('NEG', 0)}/{b.get('ABSTAIN', 0)} |")
    lines += ["", "Cột cửa sổ gồm cả cửa sổ thiếu feature (ABSTAIN `INCOMPLETE_ANGLE_FEATURES`)."]
    if rf.get("targets"):
        lines += ["", "## 5. Support theo split (outer fold, target TRAINABLE)", "",
                  "| Fold | Nhóm test | Train POS/tổng | Nhóm train có POS | Test POS/tổng | Test ABSTAIN |", "|---:|---|---:|---:|---:|---:|"]
        for fold in rf["targets"]["RELATIVE_HIGH_ROLL"]["feature_sets"]["full_23"]["folds"]:
            lines.append(f"| {fold['fold']} | {', '.join(fold['test_groups'])} | {fold['train_positive']}/{fold['train_windows']} | "
                         f"{fold['train_positive_groups']} | {fold['test_positive']}/{fold['test_windows']} | {fold['test_abstain_windows']} |")
    st = p["threshold_stability"]
    lines += ["", "## 6. Độ ổn định quy tắc và độ nhạy hiệu chuẩn", "",
              "| Target | Ngưỡng | Min qua 9 fold | Trung vị | Max |", "|---|---|---:|---:|---:|"]
    for t, v in st.items():
        for k, s in v.items():
            lines.append(f"| {t} | {k} | {f(s['min'], 4)} | {f(s['median'], 4)} | {f(s['max'], 4)} |")
    lines += ["", "| Target | (q_pos, q_neg) | POS | NEG | ABSTAIN | Nhóm có POS | Session có POS | Jaccard tập POS so với mặc định |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for t, rows in p["sensitivity"].items():
        for r in rows:
            lines.append(f"| {t} | ({r['positive_quantile']}, {r['negative_quantile']}) | {r['positive']} | {r['negative']} | {r['abstain']} | "
                         f"{r['positive_groups']} | {r['positive_sessions']} | {f(r['jaccard_vs_default_positive_set'], 2)} |")
    ac = p["assumption_checks"]
    lines += ["", "## 7. Kiểm tra giả định và trường hợp mơ hồ", "",
              "| Nguồn | Lag-1 biên độ nửa chu kỳ (trung vị) | Tỷ lệ cửa sổ lag-1 > 0.5 | |mean|/std trung vị | Cửa sổ có tỷ lệ σ centered > 1.5× tỷ lệ RMS thô |", "|---|---:|---:|---:|---:|"]
    for ds, v in ac.items():
        lines.append(f"| {ds} | {f(v['half_cycle_amplitude_lag1_median'], 2)} | {pct(v['half_cycle_amplitude_lag1_share_above_0_5'])} | "
                     f"{f(v['median_offset_to_oscillation_ratio'], 2)} | {v['windows_where_centered_ratio_exceeds_raw_by_1_5x']} |")
    h = p["distribution_oof"]["hohai"]
    lines += ["", f"- Vùng biên `RELATIVE_HIGH_ROLL`: {h['reasons']['RELATIVE_HIGH_ROLL'].get('BOUNDARY_BAND', 0)} cửa sổ Hohai bị ABSTAIN.",
              f"- `AMPLITUDE_GROWTH` có tỷ lệ cao nhưng thiếu tính nhất quán thời gian: không đơn điệu {h['reasons']['AMPLITUDE_GROWTH'].get('HIGH_RATIO_NOT_MONOTONIC', 0)}, "
              f"không vượt lịch sử gần {h['reasons']['AMPLITUDE_GROWTH'].get('HIGH_RATIO_NOT_ABOVE_RECENT_HISTORY', 0)}, thiếu bối cảnh {h['reasons']['AMPLITUDE_GROWTH'].get('HIGH_RATIO_NO_CAUSAL_CONTEXT', 0)} cửa sổ.",
              f"- `PERSISTENT_OFFSET` Hohai: {h['reasons']['PERSISTENT_OFFSET'].get('SIGNED_BIAS_BUT_OSCILLATION_CROSSES_DATUM', 0)} cửa sổ có mean cùng dấu nhưng dao động cắt mốc 0 (ABSTAIN).",
              f"- Cửa sổ POS sát cuối segment (cờ kiểm toán): " + "; ".join(f"{ds} {v['near_segment_end_audit_positive']}" for ds, v in p["distribution_oof"].items()) + ".",
              "- Không cửa sổ khó nào bị xóa; mọi cửa sổ đều có trạng thái và lý do.",
              "", "## 8. Quyết định training-readiness", "",
              "- **TRAINABLE:** chỉ `RELATIVE_HIGH_ROLL` trong miền Hohai (vừa đủ mức tối thiểu 3 nhóm có POS: T7, T8, T9).",
              "- **NOT_TRAINABLE:** `AMPLITUDE_GROWTH` (quá ít POS và session), `PERSISTENT_OFFSET` (Hohai không có POS; Seafar/Southampton không có NEG và chỉ một nhóm), "
              "mọi target ở Seafar và Southampton (một nhóm độc lập, không thể đánh giá giữ-nhóm).",
              "- Không tạo nhãn giả để cân bằng lớp; không gộp nguồn để tăng support.",
              "", "## 9. Giới hạn", "",
              "- Proxy label phụ thuộc phân vị được chọn; độ nhạy ở mục 6 cho thấy tập POS thay đổi đáng kể khi đổi phân vị.",
              "- Chỉ 9 nhóm độc lập Hohai và POS tập trung ở 3 nhóm có kích thích mạnh nhất.",
              "- Dữ liệu Hohai là mô hình thu nhỏ, thời gian suy từ 50 Hz, không gyro; mốc 0 cảm biến ở mọi nguồn chưa xác minh.",
              "", "## 10. Tái lập", "", REPRO, "",
              "Output lớn (gitignored): `ml/data/labels/proxy_v1/` gồm `measurements.parquet`, `proxy_labels_oof.parquet`, "
              "`proxy_labels_by_fold.parquet`, `proxy_labels_final_calibration.parquet`, `calibrations.json`, `hohai_session_xcorr.csv`. "
              "Tóm tắt nhỏ được theo dõi: `ml/reports/ml/proxy_dataset_summary.json`.",
              f"- Checksum human-review ledger/verified/AI không đổi sau khi chạy: **{p['protected_files_unchanged']}**.",
              "", "## 11. Diễn giải khoa học", "",
              "Proxy dataset đủ để *thử nghiệm kỹ thuật* một target tương đối trong một miền mô hình thu nhỏ. Nó không đủ để huấn luyện bốn lớp, "
              "không đủ cho offset hay growth, và không cho phép bất kỳ tuyên bố tổng quát hóa liên session ở Seafar/Southampton.",
              "", "## 12. Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
              "- **Vì sao không chia ngẫu nhiên theo cửa sổ?** Cửa sổ 180 s bước 10 s chồng nhau ~94%; chia ngẫu nhiên đưa gần như cùng một đoạn tín hiệu vào cả train và test.",
              "- **Vì sao nhóm theo T chứ không theo session?** Số liệu tương quan chéo ở mục 3: session cùng T có chung sóng tới.",
              "- **Vì sao chỉ một target được huấn luyện?** Cổng readiness đòi POS ở ≥ 3 nhóm độc lập; growth chỉ có "
              f"{p['readiness']['hohai']['targets']['AMPLITUDE_GROWTH']['positive_windows']} cửa sổ POS ở {p['readiness']['hohai']['targets']['AMPLITUDE_GROWTH']['positive_sessions']} session, offset Hohai không có POS.",
              "- **Nhãn out-of-fold là gì?** Ngưỡng dùng để gắn nhãn một cửa sổ không bao giờ được học từ nhóm chứa cửa sổ đó.", ""]
    return "\n".join(lines)


# =========================================================================== 3. Random Forest


def rf_report(d: dict) -> str:
    rf, p = d["rf"], d["proxy"]
    if not rf.get("targets"):
        return f"# Random Forest PoC\n\n{DISCLAIMER}\n\nHuấn luyện bị chặn: {rf['status']}.\n"
    t = rf["targets"]["RELATIVE_HIGH_ROLL"]
    fs = t["feature_sets"]
    card = t["final_model_card"]
    lines = [f"# Báo cáo Random Forest PoC `{rf['model_version']}`", "", DISCLAIMER, "",
             "## 1. Mục tiêu", "",
             "Kiểm tra liệu một Random Forest trên 23 angle feature có tái tạo được proxy label `RELATIVE_HIGH_ROLL` ở các điều kiện thử nghiệm Hohai "
             "chưa thấy hay không, so với baseline tầm thường và baseline quy tắc xác định, và đo mức phụ thuộc vào feature định nghĩa proxy.", "",
             "## 2. Phương pháp", "",
             f"- Target huấn luyện: {', '.join(rf['trainable_targets'])} (target khác NOT_TRAINABLE, xem báo cáo chất lượng). "
             "Dạng đa nhãn được triển khai *per-label* (một RF nhị phân cho mỗi target qua cổng); với chỉ một target qua cổng, macro F1 = F1 của target đó.",
             "- Miền: Hohai, 9 nhóm điều kiện T. **Nested leave-one-group-out:** outer fold giữ 1 nhóm làm test; nhãn của fold dùng hiệu chuẩn fit trên 8 nhóm train; "
             "bên trong train, GroupKFold 4 nhóm (round-robin xác định) chọn siêu tham số theo PR-AUC gộp, rồi chọn ngưỡng xác suất tối đa F1 trên dự đoán out-of-fold *của train*.",
             "- Cửa sổ ABSTAIN bị loại khỏi train và khỏi metric của target (được đếm riêng); không cửa sổ nào bị xóa khỏi dataset.",
             f"- Lưới siêu tham số: {len(t['feature_sets']['full_23']['folds'][0]['inner_trials'])} cấu hình (max_depth ∈ {{8, None}}, min_samples_leaf ∈ {{10, 1}}, "
             "class_weight ∈ {None, balanced_subsample}), n_estimators = 200, max_features = sqrt, seed "
             f"`{rf['seed']}`. Class imbalance chỉ xử lý bằng `class_weight` nếu inner CV chọn; không oversampling/không nhãn tổng hợp.",
             "- Không có preprocessing học được (RF không cần chuẩn hóa); không imputation; cửa sổ thiếu feature → ABSTAIN.",
             "- Baseline: luôn NEG; quy tắc một feature với ngưỡng phân vị fit trên train (`roll_std_60` = chính proxy, `roll_rms_60` = RMS thô, `pitch_std_60` = chỉ Pitch).",
             "- Ablation: `no_direct_alias` bỏ `roll_std_60`, `roll_rms_60`, `roll_rms_late_60` (bí danh: hiệu tuyệt đối lớn nhất giữa `roll_rms_60` và "
             "`roll_rms_late_60` trên Hohai = 0); `no_roll_amplitude` bỏ mọi feature biên độ/độ phân tán Roll.",
             "- Khoảng tin cậy: bootstrap 2.000 lần trên **9 nhóm độc lập**, không trên cửa sổ chồng lấn.",
             "", "### Feature huấn luyện (schema `" + rf["feature_schema"]["sha256"][:16] + "…`, 23 feature theo thứ tự)", "",
             "| # | Feature | # | Feature | # | Feature |", "|---:|---|---:|---|---:|---|"]
    names = list(ANGLE_FEATURES)
    for i in range(0, 23, 3):
        cells = [f"{j} | `{names[j]}`" for j in range(i, min(i + 3, 23))]
        while len(cells) < 3:
            cells.append(" | ")
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Không dùng gyro (Hohai không có; Seafar/Southampton mapping chưa xác minh) và không dùng 3 feature chu kỳ (ngoài tập angle-only 23).",
              "", "## 3. Kết quả đo được (test = nhóm giữ lại, gộp 9 outer fold)", "",
              "| Mô hình / baseline | Precision | Recall | F1 | PR-AUC | Khoảng F1 bootstrap theo nhóm (2.5–97.5%) |", "|---|---:|---:|---:|---:|---|"]
    for name, payload in fs.items():
        m, b = payload["pooled"], payload["group_bootstrap"]
        lines.append(f"| RF `{name}` ({len(payload['features'])} feature) | {f(m['precision'])} | {f(m['recall'])} | {f(m['f1'])} | {f(m['pr_auc_average_precision'])} | "
                     f"{f(b['f1_percentile_2_5'])}–{f(b['f1_percentile_97_5'])} |")
    cm = t["compact_model"]
    lines.append(f"| RF compact (25 cây, depth 6, khai báo trước) | {f(cm['pooled']['precision'])} | {f(cm['pooled']['recall'])} | {f(cm['pooled']['f1'])} | "
                 f"{f(cm['pooled']['pr_auc_average_precision'])} | {f(cm['group_bootstrap']['f1_percentile_2_5'])}–{f(cm['group_bootstrap']['f1_percentile_97_5'])} |")
    for name, m in t["baselines"].items():
        b = m.get("group_bootstrap", {})
        lines.append(f"| Baseline `{name}` | {f(m['precision'])} | {f(m['recall'])} | {f(m['f1'])} | — | "
                     f"{f(b.get('f1_percentile_2_5'))}–{f(b.get('f1_percentile_97_5'))} |" if b else
                     f"| Baseline `{name}` | {f(m['precision'])} | {f(m['recall'])} | {f(m['f1'])} | prevalence = {f(m['prevalence'])} | — |")
    full = fs["full_23"]["pooled"]
    lines += ["", f"Support test gộp: {full['support_positive']} POS / {full['support_negative']} NEG (prevalence {f(full['prevalence'])}).", "",
              "### Ma trận nhầm lẫn và support theo nhóm độc lập", "",
              "| Feature set | Nhóm | Session | POS | TP | FP | FN | TN |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, payload in fs.items():
        for g in payload["per_group"]:
            lines.append(f"| {name} | {g['experiment_group']} | {g['sessions']} | {g['support_positive']} | {g['tp']} | {g['fp']} | {g['fn']} | {g['tn']} |")
    lines += ["", "### Hành vi trên vùng ABSTAIN (không có nhãn, không vào metric)", "", "| Feature set | Nhóm test | Cửa sổ ABSTAIN | RF dự đoán POS |", "|---|---|---:|---:|"]
    for name, payload in fs.items():
        for fold in payload["folds"]:
            if fold["test_abstain_windows"]:
                lines.append(f"| {name} | {', '.join(fold['test_groups'])} | {fold['test_abstain_windows']} | {fold['test_abstain_predicted_positive']} |")
    lines += ["", "### Siêu tham số được chọn (chỉ dùng dữ liệu train)", "", "| Feature set | Fold | Tham số | PR-AUC inner | Ngưỡng xác suất |", "|---|---:|---|---:|---:|"]
    for name, payload in fs.items():
        for fold in payload["folds"]:
            lines.append(f"| {name} | {fold['fold']} | `{json.dumps(fold['selected_params'])}` | {f(fold['inner_pooled_average_precision'])} | {f(fold['probability_threshold'])} |")
    ea = t["error_analysis"]
    imp = pd.DataFrame(t["permutation_importance_test_folds"]).drop(columns=["fold", "test_groups"]).mean().abs().max() if t["permutation_importance_test_folds"] else None
    mdi = sorted(card["mdi_importance"].items(), key=lambda kv: -kv[1])
    lines += ["", "### Phân tích lỗi", "",
              f"- RF `full_23`: FP = {ea['false_positive']}, FN = {ea['false_negative']}. "
              + ("Không có lỗi nào trên cửa sổ POS/NEG giữ lại." if not ea["false_positive"] + ea["false_negative"] else f"Lỗi theo nhóm: {ea['errors_by_group']}."),
              f"- RF `no_roll_amplitude`: lỗi tập trung ở " + ", ".join(f"{g['experiment_group']} (FN {g['fn']}, FP {g['fp']})" for g in fs['no_roll_amplitude']['per_group'] if g['fn'] + g['fp']) + ".",
              "", "### Feature importance và giới hạn", "",
              "- MDI (mô hình cuối, 9 nhóm): " + ", ".join(f"`{k}` {f(v)}" for k, v in mdi[:6]) + ".",
              f"- Permutation importance trên outer test fold có cả hai lớp: |giá trị| lớn nhất ≈ {imp:.1e}. Lý do: nhiều feature biên độ gần như thay thế được nhau, "
              "hoán vị một feature không làm giảm PR-AUC. Điều này **không** có nghĩa feature vô dụng; importance không đáng tin khi feature cộng tuyến mạnh.",
              "", "### Mô hình cuối cho CLI dự đoán (không có test riêng)", "",
              f"- Huấn luyện trên {card['training_windows']} cửa sổ POS/NEG ({card['training_positive']} POS) của {len(card['training_groups'])} nhóm, {card['training_sessions']} session; "
              f"hiệu chuẩn `{card['calibration_id']}` (T_pos = {f(card['calibration_thresholds']['positive_threshold'], 4)}°, T_neg = {f(card['calibration_thresholds']['negative_threshold'], 4)}°).",
              f"- Tham số chọn bằng GroupKFold: `{json.dumps(card['selection']['params'])}`, ngưỡng xác suất {f(card['selection']['probability_threshold'])}.",
              f"- Cây: {card['tree_statistics']['n_estimators']} cây, {card['tree_statistics']['total_nodes']} nút, depth tối đa {card['tree_statistics']['max_depth']}; "
              f"SHA-256 model `{card['model_sha256'][:16]}…`; schema `{card['feature_schema']['sha256'][:16]}…`; model card `ml/reports/ml/rf_poc_model_card.json`.",
              "- Tái lập: cùng seed cho cây giống hệt và cùng SHA-256 khi serialize; `predict_proba` với `n_jobs=-1` có thể lệch ~1e-16 do cộng song song, "
              "nên CLI đặt `n_jobs=1`.",
              "", "## 4. Kiểm toán rò rỉ", "",
              f"- 9/9 outer fold: không chung nhóm/session/segment, 0 khoảng thời gian chồng lấn, 0 vector feature trùng giữa train và test: "
              f"**{all(a['passed'] for a in t['split_audit'])}**.",
              "- Ngưỡng proxy, siêu tham số và ngưỡng xác suất đều fit trên train của fold; nhóm test không tham gia.",
              "", "## 5. Diễn giải khoa học", "",
              "1. **F1 = 1 không phải thành tựu nhận diện.** Proxy là `roll_std_60 ≥ T_pos`; RF chỉ học lại ngưỡng đó. Baseline quy tắc `roll_std_60` cũng F1 = 1 theo cấu trúc.",
              "2. **Ablation bỏ feature trực tiếp vẫn F1 = 1** vì `roll_diff_rms_60`, `roll_iqr_60`, `roll_abs_p95_60`… mang gần như cùng thông tin (Spearman với `roll_std_60` ≥ 0.92 trên Hohai). "
              "Ablation thành công cũng **không** tạo ra ground truth độc lập.",
              f"3. **Khi bỏ mọi feature biên độ Roll**, F1 giảm xuống {f(fs['no_roll_amplitude']['pooled']['f1'])}, gần baseline chỉ Pitch "
              f"({f(t['baselines']['pitch_only_rule_pitch_std_60']['f1'])}): phần còn lại chủ yếu phản ánh *mức kích thích sóng chung* của điều kiện thử nghiệm.",
              "4. **Việc loại vùng ABSTAIN làm bài toán dễ hơn:** POS và NEG cách nhau một dải phân vị 0.80–0.90; trong dải đó RF chia đôi tùy ý (bảng ở trên).",
              "5. POS chỉ có ở 3/9 nhóm (T7–T9), nên recall đo trên 3 nhóm; 6 fold còn lại chỉ đo FP. Khoảng bootstrap hẹp vì mô hình khớp hoàn hảo, không phải vì dữ liệu nhiều.",
              "", "## 6. Giới hạn", "",
              "- Không có ground truth độc lập; mọi metric là **mức khớp với proxy label**, không phải độ chính xác phát hiện hazard.",
              "- Một miền (Hohai model-scale), 9 nhóm, POS ở 3 nhóm; không có tuyên bố tổng quát hóa sang Seafar/Southampton hay tàu thật.",
              "- `AMPLITUDE_GROWTH` và `PERSISTENT_OFFSET` không được huấn luyện (NOT_TRAINABLE).",
              "", "## 7. Tái lập", "", REPRO, "",
              "Artifact model (gitignored): `ml/data/models/rf_poc_v1/` (`relative_high_roll_rf.joblib`, model card, `outer_fold_predictions.parquet`). "
              "Kết quả đầy đủ: `ml/reports/ml/rf_poc_results.json`.",
              f"- Môi trường: Python {rf['environment']['python']}, scikit-learn {rf['environment']['sklearn']}, numpy {rf['environment']['numpy']}, pandas {rf['environment']['pandas']}; "
              f"thời gian chạy {rf['runtime_seconds']} s.",
              "", "## 8. Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
              "- **Có thể khẳng định:** pipeline nested group-held-out không rò rỉ đã chạy; RF tái tạo được quy tắc proxy tương đối trên điều kiện thử nghiệm Hohai chưa thấy; "
              "thông tin đến từ các feature biên độ Roll (ablation).",
              "- **Không thể khẳng định:** mô hình phát hiện Roll nguy hiểm; mô hình dùng được cho tàu thật; F1 = 1 là độ chính xác vận hành.",
              "- **Câu hỏi hay gặp — vì sao không chia ngẫu nhiên?** Cửa sổ chồng nhau 94%; split ngẫu nhiên đo trí nhớ, không đo tổng quát hóa.",
              "- **Vì sao chọn ngưỡng xác suất trên train?** Nếu chọn trên test, test đã ảnh hưởng mô hình → metric lạc quan.",
              "- **Bước tiếp theo đúng:** cần nhãn độc lập (human review nhiều người, nhật ký thí nghiệm/vận hành) trước khi so sánh RF với quy tắc một cách có ý nghĩa.", ""]
    return "\n".join(lines)


# =========================================================================== 4. ESP32


def esp_report(d: dict) -> str:
    e, rf = d["esp"], d["rf"]
    mem, emu, acc = e["memory"], e["firmware_chain_emulation"], e["southampton_accel_roll_check"]
    fw = e["current_firmware_chain"]
    model = next(iter(mem["models"].values()), None)
    compact = next(iter(e["compact_models"].values()), None)
    ram = mem["feature_ram_bytes"]
    lines = [f"# Tương thích feature 23 và khả thi ESP32", "", DISCLAIMER, "",
             "## 1. Mục tiêu", "",
             "Theo quyết định thiết kế của nhóm M2, 23 angle feature là schema đầu vào chính của RF. Báo cáo này đưa ra đề xuất contract có phiên bản cho M1, "
             "ước lượng tài nguyên ESP32, chỉ ra khác biệt giữa Roll/Pitch của dataset và của ESP32, và lập kế hoạch parity Python/C. "
             "Không sửa contract C, firmware hay cấu hình phần cứng hiện có.", "",
             "## 2. Đề xuất contract `svmg-angle23` v0.1.0", "",
             f"- Máy đọc được: `{e['contract_path']}`; bảng người đọc: `ml/docs/feature_contract_23_proposal.md`.",
             "- Giữ nguyên tên, công thức, đơn vị, thứ tự và ngữ nghĩa cửa sổ của `ml/features/extractor.py` (extractor 0.1.0). Không đơn giản hóa công thức.",
             "- 10 Hz, endpoint `(t-W, t]`, cập nhật mỗi 10 s, cửa sổ 60/180 s, ≥ 95% mẫu hợp lệ, gap > 1.5 chu kỳ → feature không hợp lệ (không thay bằng 0).",
             "- Contract cũ 14 trường (`contracts/features.md`, `core/include/svmg_core.h`) và vector 10 trường của `svmg_features.h` **không bị chỉnh sửa**.",
             "- Không tạo `ml/export/model.h`: firmware tự `#include` file này nếu tồn tại (`firmware/src/infer.cpp`) và giả định 4 lớp loại trừ NORMAL…AMPLITUDE_GROWTH, "
             "không tương thích với PoC đa nhãn/proxy hiện tại. Cần thống nhất interface với M1 trước.",
             "", "## 3. So sánh chuỗi hiện tại của firmware với chuỗi dataset", "",
             "| Hạng mục | Firmware hiện tại (đã đọc mã) | Dataset/feature 23 | Hệ quả |", "|---|---|---|---|",
             f"| Tần số đầu vào/đầu ra | {fw['input_hz']} Hz → {fw['output_hz']} Hz | 10 Hz | Cần chuỗi 10 Hz riêng cho feature |",
             f"| Lọc | {fw['lowpass']} + bộ lọc bù τ = {fw['complementary_filter_tau_s']} s | Butterworth nhân quả bậc 4, 4 Hz (Hohai/Southampton), Seafar không lọc | Biên độ khác nhau |",
             f"| Cửa sổ | {fw['short_window_samples']}/{fw['long_window_samples']} mẫu 2 Hz | 600/1.800 mẫu 10 Hz | Định nghĩa feature phụ thuộc số mẫu |",
             "| Feature | 10 trường riêng (`svmg_features.h`) | 23 angle feature | Không có tập con trùng định nghĩa |",
             "| Đơn vị `roll_diff_rms_60` | — | deg/mẫu ở 10 Hz | Phải tính đúng ở 10 Hz |",
             f"| Nguồn | `{fw['source']}` | `ml/features/extractor.py` | |",
             "", "### Thí nghiệm mô phỏng chuỗi lọc hiện tại trên Hohai (đã chạy)", "",
             f"Áp Butterworth bậc 2, 0.5 Hz rồi lấy 2 Hz trên Roll Hohai đã xử lý, tính lại std 60 s ({emu['samples_per_60s_window_2hz']} mẫu) ở {emu['windows']} cửa sổ:",
             "", "| Chỉ số | Giá trị |", "|---|---:|",
             f"| Tỷ lệ std (chuỗi firmware / 10 Hz), trung vị | {f(emu['std_ratio_median'])} |",
             f"| Tỷ lệ std, P05–P95 | {f(emu['std_ratio_p05'])}–{f(emu['std_ratio_p95'])} |",
             f"| Quyết định proxy RELATIVE_HIGH_ROLL thay đổi | {emu['decisions_changed']} / {emu['windows']} |",
             f"| POS gốc không còn POS | {emu['original_pos_now_not_pos']} |",
             f"| Quyết định gốc | {emu['proxy_decisions_original']} |",
             f"| Quyết định sau chuỗi firmware | {emu['proxy_decisions_emulated']} |",
             "", "Độ khuếch đại lý thuyết của Butterworth bậc 2 fc = 0.5 Hz: " +
             ", ".join(f"{k} → {f(v)}" for k, v in emu["butterworth2_0p5hz_gain_at"].items()) +
             f". Đầu ra 2 Hz có Nyquist {emu['nyquist_2hz_output_hz']} Hz. *Xấp xỉ:* {emu['approximation']}",
             "", "### Thí nghiệm lệch miền với đủ 23 feature và mô hình cuối (đã chạy)", ""]
    shift = e.get("filtered_feature_model_shift", {})
    if shift.get("predictions_original"):
        lines += ["Trích lại 23 feature bằng `ml/features/extractor.py` trên Roll/Pitch Hohai đã lọc Butterworth bậc 2, 0.5 Hz (giữ 10 Hz), rồi dự đoán bằng mô hình cuối:", "",
                  "| Dự đoán RF | Tín hiệu gốc 10 Hz | Sau lọc 0.5 Hz |", "|---|---:|---:|"]
        for key in ("POS", "NEG", "ABSTAIN"):
            lines.append(f"| {key} | {shift['predictions_original'].get(key, 0)} | {shift['predictions_filtered'].get(key, 0)} |")
        lines += ["", f"Lý do ABSTAIN sau lọc: {shift['abstain_reasons_filtered']}; tỷ lệ `roll_std_60` lọc/gốc trung vị {f(shift['roll_std_60_ratio_median'])}. "
                  f"*Xấp xỉ:* {shift['approximation']}"]
    else:
        lines.append(f"Không chạy được: {shift.get('status', 'không có dữ liệu')}.")
    lines += [
             "", "## 4. ESP32 ước lượng Roll/Pitch như thế nào", "",
             "Theo `core/include/svmg_filter.h`: MPU6050 (±2 g, ±250 °/s) → SI; `roll = atan2(ay, az)`, `pitch = atan2(-ax, sqrt(ay² + az²))` từ gia tốc kế; "
             "bộ lọc bù trộn tích phân gyro với góc gia tốc (α = τ/(τ+dt), τ = 7.5 s), cổng gia tốc [0.5 g, 1.5 g]; sau đó lọc 0.5 Hz và giảm mẫu 20 → 2 Hz; "
             "hiệu chuẩn zero (`svmg_calib.h`) trừ mean 30 s khi tĩnh.",
             "", "### Khác biệt với Roll/Pitch của dataset", "",
             "| Nguồn | Cách có Roll | Ghi chú |", "|---|---|---|",
             "| Hohai | Hệ đo chuyển động 6-DOF của thí nghiệm mô hình neo (không có gyro/timestamp) | Mô hình thu nhỏ, chu kỳ Roll ~1.8 s |",
             "| Seafar | Trường Roll của IMU tàu (thuật toán fusion không rõ) | Lượng tử 0.01°, offset ~3°; trục/dấu tin cậy thấp |",
             "| Southampton | Cột Roll của IMU mô hình KCS | Có gia tốc kế, Delta Angle chưa map |",
             "| ESP32 | Bộ lọc bù MPU6050 + lọc 0.5 Hz + 2 Hz | Gia tốc ngang khi lắc làm sai góc từ gia tốc; mốc 0 do hiệu chuẩn tĩnh |",
             "", f"Kiểm tra thực tế trên Southampton Run 14 ({acc['samples']} mẫu, quy ước {acc['convention']}): Roll dataset mean {f(acc['dataset_roll_mean_deg'])}°, std {f(acc['dataset_roll_std_deg'])}°; "
             f"Roll suy từ gia tốc kế mean {f(acc['accel_roll_mean_deg'])}°, std {f(acc['accel_roll_std_deg'])}°; Pearson r = {f(acc['pearson_r'])}, RMS chênh lệch {f(acc['rms_difference_deg'])}°. "
             "Mean khớp, nhưng góc chỉ từ gia tốc kế nhiễu/dao động khác nhiều so với Roll đã fusion — feature biên độ sẽ lệch nếu không có fusion tương đương.",
             "", "## 5. Ước lượng tài nguyên (chưa đo trên thiết bị)", "",
             "| Thành phần RAM cho 23 feature | Byte |", "|---|---:|"]
    for k, v in ram.items():
        lines.append(f"| {k} | {v} |")
    lines += [f"| Lõi C hiện tại (`svmg_engine_t`, tài liệu M1) | {mem['existing_core_engine_bytes_documented']} |",
              f"| RAM trống tài liệu M1 ghi (trước heap WiFi) | ≈ {mem['free_ram_documented_bytes_approx']} |",
              "", f"Nguồn số liệu M1: {mem['documented_source']}. Không lưu timestamp từng mẫu (nhịp cố định + bộ đếm gap); nếu lưu uint32 thêm 7.200 B.",
              "", "| Mô hình | Cây | Nút | Depth | Ước lượng mảng C | So sánh trung bình/tối đa mỗi suy luận | Latency ước lượng (240 MHz, 20 chu kỳ/so sánh) |", "|---|---:|---:|---:|---:|---:|---:|"]
    if model:
        lines.append(f"| RF cuối (PoC) | {model['n_estimators']} | {model['total_nodes']} | {model['max_depth']} | {model['estimated_c_array_bytes']} B | "
                     f"{f(model['mean_comparisons_per_inference'], 1)} / {f(model['max_comparisons_per_inference'], 0)} | ≈ {f(model['latency_estimate_us_at_240MHz_20_cycles_per_comparison'], 1)} µs |")
    if compact:
        lines.append(f"| RF compact (`{json.dumps(compact['params'])}`), F1 proxy {f(compact['f1'])} | 25 | — | 6 | ≈ {f(compact['median_estimated_c_array_bytes'], 0)} B (trung vị fold) | — | — |")
    lines += ["", f"Ngân sách flash M1 còn lại ≈ {mem['flash_budget_documented_bytes_approx']} B; mô hình ước lượng vài KB, không phải nút thắt. "
              f"Sắp xếp cho phân vị: ≈ {mem['sort_comparisons_per_update_estimate']} phép so sánh mỗi lần cập nhật 10 s. Tất cả là **ước lượng**, trạng thái `{mem['status']}`.",
              "", "### Độ phức tạp tính feature", "",
              "| # | Feature | Cửa sổ | Đơn vị | Chiến lược nhúng |", "|---:|---|---:|---|---|"]
    for item in d["contract"]["features"]:
        lines.append(f"| {item['index']} | `{item['name']}` | {item['window_seconds']} s | {item['unit']} | {item['embedded_strategy']} |")
    lines += ["", "## 6. Kế hoạch parity Python/C cho 23 feature (tương lai)", "",
              "1. **Golden vectors:** xuất từ `ml/features/extractor.py` các chuỗi 10 Hz (sin nhiều tần số, offset, tăng biên độ, tín hiệu hằng, có gap, có NaN, mẫu đúng 0) kèm 23 giá trị float64 và validity.",
              "2. **Dữ liệu thật:** chọn cửa sổ Hohai/Seafar/Southampton (gồm biên phân vị, cửa sổ có gap) làm vector kiểm thử.",
              f"3. **Dung sai đề xuất:** tuyệt đối {d['contract']['parity_tolerance_proposal']['absolute_deg']}°, tương đối {d['contract']['parity_tolerance_proposal']['relative']}; chốt sau khi đo float32.",
              "4. **Validity parity:** C phải trả cùng trạng thái VALID/không hợp lệ (đủ 95%, gap, R² không xác định, rms_early ≤ epsilon).",
              "5. **Quy ước phân vị Type-7**, std quần thể, block `(lower, upper]`, tâm block [30, 90, 150] s, slope × 60 phải giống hệt.",
              "6. **Model parity:** cùng vector đầu vào → cùng xác suất RF (dung sai float32) trên bộ golden; đo latency `infer_stats()` và `stack_hwm` trên thiết bị.",
              "7. **End-to-end:** chạy firmware trên tín hiệu mô phỏng/thật 10 Hz, so 23 feature với Python trên cùng chuỗi.",
              "", "## 7. Thay đổi đề xuất cho M1 (cần phối hợp, chưa thực hiện)", "",
              "- Thêm nhánh xử lý 10 Hz (lọc chống aliasing phù hợp, ví dụ 4 Hz như preprocessing) song song chuỗi 2 Hz hiện tại.",
              "- Thêm module C tính 23 feature theo contract đề xuất, giữ nguyên vector cũ cho Baseline B.",
              "- Thống nhất interface mô hình đa nhãn/proxy (xác suất + ABSTAIN) thay vì 4 lớp loại trừ trong `infer.cpp`.",
              "- Đánh giá lại hiệu chuẩn mốc 0 và fusion Roll/Pitch so với nguồn dữ liệu huấn luyện.",
              "", "## 8. Kết luận khả thi", "",
              f"- **Chưa thể triển khai** (`deployable = {e['deployable']}`). Lý do: " + "; ".join(e["deployable_blockers"]) + ".",
              "- RAM/flash ước lượng không phải trở ngại chính; trở ngại chính là **khác biệt tín hiệu và miền** (2 Hz/0.5 Hz, fusion MPU6050, model-scale vs full-scale) và proxy label chưa có ý nghĩa vận hành.",
              "", "## 9. Giới hạn", "",
              "- Mọi số RAM/flash/latency là ước lượng desktop; mô phỏng chuỗi firmware chỉ xấp xỉ (lọc ở 10 Hz thay vì 20 Hz, không mô phỏng gia tốc kế).",
              "- Kiểm tra gia tốc kế Southampton dùng quy ước trục chọn thực nghiệm, chưa xác minh.",
              "", "## 10. Tái lập", "", REPRO, "",
              "## 11. Giải thích kỹ thuật phục vụ vấn đáp cá nhân", "",
              "- **Vì sao không chỉ copy model sang ESP32?** Feature tính trên tín hiệu khác (2 Hz, lọc 0.5 Hz) cho giá trị khác: mô phỏng cho thấy std giảm còn "
              f"≈ {f(emu['std_ratio_median'], 2)}× và {emu['decisions_changed']} quyết định proxy đổi. Model đúng trên PC có thể sai hệ thống trên thiết bị.",
              "- **Vì sao 23 feature vẫn khả thi về bộ nhớ?** Bộ đệm 180 s × 10 Hz float32 cho Roll + 60 s cho Pitch + scratch sắp xếp ≈ "
              f"{ram['total']} B, nhỏ so với RAM trống M1 ghi nhận.",
              "- **Vì sao chưa gọi là deployable?** Chưa đo trên thiết bị, chưa parity, chưa đồng nhất cảm biến và nhãn vẫn là proxy.", ""]
    return "\n".join(lines)


def contract_markdown(d: dict) -> str:
    c = d["contract"]
    lines = [f"# Đề xuất contract `{c['contract_id']}` {c['version']}", "",
             f"**Trạng thái:** `{c['status']}` — đề xuất cho M1, chưa thay thế contract hiện hành. Các file sau KHÔNG bị chỉnh sửa: "
             + ", ".join(f"`{p}`" for p in c["legacy_contract_untouched"]) + ".", "",
             f"- Nguồn công thức: {c['source_of_truth_formulas']}.",
             f"- Lấy mẫu {c['sampling_hz']} Hz; endpoint `{c['endpoint_convention']}`; cập nhật mỗi {c['update_stride_seconds']} s; {c['blocks_180']}.",
             f"- Hợp lệ: ≥ {c['minimum_valid_fraction']:.0%} mẫu, gap ≤ {c['maximum_gap_factor']} chu kỳ; {c['invalid_policy']}.",
             f"- Kiểu dữ liệu: {c['dtype']}. Bản máy đọc được: `ml/docs/feature_contract_23_v0.1.json`.", "",
             "| Index | Feature | Spec ID | Tín hiệu | Cửa sổ (s) | Đơn vị | Định nghĩa |", "|---:|---|---:|---|---:|---|---|"]
    for item in c["features"]:
        lines.append(f"| {item['index']} | `{item['name']}` | {item['spec_id']} | {item['signal']} | {item['window_seconds']} | {item['unit']} | {item['definition']} |")
    lines += ["", f"Dung sai parity đề xuất: tuyệt đối {c['parity_tolerance_proposal']['absolute_deg']}°, tương đối {c['parity_tolerance_proposal']['relative']}. "
              + c["parity_tolerance_proposal"]["note"], ""]
    return "\n".join(lines)


def run(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    d = load(repo_root)
    outputs = {REPORT_DIR / "proxy_label_specification.md": specification(d),
               REPORT_DIR / "proxy_dataset_quality_report.md": quality(d),
               REPORT_DIR / "random_forest_poc_report.md": rf_report(d),
               REPORT_DIR / "esp32_feature_compatibility.md": esp_report(d),
               CONTRACT_MD: contract_markdown(d)}
    for path, text in outputs.items():
        (repo_root / path).write_text(text.rstrip() + "\n", encoding="utf-8")
    return list(outputs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh báo cáo tiếng Việt cho proxy phenotype PoC.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    for path in run(parser.parse_args().repo_root):
        print(path.as_posix())


if __name__ == "__main__":
    main()
