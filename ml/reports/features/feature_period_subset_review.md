# Rà soát chu kỳ và tập angle-only 23 — SVMG M2

## Kết luận rà soát

Đặc tả hiện có là **đề xuất đang chờ nhóm phê duyệt**, không phải hợp đồng đã được duyệt. Rà soát phát hiện lỗi gán đảo hai mảng ở extractor: hàm cửa sổ trả `(signal_values, timestamps, issue)`, nhưng biến nhận theo thứ tự ngược. Bộ đếm crossing vì vậy chạy trên timestamp thay vì Roll. Đây là lỗi triển khai, không phải thiếu dao động hoặc thiếu mẫu.

Đã sửa phép gán, chạy lại extraction cho ba nguồn, thêm kiểm thử hồi quy trên sin có chu kỳ biết trước và tái tạo summary/báo cáo. Kết quả trước sửa có 24 feature với ít nhất một cửa sổ `VALID`; sau sửa có 26/30. Ba gyro theo trục Roll/Pitch vẫn thiếu hoặc chưa xác nhận, nên không có hàng đủ 30 feature.

## Vì sao 24 feature khác với subset 23

Ở kết quả trước sửa lỗi, 23 feature angle-only có cửa sổ hợp lệ; feature thứ 24 là `roll_zero_crossings_180`. Subset `angle_only_23_without_gyro_or_period` cố ý loại toàn bộ Group E, kể cả crossing count, để chỉ giữ thống kê góc Roll/Pitch cùng offset/growth. Trạng thái `VALID` của crossing count không làm feature đó tự động thuộc subset.

Sau sửa lỗi, cả ba feature Group E có giá trị hợp lệ trên một phần cửa sổ: `roll_period_est_180`, `roll_zero_crossings_180` và `roll_period_cv_180`. Vì vậy số feature có ít nhất một cửa sổ `VALID` hiện là 26, nhưng subset angle-only giữ nguyên đúng 23 tên và thứ tự. Bốn gyro feature vẫn không hợp lệ.

### 23 feature trong đúng thứ tự

1. `roll_rms_60`
2. `roll_std_60`
3. `roll_mean_60`
4. `roll_peak_to_peak_60`
5. `roll_abs_p95_60`
6. `roll_abs_max_60`
7. `roll_iqr_60`
8. `roll_diff_rms_60`
9. `roll_mean_180`
10. `roll_median_180`
11. `roll_mean_abs_180`
12. `roll_dominant_sign_ratio_180`
13. `roll_segment_mean_std_180`
14. `roll_mean_shift_180`
15. `roll_rms_early_60`
16. `roll_rms_late_60`
17. `roll_rms_ratio_180`
18. `roll_rms_slope_180`
19. `roll_rms_trend_r2_180`
20. `roll_p95_trend_slope_180`
21. `pitch_rms_60`
22. `pitch_std_60`
23. `pitch_peak_to_peak_60`

## Tính nhất quán của subset trên các hàng thực

Đã kiểm tra `validity_json` từng hàng Parquet với đúng 23 tên trên. Mọi endpoint đủ 180 giây trong segment độc lập đều có cả 23 feature ở trạng thái `VALID`; candidate row mới đủ 60 giây nhưng chưa đủ 180 giây không thể có subset đầy đủ.

| Nguồn | Candidate rows 60 giây | Endpoint đủ 180 giây | Hàng đủ 23 feature | Hàng chưa đủ subset |
|---|---:|---:|---:|---:|
| Seafar | 1,384 | 1,318 | 1,318 | 66 |
| Hohai | 1,764 | 1,512 | 1,512 | 252 |
| Southampton | 277 | 34 | 34 | 243 |

Subset 23 nhất quán trên tất cả hàng đủ cửa sổ 180 giây, không phải trên mọi candidate row 60 giây. Các hàng ngắn hơn được giữ trong bảng tổng hợp cùng validity riêng, không được xem là mẫu huấn luyện đủ subset.

## Định nghĩa period và so sánh với tài liệu

Extractor dùng `roll_deg` trong cửa sổ processed 180 giây rồi trừ trung bình của chính cửa sổ: `y_i = roll_i - mean(roll)`. Tín hiệu **mean-centered**, không phải Roll chưa center và không detrend tuyến tính. Crossing lên/xuống được đếm; crossing kẹp giữa hai mẫu trái dấu nội suy tuyến tính. Period là median khoảng cách giữa crossing lên liên tiếp trong cùng đoạn liên tục; không bắc qua missing/gap. CV là population SD chia mean period, tối thiểu ba period.

Đây là quy ước phù hợp với proposal trong [`feature_specification_30.md`](../../docs/feature_specification_30.md): mean-centering, crossing nội suy, median chu kỳ crossing lên và không nối gap. Đặc tả vẫn `PENDING_TEAM_APPROVAL`; rà soát không thay đổi định nghĩa. Kiểm thử sin 0,5 Hz cho period 2 giây và kiểm thử tương lai xác nhận giá trị tại endpoint cũ không đổi.

## Bằng chứng trên cửa sổ dữ liệu thực

Chọn cửa sổ 180 giây cuối cùng có period hợp lệ trong segment processed dài nhất mỗi nguồn. Mỗi cửa sổ có 1.800 mẫu hữu hạn. Bảng tham chiếu được tính độc lập bằng chuyển dấu liên tiếp và nội suy tuyến tính; kết quả khớp với feature table đã tái sinh.

| Nguồn / segment | Endpoint (s) | Mean Roll (°) | SD Roll (°) | Crossing tổng | Crossing lên | Period intervals | Median period (s), extractor / độc lập | CV population, extractor / độc lập |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seafar / `segment_002` | 8628.8 | 3.4371 | 0.1871 | 32 | 16 | 15 | 5.0049 / 5.0049 | 1.0618 / 1.0618 |
| Hohai / `segment_000` | 892.0 | 0.0269 | 0.3286 | 197 | 99 | 98 | 1.7595 / 1.7595 | 0.2236 / 0.2236 |
| Southampton / `segment_000` | 512.0 | 0.7054 | 0.0744 | 310 | 155 | 154 | 0.7039 / 0.7039 | 2.6556 / 2.6556 |

Các cửa sổ thực đại diện có crossing; nguyên nhân undefined trước đó là lỗi dùng timestamp như tín hiệu. Tuy vậy, CV cao ở một số nguồn nghĩa là crossing intervals biến thiên mạnh; `VALID` chỉ xác nhận phép tính đủ điều kiện, không xác nhận chu kỳ vật lý ổn định.

### Tổng hợp cửa sổ đủ 180 giây

| Nguồn | Zero-crossing: số cửa sổ / trung bình / trung vị / P05–P95 | Period VALID / undefined | CV VALID / undefined |
|---|---|---:|---:|
| Seafar | 1,318 / 37.275 / 36.5 / 11–62.15 | 1,285 / 33 | 1,271 / 47 |
| Hohai | 1,512 / 194.84 / 195 / 181.55–206 | 1,512 / 0 | 1,512 / 0 |
| Southampton | 34 / 133.21 / 136.5 / 40.65–286.6 | 34 / 0 | 34 / 0 |

Seafar còn một số cửa sổ không đủ crossing lên hoặc không đủ ba chu kỳ cho CV; các trường hợp này là `UNDEFINED_MATHEMATICALLY`, không phải thiếu coverage. Hohai và Southampton có period hợp lệ trên các cửa sổ 180 giây của lần chạy này.

## Ranh giới và tính causal

CLI đọc từng Parquet riêng; `validate_segment` yêu cầu mỗi file có duy nhất một dataset/session/segment và timestamp tăng nghiêm ngặt. Extractor không nối segment/session. Cửa sổ tại `t` chỉ đọc `(t-W,t]`. Kiểm thử hồi quy thêm một quan sát tương lai lớn tại `t+0,1 s` và xác nhận period, crossing, CV ở endpoint `t` không đổi.

## Hạn chế và bước tiếp theo

- Công thức trong tài liệu feature vẫn chờ nhóm phê duyệt; báo cáo này không biến proposal thành contract.
- Mean-centering loại offset DC nhưng trend chậm, dao động nhiều thành phần hoặc noise có thể làm period/CV kém ổn định.
- So sánh detrending hoặc estimator miền tần số là thay đổi phương pháp, cần duyệt riêng. Không áp dụng thay đổi đó ở lần sửa lỗi này.
- Unit tests theo summary lần chạy: **18 đạt, 0 lỗi**. Bốn notebook được kiểm tra sau cập nhật; xem [`feature_validation_results.md`](feature_validation_results.md).
