from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.topics.models import TopicRecord, TopicRuleRecord
from app.topics.schemas import Topic, TopicWrite


class TopicService:
    """Topic operations using a request-scoped database session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_topics(self) -> list[Topic]:
        records = self.session.scalars(select(TopicRecord).order_by(TopicRecord.id)).all()
        return [Topic.model_validate(record) for record in records]

    def get_topic(self, topic_id: int) -> Topic | None:
        record = self.session.get(TopicRecord, topic_id)
        return Topic.model_validate(record) if record is not None else None

    def create_topic(self, data: TopicWrite) -> Topic:
        record = TopicRecord(**data.model_dump(exclude={"include_rules", "exclude_rules"}))
        self.replace_rules(record, data)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return Topic.model_validate(record)

    def update_topic(self, topic_id: int, data: TopicWrite) -> Topic | None:
        record = self.session.get(TopicRecord, topic_id)
        if record is None:
            return None
        self.replace_rules(record, data)
        for field, value in data.model_dump(exclude={"include_rules", "exclude_rules"}).items():
            if field == "relevance_threshold" and field not in data.model_fields_set:
                continue
            setattr(record, field, value)
        self.session.commit()
        self.session.refresh(record)
        return Topic.model_validate(record)

    def replace_rules(self, record, data):
        # Validate every referenced ID before changing the collection.
        for kind in ("include", "exclude"):
            values = getattr(data, kind + "_rules")
            if values is None:
                continue  # legacy PUT must not silently erase v0.2 rules
            existing = {rule.id: rule for rule in record.rules if rule.rule_type == kind}
            if any(value.id is not None and value.id not in existing for value in values):
                raise HTTPException(422, "规则不属于当前主题或类型，请刷新后重试。")
        for kind in ("include", "exclude"):
            values = getattr(data, kind + "_rules")
            if values is None:
                continue
            existing = {rule.id: rule for rule in record.rules if rule.rule_type == kind}
            kept = set()
            for value in values:
                if value.id is not None:
                    rule = existing[value.id]
                    rule.text, rule.enabled = value.text, value.enabled
                    kept.add(value.id)
                else:
                    record.rules.append(TopicRuleRecord(rule_type=kind, text=value.text, enabled=value.enabled))
            for id, rule in existing.items():
                if id not in kept:
                    record.rules.remove(rule)

    def delete_topic(self, topic_id: int) -> bool:
        record = self.session.get(TopicRecord, topic_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.commit()
        return True


def get_topic_service(session: Annotated[Session, Depends(get_session)]) -> TopicService:
    return TopicService(session)
