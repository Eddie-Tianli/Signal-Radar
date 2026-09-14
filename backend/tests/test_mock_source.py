import socket

import pytest

from app.collection.mock import MockSource
from app.collection.provider import get_source
from app.collection.youtube import YouTubeSource
from app.items.schemas import NormalizedItem
from app.main import app
from test_scan import scan_client


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if address[0] not in ("127.0.0.1", "::1"):
            raise AssertionError("External network access is forbidden")
        return connect(sock, address)
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in MockSource tests")
    monkeypatch.setattr(socket.socket, "connect", local_only)
    monkeypatch.setattr(YouTubeSource, "search", blocked)


def test_normalized_deterministic_content():
    source = MockSource()
    items = source.search("Christopher Nolan")
    assert len(items) == 3
    assert all(isinstance(item, NormalizedItem) and item.source == "mock" for item in items)
    assert all(item.author and item.snippet and item.published_at for item in items)
    assert items == source.search("Christopher Nolan")
    assert items[0].external_id != source.search("Other Topic")[0].external_id


@pytest.mark.parametrize("setting", ["false", None])
def test_real_source_remains_default(monkeypatch, setting):
    monkeypatch.setattr("app.collection.provider.load_dotenv", lambda *a: None)
    if setting is None:
        monkeypatch.delenv("USE_MOCK_SOURCE", raising=False)
    else:
        monkeypatch.setenv("USE_MOCK_SOURCE", setting)
    provider = get_source()
    try:
        assert isinstance(next(provider), YouTubeSource)
    finally:
        provider.close()


def test_mock_scan_api_counts_and_reads(scan_client, monkeypatch):
    client, state = scan_client
    monkeypatch.setenv("USE_MOCK_SOURCE", "true")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    app.dependency_overrides.pop(get_source)
    topic = client.post("/api/topics", json={"name": "Christopher Nolan"}).json()["id"]
    url = f"/api/topics/{topic}"
    assert client.post(url + "/scan").json() == dict(
        topic_id=topic, source="mock", fetched=3, created=3, duplicates=0)
    assert client.post(url + "/scan").json() == dict(
        topic_id=topic, source="mock", fetched=3, created=0, duplicates=3)
    items = client.get(url + "/items").json()
    assert len(items) == 3
    assert all(item["source"] == "mock" and item["topic_id"] == topic for item in items)
    assert client.post("/api/topics/999999/scan").status_code == 404
    assert state["requests"] == []
