"""Task C offline HTTP demo / optional isolated UI server. No real AI or source calls."""
import argparse,json,os,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.update(EVENT_PROCESSING_ENABLED="true",SCHEDULER_ENABLED="false",NOTIFICATIONS_ENABLED="false",OLLAMA_TRACE_ENABLED="false")
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_session
from app.collection.provider import get_source
from app.collection.source import SourceAdapter
from app.collection.youtube import SourceError
from app.items.schemas import NormalizedItem
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider,AIError
from app.ai.schemas import AnalysisResult
from app.normalization.schemas import NormalizationResult
from app.briefs.schemas import BriefResult,CompositionResult
from app.events.notifications import dispatch_candidates


class DemoSource(SourceAdapter):
    name="mock"
    batch=0
    broken=False
    def search(self,query):
        if self.broken:raise SourceError("Local demo source unavailable.",503)
        products=(5090,5080) if self.batch==0 else (5070,5060)
        return [NormalizedItem(source="mock",external_id=f"reading-{p}",title=f"【模拟】NVIDIA 发布 RTX{p} 显卡",snippet=f"本地模拟资料，非真实新闻：NVIDIA 宣布发布 RTX{p} 显卡，效果尚待核验。",author=f"模拟频道{p}",url=f"https://example.com/reading-demo/{p}") for p in products]


class DemoAI(AIProvider):
    model="fake-reading-demo-only"
    fail_compose=False
    def analyze(self,data):return AnalysisResult(relevance_score=.95,relevance_reason="模拟",exclusion_status="not_excluded",exclusion_reason="",category="product",summary="模拟资料。")
    def normalize(self,data):return NormalizationResult(headline=data.title,summary=data.text,entities=["NVIDIA"],event_type="product_release",event_date=None,keywords=["GPU"],claims=[{"text":data.text,"status":"reported"}],warnings=["离线模拟，不是真实新闻。"])
    def brief_event(self,data):return BriefResult(title=data.title,summary="；".join(f["text"] for f in data.facts),fact_indices=list(range(len(data.facts))))
    def compose_digest(self,data):
        if self.fail_compose:raise AIError("Fake composition failure",502)
        return CompositionResult(title=data.topic["name"]+"：模拟事件综合简报",core_updates=["NVIDIA 的模拟产品资料已整理，均未独立核验。"],events=[{"brief_id":b["brief_id"],"text":b["summary"]} for b in data.briefs],watch_points=[])


class DemoNotification:
    def __init__(self):self.calls=[]
    def send_event(self,name,title,kind):self.calls.append({"topic":name,"title":title,"kind":kind})


def main(serve=False):
    folder=Path("D:/pytest-temp")/uuid4().hex;folder.mkdir(parents=True)
    engine=create_engine("sqlite:///"+str(folder/"reading-demo.sqlite"),connect_args={"check_same_thread":False})
    @event.listens_for(engine,"connect")
    def foreign_keys(conn,_):conn.execute("PRAGMA foreign_keys=ON")
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    with engine.begin() as conn:config.attributes["connection"]=conn;command.upgrade(config,"head")
    def sessions():
        with Session(engine) as session:yield session
    source,provider,notifier=DemoSource(),DemoAI(),DemoNotification()
    app.dependency_overrides.update({get_session:sessions,get_source:lambda:source,get_ai_provider:lambda:provider})
    outcomes=[]
    with TestClient(app) as client:
        topic=client.post("/api/topics",json={"name":"本地验收 NVIDIA"}).json()["id"]
        for wave in (0,1,2):
            if wave==2:source.batch=1;provider.fail_compose=True
            response=client.post(f"/api/topics/{topic}/update");response.raise_for_status()
            final=json.loads(response.text.splitlines()[-1]);outcomes.append(final)
            with Session(engine) as session:dispatch_candidates(session,topic,lambda:notifier)
        assert [row["digest"]["result_kind"] for row in outcomes]==["digest","no_updates","brief_collection"]
        source.broken=True
        failed=client.post(f"/api/topics/{topic}/update");failed.raise_for_status();last=json.loads(failed.text.splitlines()[-1])
        assert last["status"]=="failed" and last["digest"] is None
        source.broken=False;provider.fail_compose=False
        focus=client.get("/api/feed?mode=focus").json();discovery=client.get("/api/feed?mode=discover").json()
        assert len(focus["cards"])==4 and len(discovery["cards"])==4
        engine.dispose()
        report={"success":True,"mode":"isolated SQLite / Fake AI / Fake source / Fake notification, HTTP endpoints",
            "outcomes":outcomes,"failed_scan":last,"focus_count":len(focus["cards"]),"discovery_count":len(discovery["cards"]),"notifications":len(notifier.calls),"database_reconnected":True}
        (folder/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"success":True,"kinds":[r["digest"]["result_kind"] for r in outcomes],"scan_failure_status":last["status"],"focus":4,"discover":4,"notifications":len(notifier.calls),"report":str(folder/"report.json")},ensure_ascii=True),flush=True)
    if serve:
        import uvicorn
        print("Isolated demo backend on 127.0.0.1:8000; stop with Ctrl+C",flush=True)
        uvicorn.run(app,host="127.0.0.1",port=8000,log_level="warning")
    app.dependency_overrides.clear();engine.dispose()


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--serve",action="store_true")
    main(parser.parse_args().serve)
