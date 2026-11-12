from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./svmg.db"
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
