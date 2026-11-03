from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.api.app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=1800,
                       connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_database() -> None:
    """Apply versioned migrations automatically in local/test environments only."""
    if settings.app_env not in {"local", "development", "test"}:
        return
    from alembic import command
    from alembic.config import Config
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")
