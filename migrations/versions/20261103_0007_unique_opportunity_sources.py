"""Prevent concurrent duplicate imports of the same opportunity URL per user."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0007"
down_revision = "20261103_0006"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_candidate_opportunity_user_source_url"

def upgrade():
    bind = op.get_bind()
    duplicates = bind.execute(sa.text("""
        SELECT user_id, source_url, COUNT(*) AS duplicate_count
        FROM candidate_opportunities
        WHERE source_url IS NOT NULL AND source_url <> ''
        GROUP BY user_id, source_url
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError(
            "Cannot enforce opportunity URL uniqueness: duplicate rows already exist "
            f"for user_id={duplicates.user_id}. Resolve duplicate opportunity records, "
            "then rerun this migration."
        )
    op.create_index(
        INDEX_NAME, "candidate_opportunities", ["user_id", "source_url"],
        unique=True,
        postgresql_where=sa.text("source_url <> ''"),
        sqlite_where=sa.text("source_url <> ''"),
    )

def downgrade():
    op.drop_index(INDEX_NAME, table_name="candidate_opportunities")
