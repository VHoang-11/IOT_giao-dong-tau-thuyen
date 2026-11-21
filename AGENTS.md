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

### Quyền sở hữu module và phối hợp liên module

README.md là nguồn chuẩn cho phân công nhóm. Quyền sở hữu xác định nhóm chịu trách nhiệm review mặc định; không phải quyền độc quyền ngăn cản tích hợp hoặc kiểm thử liên module.

| Module | Nhóm | Thư mục sở hữu |
|---|---|---|
| M1 | Embedded / Core C | `core/`, `firmware/`, `tests/firmware/` cho kiểm thử firmware M1 |
| M2 | Simulation / Machine Learning | `simulation/`, `ml/`, `core/src/sim/` |
| M3 | Backend / Data | `backend/` |
| M4 | Frontend / Infrastructure / QA | `frontend/`, `infra/`, `tests/e2e/`, `docs/` |

Quy tắc thay đổi liên module:
- Mỗi thay đổi liên module phải có mục đích cụ thể được ghi trong PR.
- Mô tả PR liệt kê các module và nhóm sở hữu bị ảnh hưởng.
- Cần review từ chủ sở hữu của mọi module bị ảnh hưởng trước khi merge.
- Thay đổi shared contract, feature semantics, model compatibility hoặc safety behavior cần compatibility review tường minh.
- Tránh refactor không liên quan; không được âm thầm đổi production behavior của module khác.
- Không bắt buộc tạo Issue riêng nếu PR đã ghi rõ phạm vi, ownership và yêu cầu review.

### Quyền test-only cho M2-led T03 / HV01
- Cho phép thay đổi chỉ phục vụ tích hợp parity ESP32 tại `firmware/target_parity/**`, `ml/parity/esp32_target.py`, `ml/parity/tests/test_esp32_target.py` và các báo cáo validation parity liên quan.
- Các thay đổi này cần review liên module từ M1 và M2.
- Quyền này không cho phép thay đổi production firmware không liên quan. Không sửa feature formulas, contract số học/validity C01-C04, golden expected values, RF weights/training data hoặc semantics an toàn của alarm.

### Git workflow
- Tên nhánh theo module: `feat/M1-XX-mô-tả`, `feat/M2-XX-mô-tả`, `feat/M3-XX-mô-tả`, `feat/M4-XX-mô-tả`; cũng chấp nhận nhánh phù hợp dưới `test/*`, `fix/*`, `docs/*`, `chore/*`.
- Commit dùng Conventional Commits, ví dụ `feat(M1): ...`, `test(M2): ...`, `fix(M3): ...`, `docs(M4): ...`.
- PR ≤ 400 dòng và ghi rõ gói công việc, module bị ảnh hưởng cùng chủ sở hữu/reviewer.

### Git — AI agent KHÔNG được commit/push
- **CẤM** AI agent tự chạy `git commit`, `git push`, `git commit --amend`, `git rebase`, `git reset --hard`, `git push --force`, tạo hoặc merge PR. Mọi commit, push và merge PR do **người dùng tự thực hiện thủ công**.
- AI chỉ được sửa file và chạy test. Xong việc thì dừng, báo danh sách file đã đổi và **gợi ý** message commit để người dùng tự copy.
- Lệnh git chỉ đọc (`git status`, `git diff`, `git log`) thì được phép.
- Không thêm `Co-Authored-By`, "Generated with Claude" hay bất kỳ dấu hiệu AI nào vào commit/PR/tài liệu, trừ khi người dùng yêu cầu.
- Nếu người dùng bảo commit/push, vẫn nhắc lại quy tắc này và hướng dẫn họ tự chạy lệnh.
- AI agent không được tự phê duyệt thay đổi liên module do chính agent thực hiện; review phải đến từ chủ sở hữu module bị ảnh hưởng.

