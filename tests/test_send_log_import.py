from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import SourceImportRow
from app.services.send_log_import import import_send_log


def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_send_log_import_preserves_ids_and_is_idempotent():
    db = make_session()
    data = b"organization,email,status,message_id,thread_id\nExample,hr@example.test,SENT,msg-123,thread-456\n"
    first = import_send_log(db, data, "outreach_send_log.csv")
    second = import_send_log(db, data, "outreach_send_log.csv")
    assert first.inserted == 1
    assert first.rows_with_message_id == 1
    assert first.rows_with_thread_id == 1
    assert second.inserted == 0
    record = db.scalar(select(SourceImportRow))
    assert record.gmail_message_id == "msg-123"
    assert record.gmail_thread_id == "thread-456"
    assert record.original_payload["status"] == "SENT"


def test_send_log_dry_run_does_not_write():
    db = make_session()
    report = import_send_log(db, b"organization,status\nExample,SENT\n", "send.csv", dry_run=True)
    assert report.inserted == 0
    assert db.scalar(select(func.count()).select_from(SourceImportRow)) == 0
