# Kiểm định pipeline labeling

Phiên bản pipeline: `0.1.0`. Mode đã chạy: `feasibility`. Test command: `python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q`; kết quả: **60 đạt, 0 lỗi, 0 bỏ qua**.

Môi trường đã chạy: `{"ipykernel": "6.31.0", "jupyter": "1.1.1", "matplotlib": "3.11.0", "nbclient": "0.11.0", "nbconvert": "7.17.1", "nbformat": "5.10.4", "numpy": "2.4.6", "pandas": "3.0.3", "pyarrow": "23.0.1", "pytest": "9.0.3", "python": "3.14.6", "pyyaml": "6.0.3"}`. Danh sách phụ thuộc được ghim tại `ml/labeling/requirements.txt`.

## Kiểm soát đã thực hiện

- Đọc validity JSON và chỉ chọn đủ 23 angle-only feature ở endpoint có lịch sử 180 giây.
- Join values/metadata one-to-one theo window ID; giữ dataset/session/segment riêng.
- Kiểm tra status/value theo schema; proxy không thể mang `VERIFIED`.
- Mặc định không có rule bật; `NORMAL` không suy từ không phát hiện abnormal.
- Cửa sổ end được dùng làm điểm chốt; không truy cập sample sau endpoint.
- Candidate output chỉ ở ignored `ml/data/labels/`, không ghi feature tables.

## Giới hạn kiểm định

Unit/integration tests bằng fixture tổng hợp chỉ kiểm tra logic; không phải nhãn thực và không dùng huấn luyện. Thực nghiệm trên real feature Parquet xác nhận counts/identity, không xác nhận hazard physics. Human review chưa diễn ra.
