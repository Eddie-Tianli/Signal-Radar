"""Opt-in checks against migrated local PostgreSQL; all inserted rows roll back."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.items.models import ItemRecord
from app.items.schemas import Item
from app.topics.models import TopicRecord
from app.items.schemas import ItemCreate
from app.items.service import ItemService
from app.collection.mock import MockSource
from app.collection.service import CollectionService
from app.ai.service import AnalysisService
from app.ai.schemas import AnalysisResult


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1 after migrating local PostgreSQL")
def test_postgresql_item_constraints_and_timezone():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                topic = TopicRecord(name="Item integration test")
                session.add(topic)
                session.flush()
                payload = dict(
                    topic_id=topic.id, source="test", external_id=str(uuid4()),
                    title="Integration test", url="https://example.com/item",
                )
                record = ItemRecord(**payload)
                session.add(record)
                session.flush()
                session.refresh(record)
                result = Item.model_validate(record)
                assert result.collected_at.utcoffset() is not None
                assert result.published_at is None
                assert result.author is None and result.snippet is None
                record.published_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
                session.flush()
                session.refresh(record)
                assert record.published_at == datetime(2026, 9, 1, tzinfo=timezone.utc)

                with pytest.raises(IntegrityError):
                    with session.begin_nested():
                        session.add(ItemRecord(**payload))
                        session.flush()

                missing = TopicRecord(name="Temporary missing-topic target")
                session.add(missing)
                session.flush()
                missing_id = missing.id
                session.delete(missing)
                session.flush()
                with pytest.raises(IntegrityError):
                    with session.begin_nested():
                        session.add(ItemRecord(**{**payload, "topic_id": missing_id, "external_id": str(uuid4())}))
                        session.flush()
                item_id = record.id
                session.delete(topic)
                session.flush()
                session.expunge_all()
                assert session.get(ItemRecord, item_id) is None
        finally:
            transaction.rollback()


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in local PostgreSQL check")
def test_postgresql_scan_insert_conflicts():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                topic = TopicRecord(name="Scan conflict integration test")
                session.add(topic)
                session.flush()
                data = ItemCreate(topic_id=topic.id, source="youtube", external_id=str(uuid4()),
                                  title="Test", url="https://example.com/test")
                service = ItemService(session)
                assert service.insert_if_new(data) is True
                assert service.insert_if_new(data) is False
                session.commit()
                assert len(service.list_recent_topic_items(topic.id)) == 1
        finally:
            transaction.rollback()
@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in local PostgreSQL check")
def test_postgresql_mock_scan():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                topic = TopicRecord(name=f"Mock integration {uuid4()}")
                session.add(topic)
                session.flush()
                service = CollectionService(session, MockSource())
                first = service.scan(topic.id)
                second = service.scan(topic.id)
                assert (first.source, first.fetched, first.created, first.duplicates) == ("mock", 3, 3, 0)
                assert (second.fetched, second.created, second.duplicates) == (3, 0, 3)
                assert len(ItemService(session).list_recent_topic_items(topic.id)) == 3
                class FakeAI:
                    def analyze(self, data):
                        return AnalysisResult(relevant=False, relevance_score=0.1,
                                              category="other", summary="Mock summary.")
                item_id = ItemService(session).list_recent_topic_items(topic.id)[0].id
                analyzed = AnalysisService(session, FakeAI()).analyze(item_id)
                assert analyzed.ai_relevant is False
                assert analyzed.ai_analyzed_at.utcoffset() is not None
                session.expire_all()
                assert session.get(ItemRecord, item_id).ai_summary == "Mock summary."
                with pytest.raises(IntegrityError):
                    with session.begin_nested():
                        session.get(ItemRecord, item_id).ai_relevance_score = 1.5
                        session.flush()
        finally:
            transaction.rollback()
