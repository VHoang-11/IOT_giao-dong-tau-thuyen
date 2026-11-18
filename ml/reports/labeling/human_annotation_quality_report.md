# Đánh giá chất lượng Human Annotation

## Kết quả hiện trạng

Review queue giữ nguyên **92 record**, gồm **29 mẫu pilot / 23 session** và **63 mẫu mở rộng**. Ledger hiện có **0 quyết định**, trên **0 review ID**; còn **92 record chưa review**.

Đã có 0 nhãn external VERIFIED, 0 phenotype HUMAN_REVIEWED và 0 proxy. Số liệu bằng 0 phản ánh artifact hiện có, không chứng minh trạng thái vật lý không xuất hiện.

## Độ phủ theo nguồn/session

| Nguồn | Queue | Session | Đã review | Chưa review | Pilot record | Pilot session | Extended record |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hohai | 84 | 21 | 0 | 84 | 21 | 21 | 63 |
| Seafar | 4 | 1 | 0 | 4 | 4 | 1 | 0 |
| Southampton | 4 | 1 | 0 | 4 | 4 | 1 | 0 |

### Độ phủ theo từng session độc lập

| Nguồn | Session | Queue | Đã review | Chưa review | Pilot | Extended | Lớp ACCEPTED |
|---|---|---:|---:|---:|---:|---:|---|
| Hohai | `Berth_B_T7_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_B_T8_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_B_T9_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_C_T7_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_C_T8_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_C_T9_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T1_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T2_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T3_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T3_Type_B` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T3_Type_C` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T4_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T5_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T6_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T6_Type_B` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T6_Type_C` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T7_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T8_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T8_Type_B` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T8_Type_C` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Hohai | `Berth_D_T9_Type_A` | 4 | 0 | 4 | 1 | 3 | Chưa có quyết định lớp |
| Seafar | `seafar_session_001` | 4 | 0 | 4 | 4 | 0 | Chưa có quyết định lớp |
| Southampton | `southampton_run_14` | 4 | 0 | 4 | 4 | 0 | Chưa có quyết định lớp |

## Phân bố lớp, phenotype và bằng chứng

### Quyết định ACCEPTED theo lớp

| Lớp | Số quyết định |
|---|---:|
| `NORMAL` | 0 |
| `HIGH_ROLL` | 0 |
| `PERSISTENT_OFFSET` | 0 |
| `AMPLITUDE_GROWTH` | 0 |
| `REVIEW_REQUIRED` | 0 |
| `UNLABELED` | 0 |

### Lớp ACCEPTED theo nguồn

| Nguồn | NORMAL | HIGH_ROLL | PERSISTENT_OFFSET | AMPLITUDE_GROWTH | REVIEW_REQUIRED | UNLABELED |
|---|---:|---:|---:|---:|---:|---:|
| Hohai | 0 | 0 | 0 | 0 | 0 | 0 |
| Seafar | 0 | 0 | 0 | 0 | 0 | 0 |
| Southampton | 0 | 0 | 0 | 0 | 0 | 0 |

### Phenotype flags và evidence category

| Nhóm | Giá trị | Số record ACCEPTED |
|---|---|---:|
| Phenotype | `HIGH_ROLL` | 0 |
| Phenotype | `PERSISTENT_OFFSET` | 0 |
| Phenotype | `AMPLITUDE_GROWTH` | 0 |
| Evidence | `OBSERVED_MOTION_PHENOTYPE` | 0 |
| Evidence | `VERIFIED_OPERATIONAL_HAZARD` | 0 |
| Evidence | `VERIFIED_NORMAL_ENVELOPE` | 0 |
| Evidence | `PROXY_RULE` | 0 |
| Evidence | `UNVERIFIED` | 0 |

Mẫu mơ hồ hoặc cần thảo luận: **0**; review ID có bất đồng: **0**.

## Bằng chứng độc lập theo nguồn

- **Seafar:** telemetry từ một session tàu thật; audit hiện có không ghi nhận event, incident hoặc operating-state annotation độc lập. Offset Roll không tự xác nhận hazard hay NORMAL.
- **Hohai:** 21 session mô hình thử nghiệm; tên sheet/configuration không phải nhãn. Workbook không kèm event/hazard labels; sampling 50 Hz là metadata thí nghiệm, không phải evidence vận hành.
- **Southampton:** điều kiện sóng trong Test Plan là provenance của thí nghiệm; 4 mẫu pilot cùng thuộc Run 14 và không có hazard reference độc lập.
- Chưa thấy operating envelope NORMAL được chấp thuận cho bất kỳ nguồn nào. Xem [kiểm kê evidence trước đó](label_evidence_report.md) để biết nguồn tài liệu đã kiểm tra.

## Độ độc lập của đánh giá và mức nhất trí

Trong toàn bộ feature windows, stride 10 giây trên cửa sổ 180 giây nghĩa là hai cửa sổ kề chia sẻ 170 giây (94,4%). Riêng review queue thưa có 3 cặp giao nhau trên 133 cặp trong cùng segment (2.3%); 4 record có tham gia giao nhau. Pilot 29 mẫu có 3 cặp giao nhau trên 7 cặp so sánh, liên quan 4 mẫu. Các cặp này tập trung ở Southampton Run 14; hiện vẫn có 0 quyết định human review. Cửa sổ overlap là quan sát phụ thuộc, không phải session độc lập.

Chưa tính mức nhất trí giữa reviewer: Chưa có ít nhất hai reviewer với quyết định ACCEPTED trên cùng sample.

## Rủi ro và giới hạn

- Không có verified external reference hoặc human decisions tại thời điểm sinh báo cáo này.
- Human review dựa trên Roll/Pitch có thể ghi nhận phenotype; không chứng minh operating hazard hay normal operating envelope.
- Hohai và Southampton là nguồn model-scale; không gộp ngưỡng với Seafar như cùng miền vật lý.
- Cửa sổ 180 giây stride 10 giây overlap cao; mọi đánh giá mô hình phải chia theo session/run/vessel, không random theo window.
- Nếu nhãn được định nghĩa từ cùng đặc trưng Roll dùng huấn luyện, kết quả dễ vòng lặp; đồng thuận với proxy không phải kiểm định an toàn.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

**Độ phủ** tính theo review ID và session, không xem mỗi cửa sổ feature là mẫu độc lập. **Tính mơ hồ** giữ đồng thời các phenotype flags và ghi lý do, không ép về một lớp. **Mức nhất trí** chỉ tính khi có ít nhất hai reviewer thật cùng đánh giá một mẫu. **Kết quả hiện tại** là chưa có reviewer, nên chưa lớp nào được xác nhận; điều này không đồng nghĩa chuyển động bất thường không tồn tại.
