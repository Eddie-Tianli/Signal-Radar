"""Reversible content deletion, independent of AI/source availability."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.items.models import ItemRecord
from app.items.schemas import Item
from app.digests.models import DigestRecord
from app.digests.schemas import DigestRead
from app.workflows.locks import topic_operation

router = APIRouter(prefix="/api", tags=["Recycle Bin"])
Kind = Literal["items", "digests"]
Database = Annotated[Session, Depends(get_session)]


class TrashItem(Item):
    deleted_at: datetime


class TrashDigest(DigestRead):
    deleted_at: datetime


class TrashContents(BaseModel):
    items: list[TrashItem]
    digests: list[TrashDigest]


def record_for(session, kind, record_id):
    model = ItemRecord if kind == "items" else DigestRecord
    record = session.get(model, record_id, populate_existing=True)
    if record is None:
        raise HTTPException(404, "内容不存在或已被永久删除。")
    return record


@router.get("/trash", response_model=TrashContents)
def contents(session: Database):
    return {"items": list(session.scalars(select(ItemRecord).where(ItemRecord.deleted_at.is_not(None))
                        .order_by(ItemRecord.deleted_at.desc(), ItemRecord.id.desc()))),
            "digests": list(session.scalars(select(DigestRecord).where(DigestRecord.deleted_at.is_not(None))
                          .order_by(DigestRecord.deleted_at.desc(), DigestRecord.id.desc())))}


@router.delete("/{kind}/{record_id}", status_code=204)
def move_to_trash(kind: Kind, record_id: int, session: Database):
    record = record_for(session, kind, record_id)
    with topic_operation(record.topic_id):
        record = record_for(session, kind, record_id)
        if record.deleted_at is None:
            record.deleted_at = datetime.now(timezone.utc)
            session.commit()
    return Response(status_code=204)


@router.post("/trash/{kind}/{record_id}/restore", status_code=204)
def restore(kind: Kind, record_id: int, session: Database):
    record = record_for(session, kind, record_id)
    with topic_operation(record.topic_id):
        record = record_for(session, kind, record_id)
        record.deleted_at = None
        session.commit()
    return Response(status_code=204)


@router.delete("/trash/{kind}/{record_id}", status_code=204)
def permanently_delete(kind: Kind, record_id: int, session: Database):
    record = record_for(session, kind, record_id)
    with topic_operation(record.topic_id):
        record = record_for(session, kind, record_id)
        if record.deleted_at is None:
            raise HTTPException(409, "请先将内容移入回收站，再执行永久删除。")
        session.delete(record)
        session.commit()
    return Response(status_code=204)
