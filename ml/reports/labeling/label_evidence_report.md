# Kiểm kê bằng chứng nhãn và điều kiện vận hành

## Kết luận

Review queue hiện có **92 mẫu** trên ba nguồn; đã tìm thấy **0 nhãn external**, **0 nhãn human-reviewed** và **0 nhãn hazard vận hành được xác minh**. Chưa có cơ sở tính inter-reviewer agreement. Đây là kết quả kiểm kê artifact/tài liệu hiện có, không phải kết luận các trạng thái vật lý không tồn tại.

## Độ phủ bằng chứng theo nguồn và session

| Nguồn | Mẫu pilot | Session độc lập | Session có metadata thử nghiệm | Quyết định reviewer | Mẫu đã review | Hazard reference | Normal envelope |
|---|---:|---:|---:|---:|---:|---:|---:|
| Seafar | 4 | 1 | 0 | 0 | 0 | 0 | 0 |
| Hohai | 84 | 21 | 21 | 0 | 0 | 0 | 0 |
| Southampton | 4 | 1 | 1 | 0 | 0 | 0 | 0 |

Session được tính theo định danh nguồn, không theo số cửa sổ. Nhiều cửa sổ trong một session không tăng số phiên độc lập.

## Seafar

JSON là telemetry theo thời gian; không thấy trường event/incident/operating-state độc lập. Một session tàu thật; offset gốc và lineage trục/rate cần lưu ý.

| Session | Số mẫu trong pilot | Metadata thực nghiệm |
|---|---:|---|
| `seafar_session_001` | 4 | nguồn `ml/data/raw/seafar/cleaned_imu_gps_data.json`; không có trường operating condition độc lập |

**Các tuyên bố không được hỗ trợ:**

- Không thể gọi Roll offset khác 0 là hazard hoặc NORMAL.
- Không thể kết luận HIGH_ROLL/PERSISTENT_OFFSET/AMPLITUDE_GROWTH từ thống kê đơn lẻ.

## Hohai

Workbook có 21 sheet/session và tên sheet chứa thông tin berth/test/type; đây là định danh cấu hình thử nghiệm, không phải nhãn trạng thái an toàn. Nguồn là mô hình thử nghiệm, thời gian suy từ 50 Hz; không có timestamp/gyro đo trực tiếp.

| Session | Số mẫu trong pilot | Metadata thực nghiệm |
|---|---:|---|
| `Berth_B_T7_Type_A` | 4 | sheet `Berth_B_T7_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_B_T8_Type_A` | 4 | sheet `Berth_B_T8_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_B_T9_Type_A` | 4 | sheet `Berth_B_T9_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_C_T7_Type_A` | 4 | sheet `Berth_C_T7_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_C_T8_Type_A` | 4 | sheet `Berth_C_T8_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_C_T9_Type_A` | 4 | sheet `Berth_C_T9_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T1_Type_A` | 4 | sheet `Berth D_T1_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T2_Type_A` | 4 | sheet `Berth D_T2_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T3_Type_A` | 4 | sheet `Berth D_T3_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T3_Type_B` | 4 | sheet `Berth_D_T3_Type B`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T3_Type_C` | 4 | sheet `Berth_D_T3_Type C`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T4_Type_A` | 4 | sheet `Berth D_T4_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T5_Type_A` | 4 | sheet `Berth D_T5_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T6_Type_A` | 4 | sheet `Berth D_T6_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T6_Type_B` | 4 | sheet `Berth_D_T6_Type B`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T6_Type_C` | 4 | sheet `Berth_D_T6_Type C`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T7_Type_A` | 4 | sheet `Berth D_T7_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T8_Type_A` | 4 | sheet `Berth D_T8_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T8_Type_B` | 4 | sheet `Berth_D_T8_Type B`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T8_Type_C` | 4 | sheet `Berth_D_T8_Type C`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |
| `Berth_D_T9_Type_A` | 4 | sheet `Berth D_T9_Type A`; 50 Hz (metadata); INFERRED_FROM_SAMPLE_INDEX |

**Các tuyên bố không được hỗ trợ:**

- Không diễn giải hậu tố Type_A/B/C thành phenotype/hazard.
- Không tuyên bố dữ liệu mô hình đại diện trực tiếp cho tàu full-scale.

## Southampton

Test Plan mô tả điều kiện thử nghiệm theo Run ID; các giá trị wave frequency/amplitude chỉ là provenance. Run 14 có điều kiện trong metadata nhưng không kèm nhãn hazard hay event reference.

| Session | Số mẫu trong pilot | Metadata thực nghiệm |
|---|---:|---|
| `southampton_run_14` | 4 | run 14.1, R1, wave 0.7976 Hz, biên độ 0.01927 m (provenance) |

**Các tuyên bố không được hỗ trợ:**

- Không suy hazard từ wave amplitude/frequency.
- Không coi Delta Angle là gyro canonical khi semantics/trục chưa xác nhận.
- Chỉ Run 14 có cửa sổ 180 giây; 4 mẫu pilot trong run này không phải 4 session độc lập.

## Nguồn đã kiểm tra

- `ml/audit/real_dataset_audit_report.md`
- `ml/data/raw/hohai/6-DOF ship motions Data.xlsx`
- `ml/data/raw/hohai/Data Description Example.pdf`
- `ml/data/raw/seafar/cleaned_imu_gps_data.json`
- `ml/data/raw/southampton/Readme/KCS Test Plan June 2023.xlsx`
- `ml/data/raw/southampton/Readme/README.txt`

## Cảnh báo thiết kế

Các cửa sổ 180 giây stride 10 giây chồng lấn xấp xỉ 94,4%; chúng không phải quan sát độc lập.
Không có nhãn độc lập để xác nhận NORMAL, HIGH_ROLL, PERSISTENT_OFFSET hay AMPLITUDE_GROWTH. Điều kiện vật lý trong workbook/Test Plan không được chuyển thành target label. Xem [báo cáo feasibility trước đó](labeling_feasibility_report.md) để biết giới hạn window eligibility.
