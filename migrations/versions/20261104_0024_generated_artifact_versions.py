"""Version lineage for tailored resume and generated career artifacts.

Revision ID: 20261104_0024
Revises: 20261104_0023
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0024"
down_revision = "20261104_0023"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("generated_artifacts", sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("generated_artifacts", sa.Column("source_sha256", sa.String(64), nullable=False, server_default=""))
    op.add_column("generated_artifacts", sa.Column("job_description_sha256", sa.String(64), nullable=False, server_default=""))
    op.add_column("generated_artifacts", sa.Column("parent_artifact_id", sa.Integer(), sa.ForeignKey("generated_artifacts.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_generated_artifact_user_type_version", "generated_artifacts", ["user_id", "artifact_type", "version_number"])

def downgrade():
    op.drop_index("ix_generated_artifact_user_type_version", table_name="generated_artifacts")
    op.drop_column("generated_artifacts", "parent_artifact_id")
    op.drop_column("generated_artifacts", "job_description_sha256")
    op.drop_column("generated_artifacts", "source_sha256")
    op.drop_column("generated_artifacts", "version_number")
