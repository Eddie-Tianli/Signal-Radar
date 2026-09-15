from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Text, true
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
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    items: Mapped[list["ItemRecord"]] = relationship(
        _item_model, back_populates="topic", passive_deletes="all"
    )
    digests: Mapped[list["DigestRecord"]] = relationship(_digest_model, back_populates="topic", passive_deletes="all")
