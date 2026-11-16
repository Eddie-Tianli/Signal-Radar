from sqlalchemy import select
from app.items.models import ItemRecord
from app.normalization.service import NormalizationService
from app.events.models import EventRecord,EventSourceRecord,EventUpdateRecord,EventDecisionRecord,TopicMatchRecord,EventTopicRecord,EventNotificationRecord
from app.events.matcher import match_fingerprint
from app.events.pipeline import decision_read,match_read
from app.topics.models import TopicRecord


def item_processing(session,item_id,topic_id=None):
    current=NormalizationService(session).get(item_id)
    if current is None or current.normalization_status!="completed":return None
    query=select(TopicMatchRecord).where(TopicMatchRecord.normalized_item_id==current.id)
    if topic_id is not None:query=query.where(TopicMatchRecord.topic_id==topic_id)
    rows=list(session.scalars(query.order_by(TopicMatchRecord.id)))
    matches=[row for row in rows if row.config_fingerprint==match_fingerprint(session.get(TopicRecord,row.topic_id))]
    decision=session.scalar(select(EventDecisionRecord).where(EventDecisionRecord.normalized_item_id==current.id))
    complete=bool(matches) and all(row.processing_status=="completed" and (row.match_status!="matched" or decision and decision.processing_status=="completed") for row in matches)
    return {"item_id":item_id,"normalized_item_id":current.id,"matches":[match_read(row) for row in matches],
        "decision":decision_read(decision),"complete":bool(complete),"stale_match_count":len(rows)-len(matches)}


def event_topics(session,event_id):
    rows=session.execute(select(TopicRecord,TopicMatchRecord).join(EventTopicRecord,EventTopicRecord.topic_id==TopicRecord.id)
        .join(TopicMatchRecord,TopicMatchRecord.id==EventTopicRecord.match_id).where(EventTopicRecord.event_id==event_id)).all()
    return list({topic.id:{"id":topic.id,"name":topic.name,"enabled":topic.enabled} for topic,match in rows
        if match.match_status=="matched" and match.processing_status=="completed" and match.config_fingerprint==match_fingerprint(topic)}.values())


def event_read(session,event,detail=False):
    sources=list(session.scalars(select(EventSourceRecord).where(EventSourceRecord.event_id==event.id).order_by(EventSourceRecord.id)))
    data={key:getattr(event,key) for key in ("id","canonical_title","event_type","event_date","summary","primary_entities","event_status","created_at","updated_at")}
    data.update({"source_count":len({source.url_key for source in sources}),"topics":event_topics(session,event.id)})
    if detail:
        data["facts"]=event.facts
        data["topic_matches"]=[{**match_read(match),"stale":match.config_fingerprint!=match_fingerprint(session.get(TopicRecord,match.topic_id))} for match in session.scalars(select(TopicMatchRecord).join(EventTopicRecord,EventTopicRecord.match_id==TopicMatchRecord.id).where(EventTopicRecord.event_id==event.id))]
        data["sources"]=[{"id":source.id,"normalized_item_id":source.normalized_item_id,"reference":source.source_reference,"claims":source.claims,"created_at":source.created_at} for source in sources]
        data["updates"]=[{key:getattr(row,key) for key in ("id","normalized_item_id","update_type","new_facts","source_reference","importance","created_at")} for row in session.scalars(select(EventUpdateRecord).where(EventUpdateRecord.event_id==event.id).order_by(EventUpdateRecord.id.desc()))]
        timeline=[{"at":event.created_at,"label":"事件首次记录（非事实核验时间）"}]
        timeline.extend({"at":source.created_at,"label":"新来源报道："+(source.source_reference.get("author") or source.source_reference["source"])} for source in sources)
        timeline.extend({"at":row["created_at"],"label":"冲突声称" if row["update_type"]=="conflict" else "重要新增声称" if row["importance"]>=.8 else "新增声称"} for row in data["updates"] if row["update_type"]!="new_event")
        data["timeline"]=sorted(timeline,key=lambda point:str(point["at"]))
        data["decisions"]=[decision_read(row) for row in session.scalars(select(EventDecisionRecord).where(EventDecisionRecord.event_id==event.id).order_by(EventDecisionRecord.id))]
        data["notifications"]=[{key:getattr(row,key) for key in ("id","topic_id","event_update_id","status","reason","error","sent_at")} for row in session.scalars(select(EventNotificationRecord).where(EventNotificationRecord.event_id==event.id).order_by(EventNotificationRecord.id))]
    return data
