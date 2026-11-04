"""Track whether imported roles remain published at their source."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0011"
down_revision = "20261104_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_opportunities", sa.Column(
        "availability_status", sa.String(length=24), nullable=False, server_default="active"
    ))
    op.add_column("candidate_opportunities", sa.Column(
        "last_seen_at", sa.DateTime(timezone=True), nullable=True
    ))
    op.create_index(
        "ix_candidate_opportunities_availability_status",
        "candidate_opportunities", ["availability_status"],
    )


def downgrade():
    op.drop_index("ix_candidate_opportunities_availability_status", table_name="candidate_opportunities")
    op.drop_column("candidate_opportunities", "last_seen_at")
    op.drop_column("candidate_opportunities", "availability_status")
