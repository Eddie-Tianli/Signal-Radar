from sqlalchemy import Boolean, Integer, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TopicRecord(Base):
    __tablename__ = "topics"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
