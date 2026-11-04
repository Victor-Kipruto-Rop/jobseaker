"""Add structured email intent and candidate-confirmed application suggestions.

Revision ID: 20261104_0017
Revises: 20261104_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0017"
down_revision = "20261104_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("email_messages", sa.Column(
        "application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    ))
    op.add_column("email_messages", sa.Column(
        "intent", sa.String(80), nullable=False, server_default="unclassified",
    ))
    op.add_column("email_messages", sa.Column(
        "suggested_status", sa.String(40), nullable=False, server_default="",
    ))
    op.add_column("email_messages", sa.Column(
        "intent_confidence", sa.Float(), nullable=False, server_default="0",
    ))
    op.add_column("email_messages", sa.Column(
        "interview_proposed_text", sa.String(500), nullable=False, server_default="",
    ))
    op.add_column("email_messages", sa.Column(
        "classification_evidence", sa.JSON(), nullable=False, server_default="{}",
    ))
    op.create_index("ix_email_messages_application_id", "email_messages", ["application_id"])


def downgrade():
    op.drop_index("ix_email_messages_application_id", table_name="email_messages")
    op.drop_column("email_messages", "classification_evidence")
    op.drop_column("email_messages", "interview_proposed_text")
    op.drop_column("email_messages", "intent_confidence")
    op.drop_column("email_messages", "suggested_status")
    op.drop_column("email_messages", "intent")
    op.drop_column("email_messages", "application_id")
