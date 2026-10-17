"""Source-of-truth models. Incident transitions and incoming events are explicitly audited."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def uid(): return str(uuid4())
def utcnow(): return datetime.now(timezone.utc)

def pk(): return mapped_column(String(36), primary_key=True, default=uid)
def stamp(): return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = pk()
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = stamp()

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = pk()
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = stamp()
    members: Mapped[list["Membership"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)
    id: Mapped[str] = pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship()

class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[str] = pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(100))
    environment: Mapped[str] = mapped_column(String(30), default="production")
    service: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="success")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    actor: Mapped[str] = mapped_column(String(120), default="")
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = stamp()
    __table_args__ = (Index("idx_deploy_project_time", "project_id", "deployed_at"),)

class CodeChange(Base):
    __tablename__ = "code_changes"
    __table_args__ = (UniqueConstraint("project_id", "sha", name="uq_project_sha"),)
    id: Mapped[str] = pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    sha: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(250))
    author: Mapped[str] = mapped_column(String(120))
    service: Mapped[str] = mapped_column(String(100), default="core")
    changed_files: Mapped[list] = mapped_column(JSON, default=list)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = stamp()

class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("idx_incident_project_seen", "project_id", "first_seen_at"),)
    id: Mapped[str] = pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    service: Mapped[str] = mapped_column(String(100), default="core")
    severity: Mapped[str] = mapped_column(String(10), default="SEV2")
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = stamp()
    updates: Mapped[list["IncidentUpdate"]] = relationship(back_populates="incident")

class IncidentUpdate(Base):
    __tablename__ = "incident_updates"
    id: Mapped[str] = pk()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = stamp()
    incident: Mapped[Incident] = relationship(back_populates="updates")
    author: Mapped[User] = relationship()

class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("project_id", "source", "external_id", name="uq_event_idempotency"),
        Index("idx_event_project_occurrence", "project_id", "occurred_at"),
    )
    id: Mapped[str] = pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(150))
    type: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(String(300))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = stamp()
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    digest: Mapped[str] = mapped_column(String(64))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = stamp()

class IncidentDeploymentLink(Base):
    __tablename__ = "incident_deployment_links"
    __table_args__ = (UniqueConstraint("incident_id", "deployment_id", name="uq_incident_deployment"),)
    id: Mapped[str] = pk()
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    linked_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = stamp()
