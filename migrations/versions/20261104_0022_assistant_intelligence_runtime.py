"""pgvector memory index and durable encrypted ingestion jobs.

Revision ID: 20261104_0022
Revises: 20261104_0021
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20261104_0022"
down_revision = "20261104_0021"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.add_column("assistant_memories", sa.Column("embedding_vector", Vector(384), nullable=True))
        op.execute("CREATE INDEX ix_assistant_memory_embedding_hnsw ON assistant_memories USING hnsw (embedding_vector vector_cosine_ops) WHERE embedding_vector IS NOT NULL")
    else:
        op.add_column("assistant_memories", sa.Column("embedding_vector", sa.JSON(), nullable=True))
    op.add_column("assistant_memories", sa.Column("content_encrypted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("assistant_facts", sa.Column("fact_value_encrypted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("assistant_entities", sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "assistant_ingestion_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_id", sa.Integer(), sa.ForeignKey("assistant_memories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("characters_indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assistant_ingestion_jobs_job_id", "assistant_ingestion_jobs", ["job_id"])
    op.create_index("ix_assistant_ingestion_jobs_user_id", "assistant_ingestion_jobs", ["user_id"])
    op.create_index("ix_assistant_ingestion_user_created", "assistant_ingestion_jobs", ["user_id", "created_at"])
    op.create_index("ix_assistant_ingestion_status_created", "assistant_ingestion_jobs", ["status", "created_at"])

def downgrade():
    op.drop_index("ix_assistant_ingestion_status_created", table_name="assistant_ingestion_jobs")
    op.drop_index("ix_assistant_ingestion_user_created", table_name="assistant_ingestion_jobs")
    op.drop_index("ix_assistant_ingestion_jobs_user_id", table_name="assistant_ingestion_jobs")
    op.drop_index("ix_assistant_ingestion_jobs_job_id", table_name="assistant_ingestion_jobs")
    op.drop_table("assistant_ingestion_jobs")
    op.drop_column("assistant_entities", "aliases")
    op.drop_column("assistant_facts", "fact_value_encrypted")
    op.drop_column("assistant_memories", "content_encrypted")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_assistant_memory_embedding_hnsw")
    op.drop_column("assistant_memories", "embedding_vector")
