from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.collection.source import SourceAdapter
from app.items.schemas import ItemCreate
from app.items.service import ItemService
from app.topics.models import TopicRecord


class ScanResult(BaseModel):
    topic_id: int
    source: str
    fetched: int
    created: int
    duplicates: int


class CollectionService:
    def __init__(self, session: Session, source: SourceAdapter):
        self.session = session
        self.source = source

    def scan(self, topic_id: int) -> ScanResult:
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        results = self.source.search(topic.name)
        items = ItemService(self.session)
        created = 0
        try:
            for result in results:
                created += items.insert_if_new(ItemCreate(topic_id=topic.id, **result.model_dump()))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return ScanResult(topic_id=topic_id, source=self.source.name, fetched=len(results),
                          created=created, duplicates=len(results) - created)
