# Đánh giá mức sẵn sàng huấn luyện

## Quyết định hiện tại

**Chưa đủ điều kiện huấn luyện Machine Learning có giám sát cho bốn lớp hazard.** Hiện chưa có quyết định review của con người hoặc nhãn tham chiếu external. 92 cửa sổ review không phải 92 quan sát độc lập; queue phủ 23 session.

| Lựa chọn | Trạng thái | Bằng chứng hiện có | Bằng chứng còn thiếu / rủi ro |
|---|---|---|---|
| Huấn luyện có giám sát bốn lớp hazard đã xác minh | CHƯA ĐỦ | 2.864 cửa sổ đủ 23 đặc trưng; 23 session trong pilot | 0 nhãn VERIFIED; cần tham chiếu sự kiện/điều kiện vận hành và miền NORMAL; chưa đo độ phủ lớp; có nguy cơ rò rỉ do cửa sổ chồng lấn và khác biệt quy mô vật lý |
| Nghiên cứu phân loại phenotype chuyển động quan sát được | CHƯA SẴN SÀNG HUẤN LUYỆN | Có chuỗi thời gian Roll/Pitch; pilot 29 hồ sơ phủ 23 session | 0 quyết định reviewer; cần ít nhất hai reviewer đánh giá chồng lặp để đo mức nhất trí; phenotype không đồng nghĩa hazard |
| Thử nghiệm kỹ thuật bằng proxy rule (nhãn suy ra theo quy tắc) | CHỈ CÓ THỂ LÀM SAU KHI DUYỆT RULE | Có cửa sổ feature và provenance | Ngưỡng mô phỏng chưa phải giới hạn hazard; nhãn vòng lặp nếu mô hình dùng cùng đặc trưng; chỉ báo cáo mức khớp với proxy, không tuyên bố an toàn |
| Thu thập thêm dữ liệu có nhãn độc lập | KHUYẾN NGHỊ | Nguồn hiện tại chưa có nhãn tham chiếu external | Cần nhật ký vận hành/sự kiện có timestamp, miền NORMAL, scale/ngữ cảnh và xác minh chuyên gia |

## Điều kiện trước huấn luyện có giám sát

1. Đánh giá 29 mẫu pilot; lưu reviewer ID, bằng chứng, ghi chú, thời điểm và audit trail.
2. Có ít nhất hai reviewer độc lập cùng đánh giá tập con, sau đó báo mức nhất trí và trường hợp bất đồng.
3. Xác minh hazard bằng tham chiếu vận hành độc lập; định nghĩa NORMAL bằng miền hoạt động dương tính đã được chấp thuận.
4. Xử lý phenotype chồng lấn và cửa sổ NEEDS_DISCUSSION trước khi tạo nhãn huấn luyện.
5. Chia tập theo session/run/vessel, không chia ngẫu nhiên các cửa sổ chồng lấn.
6. Giữ tập kiểm thử độc lập với rule/feature đã định nghĩa proxy; phân tích riêng theo quy mô và nguồn dữ liệu.

## Giải thích kỹ thuật phục vụ vấn đáp cá nhân

Không thể suy mức sẵn sàng từ số cửa sổ đơn thuần: các cửa sổ chồng lấn mạnh và tập trung trong số session hữu hạn. Human review có thể xác nhận phenotype chuyển động quan sát được nhưng không thay thế nhãn tham chiếu vận hành độc lập. Bước phù hợp hiện nay là hoàn thành pilot, đo mức nhất trí giữa reviewer và thu thập nhãn sự kiện/điều kiện vận hành. Sau đó mới quyết định nghiên cứu phenotype, thử nghiệm proxy có giới hạn hay huấn luyện nhận diện hazard.
