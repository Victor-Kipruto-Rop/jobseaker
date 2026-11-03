from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobSeeker Intelligence"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./jobseeker.db"
    ai_provider: str = "disabled"
    ai_api_key: str | None = None
    ai_model: str | None = None
    gmail_enabled: bool = False
    gmail_client_secret_file: str | None = None
    gmail_token_file: str | None = None
    gmail_read_only: bool = True
    job_discovery_enabled: bool = False
    auto_submission_enabled: bool = False
    global_automation_paused: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
