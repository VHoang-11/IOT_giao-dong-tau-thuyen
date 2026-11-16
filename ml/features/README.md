# Pipeline trích xuất 30 candidate feature

Module này tính 30 candidate feature theo đúng thứ tự trong [`ml/docs/feature_specification_30.md`](../docs/feature_specification_30.md). Đây là các định nghĩa vận hành để kiểm thử, **chưa được nhóm phê duyệt** và không thay đổi contract 14 feature hiện hành tại [`contracts/features.md`](../../contracts/features.md) hoặc [`core/include/svmg_core.h`](../../core/include/svmg_core.h).

## Kiến trúc

| Tệp | Trách nhiệm |
|---|---|
| `spec.py` | Thứ tự feature, nhóm, cửa sổ và trạng thái validity. |
| `calculations.py` | Công thức thống kê, quantile Type-7, hồi quy và zero-crossing/period. |
| `extractor.py` | Kiểm tra schema; tạo cửa sổ trailing theo từng segment; tính feature và validity. |
| `stability.py` | So sánh sensitivity cutoff 4 Hz baseline với 3 Hz thay thế trên segment đại diện; không ghi đè dữ liệu baseline. |
| `diagnostics.py` | Hình phân bố feature và trạng thái validity. |
| `reporting.py` | Sinh hai báo cáo tiếng Việt từ kết quả chạy. |
| `run.py` | CLI, chạy dataset, Parquet, summary JSON, báo cáo và unit tests. |
| `review.py` | Kiểm tra subset angle-only và đối chiếu period thực bằng phép tính tham chiếu độc lập. |
| `config.yaml` | Sampling Rate, stride, validity, quy ước công thức, sensitivity và đường dẫn. |
| `tests/` | Kiểm thử công thức và ranh giới cửa sổ trên fixture nhỏ có nghiệm biết trước. |

## Cài đặt và dữ liệu đầu vào

Tạo môi trường theo hướng dẫn tại [`ml/preprocessing/README.md`](../preprocessing/README.md), cài `ml/preprocessing/requirements.txt`, rồi đặt raw data đúng vị trí như README đó. Trước tiên cần chạy preprocessing để tạo `ml/data/processed/` và provenance. Dữ liệu raw, processed và feature Parquet đều bị `.gitignore` loại trừ; chúng không được commit. Báo cáo nhỏ, cấu hình, mã nguồn và notebook được theo dõi bằng Git.

Các dependency chính là Python, NumPy, pandas, PyArrow, SciPy, PyYAML, Matplotlib và pytest. Phiên bản chính xác của lần chạy nằm trong `ml/reports/features/feature_extraction_summary.json`.

## Chạy lại

Chạy từ repository root:

```bash
# Tạo lại dữ liệu processed từ raw data (đặt raw theo ml/preprocessing/README.md)
python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset all

# Kiểm tra schema và provenance, không ghi bảng feature
python -m ml.features.run --config ml/features/config.yaml --dataset all --dry-run

# Trích xuất một nguồn hoặc cả ba nguồn; lệnh đầy đủ chạy sensitivity và unit tests
python -m ml.features.run --config ml/features/config.yaml --dataset seafar
python -m ml.features.run --config ml/features/config.yaml --dataset hohai
python -m ml.features.run --config ml/features/config.yaml --dataset southampton
python -m ml.features.run --config ml/features/config.yaml --dataset all

# Chạy riêng bộ kiểm thử
python -m pytest ml/features/tests -q

# Tái tạo báo cáo rà soát period/subset từ Parquet và summary hiện có
python -m ml.features.review
```

`--skip-stability` chỉ bỏ sensitivity study; mặc định lệnh `--dataset all` thử lại cutoff 3 Hz trên các nguồn giảm mẫu từ 50 Hz. Chạy mỗi nguồn riêng chỉ ghi lại dữ liệu/báo cáo nguồn đó; để tái tạo summary hoàn chỉnh cần chạy `--dataset all`.

## Notebook

Từ repository root, sau khi đã chạy preprocessing và feature extraction:

```bash
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/05_feature_extraction_seafar.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/06_feature_extraction_hohai.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/07_feature_extraction_southampton.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/08_feature_extraction_comparison.ipynb
```

Notebook gọi lại `ml.features.extractor` khi minh họa phép tính, đọc feature Parquet và summary thực tế, và lưu hình lớn trong `ml/data/features/diagnostics/` (đã gitignore). Chúng không nhúng toàn bộ dữ liệu và không tự chạy lại pipeline trên raw data.

## Quy ước và giới hạn

- Mỗi Parquet là một segment độc lập; không nối session, sheet hoặc run. Cửa sổ là trailing `(t-W,t]`, stride 10 giây, không dùng dữ liệu sau endpoint.
- Hàng feature và metadata được tách: `feature_values.parquet` có `window_id` cùng đúng 30 cột; `feature_metadata.parquet` chứa danh tính nguồn/session/segment, provenance và trạng thái cho từng feature. Metadata không thuộc vector ML.
- Giá trị không hợp lệ là null trong bảng số và có lý do trong `validity_json`. Không điền 0; hàng partial không được xem là ví dụ đủ 30 feature.
- Gyro Hohai thiếu đo trực tiếp; Seafar và Southampton chưa xác minh đủ mapping canonical. Không tính gyro từ đạo hàm Roll/Pitch và không map Delta Angle thành rad/s khi chưa có bằng chứng.
- Cửa sổ 60/180 giây phải nằm hoàn toàn trong một segment. Ngưỡng coverage 95%, epsilon tỷ số RMS, quy tắc zero-crossing và các lựa chọn period/trend đều là engineering proposal, chờ nhóm xác nhận.
- Baseline preprocessing giữ 10 Hz / Butterworth bậc 4 cutoff 4 Hz. So sánh cutoff 3 Hz chỉ là sensitivity study trên segment đại diện; chưa chứng minh baseline anti-alias tối ưu hoặc đủ mạnh.

## Báo cáo kết quả

- [Kết quả Feature Extraction](../reports/features/feature_extraction_results.md)
- [Tóm tắt JSON](../reports/features/feature_extraction_summary.json)
- [Kết quả kiểm định](../reports/features/feature_validation_results.md)
- [Rà soát chu kỳ và tập angle-only 23](../reports/features/feature_period_subset_review.md)
- [Đặc tả 30 candidate feature](../docs/feature_specification_30.md)
- [Ma trận khả dụng](../docs/feature_availability_matrix.md)
