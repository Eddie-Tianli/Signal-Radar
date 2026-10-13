import pytest
from app.main import app
from test_scan import scan_client


def test_rules_crud_defaults_and_legacy_put(scan_client):
    client, _ = scan_client
    topic = client.post("/api/topics", json={"name": "ChatGPT", "description": "官方新模型"}).json()
    assert topic["relevance_threshold"] == .8 and topic["include_rules"] == []
    id = topic["id"]
    include = client.post(f"/api/topics/{id}/rules", json={"rule_type": "include", "text": "OpenAI 官方发布"}).json()
    exclude = client.post(f"/api/topics/{id}/rules", json={"rule_type": "exclude", "text": "主要讨论 GPT-5.6"}).json()
    assert include["id"] != exclude["id"]
    result = client.put(f"/api/topics/{id}/rules/{exclude['id']}", json={"text": "主要讨论旧模型", "enabled": False})
    assert result.json()["enabled"] is False
    updated = client.put(f"/api/topics/{id}", json={"name": "ChatGPT", "relevance_threshold": .9,
        "include_rules": [{"id": include["id"], "text": "官方公告", "enabled": True}]}).json()
    assert updated["include_rules"][0]["id"] == include["id"]
    assert len(updated["exclude_rules"]) == 1
    legacy = client.put(f"/api/topics/{id}", json={"name": "ChatGPT"}).json()
    assert legacy["relevance_threshold"] == .9 and legacy["include_rules"] == updated["include_rules"]
    assert client.delete(f"/api/topics/{id}/rules/{exclude['id']}").status_code == 204
    assert client.get(f"/api/topics/{id}").json()["exclude_rules"] == []
    assert client.put(f"/api/topics/{id}", json={"name": "ChatGPT", "include_rules": [{"id": 9999, "text": "x"}]}).status_code == 422


@pytest.mark.parametrize("threshold", [-.01, 1.1, "nan"])
def test_threshold_range(scan_client, threshold):
    client, _ = scan_client
    assert client.post("/api/topics", json={"name": "x", "relevance_threshold": threshold}).status_code == 422


def test_exact_rule_conflict_observable(scan_client):
    client, _ = scan_client
    topic = client.post("/api/topics", json={"name": "x", "include_rules": [{"text": "官方发布"}], "exclude_rules": [{"text": "官方发布"}]}).json()
    assert topic["rule_warnings"]
