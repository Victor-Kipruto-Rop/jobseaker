from functools import lru_cache
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "local"
    app_secret_key: str = "unsafe-local-only-change-me"
    database_url: str = "sqlite:///./jobseeker.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_path: str = "data/uploads"
    storage_backend: str = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "jobseeker"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_client_id: str = "jobseeker-api"
    gmail_enabled: bool = False
    credential_kek: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "jobseeker-api"
    job_discovery_enabled: bool = False
    gmail_client_secret_file: str | None = None
    gmail_redirect_uri: str = "http://localhost:8000/api/v1/integrations/gmail/callback"
    web_app_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    cors_origins: str = "http://localhost:3000"
    ai_default_provider: str = "mock"
    ai_fallback_provider: str = "mock"
    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_default_model: str = "gpt-4.1-mini"
    anthropic_enabled: bool = False
    anthropic_api_key: str | None = None
    anthropic_default_model: str = "claude-sonnet-4-20250514"
    global_automation_paused: bool = True
    admin_bootstrap_enabled: bool = False
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
        if settings.storage_backend == "s3" and not (
            settings.s3_bucket and settings.s3_access_key_id and settings.s3_secret_access_key
        ):
            raise ValueError("S3-compatible storage requires bucket and credentials in production")
        if settings.kafka_enabled and not settings.kafka_bootstrap_servers:
            raise ValueError("Kafka bootstrap servers are required when event streaming is enabled")
        if settings.gmail_enabled and not (settings.credential_kek or os.getenv("JOBSEEKER_CREDENTIAL_KEK")):
            raise ValueError("JOBSEEKER_CREDENTIAL_KEK is required when Gmail OAuth is enabled")
        if not settings.allowed_origins or any(not origin.startswith("https://") for origin in settings.allowed_origins):
            raise ValueError("Production CORS origins must be explicit HTTPS origins")
    return settings
