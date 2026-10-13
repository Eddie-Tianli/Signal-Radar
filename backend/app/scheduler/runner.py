import logging
from contextlib import contextmanager
from threading import Event, Lock
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_engine
from app.topics.models import TopicRecord
from app.collection.provider import get_source
from app.ai.ollama import get_ai_provider
from app.notifications.service import notify_safely, get_notification_service
from app.workflows.service import TopicUpdateService
from app.workflows.locks import topic_operation, TopicBusy

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
                    with topic_operation(topic_id):
                        result = None
                        for progress in TopicUpdateService(session, source, provider).run(topic_id, stop):
                            result = progress
                        log.info("Topic %s Scan completed Fetched %s Created %s", topic_id, result.fetched, result.created)
                        log.info("Topic %s Analysis completed Analyzed %s Relevant %s", topic_id, result.processed, result.relevant)
                        if result.digest is not None:
                            log.info("Topic %s Digest created %s", topic_id, result.digest.id)
                            if result.relevant:
                                notify_safely(topic_id, topic_name, result.relevant, notification_factory)
                        else:
                            log.info("Topic %s Digest skipped", topic_id)
                        if result.error:
                            log.error("Topic %s job failed", topic_id)
                            continue
                    log.info("Topic %s job completed", topic_id)
            except TopicBusy:
                log.info("Topic %s job skipped: operation already running", topic_id)
            except Exception:
                # Do not log exception text: database drivers/upstreams may contain secrets.
                log.error("Topic %s job failed", topic_id)
        return True
    except Exception:
        log.error("Scheduler topic enumeration failed")
        return False
    finally:
        job_lock.release()
