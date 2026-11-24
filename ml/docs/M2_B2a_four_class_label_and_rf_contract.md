# B2a — Đề xuất ontology bốn lớp và contract tích hợp RF

## Trạng thái và phạm vi

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| 23 feature và thứ tự đầu vào | `APPROVED` | Contract số học hiện hành; tài liệu này không sửa công thức. |
| Định nghĩa ontology phenotype | `PROPOSED` | Cần M1/M2 duyệt trước khi gán nhãn hoặc huấn luyện. |
| Bốn lớp loại trừ nhau | `BLOCKED` | Chưa có nhãn độc lập và chưa thống nhất cách xử lý overlap. |
| RF bốn lớp dùng trong firmware | `BLOCKED` | Artifact hiện có là PoC nhị phân theo proxy; chưa có `model.h` tương thích. |
| Huấn luyện/đánh giá trong B2a | `NOT_RUN` | Gói này chỉ thiết kế và rà soát bằng chứng hiện có. |

Các lớp ở đây mô tả **phenotype chuyển động quan sát được**. Không phải dự báo lật tàu, mức nguy hiểm hàng hải hay xác nhận an toàn.
Kết quả Wokwi 31 synthetic cases / 488 endpoints / 11.224 records là số liệu parity feature do milestone trước báo cáo; không xác nhận nhãn hay RF và không được tái diễn giải thành kết quả ML.

## Bằng chứng dữ liệu hiện có

Rà soát dựa trên `ml/reports/labeling/labeling_summary.json`, `label_evidence_summary.json`, `human_annotation_quality_report.md`, `training_readiness_assessment.md`, proxy/model reports và artifacts cục bộ. Báo cáo label hiện tại ở chế độ feasibility: các rule ứng viên tắt, không suy `NORMAL` từ việc không phát hiện lớp khác.

| Nguồn | Dữ liệu đủ 23 feature / session | Có thể đóng góp | Giới hạn nhãn và miền |
|---|---:|---|---|
| Hohai | 1.512 cửa sổ / 21 session | Khảo sát biến thiên phenotype trong thí nghiệm model-scale | Thời gian suy từ 50 Hz, không gyro trực tiếp; tên sheet/điều kiện thử không phải nhãn. Cửa sổ stride 10 s chồng lấn 94,4%. |
| Seafar | 1.318 cửa sổ / 1 session | Chuỗi cảm biến từ một tàu thật để khảo sát tín hiệu | Không có event/operating-state reference; trục, dấu, rate và mốc Roll chưa xác minh đầy đủ; một session không hỗ trợ đánh giá tổng quát. |
| Southampton | 34 cửa sổ / 1 run đủ cửa sổ 180 s | Tín hiệu model-scale và bối cảnh thử nghiệm | Test Plan là provenance, không phải hazard label; Delta Angle mapping chưa xác minh; các cửa sổ đều thuộc Run 14. |
| SVMG S0/S0b/S1/S2/S3/H1 | Các phiên mô phỏng có seed và metadata | Kiểm tra plumbing, warm-up, overlap và latency trong simulator | `expected_label`, mã scenario, event và forcing là metadata/đầu vào mô phỏng, không phải ground truth độc lập. Không chứng minh miền tàu thật. |

Pilot annotation hiện có 92 mẫu trên 23 session (84 Hohai, 4 Seafar, 4 Southampton): **0 quyết định reviewer, 0 nhãn HUMAN_REVIEWED, 0 external VERIFIED, 0 hazard reference và 0 normal-envelope reference**; 92 mẫu còn pending. Vì vậy chưa có phân bố lớp độc lập hoặc class imbalance có ý nghĩa để huấn luyện bốn lớp.

Artifact RF cục bộ `ml/data/models/rf_poc_v1/relative_high_roll_rf.joblib` có model card `rf_proxy_phenotype_poc_v0.1.0`, target `RELATIVE_HIGH_ROLL`, `label_source=PROXY_RULE`. Nó là một bài toán nhị phân POS/NEG trên nhãn proxy; model card ghi rõ không phải safety classifier. Hash cục bộ khớp model card. Không có `ml/export/model.h`. `ml/train/rf_poc_config.yaml` vẫn ghi schema `svmg-angle23-v0.1-proposal`; artifact không xác nhận preprocessing firmware hiện hành. Kết quả trên proxy chỉ đo khả năng tái tạo rule.

### Cách hiểu S0–H1

`simulation/generator/config.py` đặt `expected_label` cho S0/S0b/S1/S2/S3 và `COMBINED_SCENARIO` cho H1. Đó là nhãn mục tiêu của kịch bản, không tự xác nhận phenotype ở từng cửa sổ. `assign_motion_label()` v1 còn dùng trạng thái kích thích heel/parametric của simulator; labeler v2 dùng tiêu chí tín hiệu nhưng vẫn có ngưỡng candidate và priority. Báo cáo confirmation v2 ghi false phenotype triggers ở S0b và overlap ở S1/S3/H1; cùng simulator không phải xác nhận độc lập.

Hai priority hiện có còn không đồng nhất: hàm v1 ưu tiên `HIGH_ROLL > AMPLITUDE_GROWTH > PERSISTENT_OFFSET > NORMAL`, còn `LABEL_PRIORITY_V2` đặt `PERSISTENT_OFFSET` trước `AMPLITUDE_GROWTH`. Không chọn một thứ tự làm chuẩn trong B2a. H1 chủ ý kết hợp biển động cao và heel offset; labeler thử nghiệm ghi nhận nhiều phenotype đồng thời. Cần M1/M2 phê duyệt policy trước khi chuyển thành một lớp duy nhất.

## Ontology đề xuất

Các điều kiện dưới đây mô tả bằng chứng cần có, không đặt ngưỡng số mới. Ngưỡng, thời lượng, quy tắc biên và reference phải được M1/M2 duyệt, đóng phiên bản và kiểm tra trên tập validation trước khi tạo label dùng huấn luyện.

| Nhãn | Định nghĩa quan sát đề xuất | Bằng chứng thời gian / giới hạn |
|---|---|---|
| `NORMAL` | Roll/Pitch nằm trong operating envelope bình thường đã xác nhận cho đúng cảm biến, lắp đặt, miền và chế độ vận hành. | Không được gán chỉ vì không thấy phenotype khác. Cần reference normal-envelope độc lập; offset cảm biến hoặc thiếu coverage làm nhãn không hợp lệ. |
| `HIGH_ROLL` | Dao động Roll có biên độ lớn theo một tiêu chí đã duyệt, tách dao động quanh mean khỏi offset DC. | Cần đủ cửa sổ và duy trì theo thời lượng được duyệt; một peak đơn lẻ không đủ. Có thể cùng tồn tại với tăng biên độ hoặc offset. |
| `PERSISTENT_OFFSET` | Mean Roll duy trì lệch một phía so với datum đã hiệu chuẩn, mô tả offset cảm biến/đo được chứ không tự kết luận heel vật lý. | Cần lịch sử liên tục cùng phía và kiểm soát calibration, mounting, drift; zero calibration sai có thể tạo offset giả. Có thể cùng tồn tại với dao động lớn. |
| `AMPLITUDE_GROWTH` | Biên độ Roll tăng nhân quả qua các đoạn liên tiếp theo chỉ tiêu đã duyệt, không chỉ do nhiễu hoặc một block cực trị. | Bằng chứng cần các block 60 s trong cửa sổ 180 s và coverage C01; nếu thiếu block, lịch sử hoặc điều kiện ổn định thì không gán. Có thể cùng tồn tại với `HIGH_ROLL`. |
| `UNKNOWN` / `ABSTAIN` | Không đủ căn cứ quyết định một lớp duy nhất. | Warm-up, feature invalid/non-finite, thiếu 23 feature, quality không đạt, out-of-domain, confidence chưa hiệu chuẩn, mâu thuẫn reviewer hoặc overlap chưa có policy đều phải abstain. Không thay bằng `NORMAL`. |

Contract feature hiện hành yêu cầu 10 Hz, cập nhật 10 s, cửa sổ causal `(t-W,t]`; vector đủ 23 feature chỉ hợp lệ khi toàn bộ bit hợp lệ và giá trị hữu hạn. Coverage 180 s tuân C01: cả ba block 60 s đều cần ít nhất 570/600 mẫu. Feature invalid không được impute thành 0. Warm-up/gap/quality do contract C01–C04 quyết định; B2a không sửa các quy tắc này.

## Overlap và lựa chọn kiến trúc

| Phương án | Ưu điểm | Rủi ro / tương thích |
|---|---|---|
| A. RF softmax bốn lớp loại trừ | Khớp trực tiếp `svmg_class_t` 0–3 và `model_predict()` hiện tại. | Ép các cửa sổ overlap vào một lớp, cần priority chưa được duyệt; `NORMAL` thiếu envelope đã xác nhận; nhãn scenario không đủ ground truth. |
| B. Ba đầu ra multilabel phenotype | Biểu diễn đồng thời high roll, offset, growth; phù hợp overlap S1/S3/H1. | Không tương thích trực tiếp API firmware một `class_id`; không được coi “mọi bit 0” là `NORMAL` nếu miền chưa xác nhận. |
| C. Phân cấp: quality/OOD gate → phenotype heads → quyết định lớp | Giữ riêng tính hợp lệ, phenotype chồng lấn và quyết định cuối; có thể abstain ở overlap. | Cần M1/M2 duyệt output phụ và policy reducer. Firmware hiện chưa nhận phenotype mask hoặc nhiều score. |

**Khuyến nghị:** dùng phương án C cho thiết kế nghiên cứu: đầu tiên gate validity/OOD; sau đó giữ ba phenotype scores/flags độc lập; chỉ tạo một lớp loại trừ khi evidence duy nhất và policy mapping đã duyệt. Nếu nhiều phenotype cùng hoạt động hoặc còn tranh chấp, trả `UNKNOWN/ABSTAIN`, không tự đặt priority. Không huấn luyện classifier bốn lớp trước khi ontology, nhãn và mapping này được duyệt. M1 cần quyết định API runtime tương thích hoặc thay đổi; tài liệu này không sửa firmware.

## RF input/output contract đề xuất

**Input (các phiên bản đã tồn tại):**

- `float32[23]`, đúng thứ tự `core/include/svmg_feature_schema.h`: `roll_rms_60`, `roll_std_60`, `roll_mean_60`, `roll_peak_to_peak_60`, `roll_abs_p95_60`, `roll_abs_max_60`, `roll_iqr_60`, `roll_diff_rms_60`, `roll_mean_180`, `roll_median_180`, `roll_mean_abs_180`, `roll_dominant_sign_ratio_180`, `roll_segment_mean_std_180`, `roll_mean_shift_180`, `roll_rms_early_60`, `roll_rms_late_60`, `roll_rms_ratio_180`, `roll_rms_slope_180`, `roll_rms_trend_r2_180`, `roll_p95_trend_slope_180`, `pitch_rms_60`, `pitch_std_60`, `pitch_peak_to_peak_60`.
- `feature_schema_version=svmg-angle-23-v1`; `semantic_contract_version=svmg-angle23-semantics-1.0.0`; `validity_policy_version=svmg-angle23-validity-1.0.0`; `preprocessing_version=imu-cf-bw4-20to10-v1`.
- Chỉ suy luận khi engine xác nhận quality OK, đủ readiness và tất cả 23 feature VALID/finite. Không impute. Dữ liệu mô phỏng phải giữ provenance `SIMULATION`; dữ liệu cảm biến là `SENSOR`.

**Output (đề xuất, chưa phê duyệt):**

| ID hiện có | Tên lớp firmware | Quy tắc dùng trong hợp đồng |
|---:|---|---|
| 0 | `NORMAL` | Chỉ khi đạt normal envelope đã xác nhận. |
| 1 | `HIGH_ROLL` | Phenotype được xác nhận và policy overlap cho phép quyết định duy nhất. |
| 2 | `PERSISTENT_OFFSET` | Chỉ diễn giải là offset theo datum được duyệt. |
| 3 | `AMPLITUDE_GROWTH` | Phenotype được xác nhận theo cửa sổ causal. |
| 4 | `UNKNOWN` | Runtime abstention; không phải lớp train thay thế các nhãn mơ hồ. |

Metadata model cần mang ít nhất: `model_version`, `model_sha256`, `label_ontology_version`, `class_mapping_version`, 23 feature names/order hash, feature schema, semantic contract, validity policy, preprocessing version, dtype, training-data provenance, supported domains, calibration/OOD policy và exporter version. Version ontology/mapping chưa được gán ở đây vì cần duyệt.

Confidence phải là score đã calibration trên validation độc lập; vote fraction không tự động là xác suất. Calibration, ngưỡng abstention và OOD policy phải fit trên train/validation rồi freeze trước test. Feature min/max chỉ là guard đã biết, không tự chứng minh OOD detection. Không đạt confidence/coverage/domain gate thì trả `UNKNOWN`, đồng thời giữ Baseline B/fallback và cảnh báo cục bộ theo hành vi M1 hiện có.

API firmware hiện tại là `int model_predict(const float*, int)` trả một ID 0–3; callback tùy chọn chỉ cung cấp một `conf`. API này chưa biểu diễn multilabel scores, abstain reason hoặc calibrated per-class scores. Phải có compatibility review M1/M2 trước khi chốt header/exporter; không ép output proxy nhị phân sang enum bốn lớp.

## Kế hoạch đánh giá và cổng chấp nhận

1. **Cổng ontology:** M1/M2 duyệt định nghĩa phenotype, datum/calibration cho offset, cách xử lý overlap, `NORMAL` envelope, `UNKNOWN/ABSTAIN`, thời lượng/threshold và mapping/API. Reviewer độc lập ghi rõ evidence; scenario ID không tự sinh nhãn.
2. **Cổng dữ liệu:** gắn provenance và label-source cho từng mẫu; ít nhất hai reviewer chấm chồng lặp một tập đã chọn, lưu bất đồng/adjudication; nhãn hazard/normal cần external operating reference. Báo số lớp theo session/group, không theo số cửa sổ chồng lấn; không xem proxy là ground truth.
3. **Cổng chia tập:** giữ nguyên một `session_id`/run/vessel/seed group trong duy nhất một split; không random-split windows. Nested grouped CV chỉ trên train; validation dùng hiệu chuẩn/chọn policy; Test-G1, Test-G2 và các miền giữ riêng, không dùng để chọn ngưỡng.
4. **Cổng metric:** bắt buộc confusion matrix; precision/recall/F1 từng lớp và macro-F1; false alarm theo thời gian/session; missed-event review; detection latency tính từ event reference mà không nhìn tương lai; calibration (Brier/ECE hoặc chỉ số được M2 chốt), risk–coverage/abstention curve; phân tích OOD theo nguồn/scale/sea state; so sánh Baseline B trên cùng grouped splits.
5. **Cổng triển khai Wokwi:** chỉ sau khi cổng ontology/dữ liệu/đánh giá đạt, xác minh model exporter, version metadata, 23-vector contract, fallback, thời gian/RAM/Flash và kết quả target simulation. Kết quả Wokwi không thay thế nhãn độc lập và không chứng minh an toàn hàng hải.

Các ngưỡng đạt metric, số session tối thiểu mỗi lớp và mức rủi ro chấp nhận được phải được chủ sở hữu M1/M2 duyệt **trước khi mở test cuối**. B2a không tự đặt con số để tạo PASS.

## Quyết định cần M1/M2 phê duyệt

1. Mục tiêu là phenotype chuyển động hay hazard/operating condition; tên lớp hiện tại chỉ hỗ trợ cách hiểu phenotype.
2. Chọn A/B/C và output runtime có thể biểu diễn overlap; nếu cần lớp primary, chốt reducer/abstain policy thay vì kế thừa ngầm một priority simulator.
3. Duyệt tiêu chí HIGH_ROLL, datum và calibration PERSISTENT_OFFSET, tiêu chí AMPLITUDE_GROWTH, `NORMAL` envelope, thời gian xác nhận và xử lý boundary.
4. Duyệt loại bằng chứng nào cho `HUMAN_REVIEWED` so với `VERIFIED`; xác định reviewer/domain expertise và adjudication.
5. Duyệt schema/version cho ontology, class mapping, confidence, OOD và model output; bảo toàn mapping C hiện tại nếu không có thay đổi ABI được phê duyệt.
6. Duyệt nhóm dữ liệu, tiêu chí metric/false alarms/missed events, latency, calibration và tiêu chuẩn Wokwi trước khi huấn luyện.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

- **Vì sao không dùng S1 làm toàn bộ nhãn HIGH_ROLL?** Scenario đặt điều kiện tạo mẫu; các cửa sổ warm-up, chuyển tiếp và overlap không nhất thiết mang cùng phenotype. Event metadata cũng có thể rò rỉ target vào feature pipeline.
- **Vì sao H1 không ép thành một lớp ngay?** H1 kết hợp nhiều yếu tố và báo cáo labeler quan sát overlap. Chọn một nhãn cần policy được duyệt; nếu chưa có policy, `UNKNOWN/ABSTAIN` trung thực hơn.
- **Vì sao không dùng “không abnormal” làm NORMAL?** NORMAL cần operating envelope được xác minh. Không có nhãn abnormal không chứng minh hoạt động bình thường.
- **Wokwi parity chứng minh điều gì?** Nó hỗ trợ tương thích số học feature cho đầu vào đã đánh giá; nó không kiểm tra ontology, chất lượng nhãn, khả năng phân lớp hay tính hợp lệ hàng hải.

## Tài liệu nguồn đã rà soát

`AGENTS.md`, `README.md`, `contracts/features.md`, `contracts/features23.json`, `ml/docs/feature_contract_23_v0.2.json`, `ml/docs/M2_23_Features_ESP32_Integration.md`, `ml/features/{config.yaml,extractor.py,spec.py}`, `ml/labeling/{README.md,proxy_spec.yaml,proxy_rules.py,run.py}`, `ml/train/{README.md,rf_poc.py,rf_poc_config.yaml}`, `simulation/generator/{config.py,scenarios.py}`, `simulation/calibration/labeling_v2_independent_validation.md`, `core/include/{svmg_common.h,svmg_feature_schema.h,svmg_engine.h}`, `firmware/src/infer.cpp`, và các báo cáo label/RF readiness nêu trên.

`AGENTS.md` tham chiếu `.agents/memory/PROJECT_CONTEXT.md`, nhưng file đó không có trong checkout này. README và các contract/report nguồn đã được dùng để đối chiếu phạm vi và ownership.
