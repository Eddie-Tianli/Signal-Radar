from sqlalchemy import select
from sqlalchemy.orm import Session
from app.digests.models import DigestRecord
from app.notifications.service import NotificationService, WindowsNotificationService, get_notification_service
from app.scheduler.runner import run_cycle
from test_items import engine
from test_digests import FakeAI
from test_scheduler import factory


class FakeNotification(NotificationService):
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
    def send(self, topic_name, relevant_count):
        self.calls.append((topic_name, relevant_count))
        if self.fail:
            raise RuntimeError("SECRET notification failure")


def test_new_relevance_and_digest_notify_once(engine):
    notifier = FakeNotification()
    resources = factory(engine, FakeAI())
    run_cycle(resources, notification_factory=lambda: notifier)
    assert notifier.calls == [("Existing topic", 3)]
    run_cycle(resources, notification_factory=lambda: notifier)
    assert len(notifier.calls) == 1


def test_no_relevant_no_notification(engine):
    provider = FakeAI()
    provider.relevant = False
    notifier = FakeNotification()
    run_cycle(factory(engine, provider), notification_factory=lambda: notifier)
    assert notifier.calls == []


def test_disabled_notifications_keep_pipeline(engine, monkeypatch):
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
    assert get_notification_service() is None
    assert run_cycle(factory(engine, FakeAI()))
    with Session(engine) as session:
        assert len(list(session.scalars(select(DigestRecord)))) == 1


def test_enabled_selects_windows_service_without_sending(monkeypatch):
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "true")
    assert isinstance(get_notification_service(), WindowsNotificationService)


def test_notification_failure_preserves_success(engine, caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    assert run_cycle(factory(engine, FakeAI()), notification_factory=lambda: FakeNotification(fail=True))
    with Session(engine) as session:
        assert len(list(session.scalars(select(DigestRecord)))) == 1
    assert "Notification failed" in caplog.text
    assert "job completed" in caplog.text and "job failed" not in caplog.text
    assert "SECRET" not in caplog.text


def test_failed_digest_does_not_notify(engine):
    provider = FakeAI()
    provider.fail = True
    notifier = FakeNotification()
    run_cycle(factory(engine, provider), notification_factory=lambda: notifier)
    assert notifier.calls == []
