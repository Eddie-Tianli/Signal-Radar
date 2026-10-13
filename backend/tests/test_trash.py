from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from app.ai.ollama import get_ai_provider
from app.ai.service import AnalysisService
from app.digests.service import DigestService, NoRelevantItems
from app.items.service import ItemService
from app.items.models import ItemRecord
from app.digests.models import DigestRecord
from app.main import app
from app.workflows.locks import topic_operation
from test_items import engine
from test_scan import scan_client
from test_digests import FakeAI, add_item


@pytest.mark.parametrize("kind", ["items", "digests"])
def test_delete_restore_permanent_and_dashboard(scan_client, kind):
    client, _ = scan_client
    provider = FakeAI()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        topic = client.post("/api/topics", json={"name": "Example"}).json()["id"]
        base = f"/api/topics/{topic}"
        client.post(base + "/scan").raise_for_status()
        client.post(base + "/analyze").raise_for_status()
        digest = client.post(base + "/digest").json()
        rows = client.get(base + "/items").json() if kind == "items" else [digest]
        original = rows[0]
        path = f"/api/{kind}/{original['id']}"
        permanent = f"/api/trash/{kind}/{original['id']}"
        assert client.delete(permanent).status_code == 409
        with topic_operation(topic):
            assert client.delete(path).status_code == 409
        assert client.delete(path).status_code == 204
        assert client.delete(path).status_code == 204  # idempotent
        listed = client.get(base + ("/items" if kind == "items" else "/digests")).json()
        assert original["id"] not in [row["id"] for row in listed]
        overview = client.get("/api/dashboard").json()
        assert overview["total_items"] == (1 if kind == "items" else 2)
        assert len(overview["recent_digests"]) == (0 if kind == "digests" else 1)
        assert overview["topics"][0]["item_count"] == (1 if kind == "items" else 2)
        trash = client.get("/api/trash").json()[kind]
        assert trash[0]["deleted_at"]
        assert {k: v for k, v in trash[0].items() if k != "deleted_at"} == original
        if kind == "items":
            assert client.post(path + "/analyze").status_code == 404
            repeated = client.post(base + "/scan").json()
            assert repeated["created"] == 0 and repeated["duplicates"] == 2
        assert client.post(permanent + "/restore").status_code == 204
        assert client.get("/api/trash").json()[kind] == []
        restored = next(row for row in client.get(base + ("/items" if kind == "items" else "/digests")).json() if row["id"] == original["id"])
        # Rescanning may refresh real metrics timestamps, but never raw/AI content.
        assert {k: v for k, v in restored.items() if k not in ("popularity_score", "popularity_metrics")} == {k: v for k, v in original.items() if k not in ("popularity_score", "popularity_metrics")}
        client.delete(path).raise_for_status()
        assert client.delete(permanent).status_code == 204
        assert client.post(permanent + "/restore").status_code == 404
        assert client.delete(path).status_code == 404
        assert client.get("/api/trash").json()[kind] == []
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_trashed_items_excluded_from_all_processing_and_persist(engine):
    provider = FakeAI()
    with Session(engine) as session:
        item = add_item(session, 1)
        item.deleted_at = datetime.now(timezone.utc)
        pending = add_item(session, 2, analyzed=False)
        pending.deleted_at = datetime.now(timezone.utc)
        session.commit()
        ids = [item.id, pending.id]
    with Session(engine) as session:
        assert all(session.get(ItemRecord, id).deleted_at for id in ids)
        assert ItemService(session).list_topic_items(1) == []
        assert ItemService(session).list_recent_topic_items(1) == []
        assert AnalysisService(session, provider).analyze_topic(1, 10).processed == 0
        with pytest.raises(LookupError):
            AnalysisService(session, provider).analyze(ids[0])
        with pytest.raises(NoRelevantItems):
            DigestService(session, provider).generate(1)
        assert not DigestService(session, provider).needs_generation(1)
        assert not provider.inputs and not provider.analyses


def test_trashed_digest_remains_generation_watermark(engine):
    with Session(engine) as session:
        item = add_item(session, 1)
        session.commit()
        service = DigestService(session, FakeAI())
        result = service.generate(1)
        record = session.get(DigestRecord, result.id)
        record.deleted_at = datetime.now(timezone.utc)
        session.commit()
        assert service.history(1) == []
        assert not service.needs_generation(1)
        assert session.get(ItemRecord, item.id) is not None


def test_restore_and_permanent_delete_respect_topic_lock(scan_client):
    client, _ = scan_client
    topic = client.post("/api/topics", json={"name": "Example"}).json()["id"]
    client.post(f"/api/topics/{topic}/scan").raise_for_status()
    item = client.get(f"/api/topics/{topic}/items").json()[0]
    path = f"/api/trash/items/{item['id']}"
    client.delete(f"/api/items/{item['id']}").raise_for_status()
    with topic_operation(topic):
        assert client.post(path + "/restore").status_code == 409
        assert client.delete(path).status_code == 409
    assert len(client.get("/api/trash").json()["items"]) == 1


def test_update_skips_trashed_unanalyzed_items(scan_client):
    client, _ = scan_client
    provider = FakeAI()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        topic = client.post("/api/topics", json={"name": "Example"}).json()["id"]
        base = f"/api/topics/{topic}"
        client.post(base + "/scan").raise_for_status()
        for item in client.get(base + "/items").json():
            client.delete(f"/api/items/{item['id']}").raise_for_status()
        import json
        events = [json.loads(line) for line in client.post(base + "/update").text.splitlines()]
        assert events[-1]["status"] == "completed"
        assert events[-1]["processed"] == events[-1]["pending_remaining"] == 0
        assert events[-1]["digest"] is None
        assert not provider.analyses and not provider.inputs
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_0004_upgrade_preserves_content_and_matches_metadata(engine):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text, inspect
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0004")
        connection.execute(text("INSERT INTO items (topic_id, source, external_id, title, url, ai_summary) VALUES (1, 'test', 'old', 'Original', 'https://example.com', 'Saved AI summary')"))
        connection.execute(text("INSERT INTO digests (topic_id, title, summary, item_count) VALUES (1, 'Saved brief', 'Original brief', 1)"))
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
        assert connection.execute(text("SELECT title, ai_summary, deleted_at FROM items")).one() == ("Original", "Saved AI summary", None)
        assert connection.execute(text("SELECT summary, deleted_at FROM digests")).one() == ("Original brief", None)
        for table in ("items", "digests"):
            assert f"ix_{table}_deleted_at" in {index["name"] for index in inspect(connection).get_indexes(table)}
        command.check(config)
