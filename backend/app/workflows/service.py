"""One bounded Scan → Analyze → Digest pipeline, used by UI and Scheduler."""
from threading import Event
import logging
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from app.ai.provider import AIError
from app.ai.service import AnalysisService
from app.collection.service import CollectionService
from app.collection.youtube import SourceError
from app.digests.schemas import DigestRead
from app.digests.service import DigestService, NoRelevantItems
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.topics.policy import pending_condition


log = logging.getLogger("uvicorn.error")


class UpdateProgress(BaseModel):
    topic_id: int
    status: Literal["running", "completed", "partial", "failed"] = "running"
    stage: Literal["scan", "analyze", "digest", "complete"] = "scan"
    completed_steps: list[str] = Field(default_factory=list)
    fetched: int = 0
    created: int = 0
    duplicates: int = 0
    processed: int = 0
    relevant: int = 0
    irrelevant: int = 0
    review: int = 0
    queries: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failed: int = 0
    pending_remaining: int = 0
    digest: DigestRead | None = None
    digest_skipped: str | None = None
    error: str | None = None
    failed_stage: str | None = None


class TopicUpdateService:
    def __init__(self, session, source, provider):
        self.session, self.source, self.provider = session, source, provider

    def run(self, topic_id, stop=None):
        stop = stop or Event()
        topic = self.session.get(TopicRecord, topic_id)
        if topic is None:
            raise LookupError("Topic not found")
        progress = UpdateProgress(topic_id=topic_id)
        try:
            yield progress.model_copy(deep=True)
            scan = CollectionService(self.session, self.source).scan(topic_id)
            progress.fetched, progress.created, progress.duplicates = scan.fetched, scan.created, scan.duplicates
            progress.queries, progress.warnings = scan.queries, scan.warnings
            progress.completed_steps.append("scan")
            progress.stage = "analyze"
            yield progress.model_copy(deep=True)
            pending = list(self.session.scalars(select(ItemRecord.id).where(
                ItemRecord.topic_id == topic_id, ItemRecord.deleted_at.is_(None), pending_condition(topic)
            ).order_by(ItemRecord.id).limit(20)))
            analysis_unavailable = False
            for item_id in pending:
                if stop.is_set():
                    break
                try:
                    item = AnalysisService(self.session, self.provider).analyze(item_id)
                    progress.processed += 1
                    progress.relevant += int(item.ai_relevant)
                    progress.irrelevant += int(item.analysis_status == "invalid")
                    progress.review += int(item.analysis_status == "review")
                except AIError as error:
                    self.session.rollback()
                    log.warning("Topic %s Item %s analysis failed (%s)", topic_id, item_id, type(error).__name__)
                    progress.failed += 1
                    progress.error = str(error)
                    progress.failed_stage = "analyze"
                    if error.status_code in (503, 504):
                        analysis_unavailable = True
                        break  # Service unavailable or timed out: do not repeat the same failure 20 times.
                yield progress.model_copy(deep=True)
            progress.pending_remaining = self.session.scalar(select(func.count(ItemRecord.id)).where(
                ItemRecord.topic_id == topic_id, ItemRecord.deleted_at.is_(None), pending_condition(topic)))
            progress.completed_steps.append("analyze")
            progress.stage = "digest"
            digest_service = DigestService(self.session, self.provider)
            if not analysis_unavailable and not stop.is_set() and digest_service.needs_generation(topic_id):
                progress.stage = "digest"
                yield progress.model_copy(deep=True)
                try:
                    progress.digest = digest_service.generate(topic_id)
                    progress.completed_steps.append("digest")
                except NoRelevantItems:
                    progress.digest_skipped = "no_eligible_summaries"
            else:
                progress.digest_skipped = "analysis_unavailable" if analysis_unavailable else "stopped" if stop.is_set() else "no_new_relevant"
            progress.stage = "complete"
            progress.status = "partial" if progress.failed or progress.pending_remaining or stop.is_set() else "completed"
        except (SourceError, AIError) as error:
            self.session.rollback()
            log.warning("Topic %s update failed at %s (%s)", topic_id, progress.stage, type(error).__name__)
            progress.error = str(error)
            progress.failed_stage = progress.stage
            progress.status = "partial" if progress.completed_steps else "failed"
        except SQLAlchemyError:
            self.session.rollback()
            log.error("Topic %s update database failure at %s", topic_id, progress.stage)
            progress.error = "Database operation failed. Check the local database."
            progress.failed_stage = progress.stage
            progress.status = "partial" if progress.completed_steps else "failed"
        except Exception:
            self.session.rollback()
            log.error("Topic %s update failed at %s", topic_id, progress.stage)
            progress.error = "Topic update failed. Check local logs and retry."
            progress.failed_stage = progress.stage
            progress.status = "partial" if progress.completed_steps else "failed"
        yield progress.model_copy(deep=True)
