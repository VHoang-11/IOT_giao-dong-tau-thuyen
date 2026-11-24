# Pipeline tiền xử lý dữ liệu SVMG

Pipeline này thực hiện Data Preprocessing (tiền xử lý dữ liệu) cho Time Series (chuỗi quan sát theo thời gian) thực từ Seafar, Hohai 6-DOF và Southampton KCS, đưa dữ liệu về schema thống nhất để chuẩn bị Feature Extraction (trích xuất đặc trưng). Pipeline **chưa trích xuất 30 candidate features**, chưa gán nhãn, chưa train Random Forest và không thay đổi contract 14 feature trong [`contracts/features.md`](../../contracts/features.md) hoặc [`core/include/svmg_core.h`](../../core/include/svmg_core.h).

## Tài liệu liên quan

- [Báo cáo Real Dataset Audit](../audit/real_dataset_audit_report.md)
- [Đặc tả 30 candidate features](../docs/feature_specification_30.md)
- [Ma trận availability](../docs/feature_availability_matrix.md)
- [Thiết kế preprocessing đề xuất](../docs/preprocessing_design.md)
- [Kết quả chạy preprocessing](../reports/preprocessing/preprocessing_results.md) (được sinh sau khi chạy pipeline)
- [Rà soát kỹ thuật cuối](../reports/preprocessing/final_technical_review.md) (đối soát hàng, kiểm định filter và reproducibility)

## Kiến trúc

| Module | Trách nhiệm |
|---|---|
| `config.py`, `config.yaml` | Đọc/cấu hình đường dẫn, Sampling Rate, gap, filter và output. |
| `schemas.py` | Kiểu dữ liệu `RawSession` và `ProcessedSegment`. |
| `seafar.py` | Stream JSON record Seafar, map cột và chuyển đổi rate có đơn vị rad/min trong tên trường. |
| `hohai.py` | Đọc từng worksheet read-only; thời gian tương đối suy từ index ở 50 Hz. |
| `southampton.py` | Đọc từng IMU CSV; giữ Delta Angle raw, không tự map thành gyro. |
| `common.py` | Parse, thống kê, chính sách duplicate và phân đoạn theo timestamp. |
| `signal_processing.py` | Làm sạch, lọc causal, resampling không upsample và tạo segment độc lập. |
| `quality_checks.py` | Thống kê trước/sau, so sánh theo timestamp đầu ra và band-power. |
| `diagnostics.py` | Sinh 5 hình có tiêu đề/chú giải tiếng Việt. |
| `run.py` | CLI điều phối, ghi Parquet, provenance, summary và báo cáo. |
| `tests/` | Unit tests dùng fixture tổng hợp nhỏ; fixture không dùng để train. |

## Schema đầu ra

Mỗi Parquet có `dataset_source`, `session_id`, `segment_id`, `time_seconds`, `roll_deg`, `pitch_deg`, `gyro_x_rad_s`, `gyro_y_rad_s` cùng các kênh chuyển động bổ sung khi nguồn có. Thời gian trong Parquet là giây tương đối từ đầu session; thời gian/đơn vị gốc và nguồn provenance được lưu riêng trong `provenance.json` bên cạnh từng tệp. Gyro có thể nullable. `dataset_source`, `session_id`, `segment_id` là metadata để nhóm và kiểm toán, **không phải** đầu vào Random Forest.

## Cài đặt

Khuyến nghị tạo virtual environment của dự án với Python 3.10 trở lên:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r ml/preprocessing/requirements.txt
```

Môi trường dùng trong lần chạy đã ghi Python và phiên bản từng dependency trong `ml/reports/preprocessing/preprocessing_summary.json` (hiện Python 3.14.6). `requirements.txt` đặt các dải phiên bản tương thích; để đối chiếu số liệu chặt chẽ, nên dùng cùng phiên bản Python/dependency đã ghi trong summary.

## Vị trí dữ liệu và quy tắc Git

Đặt dữ liệu raw tại các đường dẫn repository-relative sau trước khi chạy:

- `ml/data/raw/seafar/cleaned_imu_gps_data.json`
- `ml/data/raw/hohai/6-DOF ship motions Data.xlsx` (và PDF mô tả nếu nhóm có)
- `ml/data/raw/southampton/Raw Data_IMU/*.csv` cùng workbook Test Plan trong `ml/data/raw/southampton/Readme/` nếu cần provenance điều kiện sóng.

Toàn bộ `ml/data/raw/` và `ml/data/processed/` đã được `.gitignore` loại trừ. Raw datasets phải được nhóm cung cấp riêng; Parquet, provenance và hình lớn được tạo lại tại máy chạy. Không add/commit hai thư mục dữ liệu này. Các báo cáo Markdown/JSON nhỏ và notebook được lưu riêng trong repository.

Pipeline và dependency được dùng khi tạo kết quả được ghi trong `ml/reports/preprocessing/preprocessing_summary.json`. Lệnh chạy đầy đủ tự chạy `python -m pytest ml/preprocessing/tests -q` sau khi xử lý và ghi số đạt/trượt vào báo cáo; `--dry-run` chỉ kiểm tra input, không chạy suite và không ghi artifact.

## Chạy lại

Chạy từ repository root:

```bash
# Chỉ đọc/kiểm tra schema, timestamp, duplicate và gap; không ghi artifact
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dry-run

# Chạy riêng một nguồn
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset seafar
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset hohai
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset southampton

# Chạy cả ba nguồn
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset all

# Kiểm thử
python -m pytest ml/preprocessing/tests -q
```

CLI xuất thông báo tiếng Việt. Lỗi đầu vào sẽ dừng pipeline với lỗi rõ ràng; không âm thầm bỏ qua nguồn.

## Notebook phân tích theo nguồn

Bốn notebook trong `ml/notebooks/` trình bày dữ liệu raw, kết quả preprocessing đã ghi, thống kê trước/sau, hình chẩn đoán, window eligibility và phần giải thích phục vụ vấn đáp. Chúng gọi lại loader hiện hữu trong `ml.preprocessing`, đọc Parquet và summary đã tạo; notebook không lặp lại thuật toán làm sạch hoặc ghi đè artifact. Các bảng preview chỉ hiển thị vài hàng, không nhúng toàn bộ raw data.

Từ repository root, sau khi cài dependencies ở trên, chạy và lưu output cell vào notebook bằng:

```bash
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/01_seafar_preprocessing.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/02_hohai_preprocessing.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/03_southampton_preprocessing.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/04_preprocessing_comparison.ipynb
```

Notebook yêu cầu dữ liệu raw có sẵn tại `ml/data/raw/`, cùng báo cáo summary và Parquet đã được pipeline sinh trong `ml/reports/preprocessing/` và `ml/data/processed/`. Việc chạy notebook chỉ đọc các artifact đó và ghi kết quả tính toán/biểu đồ vào `.ipynb`; muốn tái tạo dữ liệu processed, chạy CLI pipeline bằng các lệnh ở mục trên trước.

## Quyết định kỹ thuật trong cấu hình hiện tại

- Target 10 Hz để so sánh với Seafar; không upsample dữ liệu thấp tần.
- Khi giảm mẫu, các kênh liên tục dạng số hữu hạn được lọc Butterworth order 4, cutoff 4 Hz bằng `sosfilt` causal trước khi chọn mẫu 10 Hz. Bộ lọc khởi tạo steady-state ở mẫu đầu và bỏ 2 giây warmup; không bù phase bằng dữ liệu tương lai. Trường hậu tố `_raw` được giữ nguyên và không được coi là đã anti-alias.
- 10 Hz / 4 Hz là baseline thực nghiệm hiện tại. Attenuation lý thuyết tại Nyquist đầu ra 5 Hz khoảng 8,8 dB, chưa đủ để tuyên bố anti-alias đã được xác nhận đầy đủ. Giai đoạn kế tiếp cần thử bộ lọc anti-alias mạnh hơn và so sánh độ ổn định feature giữa các lựa chọn filter/Sampling Rate trước khi chọn baseline triển khai.
- Gap lớn hơn 1,5 lần median chu kỳ tạo segment mới. Không lọc hoặc nội suy qua gap/ranh giới session.
- Duplicate cùng timestamp và cùng giá trị giữ bản ghi đầu. Duplicate xung đột bị loại toàn nhóm; không lấy trung bình.
- Không điền giá trị thiếu bằng 0. Hàng thiếu timestamp/Roll/Pitch bị loại; gyro thiếu giữ null.
- Unit Seafar rate dựa trên tên trường rad/min, chuyển sang rad/s và giữ dấu; trục/nguồn phần cứng chưa xác minh. Southampton Delta Angle giữ riêng do ngữ nghĩa chưa chắc chắn. Hohai không có gyro đo.
- Thống kê báo cáo mô tả; ngưỡng quality trong config là ngưỡng kỹ thuật, không phải ngưỡng an toàn hàng hải.

## Artifact và reproducibility

- Parquet và hình chẩn đoán: `ml/data/processed/` (được gitignore).
- Báo cáo tiếng Việt: `ml/reports/preprocessing/preprocessing_results.md`.
- Summary JSON: `ml/reports/preprocessing/preprocessing_summary.json`.
- Config: `ml/preprocessing/config.yaml`; SHA-256 và revision mã nguồn nếu có được lưu trong summary.
- Summary, inventory, figure references và provenance dùng đường dẫn repository-relative để không phụ thuộc thư mục máy chạy.
- Cùng raw data, config và phiên bản dependency sẽ tạo cùng dữ liệu số đầu ra; báo cáo có thời điểm chạy và do đó không giống byte-for-byte giữa các lần chạy.

