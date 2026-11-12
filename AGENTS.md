# SVMG Agent Rules

## Ngữ cảnh dự án
- Đây là dự án **Smart Vessel Motion Guard** — hệ thống IoT giám sát dao động tàu container
- Đọc file `.agents/memory/PROJECT_CONTEXT.md` để hiểu đầy đủ dự án

## Quy tắc khi viết code

### Backend (FastAPI)
- Dùng **Python 3.10+**, **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2**
- Mọi endpoint phải có type hints đầy đủ và Pydantic schema cho request/response
- Dùng `async def` cho tất cả route handlers
- Naming: snake_case cho biến/hàm, PascalCase cho class/model
- Validate input bằng Pydantic, không validate thủ công
- Xử lý lỗi bằng HTTPException với status code và detail rõ ràng
- Mọi thao tác DB phải dùng SQLAlchemy session (không raw SQL trừ khi cần thiết)
- Log có cấu trúc (structured logging) với context (device_id, cmd_id, user_id...)

### MQTT
- Prefix topic: `svmg/{device_id}/`
- Bản tin MQTT phải validate theo JSON Schema trong `contracts/schemas/`
- Chống trùng bằng khóa `(device_id, boot_id, seq)`
- Luôn gắn `server_rx_time` khi nhận bản tin

### Bảo mật
- **KHÔNG BAO GIỜ** commit khóa, mật khẩu, token vào git
- Dùng biến môi trường (`.env`) và cập nhật `.env.example`
- JWT cho xác thực, RBAC cho phân quyền (3 vai trò: Operator, Supervisor, Admin)
- Mọi lệnh và thay đổi cấu hình PHẢI ghi nhật ký kiểm toán

### An toàn thiết kế
- KHÔNG cho phép lệnh từ xa tắt cảnh báo cục bộ
- KHÔNG cho phép mute khi alarm đang CRITICAL
- Lệnh hết TTL phải bị bỏ qua, KHÔNG thực thi muộn
- Lỗi cảm biến/mô hình → UNKNOWN/FAULT, KHÔNG mặc định NORMAL
- Ngưỡng cứng φ_hard KHÔNG được nới ra ngoài khoảng 15–25°

### Dữ liệu
- Mọi dữ liệu phải gắn cờ `SENSOR` hoặc `SIMULATION` — không được nhập nhằng
- Không gọi kết quả là "dự báo lật tàu" hay "đánh giá GM/GZ"
- Các ngưỡng chỉ là tham số demo, không phải ngưỡng an toàn hàng hải

### Git workflow
- Tên nhánh: `feat/M3-XX-mô-tả` hoặc `fix/M3-XX-mô-tả`
- Commit: Conventional Commits — `feat(backend): ...`, `fix(backend): ...`
- PR ≤ 400 dòng, ghi rõ gói công việc
- Không sửa code ngoài thư mục `backend/` (mở issue/PR cho module khác)

### Git — AI agent KHÔNG được commit/push
- **CẤM** AI agent (Claude, v.v.) tự chạy `git commit`, `git push`, `git commit --amend`, `git rebase`, `git reset --hard`, `git push --force`, tạo/merge PR. Mọi commit do **người dùng tự làm thủ công**.
- AI chỉ được sửa file và chạy test. Xong việc thì dừng, báo danh sách file đã đổi và **gợi ý** message commit để người dùng tự copy.
- Lệnh git chỉ đọc (`git status`, `git diff`, `git log`) thì được phép.
- Không thêm `Co-Authored-By`, "Generated with Claude" hay bất kỳ dấu hiệu AI nào vào commit/PR/tài liệu, trừ khi người dùng yêu cầu.
- Nếu người dùng bảo commit/push, vẫn nhắc lại quy tắc này và hướng dẫn họ tự chạy lệnh.

