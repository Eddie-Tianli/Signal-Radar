import json,os
from datetime import datetime,timedelta,timezone
from pathlib import Path
import httpx
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.ai.provider import AIError
from app.ai.ollama import OllamaProvider,get_ai_provider
from app.normalization.schemas import NormalizationResult
from app.briefs.service import BriefService
from app.briefs.schemas import BriefInput,BriefResult,CompositionInput,CompositionResult
from app.briefs.reports import ReportService
from app.briefs.feed import FeedService
from app.briefs.models import BriefRecord,BriefVersionRecord,DigestBriefRecord,ReadingRunRecord,EventReadRecord
from app.events.models import EventRecord,EventSourceRecord,EventUpdateRecord,TopicMatchRecord
from app.events.pipeline import EventPipeline
from app.events.schemas import TopicMatchResult,EventRelationResult
from app.items.models import ItemRecord
from app.topics.models import TopicRecord,TopicRuleRecord
from app.digests.models import DigestRecord
from app.workflows.service import TopicUpdateService
from app.collection.mock import MockSource
from test_items import engine
from test_scan import scan_client
from test_digests import FakeAI as LegacyAI
from test_events import raw,topic,count


class ReadingAI(LegacyAI):
    model="fake-reading"
    def __init__(self):
        super().__init__();self.normalizations=[];self.brief_calls=[];self.compositions=[];self.fail_brief=False
    def normalize(self,data):
        self.normalizations.append(data)
        # Preserve the actual title to make each mock report's identity inspectable.
        title=data.title if any('\u4e00'<=c<='\u9fff' for c in data.title) else "主题进展："+data.title
        summary="来源称："+data.title+"。具体情况尚待核验。"
        if data.text and any('\u4e00'<=c<='\u9fff' for c in data.text):summary=data.text
        entity="NVIDIA" if "NVIDIA" in data.title else "OpenAI" if "OpenAI" in data.title else "主题"
        return NormalizationResult(headline=title,summary=summary,entities=[entity],event_type="product_release",event_date=None,keywords=["进展"],claims=[{"text":summary,"status":"reported"}],warnings=[])
    def match_topic(self,data):
        return TopicMatchResult(match_status="matched" if self.relevant else "unmatched",relevance_score=.95 if self.relevant else .1,matched_rules=["description"],exclusion_reason="",match_reason="核对主题与事件资料。")
    def compare_event(self,data):
        return EventRelationResult(relation="new_event",confidence=.95,reason="资料中的核心事件不同。",new_fact_indices=[],conflicting_fact_indices=[],importance=1.0)
    def brief_event(self,data):
        self.brief_calls.append(data)
        if self.fail_brief:raise AIError("offline",503)
        text="；".join(f["text"] for f in data.facts)
        # Short source data legitimately yields a short brief.
        title="事件简讯："+data.title
        if data.entities==["主题"]:title="主题进展简讯";text="来源提及主题的一项新进展，具体情况尚待核验。"
        if any(f["status"]=="conflicting" for f in data.facts):text="来源存在冲突，尚无定论。"+text
        return BriefResult(title=title[:180],summary=text[:1000],fact_indices=list(range(len(data.facts))))
    def compose_digest(self,data):
        self.compositions.append(data)
        if self.fail:raise AIError("invalid model output",502)
        return CompositionResult(title=data.topic["name"]+"：事件综合简报",core_updates=[data.briefs[0]["summary"]],
            events=[{"brief_id":b["brief_id"],"text":b["summary"]} for b in data.briefs],watch_points=[])


def seed(session,provider=None,number=2,author=None):
    provider=provider or ReadingAI();t=topic(session);pipeline=EventPipeline(session,provider);results=[]
    for index in range(number):
        item=raw(session,t.id,title=f"NVIDIA 发布 RTX{5090-index} 显卡",body=f"NVIDIA 宣布发布 RTX{5090-index} 显卡。",author=author or f"Source {index}")
        results.append(pipeline.process_item(item.id,[t.id]))
    return t,results,provider


def test_brief_generation_sources_history_and_duplicate_no_model(engine):
    with Session(engine) as session:
        t,rows,provider=seed(session,number=1);event_id=rows[0]["decision"]["event_id"]
        first=BriefService(session,provider).get(event_id)
        assert first["generation_status"]=="completed" and first["sources"][0]["item_id"]==rows[0]["item_id"]
        duplicate=raw(session,t.id)
        EventPipeline(session,provider).process_item(duplicate.id,[t.id])
        assert len(provider.brief_calls)==1 and count(session,BriefVersionRecord)==1
        assert len(BriefService(session).get(event_id)["current_sources"])==2
        price=raw(session,t.id,title="NVIDIA RTX5090 售价公布",body="NVIDIA RTX5090 售价为1999美元。")
        update=EventPipeline(session,provider).process_item(price.id,[t.id])
        assert update["decision"]["relation"]=="event_update"
        history=BriefService(session).history(event_id)
        assert len(history)==2 and history[-1]["summary"]==first["summary"]
        assert "1999" in history[0]["summary"] and count(session,BriefRecord)==1


def test_brief_failure_is_labelled_fallback_not_ai_success(engine):
    provider=ReadingAI();provider.fail_brief=True
    with Session(engine) as session:
        t,rows,_=seed(session,provider,1);event_id=rows[0]["decision"]["event_id"]
        first=BriefService(session).get(event_id)
        assert first["generation_status"]=="fallback" and first["error"] and "来源声称" in first["summary"]
        BriefService(session,provider).ensure(event_id);assert len(provider.brief_calls)==1
        provider.fail_brief=False;new=BriefService(session,provider).ensure(event_id,True)
        assert new["generation_status"]=="completed" and new["version"]==2


def test_normal_digest_only_uses_briefs_and_snapshots(engine):
    with Session(engine) as session:
        t,rows,provider=seed(session)
        report=ReportService(session,provider).generate(t.id)
        assert report.result_kind=="digest" and "核心动态" in report.summary and "主要事件" in report.summary
        assert len(report.briefs)==2 and count(session,DigestBriefRecord)==2
        assert len({b["event_id"] for b in report.briefs})==2
        assert "snippet" not in provider.compositions[0].model_dump_json()
        assert all("description" not in row and "snippet" not in row for row in provider.compositions[0].briefs)
        assert all(source.item_id in {row["item_id"] for row in rows} for source in report.sources)
        after=ReportService(session,provider).generate(t.id)
        assert after.result_kind=="no_updates" and len(provider.compositions)==1


@pytest.mark.parametrize("number,failed",[(1,False),(2,True)])
def test_collection_fallback_never_marks_ai_digest(engine,number,failed):
    with Session(engine) as session:
        t,_,provider=seed(session,number=number);provider.fail=failed
        report=ReportService(session,provider).generate(t.id)
        assert report.result_kind=="brief_collection" and report.generation_status=="fallback"
        assert len(report.briefs)==number
        assert len(provider.compositions)==int(number>=2)


def test_no_update_no_model_and_failed_scan_not_no_news(engine,monkeypatch):
    monkeypatch.setenv("EVENT_PROCESSING_ENABLED","true")
    class Broken(MockSource):
        def search(self,query):raise AIError("network unavailable",503)
    with Session(engine) as session:
        t=topic(session);provider=ReadingAI();report=ReportService(session,provider).generate(t.id)
        assert report.result_kind=="no_updates" and report.run_stats["scan_performed"] is False and not provider.compositions
        before=count(session,DigestRecord)
        final=list(TopicUpdateService(session,Broken(),provider).run(t.id))[-1]
        assert final.status=="failed" and final.digest is None
        assert count(session,DigestRecord)==before
        run=session.scalar(select(ReadingRunRecord));assert run.status=="failed" and run.error


def test_precision_rules_and_discovery_are_separate(engine):
    with Session(engine) as session:
        t,_,provider=seed(session,number=3)
        before=FeedService(session).cards("discover")
        t.rules.append(TopicRuleRecord(rule_type="exclude",text="排除关键词：NVIDIA",enabled=True));session.commit()
        assert FeedService(session).cards("focus",t.id)==[]
        assert len(FeedService(session).cards("discover"))==len(before)
        assert t.exclude_rules[0].text=="排除关键词：NVIDIA"


def test_diversity_and_read_state_persist(engine):
    with Session(engine) as session:
        _,_,_=seed(session,number=4,author="Same channel")
        cards=FeedService(session).cards("discover",limit=10)
        assert len(cards)==2 and len({c["event_id"] for c in cards})==2
        card=cards[0];session.add(EventReadRecord(event_id=card["event_id"],brief_version_id=card["version_id"]));session.commit()
    with Session(engine) as session:
        assert any(c["is_read"] for c in FeedService(session).cards("focus"))


def test_invalidated_match_and_trash_not_in_focus(engine):
    with Session(engine) as session:
        t,rows,_=seed(session)
        item=session.get(ItemRecord,rows[0]["item_id"]);item.deleted_at=datetime.now(timezone.utc);session.commit()
        assert len(FeedService(session).cards("focus",t.id))==1
        match=session.scalar(select(TopicMatchRecord).where(TopicMatchRecord.normalized_item_id==rows[1]["normalized_item_id"]))
        match.match_status="uncertain";session.commit()
        assert FeedService(session).cards("focus",t.id)==[]


def test_report_time_limits_and_coverage_survive_restart(engine,monkeypatch):
    monkeypatch.setenv("DIGEST_MAX_EVENTS","1")
    with Session(engine) as session:
        t,_,provider=seed(session,number=3);topic_id=t.id
        first=ReportService(session,provider).generate(t.id)
        assert len(first.briefs)==1
    with Session(engine) as session:
        second=ReportService(session,ReadingAI()).generate(topic_id)
        assert second.briefs[0]["event_id"]!=first.briefs[0]["event_id"]
        empty=ReportService(session,ReadingAI()).generate(topic_id,since=datetime.now(timezone.utc)+timedelta(days=1))
        assert empty.result_kind=="no_updates"


@pytest.mark.parametrize("kind",["brief","digest"])
def test_ollama_json_retry_and_unbound_output_rejected(kind,tmp_path,monkeypatch):
    from app.ai import trace
    monkeypatch.setenv("OLLAMA_TRACE_ENABLED","true");monkeypatch.setattr(trace,"TRACE_PATH",tmp_path/"trace.jsonl")
    data=BriefInput(event_id=1,title="NVIDIA 发布显卡",entities=["NVIDIA"],event_date=None,facts=[{"text":"NVIDIA 宣布发布显卡。","status":"reported"}],sources=[])
    brief={"brief_id":1,"event_id":1,"title":"NVIDIA 发布显卡","summary":"NVIDIA 宣布发布显卡。","entities":["NVIDIA"],"verification_status":"unverified"}
    comp=CompositionInput(topic={"name":"NVIDIA"},briefs=[brief,{**brief,"brief_id":2,"event_id":2}])
    expected={"title":"NVIDIA 发布显卡","summary":"NVIDIA 宣布发布显卡。","fact_indices":[0]} if kind=="brief" else {"title":"NVIDIA 事件进展","core_updates":["NVIDIA 宣布发布显卡。"],"events":[{"brief_id":i,"text":"NVIDIA 宣布发布显卡。"} for i in (1,2)],"watch_points":[]}
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content));assert calls[-1]["stream"] is False and calls[-1]["options"]["temperature"]==0
        return httpx.Response(200,json={"message":{"content":"broken JSON" if len(calls)==1 else json.dumps(expected)}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider=OllamaProvider(client,"http://localhost:11434","fake")
        result=provider.brief_event(data) if kind=="brief" else provider.compose_digest(comp)
    assert len(calls)==2 and result.title
    logs=[json.loads(line) for line in trace.TRACE_PATH.read_text(encoding="utf-8").splitlines()]
    assert any(row["event"]=="retry" for row in logs)


def test_two_invalid_digest_outputs_degrade_without_saving_bad_ai(engine):
    with Session(engine) as session:
        t,_,_=seed(session);calls=[]
        def handler(request):calls.append(request);return httpx.Response(200,json={"message":{"content":"not JSON"}})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            report=ReportService(session,OllamaProvider(client,"http://localhost:11434","fake")).generate(t.id)
        assert len(calls)==2 and report.result_kind=="brief_collection" and "not JSON" not in report.summary


def test_reading_api_and_history(scan_client):
    from app.main import app
    client,_=scan_client;provider=ReadingAI();app.dependency_overrides[get_ai_provider]=lambda:provider
    try:
        t=client.post("/api/topics",json={"name":"OpenAI"}).json()["id"]
        client.post(f"/api/topics/{t}/scan").raise_for_status()
        for item in client.get(f"/api/topics/{t}/items").json():client.post(f"/api/items/{item['id']}/resolve").raise_for_status()
        feed=client.get("/api/feed?mode=focus");feed.raise_for_status();cards=feed.json()["cards"]
        assert cards
        event=cards[0]["event_id"]
        assert client.get(f"/api/events/{event}/brief-history").json()
        assert client.post(f"/api/briefs/{cards[0]['id']}/read").json()["is_read"]
        assert client.get(f"/api/events/{event}/brief-history").json()[0]["is_read"]
        overview=client.get("/api/reading-overview").json()
        assert overview["event_count"] >= 1 and overview["brief_count"] >= 1
        assert client.get("/api/feed?mode=discover&topic_id=1").status_code==422
        assert client.get("/api/events/9999/brief").status_code==404
    finally:app.dependency_overrides.pop(get_ai_provider,None)


@pytest.mark.parametrize("text",["NVIDIA 的消息详见 https://invented.example 。","NVIDIA 将于2099年发布新产品。","the user wants NVIDIA 用户希望了解更多。"])
def test_unsafe_brief_output_never_saved_as_ai(engine,text):
    class Unsafe(ReadingAI):
        def brief_event(self,data):return BriefResult(title="NVIDIA 的新进展",summary=text,fact_indices=[0])
    with Session(engine) as session:
        _,rows,_=seed(session,Unsafe(),1)
        brief=BriefService(session).get(rows[0]["decision"]["event_id"])
        assert brief["generation_status"]=="fallback" and text not in brief["summary"]


def test_important_conflict_updates_brief_without_losing_old_claims(engine):
    from app.normalization.schemas import Claim
    class Conflicting(ReadingAI):
        def normalize(self,data):return super().normalize(data).model_copy(update={"claims":[Claim(text=data.text,status="conflicting")]})
    with Session(engine) as session:
        t,rows,provider=seed(session,number=1);event_id=rows[0]["decision"]["event_id"]
        EventPipeline(session,Conflicting()).process_item(raw(session,t.id).id,[t.id])
        current=BriefService(session).get(event_id)
        assert current["verification_status"]=="conflicting" and "冲突" in current["summary"]
        assert len(BriefService(session).history(event_id))==2


def test_minor_update_does_not_regenerate_brief(engine):
    with Session(engine) as session:
        _,rows,provider=seed(session,number=1);event_id=rows[0]["decision"]["event_id"]
        session.add(EventUpdateRecord(event_id=event_id,normalized_item_id=rows[0]["normalized_item_id"],update_type="new_facts",new_facts=[{"text":"小幅措辞补充。","status":"reported"}],source_reference={"item_id":rows[0]["item_id"],"url":"https://example.com"},importance=.3,fact_fingerprint="minor"));session.commit()
        BriefService(session,provider).ensure(event_id)
        assert len(provider.brief_calls)==1


def test_explicit_recompose_after_fallback_does_not_renormalize(engine):
    with Session(engine) as session:
        t,_,provider=seed(session);provider.fail=True
        first=ReportService(session,provider).generate(t.id)
        provider.fail=False;second=ReportService(session,provider).generate(t.id,force=True)
        assert first.result_kind=="brief_collection" and second.result_kind=="digest"
        assert len(provider.normalizations)==2 and len(provider.brief_calls)==2 and len(provider.compositions)==2


def test_empty_successful_scan_has_real_no_update_stats(engine,monkeypatch):
    monkeypatch.setenv("EVENT_PROCESSING_ENABLED","true")
    class Empty(MockSource):
        def search(self,query):return []
    with Session(engine) as session:
        final=list(TopicUpdateService(session,Empty(),ReadingAI()).run(1))[-1]
        assert final.status=="completed" and final.digest.result_kind=="no_updates"
        assert final.digest.run_stats["scan_performed"] and final.digest.run_stats["scan_time"]
        assert final.digest.run_stats["fetched"]==0


def test_report_trash_does_not_repeat_covered_events(engine):
    with Session(engine) as session:
        t,_,provider=seed(session)
        first=ReportService(session,provider).generate(t.id)
        session.get(DigestRecord,first.id).deleted_at=datetime.now(timezone.utc);session.commit()
        assert ReportService(session,provider).generate(t.id).result_kind=="no_updates"


def test_old_digest_rows_remain_readable(engine):
    from app.digests.schemas import DigestRead
    with Session(engine) as session:
        old=DigestRecord(topic_id=1,title="旧简报",summary="历史正文",item_count=1)
        session.add(old);session.commit()
        assert DigestRead.model_validate(old).result_kind=="legacy" and old.summary=="历史正文"


def test_workspace_migration_matches_metadata(engine):
    with engine.begin() as connection:
        config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"));config.attributes["connection"]=connection
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="0010"
        command.check(config)
        command.downgrade(config,"0009")
        assert connection.scalar(text("SELECT count(*) FROM topics"))==1
        command.upgrade(config,"head");command.check(config)


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS")!="1",reason="Opt-in PostgreSQL")
def test_postgresql_reading_versions_and_reports_persist():
    from app.database import get_engine
    with get_engine().connect() as connection:
        outer=connection.begin()
        try:
            with Session(connection,join_transaction_mode="create_savepoint") as session:
                t=TopicRecord(name="NVIDIA");session.add(t);session.commit()
                provider=ReadingAI()
                for index in (0,1):EventPipeline(session,provider).process_item(raw(session,t.id,title=f"NVIDIA 发布 RTX{index} 显卡",body=f"NVIDIA 宣布发布 RTX{index} 显卡。").id,[t.id])
                report=ReportService(session,provider).generate(t.id)
                assert report.result_kind=="digest" and len(report.briefs)==2
                session.expire_all()
                assert ReportService(session,provider).generate(t.id).result_kind=="no_updates"
        finally:outer.rollback()


def test_partial_source_failure_is_not_reported_as_no_news(engine,monkeypatch):
    monkeypatch.setenv("EVENT_PROCESSING_ENABLED","true")
    from app.collection.service import ScanResult
    def partial(self,topic_id):
        return ScanResult(topic_id=topic_id,source="mock",fetched=0,created=0,duplicates=0,warnings=["One query failed"],item_ids=[])
    monkeypatch.setattr("app.collection.service.CollectionService.scan",partial)
    with Session(engine) as session:
        t=topic(session)
        result=list(TopicUpdateService(session,MockSource(),ReadingAI()).run(t.id))[-1]
        assert result.status=="partial" and result.digest is None
        assert result.warnings and result.digest_skipped=="processing_incomplete"
