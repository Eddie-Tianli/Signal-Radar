from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.items.models import ItemRecord
from app.items.schemas import Item, ItemCreate


class ItemService:
    """Internal persistence operations; constraint failures raise IntegrityError."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_item(self, data: ItemCreate) -> Item:
        # Revalidate even if a caller constructed or modified a schema manually.
        validated = ItemCreate.model_validate(data.model_dump())
        record = ItemRecord(**validated.model_dump())
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(record)
        return Item.model_validate(record)

    def list_topic_items(self, topic_id: int) -> list[Item]:
        records = self.session.scalars(
            select(ItemRecord).where(ItemRecord.topic_id == topic_id).order_by(ItemRecord.id)
        ).all()
        return [Item.model_validate(record) for record in records]
