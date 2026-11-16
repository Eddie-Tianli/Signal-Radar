from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, Boolean, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ItemNormalizationRecord(Base):
    __tablename__ = "item_normalizations"
    __table_args__ = (
        UniqueConstraint("item_id", "schema_version", "input_fingerprint", "revision", name="uq_normalization_revision"),
        CheckConstraint("normalization_status IN ('processing', 'completed', 'failed')", name="ck_normalization_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    normalization_status: Mapped[str] = mapped_column(String(20))
    headline: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    entities: Mapped[list | None] = mapped_column(JSON)
    event_type: Mapped[str | None] = mapped_column(String(80))
    event_date: Mapped[date | None] = mapped_column(Date)
    keywords: Mapped[list | None] = mapped_column(JSON)
    claims: Mapped[list | None] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    source_reference: Mapped[dict] = mapped_column(JSON)
    content_coverage: Mapped[str] = mapped_column(String(30))
    text_truncated: Mapped[bool] = mapped_column(Boolean)
    source_metadata: Mapped[dict] = mapped_column(JSON)
    matching_text: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(Text)
    normalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    item = relationship("ItemRecord", back_populates="normalizations")
