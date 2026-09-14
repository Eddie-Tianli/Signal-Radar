from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.collection.service import CollectionService, ScanResult
from app.collection.youtube import SourceError, YouTubeSource, get_youtube_source
from app.database import get_session
from app.items.schemas import Item
from app.items.service import ItemService
from app.topics.models import TopicRecord

router = APIRouter(prefix="/api/topics", tags=["Collection"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("/{topic_id}/scan", response_model=ScanResult)
def scan_topic(topic_id: int, session: DatabaseSession,
               source: Annotated[YouTubeSource, Depends(get_youtube_source)]) -> ScanResult:
    try:
        return CollectionService(session, source).scan(topic_id)
    except LookupError:
        raise HTTPException(404, "Topic not found") from None
    except SourceError as error:
        raise HTTPException(error.status_code, str(error)) from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "Could not save scan results. Check the database and retry.") from None


@router.get("/{topic_id}/items", response_model=list[Item])
def topic_items(topic_id: int, session: DatabaseSession) -> list[Item]:
    try:
        if session.get(TopicRecord, topic_id) is None:
            raise HTTPException(404, "Topic not found")
        return ItemService(session).list_recent_topic_items(topic_id)
    except SQLAlchemyError:
        raise HTTPException(503, "Could not read items. Check the database and retry.") from None
