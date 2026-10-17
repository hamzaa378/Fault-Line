"""Append-only timeline with dual clocks and exactly-once identity at the DB boundary."""
import json, hashlib
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .models import Event, AuditLog, utcnow, uid

def aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def canonical_digest(type_: str, summary: str, at: datetime, details: dict) -> str:
    obj = {"type": type_, "summary": summary, "occurred_at": aware(at).isoformat(), "details": details}
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

def append_event(db: Session, project_id: str, *, source: str, external_id: str, type_: str,
                 summary: str, occurred_at: datetime, details: dict | None = None,
                 entity_type: str | None = None, entity_id: str | None = None) -> tuple[Event, bool]:
    details = details or {}
    digest = canonical_digest(type_, summary, occurred_at, details)
    existing = db.query(Event).filter_by(project_id=project_id, source=source, external_id=external_id).first()
    if existing:
        if existing.digest != digest and not (existing.details.get("payload_sha256") and existing.details.get("payload_sha256") == details.get("payload_sha256")):
            raise HTTPException(409, "Event ID reused with conflicting payload")
        return existing, True
    event = Event(project_id=project_id, source=source, external_id=external_id, type=type_,
                  summary=summary, occurred_at=aware(occurred_at), details=details, digest=digest,
                  entity_type=entity_type, entity_id=entity_id)
    db.add(event)
    try: db.flush()
    except IntegrityError:
        # a concurrent request won the uniqueness race; roll back current transaction
        db.rollback()
        existing = db.query(Event).filter_by(project_id=project_id, source=source, external_id=external_id).first()
        if existing and (existing.digest == digest or (existing.details.get("payload_sha256") and existing.details.get("payload_sha256") == details.get("payload_sha256"))): return existing, True
        raise HTTPException(409, "Event ID reused with conflicting payload")
    return event, False

def internal_event(db: Session, project_id: str, type_: str, summary: str,
                   occurred_at: datetime, entity_type: str, entity_id: str, details: dict | None = None):
    return append_event(db, project_id, source="app", external_id=uid(), type_=type_, summary=summary,
                        occurred_at=occurred_at, entity_type=entity_type, entity_id=entity_id, details=details)

def audit(db: Session, project_id: str, actor_id: str | None, action: str,
          incident_id: str | None = None, before: dict | None = None, after: dict | None = None):
    db.add(AuditLog(project_id=project_id, actor_id=actor_id, action=action,
                    incident_id=incident_id, before=before or {}, after=after or {}))
