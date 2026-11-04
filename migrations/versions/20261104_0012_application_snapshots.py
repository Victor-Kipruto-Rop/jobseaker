"""Preserve the source job and employer details at application creation time."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0012"
down_revision = "20261104_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column(
        "job_description_snapshot", sa.Text(), nullable=False, server_default=""
    ))
    op.add_column("applications", sa.Column(
        "company_profile_snapshot", sa.JSON(), nullable=False, server_default="{}"
    ))


def downgrade():
    op.drop_column("applications", "company_profile_snapshot")
    op.drop_column("applications", "job_description_snapshot")
