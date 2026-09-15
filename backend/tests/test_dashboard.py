from app.main import app
from app.ai.ollama import get_ai_provider
from test_scan import scan_client
from test_digests import FakeAI


def test_dashboard_counts_recent_and_read_only(scan_client):
    client, _ = scan_client
    empty = client.get("/api/dashboard")
    assert empty.status_code == 200
    assert empty.json() == dict(total_topics=0, enabled_topics=0, total_items=0,
                               relevant_items=0, unanalyzed_items=0, recent_items=[], recent_digests=[])
    topic = client.post("/api/topics", json={"name": "Dashboard test"}).json()["id"]
    client.post("/api/topics", json={"name": "Disabled", "enabled": False})
    path = f"/api/topics/{topic}"
    client.post(path + "/scan").raise_for_status()
    pending = client.get("/api/dashboard").json()
    assert (pending["total_topics"], pending["enabled_topics"], pending["total_items"], pending["unanalyzed_items"]) == (2, 1, 2, 2)
    provider = FakeAI()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        client.post(path + "/analyze?limit=1").raise_for_status()
        digest = client.post(path + "/digest").json()
        result = client.get("/api/dashboard").json()
        assert result["relevant_items"] == 1 and result["unanalyzed_items"] == 1
        assert result["recent_digests"][0]["id"] == digest["id"]
        assert result["recent_digests"][0]["topic_name"] == "Dashboard test"
        assert result["recent_items"][0]["id"] > result["recent_items"][1]["id"]
        assert client.get("/api/dashboard").json() == result
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
