"""Webhook contract regression tests for the v2 GitHub integration."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from app.models import CodeChange, Deployment, Event
from app.db import get_db

SECRET = "local-test-github-secret"
REPO = "example/faultline-demo"
NOW = datetime.now(timezone.utc)
SHA = "a" * 40


def send(client, pid, payload, kind, delivery, secret=SECRET, signature_override=None):
    data = json.dumps(payload, separators=(",", ":")).encode("utf8")
    signature = "sha256=" + hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
    return client.post(f"/api/webhooks/github/{pid}", content=data, headers={
        "X-Hub-Signature-256": signature_override or signature,
        "X-GitHub-Delivery": delivery,
        "X-GitHub-Event": kind,
        "Content-Type": "application/json",
    })


def push_payload():
    committed = (NOW-timedelta(minutes=15)).isoformat()
    return {
        "repository": {"full_name": REPO}, "ref": "refs/heads/main", "after": SHA,
        "head_commit": {"timestamp": committed},
        "commits": [{"id": SHA, "message": "Fix checkout retries\nDetailed body", "timestamp": committed,
                     "author": {"name": "Dev Alice"}, "added": ["src/checkout.py"],
                     "modified": ["src/checkout.py", "tests/test_checkout.py"], "removed": []}],
    }


def deployment_payload(state="success"):
    return {
        "repository": {"full_name": REPO},
        "deployment": {"id": 42, "sha": SHA, "ref": "v3.0.1",
                       "environment": "production", "payload": {"service": "checkout-api"},
                       "created_at": (NOW-timedelta(minutes=10)).isoformat()},
        "deployment_status": {"state": state, "created_at": (NOW-timedelta(minutes=5)).isoformat()},
    }


def setup(monkeypatch, pid):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("GITHUB_PROJECT_ID", pid)
    monkeypatch.setenv("GITHUB_ALLOWED_REPOSITORIES", REPO)
    monkeypatch.setenv("GITHUB_DEFAULT_SERVICE", "checkout-api")


def test_github_push_creates_code_change_and_idempotent_deliveries(client, owner, monkeypatch):
    h, pid = owner
    setup(monkeypatch, pid)
    push = push_payload()
    first = send(client, pid, push, "push", "delivery-push")
    assert first.status_code == 200, first.text
    assert first.json()["new_changes"] == 1
    assert first.json()["duplicate"] is False
    same = send(client, pid, push, "push", "delivery-push")
    assert same.status_code == 200 and same.json()["duplicate"] is True
    assert same.json()["new_changes"] == 0
    # Different GitHub delivery for the same SHA must not duplicate domain rows.
    second = send(client, pid, push, "push", "delivery-new-id")
    assert second.status_code == 200, second.text
    assert second.json()["new_changes"] == 0
    changes = client.get(f"/api/projects/{pid}/changes", headers=h).json()
    assert len(changes) == 1
    assert changes[0]["sha"] == SHA
    assert changes[0]["author"] == "Dev Alice"
    assert changes[0]["service"] == "checkout-api"
    assert changes[0]["changed_files"] == ["src/checkout.py", "tests/test_checkout.py"]


def test_github_status_creates_deployment_and_insight(client, owner, monkeypatch):
    h, pid = owner
    setup(monkeypatch, pid)
    assert send(client, pid, push_payload(), "push", "first-push").json()["new_changes"] == 1
    pending = send(client, pid, deployment_payload("in_progress"), "deployment_status", "status-pending")
    assert pending.status_code == 200 and pending.json()["new_deployments"] == 0
    deployed = send(client, pid, deployment_payload("success"), "deployment_status", "status-success")
    assert deployed.status_code == 200, deployed.text
    assert deployed.json()["new_deployments"] == 1
    assert send(client, pid, deployment_payload("success"), "deployment_status", "status-success").json()["duplicate"] is True
    assert len(client.get(f"/api/projects/{pid}/deployments", headers=h).json()) == 1
    incident = client.post(f"/api/projects/{pid}/incidents", headers=h, json={
        "title": "Checkout unavailable after release", "severity": "SEV1", "service": "checkout-api",
        "first_seen_at": NOW.isoformat()})
    assert incident.status_code == 201, incident.text
    suspects = client.get(f"/api/projects/{pid}/incidents/{incident.json()['id']}/suspects", headers=h)
    assert suspects.status_code == 200
    assert suspects.json()["candidates"][0]["score"] >= 80
    assert "Matching commit and service in change history" in suspects.json()["candidates"][0]["reasons"]


def test_webhook_rejects_wrong_signature_repo_project_and_conflicting_replay(client, owner, monkeypatch):
    h, pid = owner
    setup(monkeypatch, pid)
    payload = push_payload()
    unauthorized = send(client, pid, payload, "push", "x-sign", signature_override="sha256=bad")
    assert unauthorized.status_code == 401
    wrong_repo = send(client, pid, {**payload, "repository": {"full_name": "other/repo"}}, "push", "x-repo")
    assert wrong_repo.status_code == 403
    wrong_project = client.post("/api/projects", headers=h, json={"name":"Another", "slug":"another"}).json()["id"]
    assert send(client, wrong_project, payload, "push", "x-project").status_code == 403
    assert send(client, pid, payload, "push", "x-replay").status_code == 200
    changed = {**payload, "ref": "refs/heads/some-other-branch"}
    assert send(client, pid, changed, "push", "x-replay").status_code == 409
    assert len(client.get(f"/api/projects/{pid}/changes", headers=h).json()) == 1


def test_webhook_payload_boundaries_and_atomicity(client, owner, monkeypatch):
    h, pid = owner
    setup(monkeypatch, pid)
    missing = send(client, pid, {"repository": {"full_name": REPO}}, "ping", "ping")
    assert missing.status_code == 200 and missing.json()["new_changes"] == 0
    bad_push = {"repository":{"full_name":REPO}, "commits":[{"id":"not_a_sha","message":"Bad"}]}
    assert send(client,pid,bad_push,"push","bad-sha").json()["new_changes"] == 0
    assert client.get(f"/api/projects/{pid}/changes", headers=h).json() == []
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET")
    assert send(client, pid, {"repository": {"full_name": REPO}}, "ping", "no-secret").status_code == 503
