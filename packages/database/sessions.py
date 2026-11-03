from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.api.app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_database() -> None:
    # Import model modules before create_all so SQLAlchemy registers every table.
    from packages.database.models import Base, Opportunity, Approval, AIUsage  # noqa: F401
    Base.metadata.create_all(bind=engine)
