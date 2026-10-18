import hmac, hashlib, json
from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc)
def iso(dt=NOW): return dt.isoformat()

def change(client, owner, sha="a"*40, service="checkout"):
    h, pid = owner
    return client.post(f"/api/projects/{pid}/changes", headers=h, json={"sha":sha,"title":"Fix timeout retry logic","author":"Alex","service":service,"changed_files":["src/retry.py"],"committed_at":iso(NOW-timedelta(minutes=15))})

def deploy(client, owner, sha="a"*40, service="checkout"):
    h, pid = owner
    return client.post(f"/api/projects/{pid}/deployments", headers=h, json={"version":"v1.0.1","environment":"production","service":service,"status":"success","commit_sha":sha,"deployed_at":iso(NOW-timedelta(minutes=5))})

def incident(client, owner):
    h, pid = owner
    return client.post(f"/api/projects/{pid}/incidents", headers=h, json={"title":"Checkout API unavailable","service":"checkout","severity":"SEV1","first_seen_at":iso()})

def test_end_to_end_suspect_evidence_and_resolution(client, owner):
    h, pid = owner
    assert change(client, owner).status_code == 201
    d = deploy(client, owner); assert d.status_code == 201, d.text
    i = incident(client, owner); assert i.status_code == 201, i.text
    iid = i.json()["id"]
    candidates = client.get(f"/api/projects/{pid}/incidents/{iid}/suspects", headers=h).json()["candidates"]
    assert candidates[0]["deployment_id"] == d.json()["id"]
    assert "Same affected service" in candidates[0]["reasons"]
    r = client.post(f"/api/projects/{pid}/incidents/{iid}/links", headers=h, json={"deployment_id":d.json()["id"],"reason":"Observed timing correlation"})
    assert r.status_code == 201
    no_resolution = client.patch(f"/api/projects/{pid}/incidents/{iid}", headers=h, json={"expected_version":1,"status":"resolved"})
    assert no_resolution.status_code == 422
    resolved = client.patch(f"/api/projects/{pid}/incidents/{iid}", headers=h, json={"expected_version":1,"status":"resolved","resolution":"Rolled back retry changes"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["version"] == 2
    stale = client.patch(f"/api/projects/{pid}/incidents/{iid}", headers=h, json={"expected_version":1,"severity":"SEV2"})
    assert stale.status_code == 409
    assert client.get(f"/api/projects/{pid}/audit", headers=h).status_code == 200

def test_two_contributors_append_notes_without_conflict(client, owner):
    h, pid = owner
    iid = incident(client, owner).json()["id"]
    for text in ["Found a retry regression", "Metrics confirm recovery"]:
        assert client.post(f"/api/projects/{pid}/incidents/{iid}/updates", headers=h, json={"body":text}).status_code == 201
    notes = client.get(f"/api/projects/{pid}/incidents/{iid}/updates", headers=h).json()
    assert [n["body"] for n in notes] == ["Found a retry regression", "Metrics confirm recovery"]
    assert client.get(f"/api/projects/{pid}/incidents/{iid}", headers=h).json()["version"] == 1

def test_idempotency_and_conflict(client, owner):
    h, pid = owner
    body = {"source":"monitor","external_id":"alert-42","type":"alert","summary":"Gateway failures","occurred_at":iso(),"details":{"count":5}}
    base = f"/api/projects/{pid}/events/ingest"
    first = client.post(base, headers=h, json=body)
    second = client.post(base, headers=h, json=body)
    assert first.status_code == 200 and first.json()["duplicate"] is False
    assert second.status_code == 200 and second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    conflicting = client.post(base, headers=h, json={**body, "summary":"Changed message"})
    assert conflicting.status_code == 409
    assert len(client.get(f"/api/projects/{pid}/events", headers=h).json()) == 1

def test_arrival_order_vs_occurrence_order(client, owner):
    h, pid = owner
    base = f"/api/projects/{pid}/events/ingest"
    def send(ext, at):
        return client.post(base, headers=h, json={"source":"ci","external_id":ext,"type":"deployment","summary":ext,"occurred_at":iso(at)})
    assert send("newer", NOW-timedelta(minutes=1)).status_code == 200
    assert send("older", NOW-timedelta(days=1)).status_code == 200
    occurrence = client.get(f"/api/projects/{pid}/events?order=occurred", headers=h).json()
    arrival = client.get(f"/api/projects/{pid}/events?order=received", headers=h).json()
    assert [e["summary"] for e in occurrence] == ["newer", "older"]
    assert [e["summary"] for e in arrival] == ["older", "newer"]

def test_project_isolation_and_rbac(client, owner):
    h,pid = owner
    user = client.post("/api/auth/register", json={"email":"viewer@test.dev","name":"Viewer Person","password":"SafePassword123"}).json()
    v = {"Authorization":f"Bearer {user['access_token']}"}
    assert client.get(f"/api/projects/{pid}/incidents", headers=v).status_code == 404
    assert client.post(f"/api/projects/{pid}/members", headers=h, json={"email":"viewer@test.dev","role":"viewer"}).status_code == 201
    assert client.get(f"/api/projects/{pid}/incidents", headers=v).status_code == 200
    assert incident(client, (v,pid)).status_code == 403
    assert deploy(client, (v,pid)).status_code == 403
    assert client.get(f"/api/projects/{pid}/audit", headers=v).status_code == 403
    assert client.post(f"/api/projects/{pid}/members", headers=v, json={"email":"owner@test.dev","role":"viewer"}).status_code == 403

def test_github_webhook_verification_and_dedupe(client, owner, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "local-test-secret")
    monkeypatch.delenv("GITHUB_PROJECT_ID", raising=False)
    monkeypatch.delenv("GITHUB_ALLOWED_REPOSITORIES", raising=False)
    h,pid = owner
    payload = json.dumps({"repository":{"full_name":"user/repo"},"ref":"refs/heads/main"}).encode()
    signature = "sha256="+hmac.new(b"local-test-secret", payload, hashlib.sha256).hexdigest()
    hdr = {"X-GitHub-Event":"push", "X-GitHub-Delivery":"delivery-1", "X-Hub-Signature-256":signature,"Content-Type":"application/json"}
    url = f"/api/webhooks/github/{pid}"
    assert client.post(url, content=payload, headers={**hdr,"X-Hub-Signature-256":"sha256=bad"}).status_code == 401
    a = client.post(url, content=payload, headers=hdr)
    assert a.status_code == 200, a.text
    b = client.post(url, content=payload, headers=hdr)
    assert b.status_code == 200 and b.json()["duplicate"] is True
    assert len(client.get(f"/api/projects/{pid}/events", headers=h).json()) == 1

def test_reject_duplicate_project_slug_and_commit_sha(client, owner):
    h, pid = owner
    duplicate = client.post('/api/projects',headers=h,json={'name':'Another project','slug':'test-system'})
    assert duplicate.status_code == 409
    assert change(client, owner).status_code == 201
    assert change(client, owner).status_code == 409

def test_timezone_required_and_resolution_null_safe(client, owner):
    h,pid=owner
    invalid=client.post(f'/api/projects/{pid}/incidents',headers=h,json={
        'title':'Missing zone','service':'core','first_seen_at':'2026-10-17T12:30:00'})
    assert invalid.status_code == 422
    valid=incident(client,owner);assert valid.status_code == 201
    iid=valid.json()['id']
    bad=client.patch(f'/api/projects/{pid}/incidents/{iid}',headers=h,json={'expected_version':1,'resolution':None})
    assert bad.status_code == 422

def test_incident_assignment_requires_existing_member(client, owner):
    h,pid=owner
    bad=client.post(f'/api/projects/{pid}/incidents',headers=h,json={
        'title':'Orphaned incident','service':'core','first_seen_at':iso(),'assigned_to_id':'unregistered-user'})
    assert bad.status_code == 422

def test_cross_project_incident_is_not_accessible(client, owner):
    h,pid=owner
    iid=incident(client,owner).json()['id']
    p2=client.post('/api/projects',headers=h,json={'name':'Other System','slug':'other-system'}).json()['id']
    assert client.get(f'/api/projects/{p2}/incidents/{iid}',headers=h).status_code==404
    assert client.patch(f'/api/projects/{p2}/incidents/{iid}',headers=h,json={'expected_version':1,'status':'investigating'}).status_code==404
