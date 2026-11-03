"""Create the generated career artifact table."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0004"
down_revision = "20261103_0003"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "generated_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_resume_id", sa.Integer(), sa.ForeignKey("resume_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_opportunity_id", sa.Integer(), sa.ForeignKey("candidate_opportunities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_generated_artifacts_user_id", "generated_artifacts", ["user_id"])
    op.create_index("ix_generated_artifacts_artifact_type", "generated_artifacts", ["artifact_type"])
    op.create_index("ix_generated_artifacts_status", "generated_artifacts", ["status"])

def downgrade():
    op.drop_index("ix_generated_artifacts_status", table_name="generated_artifacts")
    op.drop_index("ix_generated_artifacts_artifact_type", table_name="generated_artifacts")
    op.drop_index("ix_generated_artifacts_user_id", table_name="generated_artifacts")
    op.drop_table("generated_artifacts")
