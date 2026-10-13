import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from pydantic import ValidationError
from app.ai.provider import AIError
from app.digests.models import DigestRecord
from app.digests.schemas import DigestInput, DigestItem, DigestRead, DigestResult
from app.digests.validation import DigestSemanticError, validate_digest
from app.items.models import ItemRecord
from app.topics.models import TopicRecord


log = logging.getLogger("uvicorn.error")


class NoRelevantItems(Exception):
    pass


class DigestService:
    def __init__(self, session, provider):
        self.session, self.provider = session, provider

    def eligible(self, topic_id):
        return select(ItemRecord).where(
            ItemRecord.topic_id == topic_id, ItemRecord.ai_analyzed_at.is_not(None),
            ItemRecord.ai_relevant.is_(True), ItemRecord.ai_summary.is_not(None),
            func.length(func.trim(ItemRecord.ai_summary, " \t\r\n\v\f\u3000\u00a0")) > 0
        )

    def needs_generation(self, topic_id):
        latest = select(func.max(DigestRecord.generated_at)).where(DigestRecord.topic_id == topic_id).scalar_subquery()
        return self.session.scalar(select(self.eligible(topic_id).where(
            (latest.is_(None)) | (ItemRecord.ai_analyzed_at > latest)).exists()))

    def generate(self, topic_id):
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        items = list(self.session.scalars(self.eligible(topic_id).order_by(ItemRecord.ai_relevance_score.desc().nulls_last(),
                   func.coalesce(ItemRecord.published_at, ItemRecord.collected_at).desc(),
                   ItemRecord.id.desc()).limit(10)))
        log.debug("Final Digest selected %s Items for Topic %s", len(items), topic_id)
        if not items:
            raise NoRelevantItems("No analyzed relevant Items are available for a Digest.")
        data = DigestInput(topic_name=topic.name, topic_description=topic.description,
                           items=[DigestItem.model_validate(item, from_attributes=True) for item in items])
        try:
            result = DigestResult.model_validate(self.provider.digest(data))
            validate_digest(result, data)
        except (ValidationError, DigestSemanticError):
            raise AIError("AI returned an invalid structured Digest.") from None
        record = DigestRecord(topic_id=topic_id, item_count=len(items), generated_at=datetime.now(timezone.utc), **result.model_dump())
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return DigestRead.model_validate(record)

    def history(self, topic_id):
        if self.session.get(TopicRecord, topic_id) is None:
            raise LookupError("Topic not found")
        return [DigestRead.model_validate(row) for row in self.session.scalars(
            select(DigestRecord).where(DigestRecord.topic_id == topic_id)
            .order_by(DigestRecord.generated_at.desc(), DigestRecord.id.desc()))]
