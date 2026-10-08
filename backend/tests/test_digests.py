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


def test_ollama_digest_chinese_brief_from_english_items(engine):
    result = {
        "title": "OpenAI API 更新进展",
        "summary": "有信息提到，OpenAI 发布了 API 更新。\n\n"
                   "主要进展是接口响应速度有所改善，具体效果尚待确认。\n\n"
                   "后续值得关注实际使用中的响应表现。",
    }
    def handler(request):
        body = json.loads(request.content)
        assert body["format"] == DigestResult.model_json_schema()
        instruction = body["messages"][0]["content"]
        assert "即使来源是英文也必须用中文" in instruction
        assert "不要解释任务、描述用户意图" in instruction
        assert "不加入外部事实" in instruction
        assert "合并重复信息" in instruction
        assert "ai_relevance_score、较新及重复出现" in instruction
        assert "有信息提到" in instruction and "部分来源称" in instruction
        for phrase in ("the user is interested in", "the user wants", "provided metadata",
                       "based on the provided", "根据提供的信息"):
            assert phrase in instruction.split("禁止出现", 1)[1]
        assert body["options"]["temperature"] == 0
        content = json.loads(body["messages"][1]["content"])
        assert set(content["items"][0]) == {
            "title", "source", "author", "published_at", "ai_category",
            "ai_relevance_score", "ai_summary",
        }
        assert content["items"][0]["ai_summary"] == "OpenAI announced an API update with reportedly faster responses."
        return httpx.Response(200, json={"message": {"content": json.dumps(result, ensure_ascii=False)}})
    with Session(engine) as session, httpx.Client(transport=httpx.MockTransport(handler)) as client:
        item = add_item(session, 1)
        item.title = "OpenAI API update"
        item.ai_summary = "OpenAI announced an API update with reportedly faster responses."
        item.ai_relevance_score = 0.9
        session.commit()
        digest = DigestService(session, OllamaProvider(client, "http://localhost:11434", "fake")).generate(1)
        assert digest.title == result["title"] and digest.summary == result["summary"]
        assert any("\u4e00" <= char <= "\u9fff" for char in digest.title)
        for phrase in ("the user wants", "the user is interested in", "provided metadata",
                       "based on the provided", "根据提供的信息"):
            assert phrase not in (digest.title + digest.summary).lower()
        assert DigestService(session, FakeAI()).history(1)[0].summary == result["summary"]


def test_only_irrelevant_or_unanalyzed_items_do_not_call_ollama(engine):
    def handler(request):
        pytest.fail("No eligible Items must not trigger an Ollama request")
    with Session(engine) as session, httpx.Client(transport=httpx.MockTransport(handler)) as client:
        add_item(session, 1, relevant=False)
        add_item(session, 2, analyzed=False)
        session.commit()
        service = DigestService(session, OllamaProvider(client, "http://localhost:11434", "fake"))
        with pytest.raises(NoRelevantItems, match="No analyzed relevant Items"):
            service.generate(1)
        assert service.history(1) == []
