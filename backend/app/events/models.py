from datetime import date, datetime
from sqlalchemy import Integer, String, Text, JSON, Float, Boolean, Date, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (CheckConstraint("event_status IN ('active','developing','closed')",name="ck_event_status"),)
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    identity_fingerprint: Mapped[str] = mapped_column(String(64),unique=True)
    canonical_title: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(80))
    event_family: Mapped[str] = mapped_column(String(80),index=True)
    event_date: Mapped[date | None] = mapped_column(Date,index=True)
    summary: Mapped[str] = mapped_column(Text)
    primary_entities: Mapped[list] = mapped_column(JSON)
    facts: Mapped[list] = mapped_column(JSON)
    event_status: Mapped[str] = mapped_column(String(20),default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)


class EventEntityRecord(Base):
    __tablename__ = "event_entities"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id",ondelete="CASCADE"),primary_key=True)
    entity_key: Mapped[str] = mapped_column(String(240),primary_key=True,index=True)


class TopicMatchRecord(Base):
    __tablename__ = "topic_matches"
    __table_args__ = (UniqueConstraint("normalized_item_id","topic_id","config_fingerprint",name="uq_topic_match"),
        CheckConstraint("match_status IN ('matched','unmatched','uncertain')",name="ck_topic_match_status"),
        CheckConstraint("relevance_score >= 0 AND relevance_score <= 1",name="ck_topic_match_score"))
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    normalized_item_id: Mapped[int] = mapped_column(ForeignKey("item_normalizations.id",ondelete="CASCADE"),index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id",ondelete="CASCADE"),index=True)
    config_fingerprint: Mapped[str] = mapped_column(String(64))
    topic_snapshot: Mapped[dict | None] = mapped_column(JSON)
    match_status: Mapped[str] = mapped_column(String(20))
    relevance_score: Mapped[float] = mapped_column(Float)
    matched_rules: Mapped[list] = mapped_column(JSON)
    exclusion_reason: Mapped[str] = mapped_column(Text)
    match_reason: Mapped[str] = mapped_column(Text)
    ai_used: Mapped[bool] = mapped_column(Boolean)
    processing_status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class EventDecisionRecord(Base):
    __tablename__ = "event_decisions"
    __table_args__ = (UniqueConstraint("normalized_item_id","resolver_version",name="uq_event_decision"),
        CheckConstraint("relation IN ('new_event','duplicate_report','event_update','uncertain')",name="ck_event_relation"))
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    normalized_item_id: Mapped[int | None] = mapped_column(ForeignKey("item_normalizations.id",ondelete="SET NULL"),index=True)
    resolver_version: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id",ondelete="SET NULL"),index=True)
    relation: Mapped[str] = mapped_column(String(30))
    candidate_ids: Mapped[list] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    ai_used: Mapped[bool] = mapped_column(Boolean)
    processing_status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[list] = mapped_column(JSON,default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class EventSourceRecord(Base):
    __tablename__ = "event_sources"
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id",ondelete="CASCADE"),index=True)
    normalized_item_id: Mapped[int | None] = mapped_column(ForeignKey("item_normalizations.id",ondelete="SET NULL"),unique=True)
    url_key: Mapped[str] = mapped_column(String(64),index=True)
    source_reference: Mapped[dict] = mapped_column(JSON)
    claims: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class EventUpdateRecord(Base):
    __tablename__ = "event_updates"
    __table_args__ = (UniqueConstraint("event_id","fact_fingerprint",name="uq_event_update_facts"),
        CheckConstraint("update_type IN ('new_event','new_facts','conflict')",name="ck_event_update_type"),
        CheckConstraint("importance >= 0 AND importance <= 1",name="ck_event_update_importance"))
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id",ondelete="CASCADE"),index=True)
    normalized_item_id: Mapped[int | None] = mapped_column(ForeignKey("item_normalizations.id",ondelete="SET NULL"))
    update_type: Mapped[str] = mapped_column(String(20))
    new_facts: Mapped[list] = mapped_column(JSON)
    source_reference: Mapped[dict] = mapped_column(JSON)
    importance: Mapped[float] = mapped_column(Float)
    fact_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class EventTopicRecord(Base):
    __tablename__ = "event_topics"
    __table_args__ = (UniqueConstraint("event_id","topic_id","match_id",name="uq_event_topic_match"),)
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id",ondelete="CASCADE"),index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id",ondelete="CASCADE"),index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("topic_matches.id",ondelete="CASCADE"))


class EventNotificationRecord(Base):
    __tablename__ = "event_notifications"
    __table_args__ = (UniqueConstraint("topic_id","event_id","event_update_id",name="uq_event_notification"),
        CheckConstraint("status IN ('pending','sending','sent','failed','suppressed')",name="ck_event_notification_status"))
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id",ondelete="CASCADE"),index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id",ondelete="CASCADE"))
    event_update_id: Mapped[int] = mapped_column(ForeignKey("event_updates.id",ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20),default="pending",index=True)
    reason: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
