from contextlib import contextmanager
from fastapi.testclient import TestClient
from app.main import app
from app.health import dependency_status


def test_status_backward_compatible_and_sanitized(monkeypatch):
    monkeypatch.setattr("app.main.dependency_status", lambda: {"database": "connected", "ollama": "unavailable"})
    with TestClient(app) as client:
        result = client.get("/api/status").json()
        assert result == dict(name="SignalRadar API", version="0.0.1", status="running",
                             database="connected", ollama="unavailable", scheduler="disabled", notifications="disabled")
        assert client.get("/").json() == {key: result[key] for key in ("name", "version", "status")}


def test_unavailable_dependencies_are_sanitized(monkeypatch):
    def fail():
        raise RuntimeError("SECRET database URL")
    monkeypatch.setattr("app.health.get_engine", fail)
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://external.example")
    assert dependency_status() == {"database": "unavailable", "ollama": "unavailable"}


def test_ollama_offline_does_not_block_preflight(monkeypatch):
    from app import local_runtime
    monkeypatch.setattr(local_runtime, "dependency_status", lambda: {"database": "connected", "ollama": "unavailable"})
    class Connection:
        def scalar(self, statement):
            return "0004"
    class Engine:
        @contextmanager
        def connect(self):
            yield Connection()
    class Socket:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def bind(self, address):
            pass
    monkeypatch.setattr(local_runtime, "get_engine", Engine)
    monkeypatch.setattr(local_runtime.socket, "socket", Socket)
    assert local_runtime.preflight()
