"""Deterministic demo narratives. Run only with SEED_DEMO=true."""
import os
from datetime import timedelta
from .db import SessionLocal
from .models import User, Project, Membership, Deployment, CodeChange, Incident, IncidentUpdate, utcnow
from .auth import hash_password
from .events import internal_event, append_event, audit

def seed_demo():
    with SessionLocal() as db:
        if db.query(Project).filter_by(slug="orbit-commerce").first(): return
        password = os.getenv("SEED_PASSWORD", "DemoPassword123!")
        owner = db.query(User).filter_by(email="alex@faultline.dev").first()
        if not owner:
            owner = User(name="Alex Morgan", email="alex@faultline.dev", password_hash=hash_password(password))
            db.add(owner); db.flush()
        responder = db.query(User).filter_by(email="sam@faultline.dev").first()
        if not responder:
            responder = User(name="Sam Rivera", email="sam@faultline.dev", password_hash=hash_password(password))
            db.add(responder); db.flush()
        p = Project(name="Orbit Commerce", slug="orbit-commerce", description="Production commerce services and reliability signals")
        db.add(p); db.flush()
        db.add_all([Membership(project_id=p.id, user_id=owner.id, role="owner"),
                    Membership(project_id=p.id, user_id=responder.id, role="responder")])
        now = utcnow()
        change1 = CodeChange(project_id=p.id, sha="e4b8c62a93f1", title="Improve checkout session retry logic",
            author="Alex Morgan", service="checkout-api", changed_files=["services/checkout/retry.py", "services/checkout/client.py"], committed_at=now-timedelta(hours=6))
        change2 = CodeChange(project_id=p.id, sha="a917d3e81b4f", title="Add billing metrics and telemetry",
            author="Sam Rivera", service="billing-worker", changed_files=["workers/billing/metrics.py"], committed_at=now-timedelta(hours=2))
        db.add_all([change1, change2]); db.flush()
        d1 = Deployment(project_id=p.id, version="v2.18.0", environment="production", service="checkout-api",
            status="success", commit_sha=change1.sha, actor="CI / GitHub Actions", deployed_at=now-timedelta(hours=5, minutes=40))
        d2 = Deployment(project_id=p.id, version="v2.18.1", environment="production", service="billing-worker",
            status="success", commit_sha=change2.sha, actor="CI / GitHub Actions", deployed_at=now-timedelta(hours=1, minutes=50))
        d3 = Deployment(project_id=p.id, version="v2.17.9", environment="production", service="checkout-api",
            status="rolled_back", commit_sha="f43bbcdc98ab", actor="Sam Rivera", deployed_at=now-timedelta(hours=4, minutes=15))
        db.add_all([d1, d2, d3]); db.flush()
        incidents = [
            Incident(project_id=p.id, title="Checkout requests timing out", description="P95 latency rose above 8 seconds after the afternoon release. Elevated 5xx responses.",
                service="checkout-api", severity="SEV1", status="investigating", first_seen_at=now-timedelta(hours=5, minutes=25), assigned_to_id=responder.id),
            Incident(project_id=p.id, title="Payment authorization failures", description="Intermittent payment authorization errors affecting some sessions.",
                service="checkout-api", severity="SEV2", status="mitigated", first_seen_at=now-timedelta(hours=4, minutes=45), assigned_to_id=owner.id),
            Incident(project_id=p.id, title="Checkout requests timing out", description="Similar latency symptoms during a previous release.",
                service="checkout-api", severity="SEV2", status="resolved", first_seen_at=now-timedelta(days=4),
                resolved_at=now-timedelta(days=3, hours=23), resolution="Rolled back worker retry configuration", assigned_to_id=owner.id),
            Incident(project_id=p.id, title="Billing queue backlog", description="Increased processing lag in billing worker. No customer impact confirmed.",
                service="billing-worker", severity="SEV3", status="open", first_seen_at=now-timedelta(hours=1, minutes=15), assigned_to_id=responder.id),
        ]
        db.add_all(incidents); db.flush()
        for c in [change1, change2]:
            internal_event(db, p.id, "change", c.title, c.committed_at, "change", c.id,
                           {"sha": c.sha, "service": c.service})
        for d in [d1, d2, d3]:
            internal_event(db, p.id, "deployment", f"{d.version} deployed to {d.environment}", d.deployed_at,
                           "deployment", d.id, {"service": d.service, "status": d.status, "commit_sha": d.commit_sha})
        for inc in incidents:
            internal_event(db, p.id, "incident", f"{inc.severity}: {inc.title}", inc.first_seen_at,
                           "incident", inc.id, {"service": inc.service, "severity": inc.severity})
        note = IncidentUpdate(incident_id=incidents[0].id, author_id=responder.id, body="Reproduced failures in checkout. Comparing release v2.18.0 with previous version.")
        db.add(note); db.flush()
        internal_event(db, p.id, "note", "Sam Rivera: reproduced checkout latency", now-timedelta(hours=5), "incident", incidents[0].id, {"update_id": note.id})
        # intentionally late arrival; the timeline has two independent clocks
        append_event(db, p.id, source="monitor", external_id="checkout-late-001", type_="alert",
            summary="Delayed gateway timeout alert", occurred_at=now-timedelta(hours=5, minutes=20),
            details={"region": "ap-south-1", "signal": "HTTP 504", "ingestion": "buffered"})
        audit(db, p.id, owner.id, "demo.seeded", after={"incidents": len(incidents), "deployments": 3})
        db.commit()
