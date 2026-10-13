"""Single-process Topic exclusion shared by scheduled and manual writes."""
from contextlib import contextmanager
from threading import Lock
from uuid import uuid4


class TopicBusy(Exception):
    pass


_guard = Lock()
_active = {}


def claim_topic(topic_id):
    with _guard:
        if topic_id in _active:
            raise TopicBusy()
        token = uuid4().hex
        _active[topic_id] = token
        return token


def release_topic(topic_id, token):
    with _guard:
        if _active.get(topic_id) == token:
            del _active[topic_id]


@contextmanager
def topic_operation(topic_id):
    token = claim_topic(topic_id)
    try:
        yield
    finally:
        release_topic(topic_id, token)
