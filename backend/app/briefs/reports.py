import os
from datetime import datetime,timezone
from sqlalchemy import select
from app.briefs.feed import FeedService
from app.briefs.models import DigestBriefRecord
from app.briefs.schemas import CompositionInput,CompositionResult
from app.briefs.validation import validate_composition
from app.digests.models import DigestRecord
from app.digests.schemas import DigestRead
from app.events.identity import digest
from app.events.matcher import match_fingerprint
from app.topics.models import TopicRecord


def max_events():
    try:value=int(os.getenv("DIGEST_MAX_EVENTS","10"))
    except ValueError:value=10
    return min(20,max(1,value))


class ReportService:
    def __init__(self,session,provider):self.session,self.provider=session,provider

    def generate(self,topic_id,stats=None,since=None,until=None,event_status=None,allow_empty=True,force=False):
        topic=self.session.get(TopicRecord,topic_id)
        if topic is None:raise LookupError("Topic not found")
        cards=FeedService(self.session).cards("focus",topic_id,"updated",100)
        covered=set(self.session.execute(select(DigestBriefRecord.event_id,DigestBriefRecord.coverage_fingerprint).join(DigestRecord,DigestRecord.id==DigestBriefRecord.digest_id).where(DigestRecord.topic_id==topic_id)).all())
        def in_range(card):
            stamp=datetime.fromisoformat(card["updated_at"])
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            return (since is None or stamp>=since) and (until is None or stamp<=until) and (event_status is None or card["event_status"]==event_status)
        eligible=[c for c in cards if in_range(c) and (force or (c["event_id"],c["content_fingerprint"]) not in covered)]
        selected=eligible[:max_events()]
        # Preserve complete Brief units; reduce count rather than cutting facts mid-sentence.
        def payload(rows):return CompositionInput(topic={"name":topic.name,"description":topic.description},briefs=[{"brief_id":c["id"],"event_id":c["event_id"],"title":c["title"],"summary":c["summary"],"entities":c["entities"],"verification_status":c["verification_status"]} for c in rows])
        while selected and len(payload(selected).model_dump_json().encode("utf-8"))>11000:selected.pop()
        oversized=bool(eligible and not selected)
        if oversized:selected=eligible[:max_events()]
        if not selected and not allow_empty:return None
        stats={"scan_performed":False,**(stats or {}),"selected_events":len(selected),"deferred_events":len(eligible)-len(selected)}
        kind="no_updates" if not selected else "brief_collection"
        error=None;model=None
        title=f"{topic.name}：暂无重要更新" if not selected else f"{topic.name}：事件简讯集合"
        summary="未发现尚未收录的重要有效事件进展；这不代表互联网没有相关新闻。" if not selected else "简讯集合（程序整理，非 AI 综合）\n\n"+"\n\n".join(f"【{c['title']}】\n{c['summary']}" for c in selected)
        collection_summary=summary
        if not oversized and len(selected)>=2 and all(c["generation_status"]=="completed" for c in selected):
            try:
                data=payload(selected);value=self.provider.compose_digest(data)
                value=CompositionResult.model_validate_json(value.model_dump_json()) if isinstance(value,CompositionResult) else CompositionResult.model_validate(value)
                validate_composition(value,data)
                title=value.title;kind="digest";model=getattr(self.provider,"model",None)
                summary="核心动态\n"+"\n".join(value.core_updates)+"\n\n主要事件\n"+"\n\n".join(f"[事件 #{next(c['event_id'] for c in selected if c['id']==part.brief_id)}] {part.text}" for part in value.events)
                if value.watch_points:summary+="\n\n值得关注\n"+"\n".join(value.watch_points)
            except Exception:
                kind="brief_collection";title=f"{topic.name}：事件简讯集合";summary=collection_summary;model=None
                error="AI 综合未完成或未通过校验，已保留可阅读的简讯集合。"
        elif oversized:error="输入超过 AI 预算，当前展示已有简讯集合。"
        elif selected and any(c["generation_status"]=="fallback" for c in selected):error="部分事件使用程序资料摘要，未调用 AI 综合。"
        fingerprint=digest({"pipeline":"reading-1","topic":match_fingerprint(topic),"briefs":[(c["event_id"],c["content_fingerprint"]) for c in selected],"run_id":stats.get("run_id"),"since":since,"until":until,"status":event_status})
        if not selected:
            cached=self.session.scalar(select(DigestRecord).where(DigestRecord.topic_id==topic_id,DigestRecord.input_fingerprint==fingerprint,DigestRecord.deleted_at.is_(None)).order_by(DigestRecord.id.desc()).limit(1))
            if cached:return DigestRead.model_validate(cached)
        sources=[]
        for card in selected:
            for source in card["current_sources"]:
                sources.append({"unit_id":f"E{card['event_id']}","item_id":source["item_id"],"title":source.get("headline",card["title"]),"source":source["source"],"url":source["url"],"author":source.get("author"),"published_at":source.get("published_at")})
        record=DigestRecord(topic_id=topic_id,title=title[:200],summary=summary,item_count=len({s["item_id"] for s in sources}),
            generated_at=datetime.now(timezone.utc),sources=sources,input_fingerprint=fingerprint,result_kind=kind,
            generation_status="completed" if kind=="digest" or kind=="no_updates" else "fallback",generation_error=error,model_name=model,run_stats=stats)
        self.session.add(record);self.session.flush()
        for card in selected:self.session.add(DigestBriefRecord(digest_id=record.id,brief_version_id=card["version_id"],event_id=card["event_id"],coverage_fingerprint=card["content_fingerprint"],snapshot=card))
        self.session.commit();self.session.refresh(record)
        return DigestRead.model_validate(record)
