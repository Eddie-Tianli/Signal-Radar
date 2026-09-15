from datetime import datetime, timedelta, timezone
import json
import httpx
import pytest
from sqlalchemy.orm import Session
from app.ai.provider import AIError
from app.ai.schemas import AnalysisResult
from app.ai.ollama import OllamaProvider, get_ai_provider
from app.digests.schemas import DigestResult
from app.digests.service import DigestService, NoRelevantItems
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from app.main import app
from test_items import engine
from test_scan import scan_client


class FakeAI:
    def __init__(self):
        self.inputs = []
        self.analyses = []
        self.fail = False
        self.relevant = True

    def analyze(self, data):
        self.analyses.append(data)
        return AnalysisResult(relevant=self.relevant, relevance_score=0.8, category="news", summary="Item summary.")

    def digest(self, data):
        self.inputs.append(data)
        if self.fail:
            raise AIError("Local model unavailable", 503)
        return DigestResult(title="Test Brief", summary="AI-generated content: key developments.")


def add_item(session, index, relevant=True, analyzed=True):
    time = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    item = ItemRecord(topic_id=1, source="test", external_id=str(index), title=f"Item {index}",
                      url="http://localhost/item", published_at=time, collected_at=time,
                      ai_relevant=relevant, ai_analyzed_at=time if analyzed else None,
                      ai_summary="AI summary", snippet="RAW SHOULD NOT BE SENT")
    session.add(item)
    session.flush()
    return item


def test_digest_selection_persistence_history(engine):
    provider = FakeAI()
    with Session(engine) as session:
        for index in range(23):
            add_item(session, index)
        add_item(session, 24, relevant=False)
        add_item(session, 25, analyzed=False)
        fallback = add_item(session, 26)
        fallback.published_at = None
        session.commit()
        service = DigestService(session, provider)
        first = service.generate(1)
        second = service.generate(1)
        assert first.topic_id == 1 and first.item_count == 20
        assert len(session.get(TopicRecord, 1).digests) == 2
        assert [row.id for row in service.history(1)] == [second.id, first.id]
        selected = provider.inputs[0].items
        assert selected[0].title == "Item 26"
        assert selected[-1].title == "Item 4"
        assert all(item.title not in ("Item 24", "Item 25") for item in selected)
        assert "snippet" not in provider.inputs[0].model_dump_json()
    with Session(engine) as session:
        assert DigestService(session, provider).history(1)[0].summary == second.summary


def test_empty_missing_and_failure(engine):
    provider = FakeAI()
    with Session(engine) as session:
        service = DigestService(session, provider)
        with pytest.raises(NoRelevantItems):
            service.generate(1)
        with pytest.raises(LookupError):
            service.generate(999)
        assert provider.inputs == []
        add_item(session, 1)
        session.commit()
        provider.fail = True
        with pytest.raises(AIError):
            service.generate(1)
        assert service.history(1) == []


def test_digest_api(scan_client):
    client, _ = scan_client
    provider = FakeAI()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        topic = client.post("/api/topics", json={"name": "Example"}).json()["id"]
        path = f"/api/topics/{topic}"
        assert client.post(path + "/digest").status_code == 409
        assert provider.inputs == []
        assert client.post("/api/topics/999/digest").status_code == 404
        assert client.get("/api/topics/999/digests").status_code == 404
        client.post(path + "/scan").raise_for_status()
        client.post(path + "/analyze").raise_for_status()
        created = client.post(path + "/digest")
        assert created.status_code == 200
        assert client.get(path + "/digests").json() == [created.json()]
        provider.fail = True
        failed = client.post(path + "/digest")
        assert failed.status_code == 503 and failed.json()["detail"] == "Local model unavailable"
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_ollama_digest_schema(engine):
    def handler(request):
        body = json.loads(request.content)
        assert body["format"] == DigestResult.model_json_schema()
        assert "personal intelligence brief" in body["messages"][0]["content"]
        assert "snippet" not in body["messages"][1]["content"]
        return httpx.Response(200, json={"message": {"content": '{"title":"Brief","summary":"AI-generated test."}'}})
    with Session(engine) as session, httpx.Client(transport=httpx.MockTransport(handler)) as client:
        add_item(session, 1)
        session.commit()
        assert DigestService(session, OllamaProvider(client, "http://localhost:11434", "fake")).generate(1).title == "Brief"
