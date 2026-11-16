from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_session
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider,AIError
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.events.models import EventRecord,EventTopicRecord,TopicMatchRecord
from app.events.matcher import match_fingerprint
from app.events.pipeline import EventPipeline,EventBusy
from app.events.read import item_processing,event_read
from app.workflows.locks import topic_operation

router=APIRouter(prefix="/api",tags=["Events"])
DB=Annotated[Session,Depends(get_session)]
Provider=Annotated[AIProvider,Depends(get_ai_provider)]


def execute(operation):
    try:return operation()
    except LookupError as error:raise HTTPException(404,str(error)) from None
    except AIError as error:raise HTTPException(error.status_code,str(error)) from None
    except EventBusy:raise HTTPException(409,"事件处理正在运行，请稍后重试。") from None


@router.post("/items/{item_id}/resolve")
def resolve_item(item_id:int,session:DB,provider:Provider,topic_id:int|None=None,retry:bool=False):
    item=session.get(ItemRecord,item_id)
    if item is None or item.deleted_at is not None:raise HTTPException(404,"Item not found")
    if topic_id is not None and session.get(TopicRecord,topic_id) is None:raise HTTPException(404,"Topic not found")
    return execute(lambda:EventPipeline(session,provider).process_item(item_id,[topic_id] if topic_id is not None else None,retry))


@router.post("/topics/{topic_id}/resolve")
def resolve_topic(topic_id:int,session:DB,provider:Provider,limit:Annotated[int,Query(ge=1,le=10)]=3):
    with topic_operation(topic_id):return execute(lambda:EventPipeline(session,provider).process_topic(topic_id,limit))


@router.get("/items/{item_id}/event-processing")
def read_processing(item_id:int,session:DB):
    return execute(lambda:item_processing(session,item_id))


@router.get("/events")
def list_events(session:DB,topic_id:int|None=None,limit:Annotated[int,Query(ge=1,le=100)]=50):
    query=select(EventRecord)
    if topic_id is not None:
        topic=session.get(TopicRecord,topic_id)
        if topic is None:raise HTTPException(404,"Topic not found")
        query=query.where(EventRecord.id.in_(select(EventTopicRecord.event_id).join(TopicMatchRecord,TopicMatchRecord.id==EventTopicRecord.match_id).where(
            EventTopicRecord.topic_id==topic_id,TopicMatchRecord.config_fingerprint==match_fingerprint(topic),TopicMatchRecord.match_status=="matched")))
    return [event_read(session,row) for row in session.scalars(query.order_by(EventRecord.updated_at.desc(),EventRecord.id.desc()).limit(limit))]


@router.get("/events/{event_id}")
def get_event(event_id:int,session:DB):
    event=session.get(EventRecord,event_id)
    if event is None:raise HTTPException(404,"事件不存在。")
    return event_read(session,event,True)
