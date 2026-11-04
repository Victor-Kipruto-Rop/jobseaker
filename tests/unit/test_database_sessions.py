from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from packages.database import sessions


def test_alembic_config_resolves_repository_migrations(monkeypatch):
    database_url = "postgresql+psycopg://user:p%40ss@localhost/jobseeker"
    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="test", database_url=database_url),
    )

    config = sessions._alembic_config()

    repository_root = Path(sessions.__file__).resolve().parents[3]
    assert Path(config.get_main_option("script_location")) == repository_root / "migrations"
    assert config.get_main_option("sqlalchemy.url") == database_url


def test_local_initialization_applies_alembic_head(monkeypatch):
    upgrade = MagicMock()
    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="local", database_url="sqlite:///./test.db"),
    )
    monkeypatch.setattr(sessions.command, "upgrade", upgrade)

    sessions.init_database()

    upgrade.assert_called_once()
    assert upgrade.call_args.args[1] == "head"


def test_test_environment_applies_alembic_head(monkeypatch):
    upgrade = MagicMock()
    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="test", database_url="sqlite:///./test.db"),
    )
    monkeypatch.setattr(sessions.command, "upgrade", upgrade)

    sessions.init_database()

    upgrade.assert_called_once()
    assert upgrade.call_args.args[1] == "head"


def test_unsupported_environment_fails_closed(monkeypatch):
    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="staging", database_url="sqlite:///./test.db"),
    )

    with pytest.raises(RuntimeError, match="Unsupported APP_ENV"):
        sessions.init_database()


def test_production_requires_a_single_migration_head(monkeypatch):
    class NoHead:
        @staticmethod
        def get_current_head():
            return None

    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="production", database_url="postgresql://db/jobseeker"),
    )
    monkeypatch.setattr(sessions.ScriptDirectory, "from_config", lambda _config: NoHead())

    with pytest.raises(RuntimeError, match="No single Alembic migration head"):
        sessions.init_database()


def test_production_accepts_exact_migration_revision(monkeypatch):
    class CurrentHead:
        @staticmethod
        def get_current_head():
            return "revision-head"

    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = "revision-head"
    database_engine = MagicMock()
    database_engine.connect.return_value = nullcontext(connection)

    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="production", database_url="postgresql://db/jobseeker"),
    )
    monkeypatch.setattr(sessions.ScriptDirectory, "from_config", lambda _config: CurrentHead())
    monkeypatch.setattr(sessions, "engine", database_engine)

    sessions.init_database()

    connection.execute.assert_called_once()


def test_production_rejects_schema_revision_drift(monkeypatch):
    class CurrentHead:
        @staticmethod
        def get_current_head():
            return "revision-head"

    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = "old-revision"
    database_engine = MagicMock()
    database_engine.connect.return_value = nullcontext(connection)

    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="production", database_url="postgresql://db/jobseeker"),
    )
    monkeypatch.setattr(sessions.ScriptDirectory, "from_config", lambda _config: CurrentHead())
    monkeypatch.setattr(sessions, "engine", database_engine)

    with pytest.raises(RuntimeError, match="behind or divergent"):
        sessions.init_database()


def test_production_rejects_missing_migration_table(monkeypatch):
    class CurrentHead:
        @staticmethod
        def get_current_head():
            return "revision-head"

    database_engine = MagicMock()
    database_engine.connect.side_effect = RuntimeError("missing alembic_version")

    monkeypatch.setattr(
        sessions,
        "settings",
        SimpleNamespace(app_env="production", database_url="postgresql://db/jobseeker"),
    )
    monkeypatch.setattr(sessions.ScriptDirectory, "from_config", lambda _config: CurrentHead())
    monkeypatch.setattr(sessions, "engine", database_engine)

    with pytest.raises(RuntimeError, match="Production database is not migrated"):
        sessions.init_database()
