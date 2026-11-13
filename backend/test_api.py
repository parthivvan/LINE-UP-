import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
from fastapi.testclient import TestClient
from main import app

c = TestClient(app)

def H(tok): return {"Authorization": f"Bearer {tok}"}

def test_full_flow():
    r = c.post("/api/auth/register", json={"username": "Alice", "password": "secret1"}); assert r.status_code == 201
    tok = r.json()["token"]
    assert c.post("/api/auth/login", json={"username": "alice", "password": "bad-pass"}).status_code == 400
    assert c.get("/api/queues").status_code == 401
    q = c.post("/api/queues", json={"name": "Billing"}, headers=H(tok)).json()
    assert c.post("/api/queues", json={"name": "billing"}, headers=H(tok)).status_code == 409
    assert c.post("/api/queues", json={"name": "   "}, headers=H(tok)).status_code == 422
    for n in ["A", "B", "C"]:
        d = c.post(f"/api/queues/{q['id']}/tokens", json={"name": n}, headers=H(tok)).json()
    assert [t["name"] for t in d["waiting"]] == ["A", "B", "C"]
    assert d["waiting"][0]["label"] == "T-001"
    idC = d["waiting"][2]["id"]
    d = c.post(f"/api/tokens/{idC}/move", json={"direction": "up"}, headers=H(tok)).json()
    assert [t["name"] for t in d["waiting"]] == ["A", "C", "B"]
    d = c.post(f"/api/tokens/{idC}/move", json={"direction": "down"}, headers=H(tok)).json()
    assert [t["name"] for t in d["waiting"]] == ["A", "B", "C"]
    d = c.post(f"/api/tokens/{idC}/move", json={"direction": "down"}, headers=H(tok)).json()  # edge no-op
    assert [t["name"] for t in d["waiting"]] == ["A", "B", "C"]
    d = c.post(f"/api/queues/{q['id']}/serve-next", headers=H(tok)).json()
    assert d["serving"][0]["name"] == "A" and len(d["waiting"]) == 2
    idB = d["waiting"][0]["id"]
    d = c.post(f"/api/tokens/{idB}/cancel", headers=H(tok)).json()
    assert [t["name"] for t in d["waiting"]] == ["C"] and d["cancelled_count"] == 1
    d = c.post(f"/api/tokens/{d['serving'][0]['id']}/complete", headers=H(tok)).json()
    assert d["served_count"] == 1 and d["serving"] == []
    a = c.get(f"/api/queues/{q['id']}/analytics", headers=H(tok)).json()
    assert a["summary"]["served"] == 1 and a["summary"]["cancelled"] == 1 and a["summary"]["waiting"] == 1
    assert len(a["length_trend"]) >= 5 and len(a["wait_history"]) == 1
    # isolation between managers
    t2 = c.post("/api/auth/register", json={"username": "bob", "password": "secret2"}).json()["token"]
    assert c.get(f"/api/queues/{q['id']}", headers=H(t2)).status_code == 404
    assert c.post(f"/api/tokens/{idC}/cancel", headers=H(t2)).status_code == 404
    assert c.post(f"/api/queues/{q['id']}/serve-next", headers=H(tok)).status_code == 200
    assert c.post(f"/api/queues/{q['id']}/serve-next", headers=H(tok)).status_code == 400
    assert c.delete(f"/api/queues/{q['id']}", headers=H(tok)).status_code == 204
