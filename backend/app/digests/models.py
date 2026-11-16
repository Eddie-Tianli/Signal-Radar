from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.topics.models import TopicRecord


class DigestRecord(Base):
    __tablename__ = "digests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE", name="fk_digests_topic_id_topics"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    topic: Mapped[TopicRecord] = relationship(back_populates="digests")

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    sources: Mapped[list | None] = mapped_column(JSON)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))

    result_kind: Mapped[str] = mapped_column(String(30),nullable=False,default="legacy",server_default="legacy")
    generation_status: Mapped[str] = mapped_column(String(20),nullable=False,default="completed",server_default="completed")
    generation_error: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    run_stats: Mapped[dict | None] = mapped_column(JSON)
    brief_links = relationship("DigestBriefRecord",cascade="all, delete-orphan",passive_deletes=True,order_by="DigestBriefRecord.id")

    @property
    def briefs(self):return [link.snapshot for link in self.brief_links]
