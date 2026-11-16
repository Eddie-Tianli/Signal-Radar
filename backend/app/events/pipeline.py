import os
import logging
from contextlib import contextmanager,nullcontext
from threading import Lock
from sqlalchemy import select,or_
from app.ai.provider import AIError
from app.workflows.locks import topic_operation,TopicBusy
from app.normalization.service import NormalizationService
from app.normalization.models import ItemNormalizationRecord
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.events.matcher import TopicMatcher
from app.events.resolver import EventResolver
from app.events.models import EventTopicRecord,EventNotificationRecord,EventUpdateRecord

log=logging.getLogger("uvicorn.error")
_guard=Lock()


class EventBusy(Exception):pass


@contextmanager
def event_operation():
    if not _guard.acquire(blocking=False):raise EventBusy()
    try:yield
    finally:_guard.release()


def event_processing_enabled():return os.getenv("EVENT_PROCESSING_ENABLED","false").strip().lower()=="true"


def match_read(row):
    return {key:getattr(row,key) for key in ("id","topic_id","normalized_item_id","topic_snapshot","match_status","relevance_score","matched_rules","exclusion_reason","match_reason","ai_used","processing_status","error","config_fingerprint")}


def decision_read(row):
    if row is None:return None
    return {key:getattr(row,key) for key in ("id","normalized_item_id","event_id","relation","candidate_ids","reason","ai_used","processing_status","error","attempts","evidence")}


class EventPipeline:
    def __init__(self,session,provider):self.session,self.provider=session,provider

    def process_item(self,item_id,topic_ids=None,retry=False,locked_topic_id=None):
        item=self.session.get(ItemRecord,item_id)
        if item is None or item.deleted_at is not None:raise LookupError("Item not found")
        owner_lock=topic_operation(item.topic_id) if item.topic_id!=locked_topic_id else nullcontext()
        with owner_lock,event_operation():
            normalized=NormalizationService(self.session,self.provider).normalize(item_id)
            row=self.session.get(ItemNormalizationRecord,normalized.id)
            query=select(TopicRecord).order_by(TopicRecord.id)
            if topic_ids is None:query=query.where(TopicRecord.enabled.is_(True))
            else:query=query.where(TopicRecord.id.in_(topic_ids))
            topics=list(self.session.scalars(query.limit(51)))
            if len(topics)>50:raise AIError("单次最多匹配50个主题，请指定 Topic 分批处理。",422)
            matches=[TopicMatcher(self.session,self.provider).match(topic,row,retry) for topic in topics]
            matched=[match for match in matches if match.match_status=="matched"]
            decision=None;update=None;notifications=[]
            if matched:
                decision,update=EventResolver(self.session,self.provider).resolve(row,retry)
                if decision.event_id:
                    for match in matched:
                        existing=self.session.scalar(select(EventTopicRecord.id).where(EventTopicRecord.event_id==decision.event_id,
                            EventTopicRecord.topic_id==match.topic_id,EventTopicRecord.match_id==match.id))
                        if existing is None:self.session.add(EventTopicRecord(event_id=decision.event_id,topic_id=match.topic_id,match_id=match.id))
                    # Cached resolutions can recover candidate creation after a crash, but duplicates never create one.
                    if decision.relation in ("new_event","event_update"):
                        update=update or self.session.scalar(select(EventUpdateRecord).where(EventUpdateRecord.normalized_item_id==row.id,
                            EventUpdateRecord.event_id==decision.event_id).order_by(EventUpdateRecord.id.desc()).limit(1))
                    if update and not any(c.get("status")=="conflicting" for c in update.new_facts) and (update.update_type=="new_event" or update.update_type=="new_facts" and update.importance>=.8):
                        for match in matched:
                            existing=self.session.scalar(select(EventNotificationRecord).where(EventNotificationRecord.topic_id==match.topic_id,
                                EventNotificationRecord.event_id==decision.event_id,EventNotificationRecord.event_update_id==update.id))
                            if existing is None:
                                existing=EventNotificationRecord(topic_id=match.topic_id,event_id=decision.event_id,event_update_id=update.id,
                                    status="pending",reason="新事件" if update.update_type=="new_event" else "重要新增事实（估计值，未核验）")
                                self.session.add(existing);self.session.flush()
                            notifications.append(existing.id)
                    self.session.commit()
            return {"item_id":item_id,"normalized_item_id":row.id,"matches":[match_read(m) for m in matches],
                "decision":decision_read(decision),"notification_candidates":notifications}

    def process_topic(self,topic_id,limit=3,stop=None,item_ids=None):
        if self.session.get(TopicRecord,topic_id) is None:raise LookupError("Topic not found")
        ids=list(self.session.scalars(select(ItemRecord.id).where(or_(ItemRecord.topic_id==topic_id,ItemRecord.id.in_(item_ids or [])),
            ItemRecord.deleted_at.is_(None)).order_by(ItemRecord.id)))
        results=[];failed=0;reused=0
        # Completed items are cheap cache reads; only new/failed matches or unresolved records consume this round's limit.
        from app.events.read import item_processing
        for item_id in ids:
            if stop is not None and stop.is_set():break
            current=item_processing(self.session,item_id,topic_id)
            if current and current["complete"]:
                reused+=1;continue
            if len(results)+failed>=limit:break
            try:results.append(self.process_item(item_id,[topic_id],locked_topic_id=topic_id))
            except (AIError,EventBusy,TopicBusy) as error:
                self.session.rollback();failed+=1
                log.warning("Topic %s Item %s event processing failed (%s)",topic_id,item_id,type(error).__name__)
                if isinstance(error,(EventBusy,TopicBusy)) or error.status_code in (503,504):break
        return {"topic_id":topic_id,"processed":len(results),"failed":failed,"reused":reused,"results":results}
