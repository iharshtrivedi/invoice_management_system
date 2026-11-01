from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="C:\\fastapi\\secrets\\invoice_management_system.env",
        env_file_encoding='utf-8',
    )

    database_url: str
    secret_key: SecretStr
    algorithm: str = 'HS256'
    access_token_expires_minutes: int = 30

    # Mail config
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True
    frontend_url: str = 'http://localhost:8000'

    reset_token_expire_minutes: int = 60
    items_per_page: int = 10

    # Celery
    celery_broker_url: str
    celery_result_backend: str


settings = Settings()  # type: ignore[call-arg] # Loaded from .env file
