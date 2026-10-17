from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
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


settings = Settings()  # type: ignore[call-arg] # Loaded from .env file
