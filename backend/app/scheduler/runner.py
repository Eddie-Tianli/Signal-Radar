import logging
from contextlib import contextmanager
from threading import Event, Lock
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_engine
from app.topics.models import TopicRecord
from app.items.models import ItemRecord
from app.collection.provider import get_source
from app.collection.service import CollectionService
from app.ai.ollama import get_ai_provider
from app.ai.service import AnalysisService
from app.digests.service import DigestService
from app.notifications.service import notify_safely, get_notification_service

log = logging.getLogger("uvicorn.error")
job_lock = Lock()


@contextmanager
def resources():
    with Session(get_engine()) as session:
        with contextmanager(get_source)() as source, contextmanager(get_ai_provider)() as provider:
            yield session, source, provider


def run_cycle(resource_factory=resources, stop=None, notification_factory=get_notification_service):
    stop = stop or Event()
    if not job_lock.acquire(blocking=False):
        log.info("Scheduler job skipped: previous job still running")
        return False
    try:
        with resource_factory() as (session, _, _):
            ids = list(session.scalars(select(TopicRecord.id).where(TopicRecord.enabled.is_(True)).order_by(TopicRecord.id)))
        for topic_id in ids:
            if stop.is_set():
                break
            try:
                with resource_factory() as (session, source, provider):
                    topic = session.get(TopicRecord, topic_id)
                    if topic is None or not topic.enabled:
                        continue
                    topic_name = topic.name
                    log.info("Topic %s job started; scan started", topic_id)
                    scan = CollectionService(session, source).scan(topic_id)
                    log.info("Topic %s Scan completed Fetched %s Created %s", topic_id, scan.fetched, scan.created)
                    # Bounded backlog: only currently unanalyzed Items, never reanalyze successes.
                    pending = list(session.scalars(select(ItemRecord.id).where(
                        ItemRecord.topic_id == topic_id, ItemRecord.ai_analyzed_at.is_(None)
                    ).order_by(ItemRecord.id).limit(20)))
                    analyzed = relevant = 0
                    for item_id in pending:
                        if stop.is_set():
                            break
                        item = AnalysisService(session, provider).analyze(item_id)
                        analyzed += 1
                        relevant += int(item.ai_relevant)
                    log.info("Topic %s Analysis completed Analyzed %s Relevant %s", topic_id, analyzed, relevant)
                    if relevant and not stop.is_set():
                        digest = DigestService(session, provider).generate(topic_id)
                        log.info("Topic %s Digest created %s", topic_id, digest.id)
                        notify_safely(topic_id, topic_name, relevant, notification_factory)
                    else:
                        log.info("Topic %s Digest skipped", topic_id)
                    log.info("Topic %s job completed", topic_id)
            except Exception:
                # Do not log exception text: database drivers/upstreams may contain secrets.
                log.error("Topic %s job failed", topic_id)
        return True
    except Exception:
        log.error("Scheduler topic enumeration failed")
        return False
    finally:
        job_lock.release()
