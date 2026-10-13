from typing import TYPE_CHECKING

from datetime import datetime
from sqlalchemy import Boolean, Integer, Text, Float, JSON, DateTime, ForeignKey, String, CheckConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.items.models import ItemRecord
    from app.digests.models import DigestRecord


def _item_model():
    from app.items.models import ItemRecord
    return ItemRecord


def _digest_model():
    from app.digests.models import DigestRecord
    return DigestRecord


class TopicRecord(Base):
    __tablename__ = "topics"
    __table_args__ = (CheckConstraint("relevance_threshold >= 0 AND relevance_threshold <= 1", name="ck_topics_threshold"), {"sqlite_autoincrement": True})

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    items: Mapped[list["ItemRecord"]] = relationship(
        _item_model, back_populates="topic", passive_deletes="all"
    )
    digests: Mapped[list["DigestRecord"]] = relationship(_digest_model, back_populates="topic", passive_deletes="all")

    relevance_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.80, server_default="0.80")
    last_queries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rules: Mapped[list["TopicRuleRecord"]] = relationship(back_populates="topic", cascade="all, delete-orphan", order_by="TopicRuleRecord.id")

    @property
    def include_rules(self):
        return [rule for rule in self.rules if rule.rule_type == "include"]

    @property
    def exclude_rules(self):
        return [rule for rule in self.rules if rule.rule_type == "exclude"]

    @property
    def rule_warnings(self):
        from app.topics.policy import rule_warnings
        return rule_warnings(self)


class TopicRuleRecord(Base):
    __tablename__ = "topic_rules"
    __table_args__ = (CheckConstraint("rule_type IN ('include', 'exclude')", name="ck_topic_rules_type"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    rule_type: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    topic: Mapped[TopicRecord] = relationship(back_populates="rules")
