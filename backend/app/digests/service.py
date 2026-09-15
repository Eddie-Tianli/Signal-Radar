from sqlalchemy import select, func
from pydantic import ValidationError
from app.ai.provider import AIError
from app.digests.models import DigestRecord
from app.digests.schemas import DigestInput, DigestItem, DigestRead, DigestResult
from app.items.models import ItemRecord
from app.topics.models import TopicRecord


class NoRelevantItems(Exception):
    pass


class DigestService:
    def __init__(self, session, provider):
        self.session, self.provider = session, provider

    def generate(self, topic_id):
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        items = list(self.session.scalars(select(ItemRecord).where(
            ItemRecord.topic_id == topic_id, ItemRecord.ai_analyzed_at.is_not(None),
            ItemRecord.ai_relevant.is_(True)
        ).order_by(func.coalesce(ItemRecord.published_at, ItemRecord.collected_at).desc(), ItemRecord.id.desc()).limit(20)))
        if not items:
            raise NoRelevantItems("No analyzed relevant Items are available for a Digest.")
        data = DigestInput(topic_name=topic.name, topic_description=topic.description,
                           items=[DigestItem.model_validate(item, from_attributes=True) for item in items])
        try:
            result = DigestResult.model_validate(self.provider.digest(data))
        except ValidationError:
            raise AIError("AI returned an invalid structured Digest.") from None
        record = DigestRecord(topic_id=topic_id, item_count=len(items), **result.model_dump())
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
