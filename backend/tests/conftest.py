import pytest


@pytest.fixture(autouse=True)
def no_real_notifications(monkeypatch):
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must never display real Windows notifications")
    monkeypatch.setattr("app.notifications.service.WindowsNotificationService.send", forbidden)
