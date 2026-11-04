"""Capture scroll-depth engagement as a bounded recommendation signal.

Revision ID: 20261104_0019
Revises: 20261104_0018
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0019"
down_revision = "20261104_0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("recommendation_interactions", sa.Column("scroll_depth", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("recommendation_interactions", "scroll_depth")
