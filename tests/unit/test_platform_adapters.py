import asyncio
from types import SimpleNamespace

import pytest

from packages.storage import objects
from packages.events import kafka


def test_private_local_object_round_trip_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(objects, "get_settings", lambda: SimpleNamespace(
        storage_backend="local", storage_path=str(tmp_path),
    ))
    stored = objects.store_private_object(
        b"resume-bytes", "../../candidate resume.pdf", "application/pdf", owner_scope="42",
    )
    assert stored["storage"] == "local"
    assert stored["object_key"].startswith("42/")
    assert objects.read_private_object(stored["object_key"]) == b"resume-bytes"
    objects.delete_private_object(stored["object_key"])
    with pytest.raises(FileNotFoundError):
        objects.read_private_object(stored["object_key"])


def test_private_storage_rejects_empty_and_oversized_objects(tmp_path, monkeypatch):
    monkeypatch.setattr(objects, "get_settings", lambda: SimpleNamespace(
        storage_backend="local", storage_path=str(tmp_path),
    ))
    with pytest.raises(ValueError):
        objects.store_private_object(b"", "resume.pdf", "application/pdf")
    with pytest.raises(ValueError):
        objects.store_private_object(b"x" * (25 * 1024 * 1024 + 1), "resume.pdf", "application/pdf")


def test_private_storage_rejects_traversal_on_read(tmp_path, monkeypatch):
    monkeypatch.setattr(objects, "get_settings", lambda: SimpleNamespace(
        storage_backend="local", storage_path=str(tmp_path),
    ))
    with pytest.raises(ValueError):
        objects.read_private_object("../secrets.txt")


def test_event_publisher_is_disabled_without_broker(monkeypatch):
    monkeypatch.setattr(kafka, "get_settings", lambda: SimpleNamespace(kafka_enabled=False))
    assert asyncio.run(kafka.publish_event("user.activity", {"user_id": 7})) is False


def test_event_publisher_rejects_unknown_topic():
    with pytest.raises(ValueError):
        asyncio.run(kafka.publish_event("unknown.topic", {}))
