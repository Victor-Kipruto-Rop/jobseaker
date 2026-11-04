"""Persist real-time candidate preference drift state.

Revision ID: 20261104_0018
Revises: 20261104_0017
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0018"
down_revision = "20261104_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_preference_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("preference_vector", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("interaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_candidate_preference_states_user_id",
                    "candidate_preference_states", ["user_id"])


def downgrade():
    op.drop_index("ix_candidate_preference_states_user_id", table_name="candidate_preference_states")
    op.drop_table("candidate_preference_states")
