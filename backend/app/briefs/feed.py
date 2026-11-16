from datetime import datetime,timezone
from urllib.parse import urlsplit
from sqlalchemy import select,func,or_,and_
from sqlalchemy.orm import aliased
from app.briefs.service import BriefService
from app.briefs.models import EventReadRecord
from app.events.models import EventRecord,EventTopicRecord,TopicMatchRecord,EventSourceRecord,EventUpdateRecord
from app.events.matcher import match_fingerprint
from app.events.identity import digest
from app.normalization.models import ItemNormalizationRecord
from app.normalization.schemas import SCHEMA_VERSION
from app.items.models import ItemRecord
from app.topics.models import TopicRecord


def current_matches(session,event_id,topic_id=None):
    other=aliased(ItemNormalizationRecord)
    latest=select(func.max(other.id)).where(other.item_id==ItemRecord.id).correlate(ItemRecord).scalar_subquery()
    query=select(TopicRecord,TopicMatchRecord).join(TopicMatchRecord,TopicMatchRecord.topic_id==TopicRecord.id).join(EventTopicRecord,EventTopicRecord.match_id==TopicMatchRecord.id).join(ItemNormalizationRecord,ItemNormalizationRecord.id==TopicMatchRecord.normalized_item_id).join(ItemRecord,ItemRecord.id==ItemNormalizationRecord.item_id).where(
        EventTopicRecord.event_id==event_id,TopicRecord.enabled.is_(True),TopicMatchRecord.match_status=="matched",TopicMatchRecord.processing_status=="completed",
        ItemRecord.deleted_at.is_(None),ItemNormalizationRecord.id==latest,ItemNormalizationRecord.schema_version==SCHEMA_VERSION,ItemNormalizationRecord.normalization_status=="completed")
    if topic_id is not None:query=query.where(TopicRecord.id==topic_id)
    return [{"topic_id":topic.id,"name":topic.name,"score":match.relevance_score,"reason":match.match_reason,"matched_rules":match.matched_rules}
        for topic,match in session.execute(query) if match.config_fingerprint==match_fingerprint(topic) and match.relevance_score>=topic.relevance_threshold]


class FeedService:
    def __init__(self,session):self.session=session

    def cards(self,mode="focus",topic_id=None,sort="latest",limit=20):
        active=select(EventSourceRecord.event_id).join(ItemNormalizationRecord,ItemNormalizationRecord.id==EventSourceRecord.normalized_item_id).join(ItemRecord,ItemRecord.id==ItemNormalizationRecord.item_id).where(ItemRecord.deleted_at.is_(None))
        query=select(EventRecord).where(EventRecord.id.in_(active))
        if mode=="focus":
            topics=list(self.session.scalars(select(TopicRecord).where(TopicRecord.enabled.is_(True))))
            if topic_id is not None:topics=[t for t in topics if t.id==topic_id]
            if not topics:return []
            keys=or_(*(and_(TopicMatchRecord.topic_id==t.id,TopicMatchRecord.config_fingerprint==match_fingerprint(t),TopicMatchRecord.relevance_score>=t.relevance_threshold) for t in topics))
            matching=select(EventTopicRecord.event_id).join(TopicMatchRecord,TopicMatchRecord.id==EventTopicRecord.match_id).where(keys,TopicMatchRecord.match_status=="matched",TopicMatchRecord.processing_status=="completed")
            query=query.where(EventRecord.id.in_(matching))
        events=self.session.scalars(query.order_by(EventRecord.updated_at.desc(),EventRecord.id.desc()).limit(200)).all()
        cards=[];now=datetime.now(timezone.utc)
        for event in events:
            matches=current_matches(self.session,event.id,topic_id if mode=="focus" else None)
            if mode=="focus" and not matches:continue
            brief=BriefService(self.session).get(event.id)
            if not brief or brief["generation_status"]=="processing":continue
            sources=brief["current_sources"]
            raw=self.session.scalars(select(ItemRecord).join(ItemNormalizationRecord,ItemNormalizationRecord.item_id==ItemRecord.id).join(EventSourceRecord,EventSourceRecord.normalized_item_id==ItemNormalizationRecord.id).where(EventSourceRecord.event_id==event.id,ItemRecord.deleted_at.is_(None))).all()
            heat=[item.popularity_score for item in raw if item.source=="youtube" and item.popularity_score is not None and item.popularity_metrics and item.popularity_metrics.get("viewCount") is not None]
            read=self.session.get(EventReadRecord,event.id)
            update=self.session.scalar(select(EventUpdateRecord).where(EventUpdateRecord.event_id==event.id).order_by(EventUpdateRecord.id.desc()).limit(1))
            stamp=event.updated_at.replace(tzinfo=timezone.utc) if event.updated_at.tzinfo is None else event.updated_at
            channel=(sources[0].get("author") or urlsplit(sources[0].get("url","")).hostname or "unknown").casefold()
            cards.append({**brief,"topics":list({m["topic_id"]:m for m in matches}.values()),"relevance_score":max((m["score"] for m in matches),default=None),
                "popularity_score":max(heat) if heat else None,"event_status":event.event_status,
                "is_read":bool(read and read.brief_version_id and read.brief_version_id>=brief["version_id"]),
                "importance":update.importance if update else 0,"has_update":bool(update and update.update_type!="new_event"),
                "_age":max(0,(now-stamp).total_seconds()/86400),"_channel":channel})
        if mode=="discover":
            chosen=[];channels={};covered=set();seed=now.date().isoformat()
            while cards and len(chosen)<limit:
                def exploration(card):
                    diversity={str(m["topic_id"]) for m in card["topics"]} or {card["event_type"]}
                    jitter=int(digest([seed,card["event_id"]])[:8],16)/0xffffffff*.08
                    return 1/(1+card["_age"])+.2*len(diversity-covered)-.8*card["is_read"]-.2*channels.get(card["_channel"],0)+jitter
                allowed=[card for card in cards if channels.get(card["_channel"],0)<2]
                if not allowed:break
                best=max(allowed,key=exploration);cards.remove(best);chosen.append(best)
                channels[best["_channel"]]=channels.get(best["_channel"],0)+1
                covered.update({str(m["topic_id"]) for m in best["topics"]} or {best["event_type"]})
            cards=chosen
        else:
            if sort=="relevance":cards.sort(key=lambda c:(c["relevance_score"] or 0,-c["_age"]),reverse=True)
            elif sort=="popularity":cards.sort(key=lambda c:(c["popularity_score"] is not None,c["popularity_score"] or 0),reverse=True)
            elif sort=="updated":cards.sort(key=lambda c:(c["has_update"],-c["_age"]),reverse=True)
            cards=cards[:limit]
        return [{key:value for key,value in card.items() if not key.startswith("_")} for card in cards]
