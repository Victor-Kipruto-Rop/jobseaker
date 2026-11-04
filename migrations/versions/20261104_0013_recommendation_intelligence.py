"""Add behavioral recommendation events and semantic embeddings."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0013"
down_revision = "20261104_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_opportunities", sa.Column(
        "semantic_embedding", sa.JSON(), nullable=False, server_default="[]"
    ))
    op.add_column("candidate_opportunities", sa.Column(
        "embedding_model", sa.String(length=120), nullable=False, server_default=""
    ))
    op.add_column("candidate_opportunities", sa.Column(
        "embedding_text_hash", sa.String(length=64), nullable=False, server_default=""
    ))
    op.create_table(
        "recommendation_interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("candidate_opportunities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_key", sa.String(length=2200), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("recommendation_source", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("dwell_seconds", sa.Float(), nullable=True),
        sa.Column("feature_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_interactions_user_id", "recommendation_interactions", ["user_id"])
    op.create_index("ix_recommendation_interactions_opportunity_id", "recommendation_interactions", ["opportunity_id"])
    op.create_index("ix_recommendation_interactions_item_key", "recommendation_interactions", ["item_key"])
    op.create_index("ix_recommendation_interactions_event_type", "recommendation_interactions", ["event_type"])
    op.create_index("ix_recommendation_interactions_user_created", "recommendation_interactions", ["user_id", "created_at"])
    op.create_index("ix_recommendation_interactions_item_event", "recommendation_interactions", ["item_key", "event_type"])
    op.create_index("ix_recommendation_interactions_source_event", "recommendation_interactions", ["recommendation_source", "event_type"])

    # Enable native pgvector storage/indexing where the managed PostgreSQL
    # instance has the extension available. JSON embeddings remain portable.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        available = bind.execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')"
        )).scalar()
        if available:
            bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            bind.execute(sa.text(
                "ALTER TABLE candidate_opportunities ADD COLUMN semantic_vector vector(384)"
            ))
            bind.execute(sa.text(
                "CREATE INDEX ix_candidate_opportunities_semantic_vector "
                "ON candidate_opportunities USING hnsw (semantic_vector vector_cosine_ops)"
            ))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        has_column = bind.execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'candidate_opportunities' AND column_name = 'semantic_vector')"
        )).scalar()
        if has_column:
            op.execute("DROP INDEX IF EXISTS ix_candidate_opportunities_semantic_vector")
            op.execute("ALTER TABLE candidate_opportunities DROP COLUMN semantic_vector")
    for name in (
        "ix_recommendation_interactions_source_event",
        "ix_recommendation_interactions_item_event",
        "ix_recommendation_interactions_user_created",
        "ix_recommendation_interactions_event_type",
        "ix_recommendation_interactions_item_key",
        "ix_recommendation_interactions_opportunity_id",
        "ix_recommendation_interactions_user_id",
    ):
        op.drop_index(name, table_name="recommendation_interactions")
    op.drop_table("recommendation_interactions")
    op.drop_column("candidate_opportunities", "embedding_text_hash")
    op.drop_column("candidate_opportunities", "embedding_model")
    op.drop_column("candidate_opportunities", "semantic_embedding")
