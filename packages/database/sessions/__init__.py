from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.core.config import get_settings
from packages.database.models.base import Base

settings = get_settings()
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_database() -> None:
    # Import registers model classes with Base.metadata before create_all.
    from packages.database.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
