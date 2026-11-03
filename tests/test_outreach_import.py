from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import OutreachContact
from app.services.outreach_import import import_outreach_csv


def make_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_import_preserves_original_values_and_is_idempotent():
    db = make_session()
    csv_data = (
        b"organization,sector,email,outreach_status,cv_attached\n"
        b"Example Bank,Banking,careers@example.test,Sent,Yes\n"
    )
    first = import_outreach_csv(db, csv_data)
    second = import_outreach_csv(db, csv_data)

    assert first.inserted == 1
    assert second.inserted == 0
    assert second.already_imported == 1
    record = db.scalar(select(OutreachContact))
    assert record.organization == "Example Bank"
    assert record.outreach_status == "Sent"
    assert record.cv_attached == "Yes"
    assert record.original_payload["outreach_status"] == "Sent"


def test_dry_run_does_not_write():
    db = make_session()
    report = import_outreach_csv(db, b"organization,email\nExample,hello@example.test\n", dry_run=True)
    assert report.valid_rows == 1
    assert report.inserted == 0
    assert db.scalar(select(func.count()).select_from(OutreachContact)) == 0


def test_missing_organization_is_reported():
    db = make_session()
    report = import_outreach_csv(db, b"email,status\nhello@example.test,Sent\n")
    assert report.invalid_rows == 1
    assert report.inserted == 0
