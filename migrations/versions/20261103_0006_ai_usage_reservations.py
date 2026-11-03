"""Add expiring reservations for concurrent AI token budget enforcement."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0006"
down_revision = "20261103_0005"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "ai_usage_reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_usage_reservations_request_id", "ai_usage_reservations", ["request_id"])
    op.create_index("ix_ai_usage_reservations_user_id", "ai_usage_reservations", ["user_id"])
    op.create_index("ix_ai_usage_reservations_status", "ai_usage_reservations", ["status"])
    op.create_index("ix_ai_usage_reservations_expires_at", "ai_usage_reservations", ["expires_at"])

def downgrade():
    op.drop_index("ix_ai_usage_reservations_expires_at", table_name="ai_usage_reservations")
    op.drop_index("ix_ai_usage_reservations_status", table_name="ai_usage_reservations")
    op.drop_index("ix_ai_usage_reservations_user_id", table_name="ai_usage_reservations")
    op.drop_index("ix_ai_usage_reservations_request_id", table_name="ai_usage_reservations")
    op.drop_table("ai_usage_reservations")
