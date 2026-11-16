from threading import Lock
from contextlib import contextmanager
from sqlalchemy import select,or_
from app.ai.provider import AIError
from app.briefs.models import BriefRecord,BriefVersionRecord,EventReadRecord
from app.briefs.schemas import BriefInput,BriefResult
from app.briefs.validation import validate_brief
from app.events.models import EventRecord,EventUpdateRecord,EventSourceRecord
from app.events.identity import digest,evidence_key

_guard=Lock()


class BriefBusy(Exception):pass


@contextmanager
def brief_operation():
    if not _guard.acquire(blocking=False):raise BriefBusy()
    try:yield
    finally:_guard.release()


def event_sources(session,event_id):
    rows=session.scalars(select(EventSourceRecord).where(EventSourceRecord.event_id==event_id).order_by(EventSourceRecord.id)).all()
    unique={}
    for row in rows:unique.setdefault(row.url_key,row.source_reference)
    return list(unique.values())


def brief_read(session,brief,version,current=True):
    event=session.get(EventRecord,brief.event_id)
    read=session.get(EventReadRecord,event.id)
    return {"is_read":bool(read and read.brief_version_id and read.brief_version_id>=version.id),"id":brief.id,"event_id":brief.event_id,"version_id":version.id,"version":version.version,
        "content_fingerprint":version.content_fingerprint,"title":version.title,"summary":version.summary,
        "facts":version.facts,"sources":version.sources,"current_sources":event_sources(session,event.id) if current else version.sources,
        "verification_status":version.verification_status,"generation_status":version.generation_status,
        "warnings":version.warnings,"model_name":version.model_name,"error":version.error,
        "published_at":brief.created_at.isoformat(),"updated_at":version.generated_at.isoformat(),
        "event_date":str(event.event_date) if event.event_date else None,"event_type":event.event_type,
        "entities":event.primary_entities,"last_update_id":version.last_update_id}


class BriefService:
    def __init__(self,session,provider=None):self.session,self.provider=session,provider

    def get(self,event_id):
        if self.session.get(EventRecord,event_id) is None:raise LookupError("事件不存在。")
        brief=self.session.scalar(select(BriefRecord).where(BriefRecord.event_id==event_id))
        if brief is None:return None
        version=self.session.scalar(select(BriefVersionRecord).where(BriefVersionRecord.brief_id==brief.id).order_by(BriefVersionRecord.version.desc()).limit(1))
        return brief_read(self.session,brief,version) if version else None

    def history(self,event_id):
        self.get(event_id)
        brief=self.session.scalar(select(BriefRecord).where(BriefRecord.event_id==event_id))
        if brief is None:return []
        return [brief_read(self.session,brief,row,False) for row in self.session.scalars(select(BriefVersionRecord).where(BriefVersionRecord.brief_id==brief.id).order_by(BriefVersionRecord.version.desc()))]

    def inputs(self,event):
        updates=self.session.scalars(select(EventUpdateRecord).where(EventUpdateRecord.event_id==event.id,
            or_(EventUpdateRecord.update_type.in_(["new_event","conflict"]),EventUpdateRecord.importance>=.8)).order_by(EventUpdateRecord.id)).all()
        facts=list({evidence_key(fact):fact for update in updates for fact in update.new_facts}.values())
        if not facts:facts=event.facts
        if len(facts)>20:facts=[*facts[:5],*facts[-15:]]
        fingerprint=digest({"schema":"brief-1","event":event.id,"updates":[row.id for row in updates],"facts":facts})
        return facts,fingerprint,max((row.id for row in updates),default=0)

    def ensure(self,event_id,force=False):
        with brief_operation():
            event=self.session.get(EventRecord,event_id)
            if event is None:raise LookupError("事件不存在。")
            facts,fingerprint,last_update=self.inputs(event)
            old=self.get(event_id)
            if old and old["content_fingerprint"]==fingerprint and old["generation_status"]!="processing" and not force:return old
            brief=self.session.scalar(select(BriefRecord).where(BriefRecord.event_id==event_id))
            if brief is None:
                brief=BriefRecord(event_id=event_id);self.session.add(brief);self.session.flush()
            sources=event_sources(self.session,event_id)
            if not sources or not facts:raise AIError("事件缺少可追溯资料，暂不能生成简讯。",409)
            row=BriefVersionRecord(brief_id=brief.id,version=(old["version"]+1 if old else 1),content_fingerprint=fingerprint,
                last_update_id=last_update,title=event.canonical_title,summary="",facts=facts,sources=sources,
                warnings=["仅基于已有标题、描述和规范化声称；未读取视频全文或独立核验。"],
                verification_status="conflicting" if any(f.get("status")=="conflicting" for f in facts) else "unverified",
                generation_status="processing",model_name=getattr(self.provider,"model",None))
            self.session.add(row);self.session.commit()
            data=BriefInput(event_id=event.id,title=event.canonical_title,entities=event.primary_entities,
                event_date=str(event.event_date) if event.event_date else None,facts=facts,
                sources=[{key:source.get(key) for key in ("item_id","source","author","published_at")} for source in sources[:20]])
            try:
                value=self.provider.brief_event(data)
                value=BriefResult.model_validate_json(value.model_dump_json()) if isinstance(value,BriefResult) else BriefResult.model_validate(value)
                validate_brief(value,data)
                row.title,row.summary,row.generation_status=value.title,value.summary,"completed"
            except Exception:
                # No half AI result is stored. Fallback is a plainly-labelled source-claim list.
                row.title=event.canonical_title
                row.summary="\n".join(("冲突声称：" if fact.get("status")=="conflicting" else "来源声称：")+fact["text"] for fact in facts)
                row.generation_status="fallback"
                row.error="AI 简讯未通过生成或校验，当前展示程序整理的来源声称，可手动重试。"
                row.warnings=[*row.warnings,"程序资料摘要，不是成功生成的 AI 简讯。"]
            self.session.commit()
            return brief_read(self.session,brief,row)
