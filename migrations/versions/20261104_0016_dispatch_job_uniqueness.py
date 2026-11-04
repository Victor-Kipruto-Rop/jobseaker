"""Enforce one submitted job dispatch per candidate and normalized job key.

Revision ID: 20261104_0016
Revises: 20261104_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0016"
down_revision = "20261104_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("application_dispatch_keys", sa.Column("job_key", sa.String(64), nullable=False, server_default=""))
    op.create_unique_constraint(
        "uq_application_dispatch_user_job", "application_dispatch_keys", ["user_id", "job_key"]
    )


def downgrade():
    op.drop_constraint("uq_application_dispatch_user_job", "application_dispatch_keys", type_="unique")
    op.drop_column("application_dispatch_keys", "job_key")
