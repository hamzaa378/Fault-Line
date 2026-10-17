"""Transparent candidate scoring; correlation is not causation."""
import re
from datetime import timedelta
from sqlalchemy.orm import Session
from .models import Incident, Deployment, CodeChange
from .events import aware

def suspects(db: Session, incident: Incident, limit: int = 6):
    start = aware(incident.first_seen_at) - timedelta(hours=24)
    stop = aware(incident.first_seen_at) + timedelta(minutes=3)
    deployments = db.query(Deployment).filter(Deployment.project_id == incident.project_id).all()
    candidates = []
    for d in deployments:
        when = aware(d.deployed_at)
        if not start <= when <= stop: continue
        minutes = (aware(incident.first_seen_at) - when).total_seconds() / 60
        # A 3-minute clock skew grace; future deployments are not silently ignored
        temporal = max(0, round(38 * (1 - max(0, minutes) / 1440)))
        service = 37 if d.service.casefold() == incident.service.casefold() else 0
        outcome = 10 if d.status in ("success", "failed") else 0
        matching_change = None
        if d.commit_sha:
            matching_change = db.query(CodeChange).filter_by(project_id=incident.project_id, sha=d.commit_sha).first()
        change = 15 if matching_change and matching_change.service.casefold() == incident.service.casefold() else 0
        score = min(100, temporal + service + outcome + change)
        reasons = [f"Deployment {abs(round(minutes))} min {'before' if minutes >= 0 else 'after'} first symptom"]
        if service: reasons.append("Same affected service")
        if outcome: reasons.append(f"Deployment outcome: {d.status}")
        if change: reasons.append("Matching commit and service in change history")
        candidates.append({"deployment_id": d.id, "version": d.version, "service": d.service,
                           "deployed_at": d.deployed_at.isoformat(), "score": score,
                           "reasons": reasons, "commit_sha": d.commit_sha,
                           "note": "Heuristic lead only; not proof of causality"})
    candidates.sort(key=lambda c: (-c["score"], c["deployment_id"]))
    return candidates[:limit]

def recurring(db: Session, project_id: str):
    incidents = db.query(Incident).filter_by(project_id=project_id).all()
    signatures = {}
    for inc in incidents:
        name = re.sub(r"\b\d+\b", "#", inc.title.casefold())
        name = re.sub(r"[^a-z0-9#]+", " ", name).strip()
        key = (inc.service.casefold(), name)
        signatures.setdefault(key, []).append(inc.id)
    return [{"service": key[0], "signature": key[1], "count": len(ids), "incident_ids": ids}
            for key, ids in signatures.items() if len(ids) > 1]
