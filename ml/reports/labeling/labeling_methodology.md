# Phương pháp gán nhãn và quy tắc ứng viên

## Taxonomy

`HIGH_ROLL` là dao động Roll lớn so với ngưỡng vận hành có căn cứ, tách khỏi offset DC; `PERSISTENT_OFFSET` là độ lệch có dấu kéo dài theo thời gian và ổn định về dấu; `AMPLITUDE_GROWTH` là biên độ dao động tăng trong cửa sổ lịch sử; `NORMAL` chỉ dùng khi có envelope bình thường được chấp nhận độc lập. Các phenotype có thể đồng thời đúng. `UNLABELED` biểu thị chưa đủ chứng cứ; `REVIEW_REQUIRED` biểu thị xung đột/nhập nhằng cần quyết định.

## Tầng bằng chứng

Hợp đồng feature hiện hành trong `contracts/features.md`/`core/include/svmg_core.h` vẫn là 14 trường; enum lớp trong header chỉ là interface C, không phải annotation của các cửa sổ dữ liệu. Pipeline labeling không thay đổi hợp đồng đó.

- `EXTERNAL_REFERENCE`: nhãn từ annotation/event/document độc lập; hiện không có.
- `HUMAN_REVIEW`: quyết định người duyệt có người duyệt, thời điểm, ghi chú và audit trail; hiện chưa có quyết định.
- `PROXY_RULE`: ứng viên theo quy tắc, luôn giữ trạng thái `PROXY`; không phải ground truth.
- `UNKNOWN`: chưa có căn cứ. Pipeline mặc định feasibility, không tạo nhãn dứt khoát.

## Operational candidate rules (chờ nhóm xác nhận)

`HIGH_ROLL`: `roll_std_60 >= roll_std_60_deg` để giảm ảnh hưởng offset tĩnh; ngưỡng phải có nguồn độc lập, đơn vị độ và phạm vi dataset rõ. `PERSISTENT_OFFSET`: `abs(roll_mean_180) >= threshold` đồng thời `roll_dominant_sign_ratio_180 >= minimum`; đây vẫn là proxy, phụ thuộc mounting datum/deadband. `AMPLITUDE_GROWTH`: slope RMS tối thiểu cùng R² tối thiểu; chỉ định trend phù hợp không chứng minh hazard. `NORMAL`: đồng thời phải nằm trong roll-std/offset envelope được chấp nhận và không có phenotype bất thường; không dùng phủ định đơn giản. Mọi rule hiện disabled do chưa có ngưỡng được biện minh.

Tất cả rule cần `evidence_reference`; ngưỡng bắt buộc cấu hình rõ. Không mặc định dùng ngưỡng simulation, phân vị dataset, cân bằng lớp hoặc confidence score. Các ngưỡng cần nhóm phê duyệt trước khi bật.

## Cửa sổ nhân quả và ưu tiên lớp

Endpoint căn theo feature table đủ angle-only 23 ở 180 giây; cửa sổ `(t-180,t]`, 95% coverage do feature pipeline xác nhận. Tín hiệu high-roll dùng statistic trailing 60 giây tại cùng endpoint. Chỉ trong đúng session/segment; không qua gap/run/sheet. Dữ liệu tương lai sau endpoint không tham gia. Mặc định primary policy `REVIEW_REQUIRED`: nhiều cờ đồng thời giữ nguyên phenotype flags và yêu cầu review. Cấu hình `PRIORITY` chỉ chọn lớp chính để tiêu thụ downstream và vẫn bảo toàn mọi cờ + ambiguity reason.

## Rủi ro circular labeling

Nếu proxy HIGH_ROLL dùng roll_std/RMS thì các feature đó trực tiếp định nghĩa nhãn; offset dùng roll_mean/dominant-sign; growth dùng RMS blocks/slope/R². Huấn luyện/test trên cùng nhóm feature sẽ đánh giá khả năng tái tạo rule, không phải nhận diện nguy hiểm độc lập. Cần external events hoặc review độc lập và đánh giá theo session trước khi dùng cho supervised ML.

## Quy trình manual review

`review_queue.csv` lấy mẫu thời gian đều theo session, không chỉ lấy case dễ. Mẫu trống có các trường quyết định, bằng chứng, reviewer, timestamp, notes và status. Chỉ dữ liệu reviewer thực nhập mới được áp dụng; không có quyết định được tạo trong lần chạy này. Việc áp dụng quyết định giữ audit event append-only qua `audit_event`.

Các tầng queue được tạo khi có bằng chứng: `CLEAR_PROXY_CANDIDATE` và `CONFLICTING_PHENOTYPES`. `BORDERLINE_CASE` cần rule/ngưỡng cùng biên review đã được nhóm quy định; `SUSPECTED_FALSE_POSITIVE` cần một quyết định reviewer độc lập bác bỏ proxy. Khi không có rules/reviewer như lần chạy này, hai tầng đó được báo unavailable, không chế tạo ví dụ.

## Quy tắc conflict

Không loại bỏ phenotype chồng lấn. Mặc định nhãn chính `REVIEW_REQUIRED`; tùy chọn ưu tiên phải cấu hình rõ, giữ nguyên toàn bộ flags và giải thích rằng lớp chính là quy ước kỹ thuật.
