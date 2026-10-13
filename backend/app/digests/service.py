import logging
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select, func
from pydantic import ValidationError
from app.ai.provider import AIError
from app.digests.models import DigestRecord
from app.digests.schemas import DigestInput, DigestItem, DigestRead, DigestResult
from app.digests.validation import DigestSemanticError, validate_digest
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.topics.policy import analysis_fingerprint
from app.digests.consolidation import consolidate
from app.digests.prompt_data import render_digest_data, DIGEST_DATA_MAX_BYTES


log = logging.getLogger("uvicorn.error")


class NoRelevantItems(Exception):
    pass


class DigestService:
    def __init__(self, session, provider):
        self.session, self.provider = session, provider

    def eligible(self, topic_id):
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        return select(ItemRecord).where(
            ItemRecord.analysis_status == "valid", ItemRecord.analysis_fingerprint == analysis_fingerprint(topic),
            ItemRecord.ai_relevance_score >= topic.relevance_threshold, ItemRecord.exclusion_status == "not_excluded",
            ItemRecord.topic_id == topic_id, ItemRecord.deleted_at.is_(None), ItemRecord.ai_analyzed_at.is_not(None),
            ItemRecord.ai_relevant.is_(True), ItemRecord.ai_summary.is_not(None),
            func.length(func.trim(ItemRecord.ai_summary, " \t\r\n\v\f\u3000\u00a0")) > 0
        )

    def inputs(self, topic_id):
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        records = list(self.session.scalars(self.eligible(topic_id).order_by(ItemRecord.ai_relevance_score.desc().nulls_last(),
            func.coalesce(ItemRecord.published_at, ItemRecord.collected_at).desc(), ItemRecord.id.desc()).limit(15)))
        units = consolidate(records)
        if units:
            while units and len(render_digest_data(DigestInput(topic_name=topic.name,
                    topic_description=topic.description, items=units)).encode("utf-8")) > DIGEST_DATA_MAX_BYTES:
                units.pop()  # highest-scored units first; never truncate rules or instructions
            if not units:
                raise AIError("AI input is too long. Shorten Topic rules or descriptions before retrying.", 503)
        # Score/category-only jitter or a reordered ranking is not new factual information.
        facts = [{"ids": sorted(unit.item_ids), "summary": unit.ai_summary,
                  "sources": sorted([{key: value for key, value in ref.model_dump(mode="json").items() if key != "unit_id"}
                                     for ref in unit.source_refs], key=lambda ref: ref["item_id"])} for unit in units]
        facts.sort(key=lambda fact: fact["ids"])
        fingerprint = hashlib.sha256(json.dumps({"topic": analysis_fingerprint(topic), "facts": facts},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return topic, units, fingerprint

    def needs_generation(self, topic_id):
        _, units, fingerprint = self.inputs(topic_id)
        if not units:
            return False
        # Trashed snapshots still count: deleting a brief must not recreate it automatically.
        latest = self.session.scalar(select(DigestRecord).where(DigestRecord.topic_id == topic_id)
            .order_by(DigestRecord.generated_at.desc(), DigestRecord.id.desc()).limit(1))
        return latest is None or latest.input_fingerprint != fingerprint

    def generate(self, topic_id):
        topic, units, fingerprint = self.inputs(topic_id)
        items = [ref for unit in units for ref in unit.source_refs]
        log.debug("Final Digest selected %s Items for Topic %s", len(items), topic_id)
        if not items:
            raise NoRelevantItems("No analyzed relevant Items are available for a Digest.")
        data = DigestInput(topic_name=topic.name, topic_description=topic.description,
                           items=units)
        try:
            result = DigestResult.model_validate(self.provider.digest(data))
            validate_digest(result, data)
        except (ValidationError, DigestSemanticError):
            raise AIError("AI returned an invalid structured Digest.") from None
        record = DigestRecord(topic_id=topic_id, item_count=len(items),
                              sources=[ref.model_dump(mode="json") for ref in items], input_fingerprint=fingerprint, generated_at=datetime.now(timezone.utc), **result.model_dump())
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return DigestRead.model_validate(record)

    def history(self, topic_id):
        if self.session.get(TopicRecord, topic_id) is None:
            raise LookupError("Topic not found")
        return [DigestRead.model_validate(row) for row in self.session.scalars(
            select(DigestRecord).where(DigestRecord.topic_id == topic_id, DigestRecord.deleted_at.is_(None))
            .order_by(DigestRecord.generated_at.desc(), DigestRecord.id.desc()))]
