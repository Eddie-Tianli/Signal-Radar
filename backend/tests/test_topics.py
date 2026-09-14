import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_session


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'topics.db'}", connect_args={"check_same_thread": False})
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    def test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()


def test_create_topic(client):
    response = client.post("/api/topics", json={"name": "Christopher Nolan"})
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Christopher Nolan",
        "description": None,
        "enabled": True,
    }


def test_get_topic(client):
    payload = {"name": "Nolan", "description": "Film news", "enabled": False}
    created = client.post("/api/topics", json=payload).json()
    response = client.get(f"/api/topics/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"id": created["id"], **payload}


def test_list_topics(client):
    empty = client.get("/api/topics")
    assert empty.status_code == 200
    assert empty.json() == []
    first = client.post("/api/topics", json={"name": "Nolan"}).json()
    second = client.post("/api/topics", json={"name": "Space"}).json()
    response = client.get("/api/topics")
    assert response.status_code == 200
    assert response.json() == [first, second]
    assert first["id"] != second["id"]


def test_update_topic(client):
    created = client.post("/api/topics", json={"name": "Nolan"}).json()
    payload = {"name": "Cinema", "description": "Film news", "enabled": False}
    response = client.put(f"/api/topics/{created['id']}", json=payload)
    expected = {"id": created["id"], **payload}
    assert response.status_code == 200
    assert response.json() == expected
    assert client.get(f"/api/topics/{created['id']}").json() == expected


def test_put_replaces_optional_fields(client):
    created = client.post(
        "/api/topics", json={"name": "Nolan", "description": "Old", "enabled": False}
    ).json()
    response = client.put(f"/api/topics/{created['id']}", json={"name": "Cinema"})
    assert response.status_code == 200
    assert response.json() == {
        "id": created["id"], "name": "Cinema", "description": None, "enabled": True
    }


def test_delete_topic_and_do_not_reuse_id(client):
    created = client.post("/api/topics", json={"name": "Nolan"}).json()
    response = client.delete(f"/api/topics/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/topics/{created['id']}").status_code == 404
    assert client.get("/api/topics").json() == []
    next_topic = client.post("/api/topics", json={"name": "Space"}).json()
    assert next_topic["id"] > created["id"]


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_missing_topic_returns_404(client, method):
    kwargs = {"json": {"name": "Missing"}} if method == "put" else {}
    response = client.request(method, "/api/topics/999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Topic not found"}
    assert client.get("/api/topics").json() == []


@pytest.mark.parametrize("name", ["", "   ", "\t\n", None])
def test_invalid_name_rejected_on_create_and_update(client, name):
    assert client.post("/api/topics", json={"name": name}).status_code == 422
    assert client.get("/api/topics").json() == []
    created = client.post("/api/topics", json={"name": "Original"}).json()
    response = client.put(f"/api/topics/{created['id']}", json={"name": name})
    assert response.status_code == 422
    assert client.get(f"/api/topics/{created['id']}").json() == created


def test_missing_name_rejected(client):
    assert client.post("/api/topics", json={}).status_code == 422
    created = client.post("/api/topics", json={"name": "Original"}).json()
    assert client.put(f"/api/topics/{created['id']}", json={}).status_code == 422


def test_trim_name_and_allow_empty_description(client):
    response = client.post("/api/topics", json={"name": "  Nolan  ", "description": ""})
    assert response.status_code == 201
    assert response.json()["name"] == "Nolan"
    assert response.json()["description"] == ""
