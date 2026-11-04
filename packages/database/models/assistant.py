"""Persistent, user-scoped memory and personalization models for JobSeeker AI."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Boolean
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from packages.database.models.base import Base

def utcnow():
    return datetime.now(timezone.utc)

class AssistantMemory(Base):
    __tablename__ = "assistant_memories"
    __table_args__ = (
        Index("ix_assistant_memory_user_kind_created", "user_id", "memory_kind", "created_at"),
        Index("ix_assistant_memory_user_conversation", "user_id", "conversation_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True)
    memory_kind: Mapped[str] = mapped_column(String(32), default="episodic")
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    embedding_vector: Mapped[list | None] = mapped_column(Vector(384).with_variant(JSON, "sqlite"), nullable=True)
    content_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    importance: Mapped[float] = mapped_column(default=0.5)
    source: Mapped[str] = mapped_column(String(40), default="conversation")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class AssistantFact(Base):
    __tablename__ = "assistant_facts"
    __table_args__ = (UniqueConstraint("user_id", "fact_key", name="uq_assistant_fact_user_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fact_key: Mapped[str] = mapped_column(String(160))
    fact_value: Mapped[str] = mapped_column(Text)
    fact_value_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(default=0.7)
    source_memory_id: Mapped[int | None] = mapped_column(ForeignKey("assistant_memories.id", ondelete="SET NULL"), nullable=True)
    verified_by_user: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class AssistantPreference(Base):
    __tablename__ = "assistant_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    preferences: Mapped[dict | str] = mapped_column(JSON, default=dict)
    preference_vector: Mapped[list] = mapped_column(JSON, default=list)
    feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    memory_enabled: Mapped[bool] = mapped_column(default=False)
    memory_retention_days: Mapped[int] = mapped_column(Integer, default=365)
    preferences_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class AssistantFeedback(Base):
    __tablename__ = "assistant_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True)
    rating: Mapped[int] = mapped_column(Integer)
    correction: Mapped[str] = mapped_column(Text, default="")
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AssistantEntity(Base):
    __tablename__ = "assistant_entities"
    __table_args__ = (UniqueConstraint("user_id", "entity_type", "normalized_name", name="uq_assistant_entity_user_type_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(240))
    normalized_name: Mapped[str] = mapped_column(String(240))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    source_memory_id: Mapped[int | None] = mapped_column(ForeignKey("assistant_memories.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class AssistantRelation(Base):
    __tablename__ = "assistant_relations"
    __table_args__ = (UniqueConstraint("user_id", "source_entity_id", "target_entity_id", "relation_type", name="uq_assistant_relation_edge"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_entity_id: Mapped[int] = mapped_column(ForeignKey("assistant_entities.id", ondelete="CASCADE"), index=True)
    target_entity_id: Mapped[int] = mapped_column(ForeignKey("assistant_entities.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[float] = mapped_column(default=0.7)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
