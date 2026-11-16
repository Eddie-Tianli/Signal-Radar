"""Bounded Source → Event → Brief → report workflow shared by UI and Scheduler."""
from threading import Event
import logging
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.ai.provider import AIError
from app.collection.service import CollectionService
from app.collection.youtube import SourceError
from app.digests.schemas import DigestRead
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.events.pipeline import EventPipeline,event_processing_enabled


log = logging.getLogger("uvicorn.error")


class UpdateProgress(BaseModel):
    topic_id: int
    status: Literal["running", "completed", "partial", "failed"] = "running"
    stage: Literal["scan", "analyze", "normalize", "match", "events", "brief", "digest", "complete"] = "scan"
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
    run_id: int | None = None
    briefs_generated: int = 0
    brief_fallbacks: int = 0
    event_mode: bool = False
    events_processed: int = 0
    event_relations: dict[str,int] = Field(default_factory=dict)
    event_failed: int = 0
    error: str | None = None
    failed_stage: str | None = None


class TopicUpdateService:
    """Public Source → normalized event → Brief → report orchestration, shared with Scheduler."""
    def __init__(self, session, source, provider):
        self.session,self.source,self.provider=session,source,provider

    def _pending(self,topic_id,discovered):
        from sqlalchemy import or_
        from app.events.read import item_processing
        from app.briefs.service import BriefService
        from app.events.models import EventRecord
        ids=list(self.session.scalars(select(ItemRecord.id).where(or_(ItemRecord.topic_id==topic_id,ItemRecord.id.in_(discovered)),ItemRecord.deleted_at.is_(None)).order_by(ItemRecord.id)))
        pending=[]
        for item_id in ids:
            current=item_processing(self.session,item_id,topic_id)
            if not current or not current["complete"]:pending.append(item_id);continue
            decision=current["decision"]
            if decision and decision["event_id"]:
                brief=BriefService(self.session).get(decision["event_id"])
                event=self.session.get(EventRecord,decision["event_id"])
                if not brief or brief["generation_status"]=="processing" or brief["content_fingerprint"]!=BriefService(self.session).inputs(event)[1]:pending.append(item_id)
        return pending

    def run(self,topic_id,stop=None):
        from datetime import datetime,timezone
        from app.briefs.models import ReadingRunRecord
        from app.briefs.reports import ReportService
        from app.events.pipeline import EventBusy
        from app.workflows.locks import TopicBusy
        stop=stop or Event()
        topic=self.session.get(TopicRecord,topic_id)
        if topic is None:raise LookupError("Topic not found")
        progress=UpdateProgress(topic_id=topic_id,event_mode=event_processing_enabled())
        run=None;scanned=False;discovered=[];scan_counts={"valid":0,"review":0,"unassessed":0}
        def stats():
            return {"run_id":run.id if run else None,"scan_performed":scanned,"scan_time":topic.last_scan_at.isoformat() if scanned and topic.last_scan_at else None,
                "fetched":progress.fetched,"created":progress.created,"duplicates":progress.duplicates,
                "valid_items":scan_counts["valid"],"review":scan_counts["review"],"unassessed":scan_counts["unassessed"],"new_valid_items":progress.relevant,"processed":progress.processed,
                "pending_remaining":progress.pending_remaining,"failed":progress.failed,"brief_fallbacks":progress.brief_fallbacks,"warnings":progress.warnings}
        def save(stage=None):
            if stage:progress.stage=stage
            if run:
                run.stage=progress.stage;run.stats=stats();run.error=progress.error
                self.session.commit()
        def stage_started(stage):
            previous={"match":"normalize","events":"match","brief":"events"}.get(stage)
            if previous and previous not in progress.completed_steps:progress.completed_steps.append(previous)
            save(stage)
        try:
            for previous in self.session.scalars(select(ReadingRunRecord).where(ReadingRunRecord.topic_id==topic_id,ReadingRunRecord.status=="running")):
                previous.status="interrupted";previous.error="上次处理未正常结束，可重新执行。"
            run=ReadingRunRecord(topic_id=topic_id,status="running",stage="scan",stats={})
            self.session.add(run);self.session.commit();progress.run_id=run.id
            yield progress.model_copy(deep=True)
            scan=CollectionService(self.session,self.source).scan(topic_id);scanned=True;discovered=scan.item_ids
            progress.fetched,progress.created,progress.duplicates=scan.fetched,scan.created,scan.duplicates
            progress.queries,progress.warnings=scan.queries,scan.warnings;progress.completed_steps.append("scan")
            pending=self._pending(topic_id,discovered)
            if progress.event_mode:
                for item_id in pending[:3]:
                    if stop.is_set():break
                    save("normalize");yield progress.model_copy(deep=True)
                    try:
                        result=EventPipeline(self.session,self.provider).process_item(item_id,[topic_id],locked_topic_id=topic_id,on_stage=stage_started)
                        progress.processed+=1
                        for finished in ("normalize","match"):
                            if finished not in progress.completed_steps:progress.completed_steps.append(finished)
                        if result["decision"] and "events" not in progress.completed_steps:progress.completed_steps.append("events")
                        match=next((m for m in result["matches"] if m["topic_id"]==topic_id),None)
                        decision=result["decision"]
                        relation=decision["relation"] if decision else "uncertain"
                        progress.event_relations[relation]=progress.event_relations.get(relation,0)+1
                        progress.relevant+=int(bool(match and match["match_status"]=="matched" and decision and decision["event_id"]))
                        progress.irrelevant+=int(bool(match and match["match_status"]=="unmatched"))
                        progress.review+=int(not match or match["match_status"]=="uncertain" or bool(match["match_status"]=="matched" and (not decision or decision["relation"]=="uncertain")))
                        if result.get("brief"):
                            progress.briefs_generated+=1
                            if "brief" not in progress.completed_steps:progress.completed_steps.append("brief")
                            if result["brief"]["generation_status"]=="fallback":progress.brief_fallbacks+=1
                    except (AIError,EventBusy,TopicBusy) as error:
                        self.session.rollback();progress.failed+=1;progress.event_failed+=1
                        progress.failed_stage=progress.stage
                        progress.error=str(error) if isinstance(error,AIError) else "事件或主题正在处理，请稍后重试。"
                        if not isinstance(error,AIError) or error.status_code in (503,504):break
                    save();yield progress.model_copy(deep=True)
            elif pending:progress.warnings.append("自动事件处理已关闭，新增资料尚未评估，不能当作无更新。")
            progress.events_processed=progress.processed
            progress.pending_remaining=len(self._pending(topic_id,discovered))
            from app.events.read import item_processing
            for item_id in discovered:
                record=self.session.get(ItemRecord,item_id)
                if record is None or record.deleted_at is not None:continue
                state=item_processing(self.session,item_id,topic_id)
                match=next((m for m in state["matches"] if m["topic_id"]==topic_id),None) if state else None
                if not match or match["processing_status"]!="completed":scan_counts["unassessed"]+=1
                elif match["match_status"]=="matched" and state["decision"] and state["decision"]["event_id"]:scan_counts["valid"]+=1
                elif match["match_status"]=="uncertain" or match["match_status"]=="matched":scan_counts["review"]+=1
            if progress.brief_fallbacks:progress.warnings.append("部分简讯为程序资料摘要，不是成功生成的 AI 内容。")
            if not stop.is_set():
                save("digest");yield progress.model_copy(deep=True)
                progress.digest=ReportService(self.session,self.provider).generate(topic_id,stats(),allow_empty=not progress.failed and not progress.pending_remaining and not progress.warnings)
                if progress.digest:
                    progress.completed_steps.append("digest")
                    if progress.digest.generation_error:progress.warnings.append(progress.digest.generation_error)
                else:progress.digest_skipped="processing_incomplete"
            else:progress.digest_skipped="stopped"
            progress.stage="complete"
            progress.status="partial" if progress.failed or progress.pending_remaining or progress.warnings or progress.brief_fallbacks or bool(progress.digest and progress.digest.generation_error) or stop.is_set() else "completed"
        except (SourceError,AIError) as error:
            log.warning("Topic %s workflow stage %s failed (%s)",topic_id,progress.stage,type(error).__name__)
            self.session.rollback();progress.error=str(error);progress.failed_stage=progress.stage
            progress.status="partial" if progress.completed_steps else "failed"
        except SQLAlchemyError:
            log.warning("Topic %s workflow database operation failed at %s",topic_id,progress.stage)
            self.session.rollback();progress.error="Database operation failed. Check the local database.";progress.failed_stage=progress.stage
            progress.status="partial" if progress.completed_steps else "failed"
        except Exception as error:
            log.warning("Topic %s workflow stage %s failed (%s)",topic_id,progress.stage,type(error).__name__)
            self.session.rollback();progress.error="Topic update failed. Check local logs and retry.";progress.failed_stage=progress.stage
            progress.status="partial" if progress.completed_steps else "failed"
        finally:
            if run:
                try:
                    run.status=progress.status if progress.status!="running" else "interrupted"
                    run.stage=progress.stage;run.stats=stats();run.error=progress.error
                    run.report_id=progress.digest.id if progress.digest else None;run.finished_at=datetime.now(timezone.utc);self.session.commit()
                except SQLAlchemyError:self.session.rollback()
        yield progress.model_copy(deep=True)
