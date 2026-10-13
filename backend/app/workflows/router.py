from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider
from app.collection.provider import get_source
from app.collection.source import SourceAdapter
from app.database import get_session
from app.topics.models import TopicRecord
from app.workflows.locks import claim_topic, release_topic
from app.workflows.service import TopicUpdateService

router = APIRouter(prefix="/api/topics", tags=["Updates"])


@router.post("/{topic_id}/update")
def update_topic(topic_id: int, session: Annotated[Session, Depends(get_session)],
                 source: Annotated[SourceAdapter, Depends(get_source)],
                 provider: Annotated[AIProvider, Depends(get_ai_provider)]):
    if session.get(TopicRecord, topic_id) is None:
        raise HTTPException(404, "Topic not found")
    token = claim_topic(topic_id)
    def events():
        try:
            for progress in TopicUpdateService(session, source, provider).run(topic_id):
                yield progress.model_dump_json() + "\n"
        finally:
            release_topic(topic_id, token)
    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
                             background=BackgroundTask(release_topic, topic_id, token))
