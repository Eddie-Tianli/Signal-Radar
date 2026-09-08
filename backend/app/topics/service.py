from threading import Lock

from app.topics.schemas import Topic, TopicWrite


class TopicService:
    """Process-local storage; restarting the server discards all topics."""

    def __init__(self) -> None:
        self._topics: dict[int, Topic] = {}
        self._next_id = 1
        self._lock = Lock()

    def list_topics(self) -> list[Topic]:
        with self._lock:
            return list(self._topics.values())

    def get_topic(self, topic_id: int) -> Topic | None:
        with self._lock:
            return self._topics.get(topic_id)

    def create_topic(self, data: TopicWrite) -> Topic:
        with self._lock:
            topic = Topic(id=self._next_id, **data.model_dump())
            self._topics[topic.id] = topic
            self._next_id += 1
            return topic

    def update_topic(self, topic_id: int, data: TopicWrite) -> Topic | None:
        with self._lock:
            if topic_id not in self._topics:
                return None
            topic = Topic(id=topic_id, **data.model_dump())
            self._topics[topic_id] = topic
            return topic

    def delete_topic(self, topic_id: int) -> bool:
        with self._lock:
            return self._topics.pop(topic_id, None) is not None


_service = TopicService()


def get_topic_service() -> TopicService:
    return _service
