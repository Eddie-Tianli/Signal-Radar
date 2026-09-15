from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider, AIError
from app.database import get_session
from app.digests.service import DigestService, NoRelevantItems
from app.digests.schemas import DigestRead

router = APIRouter(prefix="/api/topics", tags=["Digests"])


def get_service(session: Annotated[Session, Depends(get_session)], provider: Annotated[AIProvider, Depends(get_ai_provider)]):
    try:
        yield DigestService(session, provider)
    except LookupError:
        raise HTTPException(404, "Topic not found") from None
    except NoRelevantItems as error:
        raise HTTPException(409, str(error)) from None
    except AIError as error:
        session.rollback()
        raise HTTPException(error.status_code, str(error)) from None
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "Could not read or save Digest. Check the database.") from None


@router.post("/{topic_id}/digest", response_model=DigestRead)
def generate(topic_id: int, service: Annotated[DigestService, Depends(get_service)]):
    return service.generate(topic_id)


@router.get("/{topic_id}/digests", response_model=list[DigestRead])
def history(topic_id: int, service: Annotated[DigestService, Depends(get_service)]):
    return service.history(topic_id)
