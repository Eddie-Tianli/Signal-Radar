"""Read-only overview using existing tables; no persisted statistics."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import get_session
from app.topics.models import TopicRecord
from app.items.models import ItemRecord
from app.digests.models import DigestRecord
from app.digests.schemas import DigestRead

router = APIRouter()


@router.get("/api/dashboard", tags=["Dashboard"])
def dashboard(session: Annotated[Session, Depends(get_session)]):
    try:
        topics = session.execute(select(func.count(TopicRecord.id),
            func.count(TopicRecord.id).filter(TopicRecord.enabled.is_(True)))).one()
        items = session.execute(select(func.count(ItemRecord.id),
            func.count(ItemRecord.id).filter(ItemRecord.ai_analyzed_at.is_not(None), ItemRecord.ai_relevant.is_(True)),
            func.count(ItemRecord.id).filter(ItemRecord.ai_analyzed_at.is_(None)))).one()
        recent = session.execute(select(ItemRecord, TopicRecord.name).join(TopicRecord)
            .order_by(ItemRecord.collected_at.desc(), ItemRecord.id.desc()).limit(5)).all()
        briefs = session.execute(select(DigestRecord, TopicRecord.name).join(TopicRecord)
            .order_by(DigestRecord.generated_at.desc(), DigestRecord.id.desc()).limit(5)).all()
        return {"total_topics": topics[0], "enabled_topics": topics[1], "total_items": items[0],
                "relevant_items": items[1], "unanalyzed_items": items[2],
                "recent_items": [{"id": item.id, "topic_id": item.topic_id, "topic_name": name,
                    "title": item.title, "source": item.source, "collected_at": item.collected_at} for item, name in recent],
                "recent_digests": [{**DigestRead.model_validate(digest).model_dump(), "topic_name": name} for digest, name in briefs]}
    except SQLAlchemyError:
        raise HTTPException(503, "Dashboard unavailable. Check the local database.") from None
