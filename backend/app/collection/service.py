import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.collection.source import SourceAdapter
from app.collection.query import build_queries
from app.collection.youtube import SourceError
from app.items.schemas import ItemCreate
from app.items.models import ItemRecord
from app.items.service import ItemService
from app.topics.models import TopicRecord

log = logging.getLogger("uvicorn.error")


class ScanResult(BaseModel):
    topic_id: int
    source: str
    fetched: int
    created: int
    duplicates: int
    queries: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CollectionService:
    def __init__(self, session: Session, source: SourceAdapter):
        self.session, self.source = session, source

    def scan(self, topic_id: int) -> ScanResult:
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        queries = build_queries(topic)
        results = []
        warnings = []
        topic.last_queries = []
        for query in queries:
            topic.last_queries = [*topic.last_queries, query]
            self.session.commit()  # retain the actual attempted query even if upstream fails
            try:
                results.extend(self.source.search(query))
            except SourceError as error:
                if not results:
                    raise
                warnings.append(str(error))
                log.warning("Topic %s partial search failure (%s); discovered raw Items retained", topic_id, type(error).__name__)
                break
        # De-duplicate identity before the one batched enrichment request (max 30 IDs).
        unique = list({(item.source, item.external_id): item for item in results}.values())
        try:
            unique = self.source.enrich(unique)
        except SourceError as error:
            # A statistics outage must not lose discovered raw metadata. Keep score unknown.
            warnings.append(str(error))
            log.warning("Topic %s statistics unavailable (%s); raw Items retained", topic_id, type(error).__name__)
        items = ItemService(self.session)
        created = 0
        try:
            for result in unique:
                created += items.insert_if_new(ItemCreate(topic_id=topic.id, **result.model_dump()))
                if result.popularity_metrics is not None:
                    record = self.session.scalar(select(ItemRecord).where(ItemRecord.topic_id == topic_id,
                        ItemRecord.source == result.source, ItemRecord.external_id == result.external_id))
                    if record is not None:
                        record.popularity_metrics, record.popularity_score = result.popularity_metrics, result.popularity_score
            topic.last_scan_at = datetime.now(timezone.utc)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return ScanResult(topic_id=topic_id, source=self.source.name, fetched=len(results), created=created,
                          duplicates=len(results) - created, queries=list(topic.last_queries), warnings=warnings)
