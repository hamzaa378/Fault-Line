"""Verified GitHub event projection into Faultline records without schema changes.

The GitHub event remains the append-only evidence source. Only a narrow set of
validated push/deployment_status fields becomes domain data; never trust the
entire webhook payload as a database object.
"""
import os
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import CodeChange, Deployment, utcnow, uid

_SHA = re.compile(r"^[a-fA-F0-9]{12,64}$")


def optional_repo_binding(repo: str, project_id: str) -> None:
    """Optional single-project and repository bindings for an exposed receiver."""
    expected_project = os.getenv("GITHUB_PROJECT_ID", "").strip()
    if expected_project and project_id != expected_project:
        raise HTTPException(403, "GitHub webhook not enabled for this project")
    allowed = {r.strip().lower() for r in os.getenv("GITHUB_ALLOWED_REPOSITORIES", "").split(",") if r.strip()}
    if allowed and repo.lower() not in allowed:
        raise HTTPException(403, "Repository not permitted for GitHub webhook")


def timestamp_or(value, default: datetime) -> datetime:
    if not isinstance(value, str) or not value:
        return default
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return default


def _service_name(value: object) -> str:
    default = os.getenv("GITHUB_DEFAULT_SERVICE", "core")
    service = value if isinstance(value, str) and value.strip() else default
    return str(service).strip()[:100] or "core"


def project_push(db: Session, project_id: str, payload: dict, occurred: datetime) -> list[str]:
    """Store actual commit metadata, with a unique key per project/SHA.

    GitHub push deliveries may truncate their commits list; we only project
    commits present in the verified payload and document partial coverage.
    """
    commits = payload.get("commits", [])
    if not isinstance(commits, list):
        return []
    created = []
    for commit in commits[:100]:
        if not isinstance(commit, dict):
            continue
        sha = str(commit.get("id", "")).lower()
        if not _SHA.fullmatch(sha):
            continue
        files = []
        for key in ("added", "removed", "modified"):
            paths = commit.get(key, [])
            if isinstance(paths, list):
                files += [v[:500] for v in paths if isinstance(v, str) and v.strip()]
        files = list(dict.fromkeys(files))[:200]
        author_obj = commit.get("author") or {}
        author_name = author_obj.get("name", "") if isinstance(author_obj, dict) else ""
        title = str(commit.get("message") or "GitHub commit " + sha[:12]).splitlines()[0][:250]
        record = dict(id=uid(), project_id=project_id, sha=sha, title=title,
                      author=str(author_name or "GitHub")[:120],
                      service=_service_name(None), changed_files=files,
                      committed_at=timestamp_or(commit.get("timestamp"), occurred),
                      created_at=utcnow())
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            stmt = pg_insert(CodeChange).values(**record).on_conflict_do_nothing(
                index_elements=["project_id", "sha"])
            if db.execute(stmt).rowcount:
                created.append(sha)
        elif dialect == "sqlite":
            stmt = sqlite_insert(CodeChange).values(**record).on_conflict_do_nothing(
                index_elements=["project_id", "sha"])
            if db.execute(stmt).rowcount:
                created.append(sha)
        else:
            if not db.query(CodeChange).filter_by(project_id=project_id, sha=sha).first():
                db.add(CodeChange(**record))
                db.flush()
                created.append(sha)
    return created


def project_deployment_status(db: Session, project_id: str, payload: dict, occurred: datetime) -> str | None:
    """Store terminal GitHub deployment-status outcomes, not pending states.

    One domain row per successfully handled *delivery*; repeated delivery ID
    is prevented at the evidence boundary. Different genuine status deliveries
    are retained as distinct historical observations.
    """
    status = payload.get("deployment_status") or {}
    dep = payload.get("deployment") or {}
    if not isinstance(status, dict) or not isinstance(dep, dict):
        return None
    raw_state = status.get("state")
    mapped = {"success": "success", "failure": "failed", "error": "failed"}.get(raw_state)
    if not mapped or dep.get("id") is None:
        return None
    sha = str(dep.get("sha") or "")[:64]
    ref = str(dep.get("ref") or "")[:100]
    environmental = str(dep.get("environment") or "production")[:30]
    data = dep.get("payload") or {}
    if not isinstance(data, dict):
        data = {}
    service = _service_name(data.get("service"))
    deployment = Deployment(project_id=project_id,
        version=ref or (sha[:12] if sha else f"github-{dep['id']}"),
        environment=environmental, service=service, status=mapped,
        commit_sha=sha, actor="GitHub Actions / GitHub Deployment",
        deployed_at=timestamp_or(status.get("created_at"), occurred))
    db.add(deployment)
    db.flush()
    return deployment.id
