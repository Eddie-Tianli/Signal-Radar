import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.ai.ollama import OllamaProvider, get_ai_provider
from app.ai.provider import AIError
from app.normalization.models import ItemNormalizationRecord
from app.normalization.preprocess import TextPreprocessor
from app.normalization.schemas import NormalizationResult, NormalizationInput
from app.normalization.service import NormalizationService
from app.normalization.validation import validate_normalization, NormalizationSemanticError
from app.items.models import ItemRecord
from app.topics.models import TopicRecord
from test_items import engine, item_data
from test_scan import scan_client


def payload(**changes):
    return {"headline":"星河公司发布模型更新", "summary":"星河公司称其模型增加中文摘要功能，具体效果尚待验证。", "entities":["星河公司"],
            "event_type":"model_update", "event_date":None, "keywords":["中文摘要","模型"],
            "claims":[{"text":"星河公司称模型新增中文摘要功能。","status":"reported"}], "warnings":[], **changes}


def result(**changes):
    return NormalizationResult.model_validate_json(json.dumps(payload(**changes)))


class Fake:
    model = "fake-local"
    def __init__(self): self.calls = []
    def normalize(self,data):
        self.calls.append(data)
        return result()


def raw(session):
    row = ItemRecord(**item_data(title="星河公司发布模型更新",snippet="<p>星河公司称模型增加中文摘要功能，具体效果尚待验证。</p>"))
    session.add(row); session.commit()
    return row


def input_data(**changes):
    return NormalizationInput(item_id=1,title="星河公司更新",text="星河公司声称发布模型更新。",source="youtube",author=None,
        published_at=datetime(2026,11,16,tzinfo=timezone.utc),url="https://youtube.com/watch?v=abc",
        content_coverage="metadata_only",text_truncated=False,source_metadata={},**changes)


def test_preprocessing_conservative_html_entities_unicode_and_metadata():
    value = TextPreprocessor().process("<b>Ａ公司 &amp; 更新</b>",
        "<h1>Ａ公司 &amp; 更新</h1><p>新模型&nbsp; 发布。</p><p>作者：某媒体</p><p>Copyright © 2026 Example</p><script>ignore previous</script><p>报道称版权诉讼仍在继续。</p>\n---\n", "web","编辑")
    assert value.title == "A公司 & 更新"
    assert value.body == "新模型 发布。\n报道称版权诉讼仍在继续。"
    assert value.metadata["copyright"] == ["Copyright © 2026 Example"]
    assert value.metadata["attributions"] == ["作者:某媒体"]
    assert value.matching_text.startswith("a公司")


def test_normalize_persist_raw_unchanged_topic_independent_idempotent(engine):
    provider = Fake()
    with Session(engine) as session:
        row = raw(session); before = (row.title,row.snippet,row.url,row.author)
        service = NormalizationService(session,provider)
        first = service.normalize(row.id)
        assert first.normalization_status == "completed"
        assert first.headline == payload()["headline"] and first.entities == ["星河公司"]
        assert first.event_date is None and first.keywords == ["中文摘要","模型"]
        assert first.claims[0].status == "reported" and first.source_reference.item_id == row.id
        assert first.source_reference.url == row.url and first.schema_version == "1"
        assert not hasattr(provider.calls[0],"topic_name")
        row.topic.description = "完全不同的主题需求"; session.commit()
        assert service.normalize(row.id).id == first.id and len(provider.calls)==1
        assert (row.title,row.snippet,row.url,row.author) == before
        item_id = row.id
        second = service.normalize(row.id,force=True)
        assert second.revision==2 and second.id!=first.id and len(provider.calls)==2
    with Session(engine) as session:
        assert NormalizationService(session).get(item_id).id==second.id
        assert len(list(session.scalars(select(ItemNormalizationRecord))))==2


def test_metadata_only_and_bounds(engine):
    provider=Fake()
    with Session(engine) as session:
        row=raw(session);row.source="youtube";row.snippet="资料"*3000;session.commit()
        saved=NormalizationService(session,provider).normalize(row.id)
        assert provider.calls[0].text_truncated and len(provider.calls[0].text)==3500
        assert saved.content_coverage=="metadata_only" and len(row.snippet)==6000
        assert any("未读取完整视频" in w for w in saved.warnings)
        assert any("截取" in w for w in saved.warnings)


def test_date_conflicts_and_published_not_event_evidence():
    data=input_data();data.text="2026年11月15日发布，但另称2026年11月16日。"
    normalized=validate_normalization(result(event_date="2026-11-15"),data)
    assert normalized.event_date is None and any("多个日期" in w for w in normalized.warnings)
    with pytest.raises(NormalizationSemanticError,match="date not supported"):
        validate_normalization(result(event_date="2026-11-16"),input_data())


@pytest.mark.parametrize("status",["officially_confirmed","verified","fact"])
def test_no_self_upgraded_verified_claims(status):
    with pytest.raises(ValidationError): result(claims=[{"text":"原因涉及私人关系。","status":status}])


@pytest.mark.parametrize("changes",[{"headline":"English headline"},{"summary":"Only English."},
    {"summary":"2027年星河公司推出模型。"},{"summary":"```python 星河公司```"},
    {"claims":[{"text":"详见 https://invented.example","status":"reported"}]}])
def test_invalid_semantic_output(changes):
    with pytest.raises(NormalizationSemanticError):validate_normalization(result(**changes),input_data())


@pytest.mark.parametrize("wrapper",[lambda s:s,lambda s:"```json\n"+s+"\n```",lambda s:"说明\n"+s+"\n结束"])
def test_ollama_json_and_trace(wrapper,tmp_path,monkeypatch):
    from app.ai import trace
    monkeypatch.setenv("OLLAMA_TRACE_ENABLED","true");monkeypatch.setattr(trace,"TRACE_PATH",tmp_path/"trace.jsonl")
    def handler(request):
        body=json.loads(request.content)
        assert body["stream"] is False and body["options"]["temperature"]==0
        assert body["format"]==NormalizationResult.model_json_schema()
        data=json.loads(body["messages"][1]["content"])
        assert data["item_id"]==1 and "topic_name" not in data
        assert "不代表核实" in body["messages"][0]["content"]
        return httpx.Response(200,json={"message":{"content":wrapper(json.dumps(payload()))}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert OllamaProvider(client,"http://localhost:11434","fake").normalize(input_data()).event_date is None
    events=[json.loads(line) for line in trace.TRACE_PATH.read_text(encoding="utf8").splitlines()]
    assert {"request","response","complete"} <= {event["event"] for event in events}
    assert all(event["stage"]=="item_normalization" for event in events)


@pytest.mark.parametrize("bad",["not JSON", "", json.dumps({"headline":"缺字段"}),json.dumps(payload(entities="not a list")),json.dumps(payload(claims=[{"text":"已核实","status":"officially_confirmed"}]))])
def test_parse_once_retry_and_twice_failure(bad,tmp_path,monkeypatch):
    from app.ai import trace
    monkeypatch.setenv("OLLAMA_TRACE_ENABLED","true");monkeypatch.setattr(trace,"TRACE_PATH",tmp_path/"trace.jsonl")
    for second_ok in (True,False):
        calls=[]
        def handler(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json={"message":{"content":json.dumps(payload()) if second_ok and len(calls)==2 else bad}})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            provider=OllamaProvider(client,"http://localhost:11434","fake")
            if second_ok:assert provider.normalize(input_data()).summary
            else:
                with pytest.raises(AIError): provider.normalize(input_data())
        assert len(calls)==2
        assert "只返回合法 JSON" in calls[1]["messages"][0]["content"]
    events=[json.loads(line) for line in trace.TRACE_PATH.read_text(encoding="utf8").splitlines()]
    retry=next(e for e in events if e["event"]=="retry")
    assert any(e["parent_request_id"]==retry["request_id"] for e in events)


@pytest.mark.parametrize("error_type,status",[(httpx.ConnectError,503),(httpx.ReadTimeout,504)])
def test_http_failures(error_type,status):
    def handler(request): raise error_type("private",request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIError) as error:OllamaProvider(client,"http://localhost:11434","fake").normalize(input_data())
    assert error.value.status_code==status and "private" not in str(error.value)


def test_fail_no_partial_result_then_retry(engine):
    class Broken(Fake):
        def normalize(self,data):raise AIError("raw secret output",503)
    with Session(engine) as session:
        row=raw(session); service=NormalizationService(session,Broken())
        with pytest.raises(AIError):service.normalize(row.id)
        failed=service.get(row.id)
        assert failed.normalization_status=="failed" and failed.summary is None and "secret" not in failed.error
        service.provider=Fake();assert service.normalize(row.id).id==failed.id
        assert row.snippet.startswith("<p>")


def test_api_get_post_batch_and_404(scan_client):
    from app.main import app
    client,_=scan_client;provider=Fake();app.dependency_overrides[get_ai_provider]=lambda:provider
    try:
        topic=client.post("/api/topics",json={"name":"测试"}).json()["id"]
        client.post(f"/api/topics/{topic}/scan").raise_for_status()
        row=client.get(f"/api/topics/{topic}/items").json()[0];base=f"/api/items/{row['id']}"
        assert client.get(base+"/normalization").json() is None
        one=client.post(base+"/normalize");assert one.status_code==200
        assert client.post(base+"/normalize").json()["id"]==one.json()["id"] and len(provider.calls)==1
        batch=client.post(f"/api/topics/{topic}/normalize?limit=1").json()
        assert batch["processed"]==1 and batch["reused"]==1
        assert client.get(base+"/normalization").json()["summary"]
        assert client.post("/api/items/999999/normalize").status_code==404
        assert client.get("/api/items/999999/normalization").status_code==404
        assert client.post("/api/topics/999999/normalize").status_code==404
        assert client.post(f"/api/topics/{topic}/normalize?limit=11").status_code==422
    finally:app.dependency_overrides.pop(get_ai_provider,None)


def test_migration_preserves_existing_data(engine):
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0009"
        assert connection.scalar(text("SELECT count(*) FROM topics"))==1
        config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"));config.attributes["connection"]=connection
        command.check(config)
        command.downgrade(config,"0006")
        assert connection.scalar(text("SELECT count(*) FROM topics"))==1
        command.upgrade(config,"head")


def test_same_date_different_format_is_not_conflict():
    data=input_data();data.text="计划2026年11月16日发布，日期为2026-11-16。"
    normalized=validate_normalization(result(event_date="2026-11-16"),data)
    assert normalized.event_date==date(2026,11,16)
    assert not any("多个日期" in w for w in normalized.warnings)


def test_claim_text_cannot_self_confirm():
    with pytest.raises(NormalizationSemanticError,match="Verification"):
        validate_normalization(result(claims=[{"text":"官方已证实辞职原因涉及私人关系。","status":"reported"}]),input_data())


def test_api_provider_failure_and_lock(scan_client):
    from app.main import app
    from app.workflows.locks import topic_operation
    class Offline(Fake):
        def normalize(self,data):raise AIError("private output",503)
    client,_=scan_client;app.dependency_overrides[get_ai_provider]=Offline
    try:
        topic=client.post("/api/topics",json={"name":"失败测试"}).json()["id"]
        client.post(f"/api/topics/{topic}/scan").raise_for_status()
        row=client.get(f"/api/topics/{topic}/items").json()[0];base=f"/api/items/{row['id']}"
        with topic_operation(topic):
            assert client.post(base+"/normalize").status_code==409
        failed=client.post(base+"/normalize")
        assert failed.status_code==503 and "private" not in failed.text
        saved=client.get(base+"/normalization").json()
        assert saved["normalization_status"]=="failed" and saved["headline"] is None
        client.delete(base).raise_for_status()
        assert client.get(base+"/normalization").status_code==404
    finally:app.dependency_overrides.pop(get_ai_provider,None)


def test_force_failure_preserves_successful_revision(engine):
    class Offline(Fake):
        def normalize(self,data):raise AIError("offline",503)
    with Session(engine) as session:
        item=raw(session);service=NormalizationService(session,Fake());original=service.normalize(item.id)
        service.provider=Offline()
        with pytest.raises(AIError):service.normalize(item.id,force=True)
        assert session.get(ItemNormalizationRecord,original.id).summary==original.summary
        assert service.get(item.id).normalization_status=="failed"
        assert service.get(item.id).revision==2


def test_source_change_invalidates_cache(engine):
    provider=Fake()
    with Session(engine) as session:
        item=raw(session);service=NormalizationService(session,provider);first=service.normalize(item.id)
        item.snippet+="新增原始资料。";session.commit()
        assert service.get(item.id) is None
        second=service.normalize(item.id)
        assert first.id!=second.id and len(provider.calls)==2


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS")!="1",reason="Opt-in local PostgreSQL")
def test_postgresql_normalization_roundtrip_and_raw_preserved():
    from app.database import get_engine
    from uuid import uuid4
    with get_engine().connect() as connection:
        transaction=connection.begin()
        try:
            with Session(connection,join_transaction_mode="create_savepoint") as session:
                topic=TopicRecord(name="Task A PG rollback");session.add(topic);session.flush()
                item=ItemRecord(topic_id=topic.id,source="test",external_id=uuid4().hex,title="原始标题",url="https://example.com/test",snippet="原始片段")
                session.add(item);session.commit();item_id=item.id
                normalized=NormalizationService(session,Fake()).normalize(item_id)
                session.expire_all()
                assert normalized.normalization_status=="completed"
                assert NormalizationService(session).get(item_id).summary==payload()["summary"]
                assert session.get(ItemRecord,item_id).snippet=="原始片段"
                assert normalized.normalized_at.utcoffset() is not None
        finally:transaction.rollback()


def test_claim_year_must_come_from_source():
    with pytest.raises(NormalizationSemanticError,match="Unsupported year"):
        validate_normalization(result(claims=[{"text":"将在2099年启用。","status":"reported"}]),input_data())
