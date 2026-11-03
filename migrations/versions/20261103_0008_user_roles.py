"""Add explicit candidate and administrator roles."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0008"
down_revision = "20261103_0007"
branch_labels = None
depends_on = None


def upgrade():
    # Batch mode keeps this migration compatible with local SQLite and PostgreSQL.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("role", sa.String(length=32), nullable=False, server_default="candidate")
        )
        batch.create_check_constraint(
            "ck_users_role",
            "role IN ('candidate', 'admin')",
        )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_role", type_="check")
        batch.drop_column("role")
