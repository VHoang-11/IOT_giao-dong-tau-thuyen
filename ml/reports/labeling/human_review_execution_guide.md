# Hướng dẫn thực hiện Human Review

## Chuẩn bị artifact review

Từ thư mục gốc repository, kích hoạt môi trường dự án rồi chạy:

```bash
python -m ml.labeling.human_review_workflow --prepare-batches
```

Lệnh tạo hai batch dưới `ml/data/labels/annotation_pilot/batches/` mà không thay đổi queue gốc:

- `pilot_29.csv`: đủ 23 session; Seafar 4, Hohai 21 (mỗi session một đại diện), Southampton 4.
- `extended_63.csv`: 63 cửa sổ Hohai còn lại.

Quy tắc chọn Hohai: sắp theo endpoint, start và review ID; lấy hạng trung vị thấp (lower median), xác định bởi `floor((n-1)/2)`. Cách này chọn cửa sổ theo thời gian, không dùng nhãn hay giá trị feature để ưu tiên lớp. Các batch chỉ là bản sao tham chiếu, không chứa annotation.

## Cài môi trường

Từ repository root, dùng Python 3.14 theo môi trường M2:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r ml/labeling/requirements.txt
```

## Mở giao diện và thực hiện review

```bash
python -m streamlit run ml/labeling/review_app.py
```

Trong trình duyệt trên máy local:

1. Chọn batch pilot 29 hoặc batch mở rộng 63.
2. Nhập `reviewer_id` cá nhân; không dùng ID chung cho nhiều người.
3. Chọn `review_id`; kiểm tra dataset/session/segment/window, biểu đồ Roll/Pitch, bối cảnh trước cửa sổ, cờ chất lượng, metadata và bảng 23 angle features kèm validity.
4. Đánh dấu từng phenotype là chưa đánh giá/không quan sát/quan sát; chọn evidence category, quyết định, evidence reference, ghi chú và ambiguity reason khi cần.
5. Nhấn lưu. Hệ thống kiểm tra schema, provenance, category-transition và trùng cặp mẫu/reviewer. Gửi cùng mẫu bởi reviewer khác được giữ như một đánh giá độc lập.

Không chọn `NORMAL` nếu không có operating envelope dương tính và evidence reference. `OBSERVED_MOTION_PHENOTYPE` chỉ là quan sát chuyển động; không xác nhận hazard. `VERIFIED_OPERATIONAL_HAZARD` và `VERIFIED_NORMAL_ENVELOPE` bắt buộc có tham chiếu external độc lập.

## Lưu quyết định và audit trail

Ledger hiện tại được ghi tại `ml/data/labels/annotation_pilot/review_decisions.csv`; mỗi hàng có `review_id`, `decision_id`, reviewer, annotation schema version, decision, phenotype flags, evidence, timestamp UTC và trạng thái. Audit append-only nằm tại `ml/data/labels/annotation_pilot/review_audit.jsonl`. Cả hai tệp cùng batch/plots bị `.gitignore` loại khỏi Git.

Cùng reviewer không thể gửi trùng cùng review ID; giao diện từ chối ghi đè. Nếu phát hiện lỗi trong quyết định, giữ nguyên file audit hiện tại và liên hệ người phụ trách để thực hiện quy trình sửa đổi có version riêng; không xóa/sửa dòng cũ bằng spreadsheet.

## Tái tạo báo cáo và kiểm thử

```bash
python -m ml.labeling.human_review_workflow --refresh-reports
python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q
```

Các report Markdown nhỏ được lưu trong `ml/reports/labeling/`. Không cần backend, MQTT hoặc kết nối ESP32.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Em đã làm gì?** Tạo batch xác định, giao diện xem signal/feature và lưu annotation có provenance.
- **Vì sao giữ reviewer ID và audit JSONL?** Để truy về người đưa quyết định và giữ lịch sử append-only; CSV là ledger dễ đọc để phân tích.
- **Tại sao có ba lớp evidence?** Quan sát phenotype, hazard verified và dữ liệu chưa đủ bằng chứng có ý nghĩa khác nhau; không thể xem hình Roll/Pitch là ground truth an toàn.
- **Kết quả thực tế?** Hiện batch có 29+63 record phủ 23 session, nhưng 0 quyết định thật; hệ thống không tự gán nhãn.
- **Rủi ro còn lại?** Cửa sổ trùng lặp phụ thuộc thời gian; review phải blind với `queue_suggested_label` khi phù hợp và split theo session.
