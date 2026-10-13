from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.topics.models import TopicRecord


class ItemRecord(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_items_source_external_id"),
        CheckConstraint("analysis_status IN ('pending', 'valid', 'invalid', 'review', 'failed')", name="ck_items_analysis_status"),
        CheckConstraint("exclusion_status IN ('excluded', 'not_excluded', 'uncertain')", name="ck_items_exclusion_status"),
        CheckConstraint("popularity_score >= 0 AND popularity_score <= 1", name="ck_items_popularity_score"),
        CheckConstraint("ai_relevance_score >= 0 AND ai_relevance_score <= 1", name="ck_items_ai_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE", name="fk_items_topic_id_topics"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    topic: Mapped[TopicRecord] = relationship(back_populates="items")
    ai_relevant: Mapped[bool | None] = mapped_column(Boolean)
    ai_relevance_score: Mapped[float | None] = mapped_column(Float)
    ai_category: Mapped[str | None] = mapped_column(String(50))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    analysis_fingerprint: Mapped[str | None] = mapped_column(String(64))
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    exclusion_status: Mapped[str | None] = mapped_column(String(20))
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    analysis_error: Mapped[str | None] = mapped_column(Text)
    popularity_score: Mapped[float | None] = mapped_column(Float)
    popularity_metrics: Mapped[dict | None] = mapped_column(JSON)
