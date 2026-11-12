---
trigger: glob
globs: backend/**
---

# Quy tắc backend (M3)

- Stack: Python 3.10+, FastAPI, SQLAlchemy 2.0, Pydantic v2, Paho MQTT. Route handler dùng `async def`, có type hints đầy đủ.
- Mọi bản tin MQTT vào phải qua `ingest/validator.py` (JSON Schema ở `contracts/schemas/`), gắn `server_rx_time`, khử trùng theo `(device_id, boot_id, seq)`.
- Lệnh: `SENT → DELIVERED → APPLIED/REJECTED/TIMEOUT`; `cmd_id` idempotent; quá TTL thì không gửi/không thực thi; mọi lệnh ghi audit log.
- Chặn ở API: mute khi alarm CRITICAL, lệnh tắt cảnh báo cục bộ, `phi_hard_deg` ngoài 15–25.
- RBAC: Operator < Supervisor < Admin.
- Không commit secrets; thêm biến mới vào `infra/.env.example`.
- Chỉ sửa trong `backend/`; module khác thì mở issue/PR.
