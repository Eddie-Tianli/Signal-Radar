from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import AIError, AIProvider
from app.ai.schemas import AnalysisInput, AnalysisResult, BatchResult
from app.items.models import ItemRecord
from app.items.schemas import Item
from app.topics.models import TopicRecord


class AnalysisService:
    def __init__(self, session: Session, provider: AIProvider):
        self.session, self.provider = session, provider

    def analyze(self, item_id: int) -> Item:
        item = self.session.get(ItemRecord, item_id)
        if item is None or item.deleted_at is not None:
            raise LookupError("Item not found")
        topic = item.topic
        # Bound one model request without changing or deleting the stored source content.
        data = AnalysisInput(topic_name=topic.name[:200],
                             topic_description=topic.description[:500] if topic.description else None,
                             title=item.title[:300], snippet=item.snippet[:2000] if item.snippet else None,
                             author=item.author[:100] if item.author else None, source=item.source)
        result = AnalysisResult.model_validate(self.provider.analyze(data))
        item.ai_relevant = result.relevant
        item.ai_relevance_score = result.relevance_score
        item.ai_category = result.category
        item.ai_summary = result.summary
        item.ai_analyzed_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(item)
        return Item.model_validate(item)

    def analyze_topic(self, topic_id: int, limit: int) -> BatchResult:
        if self.session.get(TopicRecord, topic_id) is None:
            raise LookupError("Topic not found")
        ids = list(self.session.scalars(select(ItemRecord.id).where(
            ItemRecord.topic_id == topic_id, ItemRecord.deleted_at.is_(None), ItemRecord.ai_analyzed_at.is_(None)
        ).order_by(ItemRecord.id).limit(limit)))
        result = BatchResult(topic_id=topic_id)
        for item_id in ids:
            try:
                item = self.analyze(item_id)
                result.processed += 1
                result.relevant += int(item.ai_relevant)
                result.irrelevant += int(not item.ai_relevant)
            except AIError:
                self.session.rollback()
                result.failed += 1
        return result
