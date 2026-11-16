"""Persistent, at-most-once send attempts. A crash after claim is not blindly retried."""
from datetime import datetime,timezone
import logging
from sqlalchemy import select,update
from app.events.models import EventNotificationRecord,EventUpdateRecord,TopicMatchRecord,EventRecord
from app.events.matcher import match_fingerprint
from app.topics.models import TopicRecord
from app.items.models import ItemRecord
from app.normalization.models import ItemNormalizationRecord
from app.notifications.service import get_notification_service
log=logging.getLogger("uvicorn.error")


def dispatch_candidates(session,topic_id,service_factory=get_notification_service):
    try:service=service_factory()
    except Exception:
        log.warning("Topic %s event notification service unavailable",topic_id);return 0
    if service is None:return 0  # disabled: keep the candidates, do not claim or send
    sent=0
    ids=list(session.scalars(select(EventNotificationRecord.id).where(EventNotificationRecord.topic_id==topic_id,
        EventNotificationRecord.status=="pending").order_by(EventNotificationRecord.id).limit(20)))
    for candidate_id in ids:
        candidate=session.get(EventNotificationRecord,candidate_id)
        topic=session.get(TopicRecord,topic_id);session.refresh(topic)
        update_record=session.get(EventUpdateRecord,candidate.event_update_id)
        matched=session.scalar(select(TopicMatchRecord.id).join(ItemNormalizationRecord,ItemNormalizationRecord.id==TopicMatchRecord.normalized_item_id)
            .join(ItemRecord,ItemRecord.id==ItemNormalizationRecord.item_id).where(TopicMatchRecord.topic_id==topic_id,
                TopicMatchRecord.normalized_item_id==update_record.normalized_item_id,TopicMatchRecord.config_fingerprint==match_fingerprint(topic),
                TopicMatchRecord.match_status=="matched",TopicMatchRecord.processing_status=="completed",ItemRecord.deleted_at.is_(None)))
        if not topic.enabled or matched is None:
            candidate.status="suppressed";candidate.error="主题停用、规则已变化或来源不可用，未发送。";session.commit();continue
        claimed=session.execute(update(EventNotificationRecord).where(EventNotificationRecord.id==candidate_id,
            EventNotificationRecord.status=="pending").values(status="sending")).rowcount
        session.commit()  # durable claim BEFORE native side effect; restart never resends sending/failed
        if not claimed:continue
        try:
            event=session.get(EventRecord,candidate.event_id)
            if hasattr(service,"send_event"):service.send_event(topic.name,event.canonical_title,update_record.update_type)
            else:service.send(topic.name,1)  # small Fake / existing service compatibility
        except Exception:
            candidate.status="failed";candidate.error="通知发送未确认，不自动重发以避免重复。"
            log.warning("Topic %s Event %s Notification failed",topic_id,candidate.event_id)
        else:
            candidate.status="sent";candidate.sent_at=datetime.now(timezone.utc);candidate.error=None;sent+=1
            log.info("Topic %s Event %s Notification sent",topic_id,candidate.event_id)
        session.commit()
    return sent
