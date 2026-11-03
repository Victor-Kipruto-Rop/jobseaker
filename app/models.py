from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OutreachContact(Base):
    __tablename__ = "outreach_contacts"
    __table_args__ = (UniqueConstraint("source_key", name="uq_outreach_source_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sector: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    contact_type: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    contact_verification: Mapped[str | None] = mapped_column(Text)
    contact_notes: Mapped[str | None] = mapped_column(Text)
    outreach_status: Mapped[str | None] = mapped_column(String(80), index=True)
    cv_attached: Mapped[str | None] = mapped_column(String(80))
    date_contacted: Mapped[str | None] = mapped_column(String(80))
    follow_up_date: Mapped[str | None] = mapped_column(String(80))
    response: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    original_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailEvent(Base):
    __tablename__ = "email_events"
    __table_args__ = (UniqueConstraint("gmail_message_id", name="uq_gmail_message_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    classification: Mapped[str | None] = mapped_column(String(80))
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_job_source_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    application_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(Integer, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(80), default="prepared", index=True)
    submission_mode: Mapped[str] = mapped_column(String(30), default="manual")
    external_confirmation: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApplicationRule(Base):
    __tablename__ = "application_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimum_match_score: Mapped[int] = mapped_column(Integer, default=85)
    allowed_titles: Mapped[list] = mapped_column(JSON, default=list)
    allowed_locations: Mapped[list] = mapped_column(JSON, default=list)
    require_verified_answers: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceImportRow(Base):
    __tablename__ = "source_import_rows"
    __table_args__ = (UniqueConstraint("source_file_key", "row_key", name="uq_source_import_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    row_key: Mapped[str] = mapped_column(String(64), nullable=False)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    organization: Mapped[str | None] = mapped_column(String(255), index=True)
    recipient: Mapped[str | None] = mapped_column(String(320), index=True)
    status: Mapped[str | None] = mapped_column(String(80))
    original_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GmailSyncState(Base):
    __tablename__ = "gmail_sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mailbox: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    history_id: Mapped[str | None] = mapped_column(String(80))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_query: Mapped[str | None] = mapped_column(Text)
    sync_status: Mapped[str] = mapped_column(String(40), default="not_started")
    last_error: Mapped[str | None] = mapped_column(Text)


class RecruiterFeedback(Base):
    __tablename__ = "recruiter_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    action_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
