# Đánh giá sẵn sàng cho supervised training

## Kết luận

**Chưa đủ nhãn độc lập để huấn luyện supervised bốn lớp.** Hiện có 0 nhãn hazard VERIFIED, 0 quan sát HUMAN_REVIEWED và 0 quyết định reviewer thực tế trong pilot.

| Lớp | VERIFIED evidence | HUMAN_REVIEWED phenotype | Proxy | Session có reference vận hành độc lập |
|---|---:|---:|---:|---:|
| `NORMAL` | 0 | 0 | 0 | 0 |
| `HIGH_ROLL` | 0 | 0 | 0 | 0 |
| `PERSISTENT_OFFSET` | 0 | 0 | 0 | 0 |
| `AMPLITUDE_GROWTH` | 0 | 0 | 0 | 0 |

Human-reviewed phenotype là evidence về chuyển động quan sát được; không tự xác nhận tình trạng nguy hiểm. Các class count không chứng minh lớp vật lý vắng mặt.

## Rủi ro phương pháp

1. **Ít phiên độc lập:** Seafar 1 session, Hohai 21 session mô hình, Southampton 1 run 180 giây. 92 mẫu là cửa sổ chọn review, không phải 92 điều kiện độc lập.
2. **Overlap leakage:** stride 10 giây trên cửa sổ 180 giây tương đương khoảng 94,4% overlap giữa cửa sổ kề. Split ngẫu nhiên sẽ rò rỉ gần như cùng tín hiệu giữa train/test.
3. **Circular labeling:** nếu proxy dựa trên roll std/mean/RMS slope rồi model học các feature đó, kết quả chỉ cho thấy model tái tạo rule.
4. **Khác scale:** Hohai/Southampton là mô hình thử nghiệm; không gộp chung với tàu thật như một ngưỡng hazard phổ quát.
5. **NORMAL chưa có envelope:** thiếu baseline/operating envelope được chấp nhận; không suy NORMAL từ không phát hiện bất thường.
6. **Reliability:** chưa có hai reviewer đánh giá cùng sample; không báo agreement/kappa giả.

## Điều kiện trước khi training

- Thu thập external event/hazard annotations với timestamp, vessel/scale, operating state và nguồn xác minh.
- Xây dựng operating envelope dương tính cho NORMAL theo từng nguồn/phạm vi tàu; có người phụ trách phê duyệt.
- Đánh giá pilot mù tối thiểu bởi hai reviewer trên một tập con chồng lặp; báo agreement riêng cho primary decision và phenotype flags.
- Chốt cách phân biệt observed phenotype với verified operational hazard; xử lý các trường hợp nhiều cờ bằng `REVIEW_REQUIRED` hoặc chính sách đã được duyệt.
- Định nghĩa split theo session/run/vessel; không chia cửa sổ overlap ngẫu nhiên.
- Đánh giá subgroup và source-scale riêng; không đưa dataset/session identity vào feature vector.
- Giữ test độc lập với rule/feature đã dùng để gán proxy; không trình bày rule agreement là safety validation.

## Lựa chọn bước tiếp theo

1. **Khuyến nghị chính — additional data acquisition:** thu thập tàu thật có operational event logs và được chuyên gia xác nhận; đồng thời thu thập các giai đoạn hoạt động bình thường có envelope rõ.
2. **Reduced-scope study:** đánh giá chất lượng quan sát phenotype Roll/Pitch trên pilot, chưa gọi hazard classification và chưa khái quát giữa scale.
3. **Proxy-label proof of concept (chỉ nếu cần minh họa kỹ thuật):** rule/threshold phải có version và nguồn, split theo session, báo kết quả là agreement với proxy và nêu circularity; không dùng làm bằng chứng an toàn.

## Giải thích kỹ thuật phục vụ vấn đáp

**Vì sao chưa train?** Không có nhãn operational hazard hoặc NORMAL independently verified. **Vì sao không dùng 92 hàng như 92 mẫu độc lập?** Chúng chồng lấn thời gian và tập trung trong 23 session nguồn. **Có thể làm gì thay thế?** Mở rộng thu thập có event reference; hoặc giới hạn bài toán thành quan sát phenotype có reviewer và không tuyên bố hazard. **Giới hạn?** Mọi kết luận chỉ thuộc các nguồn và session hiện có; chưa kiểm chứng tính đại diện vận hành.
