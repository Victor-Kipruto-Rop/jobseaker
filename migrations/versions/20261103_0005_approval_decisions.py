"""Add approval decision metadata."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261103_0005"
down_revision = "20261103_0004"
branch_labels = None
depends_on = None

def upgrade():
    inspector = inspect(op.get_bind())
    if "approvals" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("approvals")}
    if "decision_note" not in columns:
        op.add_column("approvals", sa.Column("decision_note", sa.Text(), nullable=False, server_default=""))
    if "decided_at" not in columns:
        op.add_column("approvals", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("approvals", "decided_at")
    op.drop_column("approvals", "decision_note")
