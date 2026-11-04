"""Persistent memory, preferences and feedback for personal assistant.

Revision ID: 20261104_0021
Revises: 20261104_0020
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0021"
down_revision = "20261104_0020"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "assistant_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("memory_kind", sa.String(32), nullable=False, server_default="episodic"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("source", sa.String(40), nullable=False, server_default="conversation"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_memories_user_id", "assistant_memories", ["user_id"])
    op.create_index("ix_assistant_memory_user_kind_created", "assistant_memories", ["user_id", "memory_kind", "created_at"])
    op.create_index("ix_assistant_memory_user_conversation", "assistant_memories", ["user_id", "conversation_id"])
    op.create_table(
        "assistant_facts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_key", sa.String(160), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("source_memory_id", sa.Integer(), sa.ForeignKey("assistant_memories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verified_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "fact_key", name="uq_assistant_fact_user_key"),
    )
    op.create_index("ix_assistant_facts_user_id", "assistant_facts", ["user_id"])
    op.create_table(
        "assistant_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("preference_vector", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("feedback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_preferences_user_id", "assistant_preferences", ["user_id"])
    op.create_table(
        "assistant_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("correction", sa.Text(), nullable=False, server_default=""),
        sa.Column("signals", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_feedback_user_id", "assistant_feedback", ["user_id"])

def downgrade():
    op.drop_index("ix_assistant_feedback_user_id", table_name="assistant_feedback")
    op.drop_table("assistant_feedback")
    op.drop_index("ix_assistant_preferences_user_id", table_name="assistant_preferences")
    op.drop_table("assistant_preferences")
    op.drop_index("ix_assistant_facts_user_id", table_name="assistant_facts")
    op.drop_table("assistant_facts")
    op.drop_index("ix_assistant_memory_user_conversation", table_name="assistant_memories")
    op.drop_index("ix_assistant_memory_user_kind_created", table_name="assistant_memories")
    op.drop_index("ix_assistant_memories_user_id", table_name="assistant_memories")
    op.drop_table("assistant_memories")
