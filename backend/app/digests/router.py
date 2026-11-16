from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException,Query
from datetime import datetime
from pydantic import AwareDatetime
from typing import Literal
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider, AIError
from app.database import get_session
from app.digests.service import DigestService, NoRelevantItems
from app.digests.schemas import DigestRead
from app.briefs.reports import ReportService
from app.workflows.locks import topic_operation

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
def generate(topic_id: int, service: Annotated[DigestService, Depends(get_service)],since:AwareDatetime|None=None,until:AwareDatetime|None=None,event_status:Literal["active","developing","closed"]|None=None,force:bool=False):
    with topic_operation(topic_id):
        if since and until and since>until:raise HTTPException(422,"时间范围无效。")
        return ReportService(service.session,service.provider).generate(topic_id,since=since,until=until,event_status=event_status,force=force)


@router.get("/{topic_id}/digests", response_model=list[DigestRead])
def history(topic_id: int, service: Annotated[DigestService, Depends(get_service)]):
    return service.history(topic_id)
