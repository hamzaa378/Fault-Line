"""Faultline API. Run uvicorn app.main:app --reload in backend/."""
import hashlib, hmac, json, os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from .models import User, Project, Membership, Deployment, CodeChange, Incident, IncidentUpdate, Event, AuditLog, IncidentDeploymentLink, uid, utcnow
from .schemas import (Register, Login, TokenOut, UserOut, ProjectIn, ProjectOut, MemberIn, MemberOut,
                      DeploymentIn, DeploymentOut, ChangeIn, ChangeOut, IncidentIn, IncidentPatch,
                      IncidentOut, UpdateIn, UpdateOut, EventIn, EventOut, LinkIn)
from .auth import hash_password, verify_password, create_token, current_user, require_member
from .events import append_event, internal_event, audit, aware
from .insights import suspects, recurring

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_DEMO", "false").lower() == "true":
        from .seed import seed_demo
        seed_demo()
    yield

app = FastAPI(title="Faultline API", version="1.0.0", description="Evidence-first incident and deployment tracking", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=[s.strip() for s in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")],
    allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"])

def project_or_404(db: Session, project_id: str, user: User, role="viewer"):
    membership = require_member(db, project_id, user, role)
    obj = db.get(Project, project_id)
    if not obj: raise HTTPException(404, "Project not found")
    return obj, membership

def incident_or_404(db: Session, pid: str, iid: str):
    item = db.get(Incident, iid)
    if not item or item.project_id != pid: raise HTTPException(404, "Incident not found")
    return item

def member_exists(db: Session, pid: str, user_id: str):
    if not db.query(Membership).filter_by(project_id=pid, user_id=user_id).first():
        raise HTTPException(422, "Assigned user is not a member of this project")

def commit(db):
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A record with these unique values already exists")

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "1.0.0", "database": "reachable"}

@app.post("/api/auth/register", response_model=TokenOut, status_code=201, tags=["auth"])
def register(body: Register, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409, "Email already registered")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user); commit(db); db.refresh(user)
    return {"access_token": create_token(user.id), "user": user}

@app.post("/api/auth/login", response_model=TokenOut, tags=["auth"])
def login(body: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.lower().strip()).first()
    if not user or not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(user.id), "user": user}

@app.get("/api/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(current_user)): return user

@app.get("/api/projects", response_model=list[ProjectOut], tags=["projects"])
def list_projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Project, Membership).join(Membership, Membership.project_id == Project.id).filter(Membership.user_id == user.id).order_by(Project.created_at.desc()).all()
    return [dict(id=p.id, name=p.name, slug=p.slug, description=p.description, created_at=p.created_at, role=m.role) for p,m in rows]

@app.post("/api/projects", response_model=ProjectOut, status_code=201, tags=["projects"])
def create_project(body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if db.query(Project).filter_by(slug=body.slug).first():
        raise HTTPException(409, "Project slug already exists")
    project = Project(**body.model_dump()); db.add(project)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Project slug already exists")
    db.add(Membership(project_id=project.id, user_id=user.id, role="owner"))
    audit(db, project.id, user.id, "project.created", after={"name": project.name})
    commit(db); db.refresh(project)
    return dict(id=project.id, name=project.name, slug=project.slug, description=project.description, created_at=project.created_at, role="owner")

@app.get("/api/projects/{pid}", response_model=ProjectOut, tags=["projects"])
def get_project(pid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p, membership = project_or_404(db, pid, user)
    return dict(id=p.id, name=p.name, slug=p.slug, description=p.description, created_at=p.created_at, role=membership.role)

@app.get("/api/projects/{pid}/members", response_model=list[MemberOut], tags=["projects"])
def members(pid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    rows = db.query(Membership, User).join(User, Membership.user_id == User.id).filter(Membership.project_id == pid).all()
    return [dict(user_id=u.id, email=u.email, name=u.name, role=m.role) for m,u in rows]

@app.post("/api/projects/{pid}/members", response_model=MemberOut, status_code=201, tags=["projects"])
def add_member(pid: str, body: MemberIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "owner")
    target = db.query(User).filter_by(email=body.email.lower().strip()).first()
    if not target: raise HTTPException(404, "User must register before being added")
    existing = db.query(Membership).filter_by(project_id=pid, user_id=target.id).first()
    if existing: raise HTTPException(409, "Already a project member")
    db.add(Membership(project_id=pid, user_id=target.id, role=body.role))
    audit(db, pid, user.id, "member.added", after={"email": target.email, "role": body.role})
    commit(db)
    return {"user_id": target.id, "email": target.email, "name": target.name, "role": body.role}

@app.get("/api/projects/{pid}/deployments", response_model=list[DeploymentOut], tags=["deployments"])
def list_deployments(pid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    return db.query(Deployment).filter_by(project_id=pid).order_by(Deployment.deployed_at.desc()).limit(200).all()

@app.post("/api/projects/{pid}/deployments", response_model=DeploymentOut, status_code=201, tags=["deployments"])
def create_deployment(pid: str, body: DeploymentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "maintainer")
    dep = Deployment(project_id=pid, **body.model_dump()); db.add(dep); db.flush()
    internal_event(db, pid, "deployment", f"{dep.version} deployed to {dep.environment}", dep.deployed_at,
                   "deployment", dep.id, {"service": dep.service, "status": dep.status, "commit_sha": dep.commit_sha})
    audit(db, pid, user.id, "deployment.created", after={"id": dep.id, "version": dep.version})
    commit(db); db.refresh(dep); return dep

@app.get("/api/projects/{pid}/changes", response_model=list[ChangeOut], tags=["changes"])
def list_changes(pid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    return db.query(CodeChange).filter_by(project_id=pid).order_by(CodeChange.committed_at.desc()).limit(200).all()

@app.post("/api/projects/{pid}/changes", response_model=ChangeOut, status_code=201, tags=["changes"])
def create_change(pid: str, body: ChangeIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "maintainer")
    if db.query(CodeChange).filter_by(project_id=pid, sha=body.sha).first():
        raise HTTPException(409, "Commit SHA already recorded in this project")
    change = CodeChange(project_id=pid, **body.model_dump()); db.add(change)
    try: db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Commit SHA already recorded in this project")
    internal_event(db, pid, "change", change.title, change.committed_at, "change", change.id,
                   {"sha": change.sha, "service": change.service, "files": change.changed_files})
    audit(db, pid, user.id, "change.recorded", after={"sha": change.sha})
    commit(db); db.refresh(change); return change

@app.get("/api/projects/{pid}/incidents", response_model=list[IncidentOut], tags=["incidents"])
def list_incidents(pid: str, status: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    q = db.query(Incident).filter_by(project_id=pid)
    if status: q = q.filter(Incident.status == status)
    return q.order_by(Incident.first_seen_at.desc()).limit(200).all()

@app.post("/api/projects/{pid}/incidents", response_model=IncidentOut, status_code=201, tags=["incidents"])
def create_incident(pid: str, body: IncidentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "responder")
    if body.assigned_to_id: member_exists(db, pid, body.assigned_to_id)
    inc = Incident(project_id=pid, **body.model_dump()); db.add(inc); db.flush()
    internal_event(db, pid, "incident", f"{inc.severity}: {inc.title}", inc.first_seen_at, "incident", inc.id,
                   {"service": inc.service, "severity": inc.severity})
    audit(db, pid, user.id, "incident.created", inc.id, after={"status": inc.status, "severity": inc.severity})
    commit(db); db.refresh(inc); return inc

@app.get("/api/projects/{pid}/incidents/{iid}", response_model=IncidentOut, tags=["incidents"])
def get_incident(pid: str, iid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    return incident_or_404(db, pid, iid)

@app.patch("/api/projects/{pid}/incidents/{iid}", response_model=IncidentOut, tags=["incidents"])
def patch_incident(pid: str, iid: str, body: IncidentPatch, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "responder")
    inc = incident_or_404(db, pid, iid)
    if inc.version != body.expected_version: raise HTTPException(409, "Incident was updated by another user; refresh before retrying")
    changes = body.model_dump(exclude_unset=True, exclude={"expected_version"})
    if any(key in changes and changes[key] is None for key in ("status", "severity", "resolution")):
        raise HTTPException(422, "Status, severity and resolution cannot be null")
    if not changes: return inc
    if "assigned_to_id" in changes and changes["assigned_to_id"]: member_exists(db, pid, changes["assigned_to_id"])
    new_status = changes.get("status", inc.status)
    new_resolution = changes.get("resolution", inc.resolution)
    if new_status == "resolved" and not new_resolution.strip():
        raise HTTPException(422, "Resolution details are required to resolve an incident")
    if "status" in changes:
        changes["resolved_at"] = utcnow() if new_status == "resolved" else None
    before = {k: getattr(inc, k) for k in changes if k != "resolved_at"}
    # DB atomic compare-and-swap; independent append-only notes do not bump version.
    stmt = sql_update(Incident).where(Incident.id == iid, Incident.project_id == pid,
                                      Incident.version == body.expected_version).values(**changes, version=body.expected_version+1)
    result = db.execute(stmt)
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Concurrent incident change detected; refresh before retrying")
    audit(db, pid, user.id, "incident.updated", iid, before=before, after={k: str(v) if isinstance(v, datetime) else v for k,v in changes.items()})
    internal_event(db, pid, "note", f"Incident updated by {user.name}: {', '.join(changes)}", utcnow(), "incident", iid,
                   {"changed_fields": sorted(changes)})
    commit(db); db.expire_all(); return incident_or_404(db, pid, iid)

@app.get("/api/projects/{pid}/incidents/{iid}/updates", response_model=list[UpdateOut], tags=["incidents"])
def list_updates(pid: str, iid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user); incident_or_404(db, pid, iid)
    rows = db.query(IncidentUpdate, User).join(User, IncidentUpdate.author_id == User.id).filter(IncidentUpdate.incident_id == iid).order_by(IncidentUpdate.created_at.asc()).all()
    return [{"id": n.id, "incident_id": n.incident_id, "author_id": n.author_id,
             "body": n.body, "created_at": n.created_at, "author_name": u.name} for n,u in rows]

@app.post("/api/projects/{pid}/incidents/{iid}/updates", response_model=UpdateOut, status_code=201, tags=["incidents"])
def add_update(pid: str, iid: str, body: UpdateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "responder"); incident_or_404(db, pid, iid)
    note = IncidentUpdate(incident_id=iid, author_id=user.id, body=body.body)
    db.add(note); db.flush()
    internal_event(db, pid, "note", f"{user.name}: {body.body[:120]}", utcnow(), "incident", iid, {"update_id": note.id})
    audit(db, pid, user.id, "incident.note_added", iid, after={"update_id": note.id})
    commit(db); db.refresh(note)
    return {"id": note.id, "incident_id": iid, "author_id": user.id,
            "body": note.body, "created_at": note.created_at, "author_name": user.name}

@app.post("/api/projects/{pid}/incidents/{iid}/links", status_code=201, tags=["insights"])
def link_deployment(pid: str, iid: str, body: LinkIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "responder"); incident_or_404(db, pid, iid)
    dep = db.get(Deployment, body.deployment_id)
    if not dep or dep.project_id != pid: raise HTTPException(404, "Deployment not found")
    obj = IncidentDeploymentLink(incident_id=iid, deployment_id=dep.id, reason=body.reason, linked_by_id=user.id)
    db.add(obj)
    audit(db, pid, user.id, "incident.deployment_linked", iid, after={"deployment_id": dep.id, "reason": body.reason})
    commit(db)
    return {"id": obj.id, "deployment_id": dep.id, "reason": body.reason}

@app.get("/api/projects/{pid}/incidents/{iid}/links", tags=["insights"])
def links(pid: str, iid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user); incident_or_404(db, pid, iid)
    return [{"id": r.id, "deployment_id": r.deployment_id, "reason": r.reason}
            for r in db.query(IncidentDeploymentLink).filter_by(incident_id=iid).all()]

@app.get("/api/projects/{pid}/incidents/{iid}/suspects", tags=["insights"])
def incident_suspects(pid: str, iid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    inc = incident_or_404(db, pid, iid)
    return {"incident_id": iid, "method": "Transparent temporal + service + commit heuristic v1",
            "disclaimer": "These are investigation leads, not causal conclusions.", "candidates": suspects(db, inc)}

@app.get("/api/projects/{pid}/events", response_model=list[EventOut], tags=["timeline"])
def list_events(pid: str, order: str = Query("occurred", pattern="^(occurred|received)$"),
                limit: int = Query(150, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    sort = Event.occurred_at if order == "occurred" else Event.received_at
    return db.query(Event).filter_by(project_id=pid).order_by(sort.desc(), Event.id.desc()).limit(limit).all()

@app.post("/api/projects/{pid}/events/ingest", tags=["timeline"])
def ingest_event(pid: str, body: EventIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "maintainer")
    ev, duplicate = append_event(db, pid, source=body.source, external_id=body.external_id,
                                 type_=body.type, summary=body.summary, occurred_at=body.occurred_at, details=body.details)
    if not duplicate: audit(db, pid, user.id, "event.ingested", after={"event_id": ev.id, "source": body.source})
    commit(db)
    return {"id": ev.id, "duplicate": duplicate, "occurred_at": ev.occurred_at, "received_at": ev.received_at}

@app.get("/api/projects/{pid}/audit", tags=["audit"])
def list_audit(pid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user, "maintainer")
    logs = db.query(AuditLog).filter_by(project_id=pid).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [{"id": a.id, "action": a.action, "actor_id": a.actor_id, "incident_id": a.incident_id,
             "before": a.before, "after": a.after, "created_at": a.created_at} for a in logs]

@app.get("/api/projects/{pid}/dashboard", tags=["insights"])
def dashboard(pid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project_or_404(db, pid, user)
    all_incidents = db.query(Incident).filter_by(project_id=pid).all()
    deployments = db.query(Deployment).filter_by(project_id=pid).all()
    active = [i for i in all_incidents if i.status != "resolved"]
    return {"incidents_total": len(all_incidents), "active_incidents": len(active),
            "critical_open": sum(i.severity == "SEV1" for i in active),
            "deployments_total": len(deployments), "failed_deployments": sum(d.status == "failed" for d in deployments),
            "recurring": recurring(db, pid), "by_severity": {s: sum(i.severity == s for i in all_incidents) for s in ("SEV1", "SEV2", "SEV3", "SEV4")},
            "by_status": {s: sum(i.status == s for i in all_incidents) for s in ("open", "investigating", "mitigated", "resolved")}}

@app.post("/api/webhooks/github/{pid}", tags=["webhooks"])
async def github_webhook(pid: str, request: Request, db: Session = Depends(get_db)):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret: raise HTTPException(503, "GitHub webhook secret not configured")
    payload_bytes = await request.body()
    if len(payload_bytes) > 131072: raise HTTPException(413, "Webhook payload too large")
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected): raise HTTPException(401, "Invalid GitHub webhook signature")
    if not db.get(Project, pid): raise HTTPException(404, "Project not found")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    if not delivery_id: raise HTTPException(400, "Missing delivery ID")
    event_type = request.headers.get("X-GitHub-Event", "ping")
    raw_digest = hashlib.sha256(event_type.encode() + b"\n" + payload_bytes).hexdigest()
    previously_seen = db.query(Event).filter_by(project_id=pid, source="github", external_id=delivery_id).first()
    if previously_seen:
        if previously_seen.details.get("payload_sha256") != raw_digest:
            raise HTTPException(409, "GitHub delivery ID reused for a different payload")
        return {"accepted": True, "duplicate": True, "event_id": previously_seen.id}
    try: payload = json.loads(payload_bytes)
    except (ValueError, UnicodeDecodeError): raise HTTPException(400, "Invalid JSON")
    repo = payload.get("repository", {}).get("full_name", "unknown")
    if event_type == "push":
        record_type = "change"
        summary = f"Push to {repo}: {payload.get('ref', 'unknown')}"
        timestamp = (payload.get("head_commit") or {}).get("timestamp")
    elif event_type in ("deployment", "deployment_status"):
        record_type = "deployment"
        summary = f"{event_type} on {repo}"
        timestamp = payload.get("deployment", {}).get("created_at")
    else:
        record_type = "note"; summary = f"GitHub {event_type} on {repo}"; timestamp = None
    try: occurred = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else utcnow()
    except (TypeError, ValueError): occurred = utcnow()
    if occurred.tzinfo is None: occurred = occurred.replace(tzinfo=timezone.utc)
    details = {"github_event": event_type, "repository": repo,
               "ref": str(payload.get("ref", "")), "head_sha": str(payload.get("after", "")), "payload_sha256": raw_digest}
    ev, duplicate = append_event(db, pid, source="github", external_id=delivery_id, type_=record_type,
                                 summary=summary, occurred_at=occurred, details=details)
    if not duplicate: audit(db, pid, None, "github.webhook_received", after={"event_id": ev.id, "kind": event_type})
    commit(db)
    return {"accepted": True, "duplicate": duplicate, "event_id": ev.id}
