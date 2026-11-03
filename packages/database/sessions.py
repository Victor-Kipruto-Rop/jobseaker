from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic.script import ScriptDirectory
from apps.api.app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=1800,
                       connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return config

def init_database() -> None:
    """Migrate automatically in local environments; require an exact schema revision in production."""
    config = _alembic_config()
    if settings.app_env in {"local", "development", "test"}:
        from alembic import command
        command.upgrade(config, "head")
        return
    if settings.app_env == "production":
        expected = ScriptDirectory.from_config(config).get_current_head()
        try:
            with engine.connect() as connection:
                actual = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        except Exception as exc:
            raise RuntimeError("Production database is not migrated. Run alembic upgrade head before starting the API.") from exc
        if actual != expected:
            raise RuntimeError("Production database migration revision is behind or divergent. Run alembic upgrade head.")
