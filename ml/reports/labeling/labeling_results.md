# Kết quả khảo sát và phân bố nhãn

Pipeline hiện chạy ở `feasibility` mode. Có 0 nhãn external và 0 quyết định human review. Cửa sổ không có evidence giữ trạng thái phù hợp; phân bố đầu ra không đại diện phân bố vật lý.

| Nguồn | Hàng candidate 180s | UNLABELED | REVIEW_REQUIRED | Proxy candidate | Session có cửa sổ | Session có nhãn được xác minh |
|---|---:|---:|---:|---:|---:|---:|
| Seafar | 1,318 | 1,318 | 0 | 0 | 1 | 0 |
| Hohai | 1,512 | 1,512 | 0 | 0 | 21 | 0 |
| Southampton | 34 | 34 | 0 | 0 | 1 | 0 |

### Tầng lấy mẫu review

Review queue hiện có 92 hàng; tầng khả dụng: `{"UNLABELED": 92}`. Các tầng chưa thể tạo: BORDERLINE_CASE, SUSPECTED_FALSE_POSITIVE — Không cấu hình biên review cho BORDERLINE_CASE và chưa có reviewer rejection độc lập cho SUSPECTED_FALSE_POSITIVE.


## Phân bố theo session

### Seafar

| Session | Cửa sổ (chồng lấn) | UNLABELED | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | Review required | Proxy | External verified | Human reviewed | Median std Roll 60s (°) | Median |mean Roll 180s| (°) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `seafar_session_001` | 1,318 | 1,318 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.095261 | 3.2907 |

### Hohai

| Session | Cửa sổ (chồng lấn) | UNLABELED | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | Review required | Proxy | External verified | Human reviewed | Median std Roll 60s (°) | Median |mean Roll 180s| (°) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `Berth_B_T7_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.33598 | 0.093564 |
| `Berth_B_T8_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.36785 | 0.014535 |
| `Berth_B_T9_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.29304 | 0.20975 |
| `Berth_C_T7_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.32999 | 0.017034 |
| `Berth_C_T8_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.41204 | 0.064542 |
| `Berth_C_T9_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.4207 | 0.036986 |
| `Berth_D_T1_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.24702 | 0.030642 |
| `Berth_D_T2_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.27381 | 0.0047235 |
| `Berth_D_T3_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.31462 | 0.025636 |
| `Berth_D_T3_Type_B` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.28194 | 0.070429 |
| `Berth_D_T3_Type_C` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.29021 | 0.019285 |
| `Berth_D_T4_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.27885 | 0.024538 |
| `Berth_D_T5_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.28893 | 0.0087629 |
| `Berth_D_T6_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.30694 | 0.02342 |
| `Berth_D_T6_Type_B` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.34098 | 0.011891 |
| `Berth_D_T6_Type_C` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.35284 | 0.0054722 |
| `Berth_D_T7_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.44384 | 0.089543 |
| `Berth_D_T8_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.44168 | 0.019221 |
| `Berth_D_T8_Type_B` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.40344 | 0.017012 |
| `Berth_D_T8_Type_C` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.48478 | 0.060018 |
| `Berth_D_T9_Type_A` | 72 | 72 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.49302 | 0.056845 |

### Southampton

| Session | Cửa sổ (chồng lấn) | UNLABELED | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | Review required | Proxy | External verified | Human reviewed | Median std Roll 60s (°) | Median |mean Roll 180s| (°) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `southampton_run_14` | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.017848 | 0.69209 |

## Chồng lấn và tính độc lập

Stride là 10 giây với cửa sổ 180 giây nên các cửa sổ kề nhau chồng lấn khoảng 94,4%. Số lượng hàng lớn không làm tăng số session độc lập. Southampton có 34 cửa sổ nhưng chỉ một run dài; Seafar một session; Hohai 21 sheet tách biệt.

## Khả năng hỗ trợ lớp

| Lớp | Số nhãn proxy | Session có bằng chứng độc lập | Trạng thái |
|---|---:|---:|---|
| NORMAL | 0 | 0 | Chưa có operating envelope xác nhận |
| HIGH_ROLL | 0 | 0 | Chưa có ngưỡng độc lập hoặc event label |
| PERSISTENT_OFFSET | 0 | 0 | Chưa có reference datum và tiêu chí duyệt |
| AMPLITUDE_GROWTH | 0 | 0 | Chưa có định nghĩa hazard/event độc lập |

Không có label imbalance để cân chỉnh; không tạo nhãn tổng hợp hay class counts giả.
