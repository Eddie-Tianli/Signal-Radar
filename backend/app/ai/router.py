from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.ollama import get_ai_provider
from app.ai.provider import AIError, AIProvider
from app.ai.schemas import BatchResult
from app.ai.service import AnalysisService
from app.database import get_session
from app.items.schemas import Item
from app.items.models import ItemRecord
from app.workflows.locks import topic_operation

router = APIRouter(prefix="/api", tags=["AI Analysis"])


def get_analysis_service(session: Annotated[Session, Depends(get_session)],
                         provider: Annotated[AIProvider, Depends(get_ai_provider)]):
    try:
        yield AnalysisService(session, provider)
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except AIError as error:
        session.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "Could not save or read analysis. Check the database.") from None


Service = Annotated[AnalysisService, Depends(get_analysis_service)]


@router.post("/items/{item_id}/analyze", response_model=Item)
def analyze_item(item_id: int, service: Service):
    item = service.session.get(ItemRecord, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(404, "Item not found")
    with topic_operation(item.topic_id):
        return service.analyze(item_id)


@router.post("/topics/{topic_id}/analyze", response_model=BatchResult)
def analyze_topic(topic_id: int, service: Service, limit: Annotated[int, Query(ge=1, le=10)] = 10):
    with topic_operation(topic_id):
        return service.analyze_topic(topic_id, limit)
