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
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_webhook_url: str = ""


settings = Settings()
