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
    return service.analyze(item_id)


@router.post("/topics/{topic_id}/analyze", response_model=BatchResult)
def analyze_topic(topic_id: int, service: Service, limit: Annotated[int, Query(ge=1, le=10)] = 10):
    return service.analyze_topic(topic_id, limit)
