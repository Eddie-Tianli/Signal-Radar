import pytest


@pytest.fixture(autouse=True)
def disable_ollama_trace_by_default(monkeypatch):
    # Trace-specific tests opt in and redirect output to their isolated tmp_path.
    monkeypatch.setenv("OLLAMA_TRACE_ENABLED", "false")


@pytest.fixture(autouse=True)
def no_real_notifications(monkeypatch):
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must never display real Windows notifications")
    monkeypatch.setattr("app.notifications.service.WindowsNotificationService.send", forbidden)
