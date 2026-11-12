---
trigger: always_on
---

# Quy tắc an toàn & dữ liệu (toàn dự án)

- Dữ liệu luôn gắn cờ `SENSOR` hoặc `SIMULATION`.
- Không dùng cụm "dự báo lật tàu", "đánh giá GM/GZ"; không tuyên bố giảm CO₂ từ mô phỏng.
- Ngưỡng chỉ là tham số demo, không phải ngưỡng an toàn hàng hải.
- Lỗi cảm biến/mô hình → `UNKNOWN`/`FAULT`, không mặc định `NORMAL`.
- ML ngang/kém Baseline B vẫn là kết quả hợp lệ; báo cáo trung thực.
- Commit theo Conventional Commits; nhánh `feat/M3-XX-...`.
