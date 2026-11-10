from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SecretBackendSetting = Literal["auto", "keyring", "file"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_name: str = "CC-Roster"
    host: str = "127.0.0.1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_request_body_bytes: int = 1024 * 1024
    secret_backend: SecretBackendSetting = Field(
        default="auto",
        validation_alias="CC_ROSTER_SECRET_BACKEND",
    )


settings = Settings()
