# Pipeline khảo sát và gán nhãn SVMG

## Phạm vi

Pipeline đối chiếu các cửa sổ feature đã trích xuất với tài liệu nguồn để khảo sát khả năng xây dựng nhãn `NORMAL`, `HIGH_ROLL`, `PERSISTENT_OFFSET` và `AMPLITUDE_GROWTH`. Mặc định là `feasibility`: không áp ngưỡng suy đoán và không xem dữ liệu không nhãn là NORMAL. Chế độ `exploratory_proxy` chỉ tạo ứng viên `PROXY_RULE` khi từng rule được cấu hình đủ ngưỡng cùng `evidence_reference`; proxy không phải ground truth.

Hiện cấu hình mọi rule đều tắt do chưa có giới hạn hazard/operating envelope độc lập được phê duyệt. Vì vậy lần chạy hiện tại xuất `UNLABELED` cho các cửa sổ đủ điều kiện. Không có label ground truth hoặc quyết định human review được phát hiện trong artifact hiện hành.

## Dữ liệu và quy ước

Input là `ml/data/features/{dataset}/feature_values.parquet` và `feature_metadata.parquet`. Chỉ dùng cửa sổ trailing 180 giây có đủ angle-only 23 feature `VALID`; endpoint tuân theo `(t-W,t]`. Các feature 60 giây tại endpoint vẫn sử dụng cửa sổ 60 giây tương ứng. Session và segment không bị ghép; các cửa sổ stride 10 giây chồng lấn và không độc lập. Dataset/session/segment nằm trong label metadata, không phải feature vector.

Seafar có một session thật với timestamp gaps/duplicates đã tách segment; Hohai có 21 experimental sessions, thời gian suy từ 50 Hz và không có gyro trực tiếp; Southampton có 47 model-scale runs nhưng chỉ Run 14 hỗ trợ 180 giây. Điều kiện sóng và tên thí nghiệm chỉ là provenance/context, không tự sinh nhãn. Xem [Real Dataset Audit](../audit/real_dataset_audit_report.md), [Feature Extraction results](../reports/features/feature_extraction_results.md) và [Labeling feasibility report](../reports/labeling/labeling_feasibility_report.md).

## Chạy lại

Môi trường chạy và phiên bản thư viện đã đo được ghi trong `ml/reports/labeling/labeling_summary.json`; các phiên bản tái tạo đã dùng được ghim trong `ml/labeling/requirements.txt` (Python 3.14.6). Từ repository root:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r ml/labeling/requirements.txt
python -m ml.labeling.run --config ml/labeling/config.yaml --dataset all --mode feasibility
python -m ml.labeling.run --config ml/labeling/config.yaml --dataset seafar --mode feasibility
python -m pytest ml/labeling/tests ml/features/tests ml/preprocessing/tests ml/audit -q
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/09_labeling_feasibility_seafar.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/10_labeling_feasibility_hohai.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/11_labeling_feasibility_southampton.ipynb
python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/12_labeling_comparison.ipynb
```

`--dry-run` chỉ kiểm tra schema và số cửa sổ. `--mode exploratory_proxy` vẫn không gán phenotype nếu rules chưa bật. Trước khi bật rule, cung cấp ngưỡng có đơn vị/phạm vi và tài liệu tham chiếu trong config, xem xét bằng team, rồi ghi lại rule version.

External labels (nếu nhóm cung cấp sau này) có thể được nạp từ CSV, JSONL hoặc Parquet bằng cách đặt `labeling.external_annotations_path` trong YAML. File cần `dataset_source`, `session_id`, `segment_id`, `window_start_seconds`, `window_end_seconds`, `label` và `evidence_reference`; khóa phải khớp chính xác cửa sổ hiện có, nhãn trùng cửa sổ bị từ chối. Không có external annotation path mặc định.

Review queue chia tầng `CLEAR_PROXY_CANDIDATE` và `CONFLICTING_PHENOTYPES` khi có rule; có thể bật `BORDERLINE_CASE` bằng `review_borderline_relative_margin` sau khi nhóm duyệt biên review. `SUSPECTED_FALSE_POSITIVE` chỉ được khởi tạo từ một đánh giá reviewer bác bỏ proxy, không suy ra tự động từ thống kê.

## Artifact và review

Output đầy đủ nằm trong `ml/data/labels/` (Parquet tách riêng cho proxy candidates, unlabeled, review-required và verified/human-reviewed annotations; review queue, annotation template, provenance và chẩn đoán) và bị loại khỏi Git. Báo cáo nhỏ/tái lập nằm trong `ml/reports/labeling/` và được theo dõi. Mẫu annotation được version-control tại `ml/labeling/templates/annotation_template.csv`. Chỉ quyết định người duyệt thực tế mới được ghi là `HUMAN_REVIEWED`; mọi thay đổi cần reviewer, timestamp, notes và audit trail. `append_review_event` nối sự kiện JSONL để giữ lịch sử trước/sau không bị ghi đè. Không ghi đè bảng feature.

## Phòng tránh circular validation

Nếu proxy dùng `roll_std_60`, `roll_mean_180` hay RMS slope, các feature tương ứng trực tiếp/gián tiếp định nghĩa nhãn. Độ chính xác mô hình trên những proxy label như vậy chỉ đo tái tạo rule. Cần nhãn sự kiện/tham chiếu độc lập, split theo session và kiểm định vật lý riêng trước khi diễn giải kết quả là nhận diện nguy hiểm.
