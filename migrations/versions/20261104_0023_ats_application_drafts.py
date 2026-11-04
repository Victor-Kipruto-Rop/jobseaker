"""Persisted candidate-reviewed ATS mapping drafts.

Revision ID: 20261104_0023
Revises: 20261104_0022
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0023"
down_revision = "20261104_0022"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "ats_application_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mappings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("mapping_sha256", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="needs_review"),
        sa.Column("candidate_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "application_id", name="uq_ats_draft_user_application"),
    )
    op.create_index("ix_ats_application_drafts_user_id", "ats_application_drafts", ["user_id"])
    op.create_index("ix_ats_application_drafts_application_id", "ats_application_drafts", ["application_id"])
    op.create_index("ix_ats_draft_user_status", "ats_application_drafts", ["user_id", "status"])

def downgrade():
    op.drop_index("ix_ats_draft_user_status", table_name="ats_application_drafts")
    op.drop_index("ix_ats_application_drafts_application_id", table_name="ats_application_drafts")
    op.drop_index("ix_ats_application_drafts_user_id", table_name="ats_application_drafts")
    op.drop_table("ats_application_drafts")
