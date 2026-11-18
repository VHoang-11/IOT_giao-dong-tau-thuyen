from __future__ import annotations

from io import BytesIO
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ml.labeling.human_review_workflow import (  # noqa: E402
    INITIAL_BATCH_NAME,
    EXTENDED_BATCH_NAME,
    build_quality_summary,
    load_feature_review,
    load_review_plot,
    review_plot_data_uri,
    load_pilot_forms,
    recover_decision_ledger,
    save_human_decision,
    write_human_reports,
    write_quality_summary,
    write_review_batches,
)
from ml.labeling.pilot_decisions import ANNOTATION_SCHEMA_VERSION  # noqa: E402


@st.cache_data(show_spinner=False)
def _load_feature_table(dataset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = REPO_ROOT / "ml/data/features" / dataset
    return pd.read_parquet(root / "feature_values.parquet"), pd.read_parquet(root / "feature_metadata.parquet")


def _selected_options(category: str) -> tuple[str, ...]:
    if category == "VERIFIED_NORMAL_ENVELOPE":
        return ("NORMAL",)
    if category == "UNVERIFIED":
        return ("REVIEW_REQUIRED", "UNLABELED")
    if category == "PROXY_RULE":
        return ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")
    return ("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")


def main() -> None:
    st.set_page_config(page_title="SVMG Human Review", layout="wide")
    st.title("Giao diện Human Review — Smart Vessel Motion Guard")
    st.caption("Giao diện local chỉ phục vụ đánh giá con người; không kết nối backend, MQTT hoặc ESP32 và không tự sinh nhãn.")

    form_path = REPO_ROOT / "ml/data/labels/annotation_pilot/annotation_pilot.csv"
    try:
        forms = load_pilot_forms(REPO_ROOT, form_path)
        ledger = recover_decision_ledger(REPO_ROOT, forms)
    except Exception as exc:
        st.error(f"Không tải được artifact review: {exc}")
        st.stop()

    batches_dir = REPO_ROOT / "ml/data/labels/annotation_pilot/batches"
    if not (batches_dir / "pilot_29.csv").is_file() or not (batches_dir / "extended_63.csv").is_file():
        try:
            write_review_batches(REPO_ROOT, forms)
        except Exception as exc:
            st.error(f"Không tạo được batch review: {exc}")
            st.stop()

    sidebar = st.sidebar
    sidebar.header("Phiên review")
    reviewer_id = sidebar.text_input("Mã reviewer cá nhân", placeholder="Ví dụ: R001")
    batch_name = sidebar.selectbox("Batch", [INITIAL_BATCH_NAME, EXTENDED_BATCH_NAME, "all_92"])
    batch_file = {INITIAL_BATCH_NAME: "pilot_29.csv", EXTENDED_BATCH_NAME: "extended_63.csv"}.get(batch_name)
    if batch_file:
        batch = pd.read_csv(batches_dir / batch_file, keep_default_na=False)
    else:
        batch = forms.assign(review_id=forms.review_sample_id)

    if reviewer_id.strip():
        previously_reviewed = set(ledger.loc[ledger.reviewer_id.astype(str).eq(reviewer_id.strip()),
                                             "review_id"].astype(str))
        available = batch.loc[~batch.review_id.astype(str).isin(previously_reviewed)].copy()
        sidebar.write(f"Đã gửi bởi bạn trong batch này: {len(batch) - len(available)}")
    else:
        available = batch.copy()
        sidebar.info("Nhập reviewer ID trước khi lưu. Quyết định của từng reviewer được ghi riêng.")
    sidebar.metric("Số record trong batch", len(batch))
    sidebar.metric("Số quyết định đã lưu toàn bộ", len(ledger))

    if available.empty:
        st.success("Bạn đã review hết record trong batch này. Quyết định hiện có không bị ghi đè.")
        return

    def _format_review_id(review_id: str) -> str:
        row = available.loc[available.review_id.astype(str).eq(str(review_id))].iloc[0]
        return (f"{row.dataset_source} · {row.session_id} · {row.segment_id} · "
                f"({float(row.window_start_seconds):.1f}, {float(row.window_end_seconds):.1f}] giây")

    review_id = st.selectbox("Chọn record cần đánh giá", available.review_id.astype(str).tolist(),
                             format_func=_format_review_id)
    sample = available.loc[available.review_id.astype(str).eq(str(review_id))].iloc[0]
    identity = st.columns(4)
    identity[0].metric("Dataset", sample.dataset_source)
    identity[1].metric("Session", sample.session_id)
    identity[2].metric("Segment", sample.segment_id)
    identity[3].metric("ID review", review_id)
    st.write(f"**Cửa sổ:** ({float(sample.window_start_seconds):.1f}, {float(sample.window_end_seconds):.1f}] giây")
    st.write(f"**Schema:** {ledger.annotation_schema_version.iloc[0] if len(ledger) else ANNOTATION_SCHEMA_VERSION}")

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Tín hiệu Roll/Pitch và lịch sử")
        plot_path = (REPO_ROOT / str(sample.plot_path)).resolve()
        try:
            plot_bytes = load_review_plot(REPO_ROOT, sample.to_dict())
            with Image.open(BytesIO(plot_bytes)) as image:
                diagnostics = {
                    "Đường dẫn đã phân giải": str(plot_path),
                    "Tệp tồn tại": plot_path.is_file(),
                    "Độ dài PNG (byte)": len(plot_bytes),
                    "Định dạng": image.format,
                    "Kích thước (pixel)": f"{image.width} × {image.height}",
                    "Cách truyền đến trình duyệt": "data URI nhúng trong phần tử ảnh",
                }
            with st.expander("Chẩn đoán ảnh", expanded=False):
                st.json(diagnostics)
            st.image(review_plot_data_uri(plot_bytes), caption="Tín hiệu đã preprocessing; vùng tô là cửa sổ review, phần trước là lịch sử cùng segment.", width="stretch")
        except (FileNotFoundError, ValueError) as exc:
            st.error(f"Không thể đọc hoặc giải mã signal plot tại `{plot_path}`: {exc}. Kiểm tra lại tệp PNG của record này.")
        st.subheader("23 angle features tại endpoint")
        try:
            feature_rows = load_feature_review(REPO_ROOT, sample.to_dict())
            st.dataframe(feature_rows, width="stretch", hide_index=True)
        except Exception as exc:
            st.error(f"Không thể ghép feature row: {exc}")
    with right:
        st.subheader("Chất lượng và experiment metadata")
        try:
            st.json(json.loads(sample.quality_flags_json))
        except json.JSONDecodeError:
            st.warning(sample.quality_flags_json)
        try:
            st.json(json.loads(sample.experiment_metadata_json))
        except json.JSONDecodeError:
            st.warning(sample.experiment_metadata_json)
        if str(sample.experiment_metadata_reference).strip():
            st.write("**Tham chiếu tài liệu:**", sample.experiment_metadata_reference)
        st.caption("Metadata thử nghiệm là provenance, không tự tạo nhãn an toàn.")

    st.divider()
    st.subheader("Biểu mẫu annotation")
    st.caption("Giao diện chỉ ghi nhận phenotype quan sát được, reference đã xác minh hoặc evidence chưa đủ; không cho reviewer tự khai một nhãn proxy thành ground truth.")
    with st.form(f"review-{review_id}"):
        category = st.selectbox("Loại bằng chứng", [
            "OBSERVED_MOTION_PHENOTYPE", "VERIFIED_OPERATIONAL_HAZARD",
            "VERIFIED_NORMAL_ENVELOPE", "UNVERIFIED"],
            format_func=lambda value: {
                "OBSERVED_MOTION_PHENOTYPE": "Quan sát phenotype chuyển động",
                "VERIFIED_OPERATIONAL_HAZARD": "Hazard vận hành có nguồn xác minh độc lập",
                "VERIFIED_NORMAL_ENVELOPE": "Operating envelope NORMAL được xác nhận",
                "UNVERIFIED": "Chưa đủ hoặc chưa xác minh bằng chứng",
                "PROXY_RULE": "Nhãn proxy theo rule (không phải ground truth)",
            }[value])
        st.markdown("**Mỗi phenotype:** chọn chưa đánh giá, không quan sát thấy hoặc quan sát thấy.")
        flag_inputs = {}
        flag_columns = st.columns(3)
        states = {"Chưa đánh giá": None, "Không quan sát thấy": False, "Quan sát thấy": True}
        for idx, flag in enumerate(("HIGH_ROLL", "PERSISTENT_OFFSET", "AMPLITUDE_GROWTH")):
            label = {"HIGH_ROLL": "Dao động Roll biên độ lớn",
                     "PERSISTENT_OFFSET": "Roll lệch kéo dài",
                     "AMPLITUDE_GROWTH": "Biên độ dao động tăng"}[flag]
            selected = flag_columns[idx].selectbox(label, list(states), key=f"{review_id}-{flag}")
            flag_inputs[flag] = states[selected]
        decision = st.selectbox("Quyết định chính", _selected_options(category))
        review_status = st.selectbox("Trạng thái review", ["ACCEPTED", "NEEDS_DISCUSSION", "REJECTED"],
            format_func=lambda value: {"ACCEPTED": "Chấp nhận nhận định này", "NEEDS_DISCUSSION": "Cần thảo luận thêm", "REJECTED": "Bác bỏ nhận định đề xuất"}[value])
        evidence_reference = st.text_input("Evidence reference", value=str(sample.plot_path),
            help="Với VERIFIED/PROXY, nhập nguồn độc lập hoặc rule/config cụ thể. Hình tín hiệu không phải external hazard reference.")
        notes = st.text_area("Ghi chú và căn cứ của reviewer", placeholder="Mô tả tín hiệu quan sát được, độ không chắc chắn và lý do chọn quyết định.")
        ambiguity_reason = st.text_input("Lý do mơ hồ/chồng lấn (nếu có)")
        submitted = st.form_submit_button("Lưu quyết định không thể ghi đè")

    if submitted:
        if not reviewer_id.strip():
            st.error("Cần reviewer ID cá nhân trước khi lưu.")
        elif not notes.strip():
            st.error("Ghi chú reviewer là trường bắt buộc.")
        else:
            try:
                record = save_human_decision(REPO_ROOT, review_id, reviewer_id=reviewer_id,
                    evidence_category=category, reviewer_decision=decision,
                    phenotype_flags=flag_inputs, evidence_reference=evidence_reference,
                    reviewer_notes=notes, review_status=review_status,
                    ambiguity_reason=ambiguity_reason)
                summary = build_quality_summary(REPO_ROOT)
                write_human_reports(REPO_ROOT, summary)
                write_quality_summary(REPO_ROOT, summary)
                st.success(f"Đã lưu quyết định {record['decision_id']} với status {record['label_status']}; audit history đã nối thêm.")
                st.rerun()
            except Exception as exc:
                st.error(f"Không lưu được quyết định: {exc}")

    st.caption("Chưa có thao tác nào lưu đến khi bấm nút. Không hiển thị nhãn gợi ý trước khi review để hạn chế anchoring bias.")


if __name__ == "__main__":
    main()
