"""Create the initial JobSeeker identity and career schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from packages.database.models import Base
from packages.database.models import identity, career, entities  # noqa: F401

revision = "20261103_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "ai_usage" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("ai_usage")}
        if "user_id" not in columns:
            op.add_column("ai_usage", sa.Column("user_id", sa.Integer(), nullable=True))
            try:
                op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])
            except Exception:
                pass
    if "approvals" in inspector.get_table_names():
        approval_columns = {column["name"] for column in inspector.get_columns("approvals")}
        if "user_id" not in approval_columns:
            op.add_column("approvals", sa.Column("user_id", sa.Integer(), nullable=True))
            try:
                op.create_index("ix_approvals_user_id", "approvals", ["user_id"])
            except Exception:
                pass
    later_migration_tables = {"email_accounts", "email_messages", "oauth_states", "account_tokens", "generated_artifacts", "ai_usage_reservations"}
    baseline_tables = [table for table in Base.metadata.sorted_tables
                       if table.name not in later_migration_tables]
    Base.metadata.create_all(bind=bind, tables=baseline_tables, checkfirst=True)

def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
