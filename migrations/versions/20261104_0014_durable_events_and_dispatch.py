"""Durable event delivery, inbox deduplication and application dispatch idempotency.

Revision ID: 20261104_0014
Revises: 20261104_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0014"
down_revision = "20261104_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "event_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False),
        sa.Column("partition_key", sa.String(255), nullable=False, server_default=""),
        sa.Column("envelope", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("event_id", name="uq_event_outbox_event_id"),
    )
    op.create_index("ix_event_outbox_status_available", "event_outbox", ["status", "available_at"])
    op.create_index("ix_event_outbox_topic_created", "event_outbox", ["topic", "created_at"])
    op.create_table(
        "event_inbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("consumer_name", sa.String(120), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("consumer_name", "event_id", name="uq_event_inbox_consumer_event"),
    )
    op.create_index("ix_event_inbox_processed_at", "event_inbox", ["processed_at"])
    op.create_table(
        "application_dispatch_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_application_dispatch_user_key"),
        sa.UniqueConstraint("user_id", "application_id", name="uq_application_dispatch_user_app"),
    )
    op.create_index("ix_application_dispatch_status", "application_dispatch_keys", ["status", "created_at"])


def downgrade():
    op.drop_index("ix_application_dispatch_status", table_name="application_dispatch_keys")
    op.drop_table("application_dispatch_keys")
    op.drop_index("ix_event_inbox_processed_at", table_name="event_inbox")
    op.drop_table("event_inbox")
    op.drop_index("ix_event_outbox_topic_created", table_name="event_outbox")
    op.drop_index("ix_event_outbox_status_available", table_name="event_outbox")
    op.drop_table("event_outbox")
