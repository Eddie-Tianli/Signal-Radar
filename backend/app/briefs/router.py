from typing import Annotated,Literal
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database import get_session
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider,AIError
from app.briefs.service import BriefService,BriefBusy
from app.briefs.feed import FeedService
from app.briefs.models import BriefRecord,BriefVersionRecord,EventReadRecord,ReadingRunRecord
from app.events.pipeline import event_operation,EventBusy
from app.events.models import TopicMatchRecord,EventRecord
from app.topics.models import TopicRecord

router=APIRouter(prefix="/api",tags=["Reading Workspace"])
DB=Annotated[Session,Depends(get_session)]
Provider=Annotated[AIProvider,Depends(get_ai_provider)]


def execute(operation):
    try:return operation()
    except LookupError as error:raise HTTPException(404,str(error)) from None
    except AIError as error:raise HTTPException(error.status_code,str(error)) from None
    except (BriefBusy,EventBusy):raise HTTPException(409,"简讯或事件正在处理，请稍后重试。") from None


@router.get("/events/{event_id}/brief")
def get_brief(event_id:int,session:DB):return execute(lambda:BriefService(session).get(event_id))


@router.post("/events/{event_id}/brief")
def generate_brief(event_id:int,session:DB,provider:Provider,force:bool=False):
    def operation():
        with event_operation():return BriefService(session,provider).ensure(event_id,force)
    return execute(operation)


@router.get("/events/{event_id}/brief-history")
def brief_history(event_id:int,session:DB):return execute(lambda:BriefService(session).history(event_id))


@router.get("/feed")
def feed(session:DB,mode:Literal["focus","discover"]="focus",topic_id:int|None=None,sort:Literal["latest","relevance","popularity","updated"]="latest",limit:Annotated[int,Query(ge=1,le=50)]=20):
    if topic_id is not None and session.get(TopicRecord,topic_id) is None:raise HTTPException(404,"Topic not found")
    if mode=="discover" and topic_id is not None:raise HTTPException(422,"开放发现不使用精准主题筛选。")
    return {"mode":mode,"cards":FeedService(session).cards(mode,topic_id,sort,limit),
        "scope":"仅当前已采集事件库；真实来源目前为 YouTube，Mock 为模拟数据。未进行全网搜索，也未读取完整视频。"}


@router.post("/briefs/{brief_id}/read")
def mark_read(brief_id:int,session:DB):
    brief=session.get(BriefRecord,brief_id)
    if brief is None:raise HTTPException(404,"简讯不存在。")
    version=session.scalar(select(BriefVersionRecord).where(BriefVersionRecord.brief_id==brief_id).order_by(BriefVersionRecord.version.desc()).limit(1))
    if version is None or version.generation_status=="processing":raise HTTPException(409,"简讯尚未完成。")
    row=session.get(EventReadRecord,brief.event_id)
    if row is None:row=EventReadRecord(event_id=brief.event_id);session.add(row)
    row.brief_version_id=version.id;row.read_at=datetime.now(timezone.utc);session.commit()
    return {"event_id":brief.event_id,"version_id":version.id,"is_read":True}


@router.get("/topics/{topic_id}/reading-status")
def reading_status(topic_id:int,session:DB):
    if session.get(TopicRecord,topic_id) is None:raise HTTPException(404,"Topic not found")
    row=session.scalar(select(ReadingRunRecord).where(ReadingRunRecord.topic_id==topic_id).order_by(ReadingRunRecord.id.desc()).limit(1))
    if row is None:return None
    from app.workflows.locks import topic_active
    return {key:getattr(row,key) for key in ("id","topic_id","status","stage","stats","error","report_id","started_at","finished_at")}|{"active":topic_active(topic_id)}


@router.get("/reading-overview")
def overview(session:DB):
    return {"recent_briefs":FeedService(session).cards("focus",limit=6),
        "discovery":FeedService(session).cards("discover",limit=4),
        "review_count":current_review_count(session),
        "event_count":session.scalar(select(func.count()).select_from(EventRecord)),
        "brief_count":session.scalar(select(func.count()).select_from(BriefRecord)),
        "scope":"当前本机已采集事件库，非全网覆盖。"}


def current_review_count(session):
    from app.normalization.models import ItemNormalizationRecord
    from app.items.models import ItemRecord
    from app.events.matcher import match_fingerprint
    latest=select(func.max(ItemNormalizationRecord.id)).group_by(ItemNormalizationRecord.item_id)
    rows=session.execute(select(TopicRecord,TopicMatchRecord).join(TopicMatchRecord,TopicMatchRecord.topic_id==TopicRecord.id)
        .join(ItemNormalizationRecord,ItemNormalizationRecord.id==TopicMatchRecord.normalized_item_id).join(ItemRecord,ItemRecord.id==ItemNormalizationRecord.item_id).where(
            TopicRecord.enabled.is_(True),TopicMatchRecord.match_status=="uncertain",ItemRecord.deleted_at.is_(None),ItemNormalizationRecord.id.in_(latest))).all()
    return sum(match.config_fingerprint==match_fingerprint(topic) for topic,match in rows)
