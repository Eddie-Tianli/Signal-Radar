from datetime import datetime
from sqlalchemy import Integer,String,Text,JSON,DateTime,ForeignKey,UniqueConstraint,CheckConstraint,func
from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.database import Base


class BriefRecord(Base):
    __tablename__="briefs"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    event_id:Mapped[int]=mapped_column(ForeignKey("events.id",ondelete="CASCADE"),unique=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    versions=relationship("BriefVersionRecord",cascade="all, delete-orphan",passive_deletes=True,order_by="BriefVersionRecord.version")


class BriefVersionRecord(Base):
    __tablename__="brief_versions"
    __table_args__=(UniqueConstraint("brief_id","version",name="uq_brief_version"),
        CheckConstraint("generation_status IN ('processing','completed','fallback')",name="ck_brief_generation"))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    brief_id:Mapped[int]=mapped_column(ForeignKey("briefs.id",ondelete="CASCADE"),index=True)
    version:Mapped[int]=mapped_column(Integer)
    content_fingerprint:Mapped[str]=mapped_column(String(64),index=True)
    last_update_id:Mapped[int]=mapped_column(Integer)
    title:Mapped[str]=mapped_column(Text)
    summary:Mapped[str]=mapped_column(Text)
    facts:Mapped[list]=mapped_column(JSON)
    sources:Mapped[list]=mapped_column(JSON)
    warnings:Mapped[list]=mapped_column(JSON)
    verification_status:Mapped[str]=mapped_column(String(30))
    generation_status:Mapped[str]=mapped_column(String(20))
    model_name:Mapped[str|None]=mapped_column(Text)
    error:Mapped[str|None]=mapped_column(Text)
    generated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())


class DigestBriefRecord(Base):
    __tablename__="digest_briefs"
    __table_args__=(UniqueConstraint("digest_id","event_id",name="uq_digest_event"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    digest_id:Mapped[int]=mapped_column(ForeignKey("digests.id",ondelete="CASCADE"),index=True)
    brief_version_id:Mapped[int|None]=mapped_column(ForeignKey("brief_versions.id",ondelete="SET NULL"),index=True)
    event_id:Mapped[int|None]=mapped_column(ForeignKey("events.id",ondelete="SET NULL"),index=True)
    coverage_fingerprint:Mapped[str]=mapped_column(String(64))
    snapshot:Mapped[dict]=mapped_column(JSON)


class ReadingRunRecord(Base):
    __tablename__="reading_runs"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    topic_id:Mapped[int]=mapped_column(ForeignKey("topics.id",ondelete="CASCADE"),index=True)
    status:Mapped[str]=mapped_column(String(20))
    stage:Mapped[str]=mapped_column(String(30))
    stats:Mapped[dict]=mapped_column(JSON)
    error:Mapped[str|None]=mapped_column(Text)
    report_id:Mapped[int|None]=mapped_column(ForeignKey("digests.id",ondelete="SET NULL"))
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))


class EventReadRecord(Base):
    __tablename__="event_reads"
    event_id:Mapped[int]=mapped_column(ForeignKey("events.id",ondelete="CASCADE"),primary_key=True)
    brief_version_id:Mapped[int|None]=mapped_column(ForeignKey("brief_versions.id",ondelete="SET NULL"))
    read_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
