from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "local"
    app_secret_key: str = "unsafe-local-only-change-me"
    database_url: str = "sqlite:///./jobseeker.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_path: str = "data/uploads"
    gmail_enabled: bool = False
    gmail_client_secret_file: str | None = None
    gmail_redirect_uri: str = "http://localhost:8000/api/v1/integrations/gmail/callback"
    web_app_url: str = "http://localhost:3000"
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
    def allowed_origins(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

@lru_cache
def get_settings():
    settings = Settings()
    if settings.app_env == "production":
        if (settings.app_secret_key == "unsafe-local-only-change-me" or
                settings.app_secret_key.lower().startswith("replace-with-") or
                "change-me" in settings.app_secret_key.lower() or len(settings.app_secret_key) < 32):
            raise ValueError("APP_SECRET_KEY must be a unique random value of at least 32 characters in production")
        if not settings.database_url.startswith("postgresql"):
            raise ValueError("Production requires PostgreSQL")
        if not settings.allowed_origins or any(not origin.startswith("https://") for origin in settings.allowed_origins):
            raise ValueError("Production CORS origins must be explicit HTTPS origins")
    return settings
