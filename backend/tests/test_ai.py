import json

import httpx
import pytest
from pydantic import ValidationError

from app.ai.ollama import OllamaProvider, get_ai_provider
from app.ai.provider import AIError, AIProvider
from app.ai.schemas import AnalysisInput, AnalysisResult
from app.collection.mock import MockSource
from app.collection.provider import get_source
from app.main import app
from test_scan import scan_client


RESULT = dict(relevant=True, relevance_score=0.87, category="news", summary="A short factual summary.")
INPUT = AnalysisInput(topic_name="Nolan", topic_description=None, title="Interview",
                      snippet="A director interview", author="Studio", source="mock")


def test_ollama_structured_output():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["format"] == AnalysisResult.model_json_schema()
        assert payload["options"]["temperature"] == 0
        assert payload["stream"] is False
        assert json.loads(payload["messages"][1]["content"]) == INPUT.model_dump()
        return httpx.Response(200, json={"message": {"content": json.dumps(RESULT)}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert OllamaProvider(client, "http://localhost:11434", "test-model").analyze(INPUT).model_dump() == RESULT


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf")])
def test_score_rejected(score):
    with pytest.raises(ValidationError):
        AnalysisResult(**{**RESULT, "relevance_score": score})


@pytest.mark.parametrize("score", [0, 1])
def test_score_boundaries(score):
    assert AnalysisResult(**{**RESULT, "relevance_score": score}).relevance_score == score


@pytest.mark.parametrize("status,body,expected", [
    (404, {}, 503), (500, {}, 502), (200, {"message": {"content": "not JSON"}}, 502),
    (200, {"message": {"content": json.dumps({**RESULT, "relevance_score": 2})}}, 502),
])
def test_ollama_bad_responses(status, body, expected):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as client:
        with pytest.raises(AIError) as error:
            OllamaProvider(client, "http://localhost:11434", "test").analyze(INPUT)
        assert error.value.status_code == expected


@pytest.mark.parametrize("failure,expected", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_ollama_connection_errors(failure, expected):
    def handler(request):
        raise failure("private upstream details")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIError) as error:
            OllamaProvider(client, "http://localhost:11434", "test").analyze(INPUT)
        assert error.value.status_code == expected
        assert "private" not in str(error.value)


@pytest.mark.parametrize("url,model", [("http://localhost:11434", ""), ("https://external.example", "test")])
def test_configuration_errors_without_network(url, model):
    def handler(request):
        pytest.fail("Configuration errors must not call HTTP")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIError, match="OLLAMA"):
            OllamaProvider(client, url, model).analyze(INPUT)


class FakeAI(AIProvider):
    def __init__(self):
        self.calls = []
        self.fail = False

    def analyze(self, data):
        self.calls.append(data)
        if self.fail:
            raise AIError("Local model unavailable", 503)
        return AnalysisResult(**RESULT)


@pytest.fixture
def ai_client(scan_client):
    client, _ = scan_client
    provider = FakeAI()
    app.dependency_overrides[get_source] = MockSource
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        topic = client.post("/api/topics", json={"name": "Nolan", "description": "Film news"}).json()["id"]
        client.post(f"/api/topics/{topic}/scan").raise_for_status()
        items = client.get(f"/api/topics/{topic}/items").json()
        yield client, provider, topic, items
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_analysis_persist_and_batch_only_unanalyzed(ai_client):
    client, provider, topic, items = ai_client
    response = client.post(f"/api/items/{items[0]['id']}/analyze")
    assert response.status_code == 200
    assert response.json()["ai_relevance_score"] == 0.87
    assert response.json()["ai_analyzed_at"]
    saved = client.get(f"/api/topics/{topic}/items").json()[0]
    assert saved["ai_summary"] == RESULT["summary"]
    assert provider.calls[0].topic_description == "Film news"
    batch = client.post(f"/api/topics/{topic}/analyze?limit=1").json()
    assert batch == dict(topic_id=topic, processed=1, relevant=1, irrelevant=0, failed=0)
    assert client.post(f"/api/topics/{topic}/analyze").json()["processed"] == 1
    assert client.post(f"/api/topics/{topic}/analyze").json()["processed"] == 0
    assert len(provider.calls) == 3
    assert client.post(f"/api/topics/{topic}/analyze?limit=11").status_code == 422


def test_missing_and_provider_failure(ai_client):
    client, provider, topic, items = ai_client
    assert client.post("/api/items/999999/analyze").status_code == 404
    assert client.post("/api/topics/999999/analyze").status_code == 404
    assert provider.calls == []
    provider.fail = True
    response = client.post(f"/api/items/{items[0]['id']}/analyze")
    assert response.status_code == 503
    assert response.json()["detail"] == "Local model unavailable"
    assert client.post(f"/api/topics/{topic}/analyze").json() == dict(
        topic_id=topic, processed=0, relevant=0, irrelevant=0, failed=3)
    assert all(item["ai_analyzed_at"] is None for item in client.get(f"/api/topics/{topic}/items").json())
