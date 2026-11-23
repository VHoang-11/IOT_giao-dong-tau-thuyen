# M2-R1 – RF compact Hohai và export C cho demo cô lập (KHÔNG phải tích hợp firmware)

**Chạy:** `.venv/bin/python -m ml.train.rf_demo_m2r1` (cấu hình `demo_export` trong `ml/train/rf_poc_config.yaml`). Artifact sinh ra (`svmg_rf_proxy_demo.{h,c}`, `results.json`, `heldout_replay_vectors.csv`) nằm trong `ml/data/models/rf_demo_m2r1/` (gitignored). Không sinh `ml/export/model.h`, không đổi firmware production, không đăng ký với `svmg_engine_set_rf()`.

**Dữ liệu/mô hình:** 1512 cửa sổ Hohai đủ 23 feature, 21 session, 9 nhóm độc lập T1–T9 (3 nhóm có POS). RF `n_estimators=25, max_depth=6, min_samples_leaf=10, balanced_subsample`, seed 20261117, ngưỡng 0.5 cố định. Đánh giá leave-one-Tn-out với nhãn fold sẵn có: TP 209, FP 0, FN 0, TN 1118, F1 1.0. Model demo = fold giữ lại `hohai|T9` (train T1–T8: 1166 cửa sổ, 130 POS; held-out 216 cửa sổ: 46 POS, 124 NEG, 46 ABSTAIN).

**Giới hạn (bắt buộc đọc):** nhãn POS/NEG sinh từ luật ngưỡng phân vị trên chính các feature (chủ yếu `roll_std_60`), nên F1 = 1.0 chỉ cho thấy RF tái tạo được luật proxy, không phải phân loại nguy hiểm đã kiểm chứng. NEG ≠ NORMAL đã kiểm chứng. Chỉ 3 nhóm có POS nên khoảng bootstrap theo nhóm [1.0, 1.0] không mang thông tin về độ chính xác vận hành. ABSTAIN bị loại khỏi train/metric; model vẫn dự đoán POS cho 64/185 cửa sổ ABSTAIN ở các fold test. Feature Hohai dùng `feature_spec_version=candidate-30-v1` và tiền xử lý khác `imu-cf-bw4-20to10-v1` của `contracts/features23.json`: chỉ thứ tự tên 23 feature trùng (SHA-256 `060095dd…a1c8`), KHÔNG tương thích production.

**Hợp đồng I/O replay (tách biệt `svmg_class_t` bốn lớp):**
- Vào: `const float features[23]` theo đúng thứ tự `svmg_rf_proxy_demo_feature_names` (= `contracts/features23.json`), `n_features` phải bằng 23.
- Ra: `int svmg_rf_proxy_demo_predict(const float*, size_t, svmg_rf_proxy_demo_output_t*)` trả `0` OK, `-1` NULL, `-2` sai độ dài, `-3` NaN/Inf; `out.pred` ∈ {0 proxy-NEG, 1 proxy-POS, −1 không hợp lệ}, `out.score` = P(proxy-POS) ∈ [0,1] (−1 khi lỗi). Lỗi KHÔNG được ánh xạ thành NEG/NORMAL.
- Metadata (model_version `rf_proxy_demo_m2r1_v0.1.0`, rule_version, nhóm train/held-out, cờ `production_preprocessing_equivalent=false`) nằm trong macro `SVMG_RF_PROXY_DEMO_METADATA_JSON`. Không biên dịch với `-ffast-math` (cần `isfinite`).

**Parity Python vs C:** ngưỡng lưu float32 làm tròn xuống ⇒ so sánh tương đương chính xác với sklearn trên đầu vào float32. 216 vector held-out và toàn bộ 1512 vector: 0 lệch pred, |Δscore| tối đa 3.0e-8 (dung sai 1e-6), 0 lỗi status; độ dài 0/22/24, NaN, Inf đều bị từ chối. Sinh lại hai lần cho mã C giống hệt từng byte.

**Kích thước:** 209 nút (92 nút trong, 117 lá, sâu tối đa 5), mảng model 1931 B; object `-Os` cho ESP32 (xtensa-esp32-elf-gcc) 2689 B `.text` (gồm rodata), host 2590 B; trung bình 53 phép so sánh/lần suy luận.
