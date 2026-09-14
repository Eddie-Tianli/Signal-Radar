from pathlib import Path
from io import StringIO

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.topics.schemas import TopicWrite
from app.topics.service import TopicService


def test_postgresql_migration_sql(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "offline-generation-only")
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE topics" in sql
    assert "SERIAL" in sql
    assert "BOOLEAN DEFAULT true NOT NULL" in sql


def test_migration_and_persistence_across_engines(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    engine = create_engine(url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as session:
        created = TopicService(session).create_topic(TopicWrite(name="Persistent topic"))
    engine.dispose()

    engine = create_engine(url)
    try:
        with Session(engine) as session:
            assert TopicService(session).get_topic(created.id) == created
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert "topics" in inspect(connection).get_table_names()
            command.downgrade(config, "base")
            assert "topics" not in inspect(connection).get_table_names()
    finally:
        engine.dispose()
