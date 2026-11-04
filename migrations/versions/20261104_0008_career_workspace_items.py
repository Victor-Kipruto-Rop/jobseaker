"""Add persistent candidate tasks, notes, learning and project records."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0008"
down_revision = "20261103_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "career_workspace_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_career_workspace_items_user_id", "career_workspace_items", ["user_id"])
    op.create_index("ix_career_workspace_items_item_type", "career_workspace_items", ["item_type"])
    op.create_index("ix_career_workspace_user_type_status", "career_workspace_items", ["user_id", "item_type", "status"])
    op.create_index("ix_career_workspace_user_due", "career_workspace_items", ["user_id", "due_at"])


def downgrade():
    op.drop_index("ix_career_workspace_user_due", table_name="career_workspace_items")
    op.drop_index("ix_career_workspace_user_type_status", table_name="career_workspace_items")
    op.drop_index("ix_career_workspace_items_item_type", table_name="career_workspace_items")
    op.drop_index("ix_career_workspace_items_user_id", table_name="career_workspace_items")
    op.drop_table("career_workspace_items")
