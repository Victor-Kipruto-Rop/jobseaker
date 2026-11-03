from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "local"
    app_secret_key: str = "unsafe-local-only-change-me"
    database_url: str = "sqlite:///./jobseeker.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    ai_default_provider: str = "mock"
    ai_fallback_provider: str = "mock"
    ai_monthly_budget_usd: float = 20.0
    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_default_model: str = "gpt-4.1-mini"
    anthropic_enabled: bool = False
    anthropic_api_key: str | None = None
    anthropic_default_model: str = "claude-sonnet-4-20250514"
    global_automation_paused: bool = True
    auto_email_send: bool = False
    auto_application_submit: bool = False
    @property
    def allowed_origins(self): return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings(): return Settings()
