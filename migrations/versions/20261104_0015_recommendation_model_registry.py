"""Persist versioned recommendation model registry metadata.

Revision ID: 20261104_0015
Revises: 20261104_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0015"
down_revision = "20261104_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recommendation_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("algorithm", sa.String(80), nullable=False),
        sa.Column("artifact_key", sa.String(500), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("feature_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("training_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("model_name", "model_version", name="uq_recommendation_model_version"),
    )
    op.create_index("ix_recommendation_models_status_trained", "recommendation_models", ["status", "trained_at"])


def downgrade():
    op.drop_index("ix_recommendation_models_status_trained", table_name="recommendation_models")
    op.drop_table("recommendation_models")
