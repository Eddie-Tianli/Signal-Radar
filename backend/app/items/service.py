from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.items.models import ItemRecord
from app.items.schemas import Item, ItemCreate
from app.events.identity import url_key


class ItemService:
    """Internal persistence operations; constraint failures raise IntegrityError."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_item(self, data: ItemCreate) -> Item:
        # Revalidate even if a caller constructed or modified a schema manually.
        validated = ItemCreate.model_validate(data.model_dump())
        if self.session.scalar(select(ItemRecord.id).where(or_(ItemRecord.url==validated.url,ItemRecord.canonical_url_hash==url_key(validated.url))).limit(1)) is not None:
            raise IntegrityError("Item URL already exists",{},ValueError("Duplicate Item URL"))
        record = ItemRecord(**validated.model_dump(), canonical_url_hash=url_key(validated.url))
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
            select(ItemRecord).where(ItemRecord.topic_id == topic_id, ItemRecord.deleted_at.is_(None)).order_by(ItemRecord.id)
        ).all()
        return [Item.model_validate(record) for record in records]

    def insert_if_new(self, data: ItemCreate) -> bool:
        """Insert atomically, skipping only identity conflicts. Caller commits."""
        if self.session.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        validated = ItemCreate.model_validate(data.model_dump())
        if self.session.scalar(select(ItemRecord.id).where(or_(ItemRecord.canonical_url_hash==url_key(validated.url), ItemRecord.url==validated.url)).limit(1)) is not None:
            return False
        statement = insert(ItemRecord).values(**validated.model_dump(), canonical_url_hash=url_key(validated.url)).on_conflict_do_nothing().returning(ItemRecord.id)
        return self.session.execute(statement).scalar_one_or_none() is not None

    def list_recent_topic_items(self, topic_id: int) -> list[Item]:
        records = self.session.scalars(select(ItemRecord).where(
            ItemRecord.topic_id == topic_id, ItemRecord.deleted_at.is_(None)
        ).order_by(ItemRecord.collected_at.desc(), ItemRecord.id.desc())).all()
        return [Item.model_validate(record) for record in records]
