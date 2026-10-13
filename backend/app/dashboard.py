"""Read-only overview using existing tables; no persisted statistics."""
from collections import Counter
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_, or_, false
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import get_session
from app.topics.models import TopicRecord
from app.items.models import ItemRecord
from app.digests.models import DigestRecord
from app.digests.schemas import DigestRead
from app.topics.policy import analysis_fingerprint

router = APIRouter()


@router.get("/api/dashboard", tags=["Dashboard"])
def dashboard(session: Annotated[Session, Depends(get_session)]):
    try:
        topics = session.execute(select(func.count(TopicRecord.id),
            func.count(TopicRecord.id).filter(TopicRecord.enabled.is_(True)))).one()
        topic_records = list(session.scalars(select(TopicRecord)))
        current = or_(*(and_(ItemRecord.topic_id == topic.id, ItemRecord.analysis_fingerprint == analysis_fingerprint(topic)) for topic in topic_records)) if topic_records else false()
        fingerprints = {topic.id: analysis_fingerprint(topic) for topic in topic_records}
        analysis_counts = {topic.id: Counter() for topic in topic_records}
        for topic_id, status, fingerprint in session.execute(select(ItemRecord.topic_id, ItemRecord.analysis_status,
                ItemRecord.analysis_fingerprint).where(ItemRecord.deleted_at.is_(None))):
            analysis_counts[topic_id][status if status == "failed" or fingerprint == fingerprints[topic_id] else "pending"] += 1
        def analysis_state(topic_id):
            counts = analysis_counts[topic_id]
            return "failed" if counts["failed"] else "pending" if counts["pending"] else "review" if counts["review"] else "completed" if counts else "empty"
        pending = or_(ItemRecord.analysis_fingerprint.is_(None), ~current, ItemRecord.analysis_status.in_(["pending", "failed"]))
        items = session.execute(select(func.count(ItemRecord.id),
            func.count(ItemRecord.id).filter(current, ItemRecord.analysis_status == "valid"),
            func.count(ItemRecord.id).filter(pending)).where(ItemRecord.deleted_at.is_(None))).one()
        recent = session.execute(select(ItemRecord, TopicRecord.name).join(TopicRecord).where(ItemRecord.deleted_at.is_(None))
            .order_by(ItemRecord.collected_at.desc(), ItemRecord.id.desc()).limit(5)).all()
        briefs = session.execute(select(DigestRecord, TopicRecord.name).join(TopicRecord).where(DigestRecord.deleted_at.is_(None))
            .order_by(DigestRecord.generated_at.desc(), DigestRecord.id.desc()).limit(5)).all()
        topic_summaries = session.execute(select(TopicRecord.id, TopicRecord.name, TopicRecord.enabled,
            func.count(ItemRecord.id), func.max(ItemRecord.collected_at)).outerjoin(ItemRecord, and_(ItemRecord.topic_id == TopicRecord.id, ItemRecord.deleted_at.is_(None)))
            .group_by(TopicRecord.id, TopicRecord.name, TopicRecord.enabled).order_by(TopicRecord.id)).all()
        return {"topics": [{"id": row[0], "name": row[1], "enabled": row[2], "item_count": row[3], "last_collected_at": row[4], "analysis_counts": dict(analysis_counts[row[0]]), "analysis_state": analysis_state(row[0]), "last_analysis_at": session.scalar(select(func.max(ItemRecord.ai_analyzed_at)).where(ItemRecord.topic_id == row[0], ItemRecord.deleted_at.is_(None))), "last_queries": next(topic.last_queries for topic in topic_records if topic.id == row[0]), "last_scan_at": next(topic.last_scan_at for topic in topic_records if topic.id == row[0])} for row in topic_summaries],
                "analyzed_items": items[0] - items[2], "total_topics": topics[0], "enabled_topics": topics[1], "total_items": items[0],
                "relevant_items": items[1], "unanalyzed_items": items[2],
                "recent_items": [{"id": item.id, "topic_id": item.topic_id, "topic_name": name,
                    "title": item.title, "source": item.source, "collected_at": item.collected_at} for item, name in recent],
                "recent_digests": [{**DigestRead.model_validate(digest).model_dump(), "topic_name": name} for digest, name in briefs]}
    except SQLAlchemyError:
        raise HTTPException(503, "Dashboard unavailable. Check the local database.") from None
