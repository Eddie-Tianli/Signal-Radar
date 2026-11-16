from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_session
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider, AIError
from app.items.models import ItemRecord
from app.normalization.service import NormalizationService
from app.normalization.schemas import NormalizationRead, NormalizationBatch
from app.workflows.locks import topic_operation

router = APIRouter(prefix="/api", tags=["Item Normalization"])
DB = Annotated[Session, Depends(get_session)]
Provider = Annotated[AIProvider, Depends(get_ai_provider)]


def execute(operation):
    try:
        return operation()
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except AIError as error:
        # Only sanitized service errors reach the client, never the model response.
        raise HTTPException(error.status_code, str(error)) from None


@router.get("/items/{item_id}/normalization", response_model=NormalizationRead | None)
def read_normalization(item_id: int, session: DB):
    return execute(lambda: NormalizationService(session).get(item_id))


@router.post("/items/{item_id}/normalize", response_model=NormalizationRead)
def normalize_item(item_id: int, session: DB, provider: Provider, force: bool = False):
    item = session.get(ItemRecord, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(404, "Item not found")
    with topic_operation(item.topic_id):
        return execute(lambda: NormalizationService(session, provider).normalize(item_id, force))


@router.post("/topics/{topic_id}/normalize", response_model=NormalizationBatch)
def normalize_topic(topic_id: int, session: DB, provider: Provider,
                    limit: Annotated[int, Query(ge=1, le=10)] = 3):
    with topic_operation(topic_id):
        return execute(lambda: NormalizationService(session, provider).normalize_topic(topic_id, limit))
