"""Offline HTTP acceptance demo. Isolated DB, explicit Fake AI, no native notifications."""
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.update(SCHEDULER_ENABLED="false",NOTIFICATIONS_ENABLED="false",OLLAMA_TRACE_ENABLED="false")
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_session
from app.collection.provider import get_source
from app.collection.source import SourceAdapter
from app.items.schemas import NormalizedItem
from app.ai.ollama import get_ai_provider
from app.ai.provider import AIProvider
from app.ai.schemas import AnalysisResult
from app.normalization.schemas import NormalizationResult
from app.events.notifications import dispatch_candidates


class DemoSource(SourceAdapter):
    name="mock"
    batch=0
    def search(self,query):
        originals=[("NVIDIA 发布 RTX5090 显卡","NVIDIA 宣布发布 RTX5090 显卡。"),
            ("NVIDIA announces RTX5090 GPU","NVIDIA announces the RTX5090 graphics card."),
            ("NVIDIA 公布 RTX5090 售价","NVIDIA 宣布 RTX5090 显卡售价为1999美元。")]
        title,body=originals[self.batch]
        return [NormalizedItem(source="mock",external_id=f"demo-{self.batch}",title=title,snippet=body,
            author=f"模拟来源{self.batch+1}",url=f"https://example.com/event-demo/{self.batch}")]


class DemoAI(AIProvider):
    model="fake-demo-only"
    calls=0
    def analyze(self,data):
        return AnalysisResult(relevance_score=.95,relevance_reason="模拟结果",exclusion_status="not_excluded",exclusion_reason="",category="product",summary="模拟资料，不是真实新闻。")
    def normalize(self,data):
        self.calls+=1
        pricing="/2" in data.url
        text="NVIDIA 宣布 RTX5090 显卡售价为1999美元。" if pricing else "NVIDIA 宣布发布 RTX5090 显卡。"
        return NormalizationResult(headline="NVIDIA 公布 RTX5090 售价" if pricing else "NVIDIA 发布 RTX5090 显卡",summary=text,
            entities=["NVIDIA"],event_type="pricing" if pricing else "product_release",event_date=None,
            keywords=["RTX5090"],claims=[{"text":text,"status":"reported"}],warnings=["离线模拟验收，不是真实新闻。"])


class DemoNotifications:
    def __init__(self):self.calls=[]
    def send_event(self,name,title,kind):self.calls.append({"topic":name,"title":title,"type":kind})


def main():
    print("Offline demo: Fake AI/notifications; Ollama availability messages do not affect this demo.")
    folder=Path("D:/pytest-temp")/uuid4().hex;folder.mkdir(parents=True)
    engine=create_engine("sqlite:///"+str(folder/"event-demo.sqlite"),connect_args={"check_same_thread":False})
    @event.listens_for(engine,"connect")
    def foreign_keys(conn,_):conn.execute("PRAGMA foreign_keys=ON")
    config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
    with engine.begin() as conn:
        config.attributes["connection"]=conn;command.upgrade(config,"head")
    def sessions():
        with Session(engine) as session:yield session
    source,provider,notifier=DemoSource(),DemoAI(),DemoNotifications()
    app.dependency_overrides.update({get_session:sessions,get_source:lambda:source,get_ai_provider:lambda:provider})
    stages=[]
    try:
        with TestClient(app) as client:
            response=client.post("/api/topics",json={"name":"NVIDIA"});response.raise_for_status();topic_id=response.json()["id"]
            event_id=None
            for index,relation in enumerate(("new_event","duplicate_report","event_update")):
                source.batch=index
                scan=client.post(f"/api/topics/{topic_id}/scan");scan.raise_for_status()
                item=client.get(f"/api/topics/{topic_id}/items").json()[0]
                norm=client.post(f"/api/items/{item['id']}/normalize");norm.raise_for_status()
                resolved=client.post(f"/api/items/{item['id']}/resolve?topic_id={topic_id}");resolved.raise_for_status();data=resolved.json()
                assert data["decision"]["relation"]==relation
                if event_id is None:event_id=data["decision"]["event_id"]
                assert data["decision"]["event_id"]==event_id
                with Session(engine) as session:dispatch_candidates(session,topic_id,lambda:notifier)
                stages.append({"scan":scan.json(),"item_id":item["id"],"normalized_item_id":norm.json()["id"],
                    "decision":data["decision"],"notifications_so_far":len(notifier.calls)})
            assert [row["notifications_so_far"] for row in stages]==[1,1,2]
            engine.dispose()  # reconnect to the persisted file; no in-memory dedup state
            detail=client.get(f"/api/events/{event_id}");detail.raise_for_status();detail=detail.json()
            assert detail["source_count"]==3 and len(detail["updates"])==2
            assert len(client.get("/api/events").json())==1
            report={"mode":"offline Fake AI / Fake Notification, HTTP endpoints, isolated SQLite","success":True,
                "stages":stages,"event":detail,"model_calls":provider.calls,"notifications":notifier.calls,
                "database_reconnected":True,"public_network_calls":0,"native_notifications":0}
            (folder/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps({"success":True,"event_id":event_id,"relations":[r["decision"]["relation"] for r in stages],
                "sources":detail["source_count"],"updates":len(detail["updates"]),"notifications":len(notifier.calls),"report":str(folder/"report.json")},ensure_ascii=True))
    finally:
        app.dependency_overrides.clear();engine.dispose()


if __name__=="__main__":main()
