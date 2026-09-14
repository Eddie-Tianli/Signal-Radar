from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.items.models import ItemRecord
from app.items.schemas import Item, ItemCreate
from app.topics.models import TopicRecord
from app.items.service import ItemService
from app.collection.source import SourceAdapter
from app.items.schemas import NormalizedItem


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'items.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        connection.execute(text("INSERT INTO topics (name, enabled) VALUES ('Existing topic', true)"))
        command.upgrade(config, "head")
    try:
        yield engine
    finally:
        engine.dispose()


def item_data(**changes):
    return ItemCreate(**{
        "topic_id": 1, "source": "rss", "external_id": "entry-1",
        "title": "Example article", "url": "https://example.com/article", **changes,
    }).model_dump()


def test_create_item_and_topic_relationship(engine):
    with Session(engine) as session:
        record = ItemRecord(**item_data(
            author="Example author", snippet="Summary",
            published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        ))
        session.add(record)
        session.commit()
        item_id = record.id
    with Session(engine) as session:
        record = session.get(ItemRecord, item_id)
        assert record.topic.name == "Existing topic"
        result = Item.model_validate(record)
        assert result.topic_id == 1
        assert result.author == "Example author"
        assert result.snippet == "Summary"
        assert result.published_at.year == 2026
        assert result.collected_at is not None


def test_missing_topic_rejected_by_database(engine):
    with Session(engine) as session:
        session.add(ItemRecord(**item_data(topic_id=999)))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_source_external_id_unique_across_topics(engine):
    with Session(engine) as session:
        second = TopicRecord(name="Second topic")
        session.add(second)
        session.add(ItemRecord(**item_data()))
        session.commit()
        session.add(ItemRecord(**item_data(topic_id=second.id)))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(ItemRecord(**item_data(source="youtube")))
        session.add(ItemRecord(**item_data(external_id="entry-2")))
        session.commit()
        assert session.query(ItemRecord).count() == 3


def test_nullable_fields(engine):
    with Session(engine) as session:
        record = ItemRecord(**item_data())
        session.add(record)
        session.commit()
        result = Item.model_validate(record)
        assert result.author is None
        assert result.published_at is None
        assert result.snippet is None
        assert result.collected_at is not None


def test_topic_deletion_cascades(engine):
    with Session(engine) as session:
        session.add(ItemRecord(**item_data()))
        session.commit()
        session.delete(session.get(TopicRecord, 1))
        session.commit()
        assert session.query(ItemRecord).count() == 0


def test_migration_head_and_downgrade_preserve_topics(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert "items" in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT name FROM topics WHERE id=1")) == "Existing topic"
        config.attributes["connection"] = connection
        command.downgrade(config, "0001")
        assert "items" not in inspect(connection).get_table_names()
        assert "topics" in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert "items" in inspect(connection).get_table_names()


@pytest.mark.parametrize("field", ["source", "external_id", "title", "url"])
def test_required_strings_are_not_blank(field):
    with pytest.raises(ValidationError):
        item_data(**{field: "   "})


def test_published_at_requires_timezone():
    with pytest.raises(ValidationError):
        item_data(published_at="2026-09-01T12:00:00")


def test_service_create_query_and_relationship(engine):
    with Session(engine) as session:
        service = ItemService(session)
        first = service.create_item(ItemCreate(**item_data()))
        second = service.create_item(ItemCreate(**item_data(external_id="entry-2")))
        assert service.list_topic_items(1) == [first, second]
        assert service.list_topic_items(999) == []
        topic = session.get(TopicRecord, 1)
        assert [item.id for item in topic.items] == [first.id, second.id]
        assert topic.items[0].topic is topic


def test_service_duplicate_rollback_and_missing_topic(engine):
    with Session(engine) as session:
        service = ItemService(session)
        service.create_item(ItemCreate(**item_data()))
        with pytest.raises(IntegrityError):
            service.create_item(ItemCreate(**item_data()))
        assert len(service.list_topic_items(1)) == 1
        with pytest.raises(IntegrityError):
            service.create_item(ItemCreate(**item_data(topic_id=999, external_id="missing")))
        assert len(service.list_topic_items(1)) == 1


@pytest.mark.parametrize("field", ["title", "url"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_service_revalidates_required_fields(engine, field, value):
    with Session(engine) as session:
        data = ItemCreate(**item_data())
        setattr(data, field, value)
        with pytest.raises(ValidationError):
            ItemService(session).create_item(data)
        assert ItemService(session).list_topic_items(1) == []


class FakeSource(SourceAdapter):
    """Test-only deterministic adapter. No network requests."""

    def search(self, query: str) -> list[NormalizedItem]:
        return [NormalizedItem(
            source="test", external_id="fake-1", title=query,
            url="https://example.com/fake-1",
        )]


def test_fake_source_to_item_service(engine):
    with pytest.raises(TypeError):
        SourceAdapter()
    results = FakeSource().search("Example topic")
    assert isinstance(results[0], NormalizedItem)
    with Session(engine) as session:
        service = ItemService(session)
        created = service.create_item(ItemCreate(topic_id=1, **results[0].model_dump()))
        assert created.title == "Example topic"
        assert created.source == "test"
        assert service.list_topic_items(1) == [created]
