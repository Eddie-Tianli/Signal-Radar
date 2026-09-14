from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.topics.models import TopicRecord
from app.topics.schemas import Topic, TopicWrite


class TopicService:
    """Topic operations using a request-scoped database session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_topics(self) -> list[Topic]:
        records = self.session.scalars(select(TopicRecord).order_by(TopicRecord.id)).all()
        return [Topic.model_validate(record) for record in records]

    def get_topic(self, topic_id: int) -> Topic | None:
        record = self.session.get(TopicRecord, topic_id)
        return Topic.model_validate(record) if record is not None else None

    def create_topic(self, data: TopicWrite) -> Topic:
        record = TopicRecord(**data.model_dump())
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return Topic.model_validate(record)

    def update_topic(self, topic_id: int, data: TopicWrite) -> Topic | None:
        record = self.session.get(TopicRecord, topic_id)
        if record is None:
            return None
        for field, value in data.model_dump().items():
            setattr(record, field, value)
        self.session.commit()
        self.session.refresh(record)
        return Topic.model_validate(record)

    def delete_topic(self, topic_id: int) -> bool:
        record = self.session.get(TopicRecord, topic_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.commit()
        return True


def get_topic_service(session: Annotated[Session, Depends(get_session)]) -> TopicService:
    return TopicService(session)
