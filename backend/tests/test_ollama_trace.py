import json
import logging

import httpx
import pytest

from app.ai import trace as trace_module
from app.ai.ollama import OllamaProvider
from app.ai.provider import AIError
from app.ai.schemas import AnalysisInput
from app.digests.schemas import DigestInput, DigestItem


BRIEF = {"title": "OpenAI GPT 最新进展", "summary": "OpenAI GPT 的 API 有新进展，相关效果仍值得关注。"}
ANALYSIS = {"relevance_reason": "主题相符", "exclusion_status": "not_excluded", "exclusion_reason": "", "relevant": True, "relevance_score": 0.9, "category": "news", "summary": "OpenAI 的 API 有新进展。"}


def digest_input(summary="PRIVATE_ITEM_SUMMARY"):
    return DigestInput(topic_name="OpenAI GPT", topic_description="PRIVATE_TOPIC_DESCRIPTION",
                       items=[DigestItem(title="OpenAI update", source="mock", author="作者",
                                         published_at=None, ai_category="news",
                                         ai_relevance_score=0.9, ai_summary=summary)])


def envelope(content, **extra):
    return {"model": "local-test", "message": {"role": "assistant", "content": content}, **extra}


@pytest.fixture
def trace_file(tmp_path, monkeypatch):
    path = tmp_path / "logs" / "ollama_trace.jsonl"
    monkeypatch.setattr(trace_module, "TRACE_PATH", path)
    monkeypatch.setenv("OLLAMA_TRACE_ENABLED", "true")
    return path


def records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_trace_off_even_with_debug_does_not_write_content(trace_file, monkeypatch, caplog):
    monkeypatch.setenv("OLLAMA_TRACE_ENABLED", "false")
    caplog.set_level(logging.DEBUG)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json=envelope("PRIVATE_INVALID_RESPONSE")
    ))) as client:
        with pytest.raises(AIError):
            OllamaProvider(client, "http://localhost:11434", "local-test").digest(digest_input())
    assert not trace_file.exists()
    assert not trace_file.parent.exists()
    assert all(value not in caplog.text for value in (
        "PRIVATE_ITEM_SUMMARY", "PRIVATE_TOPIC_DESCRIPTION", "PRIVATE_INVALID_RESPONSE"))


@pytest.mark.parametrize("stage", ["digest", "item_analyze"])
def test_trace_records_actual_http_request_and_full_response(trace_file, stage):
    sent = []
    output = BRIEF if stage == "digest" else ANALYSIS
    response_json = envelope(json.dumps(output, ensure_ascii=False), total_duration=100,
                             prompt_eval_count=200, eval_count=50, eval_duration=30, done=True)
    raw_body = json.dumps(response_json, ensure_ascii=False, indent=2)
    def handler(request):
        sent.append(request)
        assert request.extensions["timeout"]["read"] == 180
        return httpx.Response(200, text=raw_body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client, "http://localhost:11434", "local-test")
        if stage == "digest":
            provider.digest(digest_input("完整摘要" * 500 + "END_OF_SUMMARY"))
        else:
            provider.analyze(AnalysisInput(topic_name="OpenAI GPT", topic_description=None,
                                          title="API update", snippet="PRIVATE_RAW_SNIPPET", author=None, source="mock"))
    events = records(trace_file)
    request = next(row for row in events if row["event"] == "request")
    payload = json.loads(sent[0].content)
    assert request["payload"] == payload
    assert request["request_body"] == sent[0].content.decode("utf-8")
    assert request["messages"] == payload["messages"] == request["prompt"]
    assert request["system_message"] == [payload["messages"][0]["content"]]
    assert request["user_message"] == [payload["messages"][1]["content"]]
    assert request["format"] == payload["format"] and request["options"] == payload["options"]
    assert request["temperature"] == 0 and request["stream"] is False
    assert request["endpoint"] == "/api/chat" and request["model"] == "local-test"
    assert request["stage"] == stage and request["attempt"] == 1
    assert request["item_count"] == (1 if stage == "digest" else None)
    assert request["timestamp"] and request["request_id"] and request["call_id"]
    response = next(row for row in events if row["event"] == "response")
    assert response["raw_response"] == raw_body
    assert response["status_code"] == 200 and response["elapsed_ms"] >= 0
    details = next(row for row in events if row["event"] == "response_details")
    assert details["response_json"] == response_json
    assert details["content"] == response_json["message"]["content"]
    assert details["model"] == "local-test" and details["statistics"]["eval_count"] == 50
    assert all(row["request_id"] == request["request_id"] for row in events)
    assert events[-1]["event"] == "complete"


@pytest.mark.parametrize("raw_response,event", [
    ("not valid HTTP JSON", "response_structure_error"),
    (json.dumps({"message": {}}), "response_structure_error"),
    (json.dumps(envelope([])), "response_structure_error"),
    (json.dumps(envelope("")), "empty_content"),
    (json.dumps(envelope(None)), "empty_content"),
    (json.dumps(envelope("PRIVATE_INVALID_MODEL_JSON")), "json_parse_error"),
    (json.dumps(envelope('{"title":"缺少摘要"}')), "validation_error"),
    (json.dumps(envelope('{"title":123,"summary":"内容"}')), "validation_error"),
    (json.dumps(envelope('{"title":"其他主题","summary":"这是完全无关的中文故事。"}')), "business_validation_error"),
])
def test_errors_preserve_raw_response_and_identify_layer(trace_file, raw_response, event):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=raw_response))) as client:
        with pytest.raises(AIError) as error:
            OllamaProvider(client, "http://localhost:11434", "fake").digest(digest_input())
    assert str(error.value) == ("Ollama returned empty content. Check model output budget or try again." if event == "empty_content" else "Ollama returned invalid structured analysis. Retry or check model support.")
    events = records(trace_file)
    responses = [row for row in events if row["event"] == "response"]
    assert len(responses) == 2 and all(row["raw_response"] == raw_response for row in responses)
    failures = [row for row in events if row["event"] == event]
    assert failures
    assert events.index(responses[0]) < events.index(failures[0])
    assert events[-1]["event"] == "retry_failed"
    if event == "validation_error":
        assert failures[0]["error_type"] == "ValidationError"
        assert failures[0]["details"][0]["loc"] in (["summary"], ["title"])
        assert failures[0]["details"][0]["msg"]
        assert "input" not in failures[0]["details"][0]


def test_retry_has_distinct_request_ids_and_shared_call(trace_file):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=envelope("bad JSON" if len(calls) == 1 else json.dumps(BRIEF)))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert OllamaProvider(client, "http://localhost:11434", "fake").digest(digest_input()).title == BRIEF["title"]
    events = records(trace_file)
    requests = [row for row in events if row["event"] == "request"]
    assert len(requests) == 2
    first, second = requests
    assert first["request_id"] != second["request_id"]
    assert first["call_id"] == second["call_id"]
    assert second["parent_request_id"] == first["request_id"]
    assert [first["attempt"], second["attempt"]] == [1, 2]
    assert [row["payload"] for row in requests] == calls
    retry = next(row for row in events if row["event"] == "retry")
    assert retry["request_id"] == first["request_id"] and retry["next_attempt"] == 2
    assert retry["reason"] == "json_parse_error"
    assert events[-1]["event"] == "complete"


@pytest.mark.parametrize("exception,status", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_http_failure_is_traced(trace_file, exception, status):
    def handler(request):
        raise exception("local service unavailable", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIError) as error:
            OllamaProvider(client, "http://localhost:11434", "fake").digest(digest_input())
    assert error.value.status_code == status
    events = records(trace_file)
    failure = next(row for row in events if row["event"] == "http_error")
    assert failure["error_type"] == exception.__name__
    assert failure["phase"] == "http_request" and failure["elapsed_ms"] >= 0
    assert not any(row["event"] in ("retry", "response") for row in events)


@pytest.mark.parametrize("status", [404, 500])
def test_server_error_body_preserved(trace_file, status):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        status, json={"error": "model failure"}
    ))) as client:
        with pytest.raises(AIError):
            OllamaProvider(client, "http://localhost:11434", "fake").digest(digest_input())
    events = records(trace_file)
    assert next(row for row in events if row["event"] == "response")["status_code"] == status
    assert next(row for row in events if row["event"] == "response_details")["response_json"] == {"error": "model failure"}
    assert events[-1]["event"] == "server_error"


def test_trace_redacts_credentials_without_changing_http_payload(trace_file, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "private-api-value")
    monkeypatch.setenv("DB_PASSWORD", 'private-db-"value')
    summary = 'private-api-value private-db-"value Authorization: Bearer private-header-value'
    def handler(request):
        assert request.headers["authorization"] == "Bearer private-header-value"
        assert "private-api-value" in request.content.decode()
        return httpx.Response(200, json=envelope(json.dumps(BRIEF),
                                               api_key="private-api-value", authorization="Bearer private-header-value",
                                               debug_echo=summary))
    with httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer private-header-value"}) as client:
        OllamaProvider(client, "http://localhost:11434", "fake").digest(digest_input(summary))
    logged = trace_file.read_text(encoding="utf-8")
    assert all(secret not in logged for secret in ("private-api-value", "private-db-", "private-header-value"))
    assert "[REDACTED]" in logged
    assert all("headers" not in row for row in records(trace_file))


def test_trace_appends_and_write_failure_does_not_fail_inference(trace_file, monkeypatch, tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=envelope(json.dumps(BRIEF))))) as client:
        provider = OllamaProvider(client, "http://localhost:11434", "fake")
        provider.digest(digest_input())
        first = trace_file.read_bytes()
        provider.digest(digest_input())
        assert trace_file.read_bytes().startswith(first)
        assert len({row["call_id"] for row in records(trace_file)}) == 2
        blocked_directory = tmp_path / "not-a-directory"
        blocked_directory.write_text("existing file", encoding="utf-8")
        monkeypatch.setattr(trace_module, "TRACE_PATH", blocked_directory / "ollama_trace.jsonl")
        assert provider.digest(digest_input()).model_dump() == BRIEF
