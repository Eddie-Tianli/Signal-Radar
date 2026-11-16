import hashlib
import json
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.ai.provider import AIError, AIProvider
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.normalization.models import ItemNormalizationRecord
from app.normalization.preprocess import TextPreprocessor
from app.normalization.schemas import SCHEMA_VERSION, NormalizationInput, NormalizationRead, NormalizationResult, NormalizationBatch
from app.normalization.validation import validate_normalization

log = logging.getLogger("uvicorn.error")


class NormalizationService:
    def __init__(self, session: Session, provider: AIProvider | None = None):
        self.session, self.provider = session, provider

    def prepare(self, item_id):
        item = self.session.get(ItemRecord, item_id)
        if item is None or item.deleted_at is not None:
            raise LookupError("Item not found")
        cleaned = TextPreprocessor().process(item.title, item.snippet, item.source, item.author)
        published = item.published_at
        if published and published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        data = NormalizationInput(item_id=item.id, title=cleaned.title[:300], text=cleaned.body[:3500],
            source=item.source, author=item.author[:200] if item.author else None, published_at=published,
            url=item.url, source_metadata=cleaned.metadata,
            content_coverage="metadata_only" if item.source == "youtube" else "snippet_only",
            text_truncated=len(cleaned.body)>3500 or len(cleaned.title)>300 or bool(item.author and len(item.author)>200))
        raw = {key: getattr(item,key) for key in ("title","snippet","source","author","url","published_at","external_id")}
        raw["published_at"] = published.isoformat() if published else None
        fingerprint = hashlib.sha256(json.dumps({"preprocessor": "1", "raw":raw}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return item, cleaned, data, fingerprint

    def latest(self, item_id, fingerprint):
        return self.session.scalar(select(ItemNormalizationRecord).where(
            ItemNormalizationRecord.item_id==item_id, ItemNormalizationRecord.schema_version==SCHEMA_VERSION,
            ItemNormalizationRecord.input_fingerprint==fingerprint).order_by(ItemNormalizationRecord.revision.desc()).limit(1))

    def get(self, item_id):
        _, _, _, fingerprint = self.prepare(item_id)
        record = self.latest(item_id, fingerprint)
        return NormalizationRead.model_validate(record) if record else None

    def normalize(self, item_id, force=False):
        item, cleaned, data, fingerprint = self.prepare(item_id)
        record = self.latest(item_id, fingerprint)
        if record and record.normalization_status=="completed" and not force:
            return NormalizationRead.model_validate(record)
        # Explicit force creates a new revision, preserving the old successful brief.
        if record is None or record.normalization_status=="completed":
            record = ItemNormalizationRecord(item_id=item_id, schema_version=SCHEMA_VERSION,
                input_fingerprint=fingerprint, revision=record.revision+1 if record else 1,
                normalization_status="processing", warnings=[],
                source_reference={"item_id":item.id,"url":item.url,"source":item.source,"author":item.author,
                                  "published_at":data.published_at.isoformat() if data.published_at else None},
                content_coverage=data.content_coverage, text_truncated=data.text_truncated,
                source_metadata=cleaned.metadata, matching_text=cleaned.matching_text,
                model_name=getattr(self.provider,"model",type(self.provider).__name__))
            self.session.add(record)
        record.normalization_status, record.error = "processing", None
        record.model_name = getattr(self.provider,"model",type(self.provider).__name__)
        self.session.commit()  # visible in-flight marker; crash can be retried, no partial result
        try:
            result = NormalizationResult.model_validate(self.provider.normalize(data))
            result = validate_normalization(result, data)
        except Exception as error:
            # Provider failures must leave a retryable marker, never a half-written brief.
            record.normalization_status = "failed"
            record.error = "规范化失败：结构化结果或事实安全校验未通过，请重试或查看本机 Trace。"
            if isinstance(error, AIError) and error.status_code in (503,504):
                record.error = "规范化失败：Ollama 不可用或请求超时，请检查本机服务和模型后重试。"
            self.session.commit()
            log.warning("Item %s normalization failed (%s)", item_id, type(error).__name__)
            raise AIError(record.error, error.status_code if isinstance(error, AIError) else 502) from None
        for key,value in result.model_dump().items():
            setattr(record,key,[claim.model_dump() for claim in result.claims] if key=="claims" else value)
        record.normalization_status, record.normalized_at = "completed", datetime.now(timezone.utc)
        self.session.commit()
        return NormalizationRead.model_validate(record)

    def normalize_topic(self, topic_id, limit):
        if self.session.get(TopicRecord,topic_id) is None:
            raise LookupError("Topic not found")
        result = NormalizationBatch(topic_id=topic_id)
        ids = self.session.scalars(select(ItemRecord.id).where(ItemRecord.topic_id==topic_id,
            ItemRecord.deleted_at.is_(None)).order_by(ItemRecord.id)).all()
        for item_id in ids:
            current = self.get(item_id)
            if current and current.normalization_status=="completed":
                result.reused += 1
                continue
            if result.processed + result.failed >= limit:
                break
            try:
                self.normalize(item_id)
                result.processed += 1
            except AIError as error:
                result.failed += 1
                if error.status_code in (503,504):
                    break
        return result
