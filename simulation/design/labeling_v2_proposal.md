# SVMG — Đề xuất chuẩn hóa mô phỏng và nhãn `labeling_v2`

**Trạng thái:** Được Hoàng (Embedded/Core Lead) và nhóm phê duyệt toàn bộ theo yêu cầu M2-01.4e; đang triển khai. Ngưỡng phân loại v2 và profile sea state vẫn là ứng viên chưa hiệu chỉnh thực nghiệm.
**Phạm vi:** Định nghĩa nhãn, profile kích động G1, ma trận 605 phiên, H1 và tác động feature contract.
**Nguồn:** Quyết định nhóm được phê duyệt trong yêu cầu M2-01.4e; các giá trị lịch sử lấy từ source/config. Repository không có bảng SS0–SS5 đã hiệu chỉnh hoặc danh sách 30 feature ứng viên có sẵn. Profile SS và ngưỡng chưa có hiệu chuẩn thực nghiệm được ghi rõ là ứng viên.

### Lịch sử quyết định

- **M2-01.4e:** Hoàng (M1/Core Lead) và nhóm phê duyệt toàn bộ thiết kế labeling v2, sea-state profile ứng viên, ma trận 605 phiên, H1 Combined Scenario, và mục tiêu 30 feature cho Random Forest. Việc phê duyệt số lượng 30 không tự phê duyệt contract/thứ tự/công thức của từng feature. `contracts/features.md` và cấu trúc C vẫn thuộc thay đổi riêng phối hợp M1.

## 1. Thực trạng `labeling_v1`

`assign_motion_label()` trong [`scenarios.py`](../generator/scenarios.py) hiện áp dụng quy tắc trên tín hiệu roll sạch của simulator:

1. Chưa đủ cửa sổ RMS 60 giây: trả `None` (warm-up).
2. RMS roll quanh 0 ≥ 6°: `HIGH_ROLL`.
3. Nếu không, parametric excitation đang bật: `AMPLITUDE_GROWTH`.
4. Nếu không, heel offset có độ lớn ≥ 3° và duy trì ≥ 120 giây: `PERSISTENT_OFFSET`.
5. Các trường hợp còn lại: `NORMAL`.

Đây là phiên bản cần giữ nguyên để tái lập kết quả cũ. Không thay đổi implementation của v1 khi triển khai v2; kết quả mới phải ghi version nhãn rõ ràng và có thể tính song song trên cùng chuỗi.

Một số điểm không nhất quán đã được phát hiện:

- `HIGH_ROLL` hiện tính RMS quanh 0 nên bao gồm mean/heel tĩnh, trong khi tên lớp được mô tả là dao động mạnh.
- Nhãn `AMPLITUDE_GROWTH` đang theo trạng thái nguồn sinh `h > 0`, không đòi hỏi biên độ quan sát tăng.
- S2/H1 dùng điều kiện heel từ metadata sự kiện để gán nhãn; đây là ground truth hữu ích khi audit nhưng không nên biến thành feature RF.
- H1 được mô tả là sensor fault trong simulation README/config, nhưng scenario runner triển khai kết hợp biển động và heel.
- Config hiện xác nhận tổng số phiên theo split, chưa biểu diễn ma trận scenario × split.

## 2. Đề xuất `labeling_v2`

### 2.1 Tách chất lượng dữ liệu, trạng thái nguồn và hình thái chuyển động

Lưu ba khái niệm riêng:

- **Quality/status:** `FAULT`, `UNKNOWN`, invalid hoặc warm-up. Đây không phải lớp chuyển động thứ năm. Thiếu lịch sử cần thiết có thể được biểu diễn là `UNKNOWN` hoặc trạng thái warm-up theo contract được nhóm chọn.
- **Source/provenance metadata:** scenario ID, `parametric_excitation_active`, h, Ω, sea state, seed và thời điểm sự kiện. Chỉ dùng để tái lập, phân tầng, kiểm chứng và tạo ground truth; không đưa vào feature matrix của RF.
- **Observed motion phenotype:** một trong bốn lớp `NORMAL`, `HIGH_ROLL`, `PERSISTENT_OFFSET`, `AMPLITUDE_GROWTH`, suy ra nhân quả từ tín hiệu đến thời điểm hiện tại.

Ground-truth label cho dữ liệu tổng hợp có thể được tính offline từ tín hiệu roll sạch của mô phỏng; feature đầu vào mô hình phải được tạo từ đường dữ liệu cảm biến/IMU mà ESP32 có thể quan sát. Không dùng giá trị `h`, `scenario_id`, `t0`, sea-state label, seed, heel truth hoặc roll tương lai làm feature RF.

### 2.2 HIGH_ROLL — dao động quanh mean

Đề xuất dùng **RMS centered trên cửa sổ 60 giây**:

`rms_centered_60(t) = sqrt(mean((roll_i - mean_roll_60)^2))`

Đại lượng này bằng population standard deviation trên cùng mẫu/cùng cửa sổ. Vì vậy, nếu bộ 30 feature có `roll_std_60`, hãy dùng một trong hai tên/định nghĩa; không thêm cả hai như hai feature độc lập.

**Không tự chuyển ngưỡng 6° của v1 sang metric centered.** Ngưỡng v2 được hiệu chỉnh trên Validation sau khi nhóm chốt ý nghĩa lớp và tiêu chí đánh giá. Đề xuất quy trình:

1. Tính `rms_centered_60` từ tín hiệu roll sạch làm truth và từ tín hiệu quan sát như feature; lưu riêng hai luồng để đo ảnh hưởng nhiễu.
2. Quét các ngưỡng ứng viên trên **Validation theo session**, không chia ngẫu nhiên các cửa sổ trượt.
3. Báo cáo phát hiện S1, false positive trên S0/S0b, và các cửa sổ S2/H1 có dao động thực sự lớn. Báo cáo event-level detection latency cùng tỷ lệ theo cửa sổ.
4. Chọn ngưỡng theo tiêu chí nhóm thống nhất; không dùng Test-G1/Test-G2 để điều chỉnh ngưỡng. Nếu cần ước lượng bất định, bootstrap theo session thay vì theo cửa sổ tương quan.
5. Ghi threshold, đơn vị, cửa sổ, phiên bản labeler và nguồn tín hiệu vào metadata.

Với S2, offset tĩnh không tự đẩy `rms_centered_60` lên cao. Nếu S2 đồng thời có dao động mạnh thì HIGH_ROLL vẫn có thể hợp lệ. Nên giữ hai cờ chẩn đoán độc lập (ví dụ `high_roll_active`, `persistent_offset_active`) để không mất thông tin đồng thời, kể cả khi output classifier chỉ nhận một nhãn chính.

### 2.3 PERSISTENT_OFFSET — offset có dấu và thời lượng

Đề xuất xác định offset từ mean roll có dấu, không từ `heel_offset_rad` nội bộ của generator:

- Dùng signed `mean_roll` trên cửa sổ đã thống nhất; hợp đồng feature hiện có mô tả `mean_roll` và `heel_duration_s` trong cửa sổ 180 giây.
- Bắt đầu đếm liên tục khi `abs(mean_roll)` vượt ngưỡng heel; giữ dấu (+/−) để biểu diễn hướng nghiêng.
- Chỉ bật trạng thái persistent sau ít nhất **120 giây liên tục** thỏa điều kiện. Khi rời ngưỡng hoặc đổi dấu theo quy tắc nhóm chọn, reset/điều chỉnh timer một cách xác định.
- Lưu riêng `event_t0` và `persistent_qualified_at`; không đồng nhất thời điểm bắt đầu sự kiện với thời điểm đủ điều kiện nhãn.

Ngưỡng heel 3° và thời lượng 120 giây là thông số trong brief M2/labeler hiện tại. Cách lấy mean, ngưỡng áp dụng cho mean 60 hay 180 giây, xử lý vùng hysteresis và reset khi đổi dấu cần nhóm phê duyệt. Nếu dùng mean 180 giây, cần kiểm tra độ trễ và hiện tượng pha loãng mean khi sự kiện vừa bắt đầu.

Khi offset bền và dao động mạnh cùng xuất hiện, giữ cả hai cờ phenotype. Thứ tự ưu tiên đã được duyệt cho v2 là `HIGH_ROLL > PERSISTENT_OFFSET > AMPLITUDE_GROWTH > NORMAL`; nhãn chính không làm mất các cờ phenotype phụ.

### 2.4 AMPLITUDE_GROWTH — bằng chứng quá khứ

Tách:

- `parametric_excitation_active`: trạng thái nguồn sinh, dùng metadata/stratification; tuyệt đối không dùng làm feature RF hoặc tự nó làm nhãn morphology.
- `observed_amplitude_growth`: cờ đo từ xu hướng RMS quá khứ; chỉ khi đạt tiêu chí đã hiệu chỉnh mới tạo nhãn `AMPLITUDE_GROWTH`.

Đề xuất đánh giá trên chuỗi RMS 60 giây trong cửa sổ **trailing 180 giây**. Tại mỗi thời điểm `t`, chỉ dùng mẫu có timestamp `<= t`. Có thể tính:

- `slope_180`: slope hồi quy RMS theo thời gian, đơn vị độ/phút (cùng ý tưởng với `trend_rms_slope` trong feature contract).
- `growth_ratio_180`: RMS ở đoạn 60 giây gần nhất chia cho RMS đoạn 60 giây cũ hơn trong cửa sổ 180 giây; phải định nghĩa epsilon theo noise floor/độ phân giải đã biết để tránh chia số gần 0.
- Tùy nhóm chọn một tiêu chí hoặc kết hợp slope và ratio. Hai đại lượng tương quan, nên kiểm tra tính tăng ích trên Validation trước khi đưa cả hai vào feature vector.

Hiệu chỉnh slope, ratio và thời lượng xác nhận bằng Validation đã nhóm theo session: đo false positive trên S0/S0b/S2, recall đối với các phiên S3 thực sự tăng biên độ, và latency từ lúc bắt đầu xu hướng quan sát được. Chỉ xác nhận nhãn sau khi score nhân quả vượt ngưỡng trong thời gian đã chọn; không dùng `late_session_rms`, dữ liệu sau `t`, `h`, hoặc `t0` đã biết trước. Cửa sổ 180 giây có thể ảnh hưởng mục tiêu detection latency 120 giây trong [`ml/README.md`](../../ml/README.md); cần đánh giá trade-off bằng số liệu, không đặt ngưỡng tùy ý.

### 2.5 NORMAL, FAULT và UNKNOWN

- `NORMAL`: dữ liệu đủ chất lượng/lịch sử và không thỏa các điều kiện phenotype đã phê duyệt.
- `FAULT`: trạng thái thiết bị/cảm biến/dữ liệu lỗi, thuộc quality/fault handling. Không tính là class chuyển động thứ năm.
- `UNKNOWN`/warm-up: không đủ lịch sử hoặc không thể quyết định tin cậy. Không đưa các cửa sổ này vào mẫu số phân bố lớp.

### 2.6 Nhãn chính khi có đồng thời nhiều phenotype

Contract classifier hiện là đơn nhãn. Đề xuất lưu các phenotype flags độc lập, sau đó sinh `primary_motion_label` theo thứ tự phiên bản hóa. Thứ tự ứng viên để nhóm duyệt là:

`HIGH_ROLL > PERSISTENT_OFFSET > AMPLITUDE_GROWTH > NORMAL`

Đây là thứ tự đã được duyệt cho v2, khác vị trí tương đối giữa AMPLITUDE_GROWTH và PERSISTENT_OFFSET trong v1. `FAULT`/`UNKNOWN` được xử lý ở quality/status trước nhãn chuyển động.

## 3. Profile Sea State ứng viên

Các giá trị do yêu cầu M2-01.4d cung cấp; tất cả đang ở trạng thái **đề xuất, chưa hiệu chỉnh**:

| Sea state | σw ứng viên | Đơn vị | Trạng thái/cách hiểu |
|---|---:|---|---|
| SS0 | 0.5° | độ tương đương góc của kích động `w(t)` | Đề xuất, chưa hiệu chỉnh |
| SS1 | 0.9° | độ tương đương góc của kích động `w(t)` | Đề xuất, chưa hiệu chỉnh |
| SS2 | 1.5° | độ tương đương góc của kích động `w(t)` | Đề xuất, chưa hiệu chỉnh |
| SS3 | 2.2° | độ tương đương góc của kích động `w(t)` | Đề xuất, chưa hiệu chỉnh |
| SS4 | 3.0° | độ tương đương góc của kích động `w(t)` | Đề xuất; cùng cận dưới miền σw S1 được brief nêu |
| SS5 | 4.5° | độ tương đương góc của kích động `w(t)` | Đề xuất; cùng cận trên miền σw S1 được brief nêu |

σw này là độ lệch chuẩn của kích động tương đương đưa vào vế phải phương trình roll; **không phải độ cao sóng, góc roll đầu ra hay trạng thái biển thực**. Trong các nguồn repository đã kiểm tra không có bảng SS0–SS5 đã hiệu chỉnh. Chỉ miền S1 3–4.5° có căn cứ trong brief M2; việc gán 3.0° cho SS4 và 4.5° cho SS5 là đề xuất của yêu cầu này, chưa phải xác nhận vật lý.

Để nhất quán:

- S0 lấy sigma từ SS0–SS3; S3 lấy SS1–SS2.
- S1 chọn SS4 hoặc SS5 và dùng sigma tương ứng đúng từ bảng, thay vì hiện trạng chọn tên SS4/SS5 nhưng lấy sigma độc lập ngẫu nhiên trong 3–4.5°.
- H1 chọn SS4 hoặc SS5 và dùng cùng ánh xạ; đồng thời thêm heel offset 3–6°.
- Chuyển độ sang radian đúng một lần ở biên cấu hình; metadata lưu cả giá trị profile, đơn vị và sigma đã dùng.

Phương pháp kiểm tra sau khi được duyệt: chạy nhiều seed lặp lại trên toàn miền T0/damping hiện hành; lưu seed và tham số; báo cáo phân phối σw, RMS centered, RMS quanh 0, P95/peak range và tỷ lệ từng phenotype theo scenario. Kiểm tra sự đơn điệu kỳ vọng giữa mức kích động và phân phối đáp ứng nhưng không ép tỷ lệ nhãn bằng cách tự đổi sigma. Hiệu chỉnh thực nghiệm (nếu có) phải được ghi riêng so với profile ứng viên.

## 4. Ma trận 605 phiên

Ma trận do yêu cầu M2-01.4d cung cấp; tổng mỗi cột khớp kế hoạch split trong config hiện tại.

| Scenario | Train | Val | Test-G1 | Test-G2 | Tổng theo scenario |
|---|---:|---:|---:|---:|---:|
| S0 | 80 | 20 | 30 | 30 | 160 |
| S0b | 30 | 10 | 15 | 15 | 70 |
| S1 | 50 | 15 | 20 | 20 | 105 |
| S2 | 50 | 15 | 20 | 20 | 105 |
| S3 | 50 | 15 | 20 | 20 | 105 |
| H1 | 20 | 10 | 15 | 15 | 60 |
| **Tổng theo split** | **280** | **85** | **120** | **120** | **605** |

Đây là phân bổ **số phiên**, không phải số cửa sổ hay số mẫu. Phiên là đơn vị group khi chia dữ liệu. Đề xuất Test-G1/Test-G2 dùng cùng ma trận scenario; để đo ảnh hưởng generator có thể ghép cặp T0, damping, t0 và seed theo session giữa hai test. Nếu muốn kiểm tra miền tham số mở rộng như cấu hình hiện tại (Train/Val T0 14–26 s, damping 0.03–0.06; tests 12–32 s, 0.02–0.08), cần báo cáo riêng hiệu ứng domain shift thay vì trộn nó với hiệu ứng G1/G2.

## 5. H1 — Combined Scenario và fault injection

Đề xuất thống nhất:

- **H1 = Combined Scenario:** SS4–SS5 cùng heel offset 3–6°.
- H1 là scenario/provenance, không phải class thứ năm. Nhãn chuyển động chính được tính từ tín hiệu và thứ tự ưu tiên đã phê duyệt; các cờ high-roll/offset/growth có thể cùng đúng.
- **Fault injection** là tình huống riêng (ví dụ mã fault scenario độc lập) tạo spike, stuck-at, NaN hoặc invalid sample. Lỗi được biểu diễn qua quality/status (`FAULT`, `sensor_ok`, validity) thay vì trộn vào phenotype chuyển động.

Tài liệu/cấu hình M2 đã đồng bộ trong bước triển khai; các phần liên thành viên còn lại:

- `simulation/README.md`, `simulation/generator/config.py` và `simulation/generator/scenarios.py` đã cập nhật H1 Combined, candidate profile, labeler versions và cùng sea-state mapping S1/H1.
- `ml/README.md` và tài liệu giao diện liên quan cần phối hợp cập nhật khi M2-04 chuẩn hóa feature contract.
- Fault injector/test riêng sẽ cần file mới trong simulation và kiểm thử tương ứng; chưa thuộc implementation này.
- Contract event/telemetry chỉ cần sửa nếu nhóm quyết định biểu diễn FAULT khác hiện tại. Chưa đề xuất thay `contracts/features.md` hoặc `FeatureVector C` trong bước này.

## 6. Tác động nếu mở rộng Feature Contract từ 14 lên 30

Contract hiện hành mô tả 14 feature và yêu cầu thứ tự nhất quán Python/C/backend; [`FeatureVector`](../../core/include/svmg_core.h) hiện có 13 `float` cùng một cờ `bool`.

- **RAM:** nếu 30 feature gồm 29 `float` + 1 `bool`, struct có thể khoảng 120 byte sau padding, so với khoảng 56 byte hiện tại; chênh khoảng 64 byte cho một vector. Đây chỉ là ước tính ABI, chưa gồm ring buffer, stack, input buffer, model và runtime. Buffer lưu lịch sử nhiều mẫu có thể tốn hơn struct.
- **Flash:** không tăng chỉ theo kích thước vector. RF export thường tăng theo số node/threshold và bộ dữ liệu huấn luyện; cần đo file model thực tế trên target.
- **Thời gian ESP32:** tính feature mới tạo thêm phép tính và truy cập cửa sổ. Chi phí không nhất thiết tăng đúng tỷ lệ 30/14 vì có thể dùng chung thống kê; cần benchmark trên ESP32 với worst-case cửa sổ và chu kỳ inference 2 Hz.
- **Python/C parity:** mọi tên, đơn vị, index, quy tắc cửa sổ, ddof, warm-up, NaN handling và thứ tự phải giống nhau. Cần vector test golden chung và tăng version model/feature schema theo quy trình nhóm.
- **Chi phí M1:** cần sửa extractor C/struct, test C, tích hợp firmware, đo RAM/latency và xác minh model export/inference. Đây là thay đổi cross-member, phải được M1 duyệt trước.
- **Trùng thông tin:** `energy_roll = rms_roll²` trên cùng cửa sổ; centered RMS bằng population std trên cùng cửa sổ; `max_abs_roll` và P95(abs roll) tương quan; slope và growth ratio cũng có thể tương quan. Chỉ giữ feature bổ sung nếu validation chứng minh giá trị tăng thêm.
- **Giới hạn roll 1-DOF:** simulator hiện không mô phỏng pitch/yaw độc lập, hướng sóng, gia tốc tịnh tiến tàu hay dynamics đa trục. Các feature pitch, cross-axis, wave direction hoặc sensor fault cần nguồn/mô hình riêng; không nên giả lập thành chuyển động đa dạng tùy tiện. `sensor_ok` là quality flag hơn là phenotype roll.

**Quyết định đã duyệt:** mục tiêu là 30 feature cho Random Forest. Repository hiện chỉ có contract 14 feature; danh sách 30 ứng viên chi tiết không tìm thấy. Danh sách, thứ tự, công thức, đơn vị và cửa sổ dưới đây là **đề xuất kỹ thuật để chuẩn hóa ở M2-04**, không phải contract đã duyệt. Bốn feature pitch không được hỗ trợ bởi roll 1-DOF và phải bị loại/để dành đến khi có mô hình đa trục hoặc nguồn dữ liệu phù hợp; không tạo giá trị pitch giả.

| # | Feature ứng viên | Đơn vị / cửa sổ | Hỗ trợ roll 1-DOF | Chi phí ESP32 sơ bộ |
|---:|---|---|---|---|
| 1 | `roll_rms_60` | deg / 60 s | Có; RMS quanh 0, giữ để tương thích | Thấp |
| 2 | `roll_std_60` | deg / 60 s | Có; đây cũng là RMS centered, không thêm feature centered RMS thứ hai | Thấp |
| 3 | `roll_mean_60` | deg / 60 s | Có, từ roll | Thấp |
| 4 | `p95_abs_roll_60` | deg / 60 s | Có | Trung bình |
| 5 | `max_abs_roll_60` | deg / 60 s | Có | Thấp |
| 6 | `roll_zero_crossing_rate_60` | 1/s / 60 s | Có | Thấp |
| 7 | `roll_mean_180` | deg / 180 s | Có, signed | Thấp |
| 8 | `roll_std_180` | deg / 180 s | Có | Thấp |
| 9 | `roll_slope_180` | deg/min / trailing 180 s | Có | Trung bình |
| 10 | `heel_duration_180` | s / 180 s | Có, từ quan sát roll; exact threshold policy belongs to label/feature calibration | Thấp |
| 11 | `roll_iqr_60` | deg / 60 s | Có | Trung bình |
| 12 | `roll_skewness_60` | dimensionless / 60 s | Có | Trung bình |
| 13 | `roll_kurtosis_60` | dimensionless / 60 s | Có | Trung bình |
| 14 | `roll_p2p_60` | deg / 60 s | Có; correlated with max/P95, validate incremental value | Thấp |
| 15 | `gx_mean_60` | rad/s / 60 s | Có, IMU roll axis | Thấp |
| 16 | `gx_std_60` | rad/s / 60 s | Có | Thấp |
| 17 | `p95_abs_gx_60` | rad/s / 60 s | Có | Trung bình |
| 18 | `gx_zero_crossing_rate_60` | 1/s / 60 s | Có | Thấp |
| 19 | `gx_slope_180` | (rad/s)/min / trailing 180 s | Có | Trung bình |
| 20 | `roll_accel_std_60` | rad/s² / 60 s | Derivable from gx differences; noise-sensitive | Trung bình |
| 21 | `p95_abs_roll_accel_60` | rad/s² / 60 s | Derivable from gx differences; noise-sensitive | Trung bình |
| 22 | `ay_mean_60` | m/s² / 60 s | Available from IMU projection; strongly affected by roll/gravity | Thấp |
| 23 | `ay_std_60` | m/s² / 60 s | Available from IMU | Thấp |
| 24 | `az_mean_60` | m/s² / 60 s | Available from IMU projection | Thấp |
| 25 | `az_std_60` | m/s² / 60 s | Available from IMU | Thấp |
| 26 | `data_valid_fraction_60` | fraction / 60 s | Sensor quality, not motion morphology | Thấp |
| 27 | `pitch_rms_60` | deg / 60 s | **Unsupported**: no pitch state | — |
| 28 | `pitch_p95_abs_60` | deg / 60 s | **Unsupported**: no pitch state | — |
| 29 | `pitch_mean_180` | deg / 180 s | **Unsupported**: no pitch state | — |
| 30 | `pitch_std_180` | deg / 180 s | **Unsupported / placeholder proposal**: no pitch state; fourth pitch candidate is absent from current repository | — |

The current 14-feature contract contains three pitch features; no fourth pitch candidate is listed in the repository. `pitch_std_180` is shown only as a placeholder proposal to make the four unsupported pitch slots explicit, and needs group/M1 decision before it could enter any contract. Do not synthesize pitch values. These 30 rows are a discussion list, not a final contract: remove mathematical duplicates (for example, `roll_std_60` and centered RMS are one quantity; `roll_rms_60` and energy are deterministically related) and confirm added value on Validation. Keep `sensor_ok` and `data_quality_pct` as quality metadata unless an explicit fault classification task requires them as model inputs. Cost tiers are qualitative and need target benchmark. M2-04 must coordinate feature naming/order/formulas with Hoàng; a separate PR must update the contract and Python/C implementation together.

## 7. Các việc còn lại cần hiệu chỉnh hoặc phối hợp

1. Hiệu chỉnh HIGH_ROLL centered threshold và AMPLITUDE_GROWTH slope/ratio/floor/confirmation trên Validation; hiện các giá trị này chưa được chốt.
2. Xác nhận/hiệu chỉnh chi tiết signed-mean offset window, threshold policy, reset/hysteresis, với thời gian persistent tối thiểu 120 s đã duyệt.
3. Xác nhận việc giữ priority `HIGH_ROLL > PERSISTENT_OFFSET > AMPLITUDE_GROWTH > NORMAL` và các phenotype flags độc lập.
4. Hiệu chỉnh profile sea state bằng dữ liệu phù hợp; các sigma hiện tại là candidate.
5. Chuẩn hóa danh sách/công thức/thứ tự 30 feature ở M2-04 cùng M1; con số 30 đã được duyệt nhưng contract chưa đổi.
6. Xác nhận quy trình Validation và tiêu chí chấp nhận trước khi sinh dataset; Test-G1/Test-G2 không được dùng để tune.

## 8. File bị ảnh hưởng trong bước triển khai sau

### M2-owned

- `simulation/generator/scenarios.py` — labeler v2, phenotype flags, source/observed separation và mapping sea state.
- `simulation/generator/config.py` — profile, thresholds đã được duyệt, ma trận scenario × split, ScenarioDefinition H1 và version.
- `simulation/tests/test_generator.py` — regression v1, tests v2, simultaneous phenotypes, boundaries, causality và reproducibility.
- `simulation/visualization/plot_scenarios.py` — báo cáo/plot v2, profile, latency, confusion theo phiên.
- `simulation/README.md`, `ml/README.md`, có thể `README.md` — đồng bộ thuật ngữ scenario/class/quality.
- Một fault-injection module/test mới nếu nhóm duyệt tình huống fault riêng.

### Chỉ khi có phê duyệt feature/contract

- `contracts/features.md`, `core/include/svmg_core.h`, `core/src/features.c`, `ml/features_c.py` và test parity Python/C.
- Schema telemetry/event chỉ khi cách biểu diễn class/FAULT được nhóm thay đổi.

`contracts/features.md` và `FeatureVector C` chưa được sửa trong M2-01.4e; thay đổi contract 30 feature được tách sang PR phối hợp M1.

## 9. Kế hoạch kiểm thử và tiêu chí chấp nhận trước dataset

### Kiểm thử sau khi nhóm duyệt

1. **Regression v1:** chạy lại golden cases/seed đã lưu để chứng minh `labeling_v1` không đổi.
2. **Unit v2:** kiểm tra centered RMS, mean có dấu, duration liên tục/reset, threshold boundaries, warm-up và ưu tiên phenotype.
3. **Causality:** thay đổi mẫu tương lai không được thay đổi nhãn tại thời điểm hiện tại; không feature nào phụ thuộc h, scenario ID, sigma thật, seed, t0 kế hoạch hoặc metadata kết quả.
4. **Scenario sweep:** nhiều seed cho cả sáu scenario; báo cáo kết quả theo session và window, transition/warm-up riêng, valid runs, latency và false labels. Không chỉnh tham số tự động để đạt class ratio.
5. **Sea mapping:** assert cùng một sea-state code luôn ánh xạ đúng σw ở S1/H1; verify quy đổi deg→rad một lần và metadata khớp giá trị đã dùng.
6. **605 manifest:** kiểm tra ma trận đúng từng ô, tổng 280/85/120/120 và 605; session ID không trùng split; mọi cửa sổ của cùng session nằm cùng split.
7. **Test-G1/G2:** khi G2 sẵn sàng, dùng cùng labeler; paired parameter plan hoặc tách rõ generator shift với physical-parameter shift.
8. **Feature nếu mở rộng:** golden vectors Python/C, thứ tự/index/units, model export và benchmark RAM/Flash/latency trên ESP32.

### Tiêu chí chấp nhận trước khi sinh dataset chính thức

- Nhóm đã duyệt bằng văn bản định nghĩa v2, priority, threshold-calibration policy, sea profile, H1 và phân bổ 605.
- v1 còn tái lập được; dataset/metadata ghi rõ label version, generator version, seed và profile.
- Validation được dùng cho chọn ngưỡng; Test-G1/Test-G2 không dùng để tune.
- Không có feature leakage từ source metadata; split/group được tạo theo session.
- Báo cáo outcome theo session cho thấy S0/S0b, S1, S2, S3, H1 được đánh giá theo tiêu chí đã duyệt; các phiên không đạt kỳ vọng được giữ và báo cáo, không bị loại âm thầm.
- Cùng một labeler áp dụng cho G1/G2; khác biệt phân bố được báo cáo thay vì bù bằng chỉnh tham số để ép nhãn.
- Ma trận đủ 605 phiên và các kiểm thử liên quan đạt; chưa tạo dataset trước khi các tiêu chí trên được ký duyệt.
