from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./svmg.db"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    contracts_dir: str = ""  # mac dinh: <repo>/contracts/schemas
    alarm_escalation_enabled: bool = True
    alarm_escalate_after_s: int = 60         # canh bao chua ACK sau N giay -> leo thang
    alarm_escalation_check_s: int = 5        # chu ky quet
    mqtt_enabled: bool = True
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str = "backend"
    mqtt_pass: str = ""
    mqtt_tls: bool = False                   # bat TLS toi broker (thuong dung cong 8883); production nen bat
    mqtt_ca_certs: str = ""                  # duong dan CA cua broker; rong = dung kho CA cua he dieu hanh
    auto_register_devices: bool = True       # false = chi nhan thiet bi Admin da dang ky truoc (POST /devices); nen dung o production
    docs_enabled: Optional[bool] = None     # None = tu dong: bat o dev, TAT o production (/docs, /redoc, /openapi.json)
    env: str = "dev"                        # "production" -> bat buoc JWT_SECRET manh, neu khong tu choi khoi dong
    admin_username: str = "admin"            # tao admin dau tien khi bang users rong va ADMIN_PASSWORD duoc dat
    admin_password: str = ""
    login_max_failures: int = 5              # sai qua N lan ...
    login_lockout_s: int = 300               # ... thi khoa N giay (theo username + IP)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_webhook_url: str = ""
    notify_cooldown_s: int = 30              # cung (loai, thiet bi, canh bao) khong gui lai trong N giay
    notify_timeout_s: float = 5.0
    notify_retries: int = 2                  # so lan thu lai sau lan dau that bai
    notify_backoff_s: float = 1.0            # cho 1s, 2s, ... giua cac lan thu lai
    # Don du lieu cu (retention). 0 = giu mai (mac dinh an toan). Chi ap dung cho device_health va telemetry
    # KHONG thuoc chuyen nao; telemetry cua chuyen, canh bao, lenh, audit KHONG bao gio bi xoa.
    retention_health_days: int = Field(0, ge=0)
    retention_telemetry_days: int = Field(0, ge=0)
    retention_batch: int = Field(5000, ge=1)       # xoa tung lo nho, commit tung lo de khong khoa DB lau
    retention_interval_s: int = Field(3600, ge=60)
    health_stale_s: int = 90                # thiet bi im qua N giay = 'stale' (health gui moi 30s -> 3 chu ky)


    @property
    def docs_on(self) -> bool:
        """Tai lieu API (Swagger) co duoc phuc vu khong. Mac dinh tat o production de khong lo cau truc API."""
        return self.docs_enabled if self.docs_enabled is not None else self.env.lower() != "production"


settings = Settings()
