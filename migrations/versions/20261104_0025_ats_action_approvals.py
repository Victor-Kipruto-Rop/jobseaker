"""Persist individually approved ATS field actions.

Revision ID: 20261104_0025
Revises: 20261104_0024
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0025"
down_revision = "20261104_0024"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "ats_action_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("ats_application_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.String(200), nullable=False),
        sa.Column("action_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="approved"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_error", sa.String(500), nullable=False, server_default=""),
        sa.UniqueConstraint("user_id", "application_id", "field_id", name="uq_ats_action_user_app_field"),
    )
    op.create_index("ix_ats_action_approvals_user_id", "ats_action_approvals", ["user_id"])
    op.create_index("ix_ats_action_approvals_application_id", "ats_action_approvals", ["application_id"])
    op.create_index("ix_ats_action_approvals_draft_id", "ats_action_approvals", ["draft_id"])
    op.create_index("ix_ats_action_status_created", "ats_action_approvals", ["status", "approved_at"])

def downgrade():
    op.drop_index("ix_ats_action_status_created", table_name="ats_action_approvals")
    op.drop_index("ix_ats_action_approvals_draft_id", table_name="ats_action_approvals")
    op.drop_index("ix_ats_action_approvals_application_id", table_name="ats_action_approvals")
    op.drop_index("ix_ats_action_approvals_user_id", table_name="ats_action_approvals")
    op.drop_table("ats_action_approvals")
