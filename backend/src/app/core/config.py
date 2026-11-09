from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CC-Roster"
    host: str = "127.0.0.1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_request_body_bytes: int = 1024 * 1024


settings = Settings()
