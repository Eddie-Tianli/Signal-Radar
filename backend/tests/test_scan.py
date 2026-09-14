from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.collection.youtube import YouTubeSource
from app.collection.provider import get_source
from app.database import get_session
from app.main import app
from test_youtube import video


@pytest.fixture
def scan_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scan.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    def sessions():
        with Session(engine) as session:
            yield session
    state = {"key": "test-key", "status": 200, "items": [video("one"), video("two")], "requests": []}
    def handler(request):
        state["requests"].append(request)
        return httpx.Response(state["status"], json={"items": state["items"]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as upstream:
        app.dependency_overrides[get_session] = sessions
        app.dependency_overrides[get_source] = lambda: YouTubeSource(upstream, state["key"])
        try:
            with TestClient(app) as client:
                yield client, state
        finally:
            app.dependency_overrides.pop(get_session, None)
            app.dependency_overrides.pop(get_source, None)
            engine.dispose()


def test_scan_create_repeat_counts_and_items(scan_client):
    client, state = scan_client
    topic = client.post("/api/topics", json={"name": "Nolan"}).json()
    url = f"/api/topics/{topic['id']}"
    assert client.get(url + "/items").json() == []
    first = client.post(url + "/scan")
    assert first.status_code == 200
    assert first.json() == {"topic_id": topic["id"], "source": "youtube", "fetched": 2, "created": 2, "duplicates": 0}
    assert state["requests"][0].url.params["q"] == "Nolan"
    second = client.post(url + "/scan")
    assert second.json() == {"topic_id": topic["id"], "source": "youtube", "fetched": 2, "created": 0, "duplicates": 2}
    items = client.get(url + "/items").json()
    assert len(items) == 2
    assert items[0]["id"] > items[1]["id"]
    assert items[0]["source"] == "youtube"
    assert items[0]["title"] == "Film & News"
    assert items[0]["author"] == "Channel"
    assert items[0]["collected_at"]
    assert items[0]["topic_id"] == topic["id"]


def test_missing_topic_before_network(scan_client):
    client, state = scan_client
    assert client.post("/api/topics/999/scan").status_code == 404
    assert client.get("/api/topics/999/items").status_code == 404
    assert state["requests"] == []


@pytest.mark.parametrize("key,status,expected", [("", 200, 503), ("test-key", 403, 502), ("test-key", 500, 502)])
def test_scan_errors(scan_client, key, status, expected):
    client, state = scan_client
    state.update(key=key, status=status)
    topic = client.post("/api/topics", json={"name": "Nolan"}).json()
    response = client.post(f"/api/topics/{topic['id']}/scan")
    assert response.status_code == expected
    assert response.json()["detail"]
    assert "test-key" not in response.text
    assert client.get(f"/api/topics/{topic['id']}/items").json() == []


def test_duplicate_in_response_and_across_topics(scan_client):
    client, state = scan_client
    state["items"] = [video("one"), video("one"), video("two")]
    first = client.post("/api/topics", json={"name": "First"}).json()["id"]
    second = client.post("/api/topics", json={"name": "Second"}).json()["id"]
    assert client.post(f"/api/topics/{first}/scan").json() == {
        "topic_id": first, "source": "youtube", "fetched": 3, "created": 2, "duplicates": 1,
    }
    assert client.post(f"/api/topics/{second}/scan").json()["duplicates"] == 3
    assert client.get(f"/api/topics/{second}/items").json() == []


def test_bad_response_does_not_partially_persist(scan_client):
    client, state = scan_client
    state["items"] = [video(), {}]
    topic = client.post("/api/topics", json={"name": "Nolan"}).json()["id"]
    assert client.post(f"/api/topics/{topic}/scan").status_code == 502
    assert client.get(f"/api/topics/{topic}/items").json() == []
