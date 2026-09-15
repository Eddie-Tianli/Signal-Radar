from contextlib import contextmanager
from threading import Event
import asyncio
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.collection.mock import MockSource
from app.digests.models import DigestRecord
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.scheduler.runner import run_cycle, job_lock
from app.scheduler.lifecycle import configured_scheduler, LocalScheduler
from app.scheduler.lifecycle import lifespan
from test_items import engine
from test_digests import FakeAI


def factory(engine, provider, source=None):
    @contextmanager
    def resources():
        with Session(engine) as session:
            yield session, source or MockSource(), provider
    return resources


def test_enabled_pipeline_and_no_change(engine):
    provider = FakeAI()
    with Session(engine) as session:
        session.add(TopicRecord(name="Disabled", enabled=False))
        session.commit()
    resources = factory(engine, provider)
    assert run_cycle(resources)
    assert len(provider.analyses) == 3 and len(provider.inputs) == 1
    assert run_cycle(resources)
    assert len(provider.analyses) == 3 and len(provider.inputs) == 1
    with Session(engine) as session:
        assert len(list(session.scalars(select(ItemRecord)))) == 3
        assert len(list(session.scalars(select(DigestRecord)))) == 1
        assert all(item.ai_analyzed_at for item in session.scalars(select(ItemRecord)))


def test_irrelevant_skips_digest(engine):
    provider = FakeAI()
    provider.relevant = False
    run_cycle(factory(engine, provider))
    assert len(provider.analyses) == 3
    assert provider.inputs == []


def test_topic_failure_isolated(engine, caplog):
    class Source(MockSource):
        def search(self, query):
            if query == "Existing topic":
                raise RuntimeError("SECRET")
            return super().search(query)
    with Session(engine) as session:
        session.add(TopicRecord(name="Second"))
        session.commit()
    provider = FakeAI()
    run_cycle(factory(engine, provider, Source()))
    assert len(provider.inputs) == 1
    assert "Topic 1 job failed" in caplog.text and "SECRET" not in caplog.text


def test_overlapping_job_skipped():
    def must_not_run():
        raise AssertionError("Overlapping job accessed resources")
    with job_lock:
        assert run_cycle(must_not_run) is False


def test_disabled_and_tests_never_start(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    assert configured_scheduler() is None
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    assert configured_scheduler() is None


def test_loop_wait_and_shutdown_without_thread():
    calls = []
    scheduler = LocalScheduler(60, job=lambda **kwargs: calls.append(kwargs))
    class FakeEvent:
        def wait(self, interval):
            assert interval == 60
            return len(calls) == 1
    scheduler.stop_event = FakeEvent()
    scheduler._loop()
    assert len(calls) == 1
    idle = LocalScheduler(60)
    idle.stop()
    assert idle.stop_event.is_set()


def test_stopped_cycle_does_not_process_topics(engine):
    provider = FakeAI()
    stop = Event()
    stop.set()
    run_cycle(factory(engine, provider), stop)
    assert provider.analyses == []


def test_lifespan_start_stop_without_background_thread(monkeypatch):
    calls = []
    class FakeScheduler:
        def start(self):
            calls.append("start")
        def stop(self):
            calls.append("stop")
    monkeypatch.setattr("app.scheduler.lifecycle.configured_scheduler", lambda: FakeScheduler())
    async def run():
        async with lifespan(None):
            assert calls == ["start"]
    asyncio.run(run())
    assert calls == ["start", "stop"]


def test_configured_interval_without_starting(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("app.scheduler.lifecycle.sys", SimpleNamespace(modules={}))
    monkeypatch.setattr("app.scheduler.lifecycle.load_dotenv", lambda *a: None)
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    assert configured_scheduler() is None
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCAN_INTERVAL_MINUTES", "2")
    scheduler = configured_scheduler()
    assert scheduler.interval == 120 and scheduler.thread is None
    monkeypatch.setenv("SCAN_INTERVAL_MINUTES", "nan")
    with pytest.raises(RuntimeError, match="SCAN_INTERVAL_MINUTES"):
        configured_scheduler()
