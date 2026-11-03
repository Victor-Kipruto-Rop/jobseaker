"""Add explicit candidate and administrator roles."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0008"
down_revision = "20261103_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="candidate"),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('candidate', 'admin')",
    )


def downgrade():
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
