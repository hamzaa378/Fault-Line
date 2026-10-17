from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
# Email validation without extra email-validator dependency: validate modestly using regex in schema

class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_sqlite_datetime(cls, value):
        # SQLite strips timezone information; its stored times are always UTC.
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

def as_utc(dt: datetime):
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone (e.g. Z)")
    return dt.astimezone(timezone.utc)

class Register(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
class Login(BaseModel):
    email: str
    password: str
class UserOut(ORM):
    id: str
    email: str
    name: str
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(default="", max_length=2000)
class ProjectOut(ORM):
    id: str
    name: str
    slug: str
    description: str
    created_at: datetime
    role: str | None = None
class MemberIn(BaseModel):
    email: str
    role: Literal["maintainer", "responder", "viewer"]
class MemberOut(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
class DeploymentIn(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    environment: str = Field(default="production", max_length=30)
    service: str = Field(min_length=1, max_length=100)
    status: Literal["success", "failed", "in_progress", "rolled_back"] = "success"
    commit_sha: str = Field(default="", max_length=64)
    actor: str = Field(default="", max_length=120)
    deployed_at: datetime
    _dt = field_validator("deployed_at")(as_utc)
class DeploymentOut(ORM):
    id: str
    project_id: str
    version: str
    environment: str
    service: str
    status: str
    commit_sha: str
    actor: str
    deployed_at: datetime
    created_at: datetime
class ChangeIn(BaseModel):
    sha: str = Field(min_length=7, max_length=64, pattern=r"^[a-fA-F0-9]+$")
    title: str = Field(min_length=2, max_length=250)
    author: str = Field(min_length=1, max_length=120)
    service: str = Field(default="core", min_length=1, max_length=100)
    changed_files: list[str] = Field(default_factory=list, max_length=100)
    committed_at: datetime
    _dt = field_validator("committed_at")(as_utc)
class ChangeOut(ORM):
    id: str
    project_id: str
    sha: str
    title: str
    author: str
    service: str
    changed_files: list[str]
    committed_at: datetime
    created_at: datetime
class IncidentIn(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(default="", max_length=10000)
    service: str = Field(default="core", min_length=1, max_length=100)
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"] = "SEV2"
    first_seen_at: datetime
    assigned_to_id: str | None = None
    _dt = field_validator("first_seen_at")(as_utc)
class IncidentPatch(BaseModel):
    expected_version: int = Field(ge=1)
    status: Literal["open", "investigating", "mitigated", "resolved"] | None = None
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"] | None = None
    assigned_to_id: str | None = None
    resolution: str | None = Field(default=None, max_length=10000)
class IncidentOut(ORM):
    id: str
    project_id: str
    title: str
    description: str
    service: str
    severity: str
    status: str
    assigned_to_id: str | None
    first_seen_at: datetime
    resolved_at: datetime | None
    resolution: str
    version: int
    created_at: datetime
class UpdateIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
class UpdateOut(ORM):
    id: str
    incident_id: str
    author_id: str
    body: str
    created_at: datetime
    author_name: str = ""
class EventIn(BaseModel):
    source: Literal["cli", "ci", "monitor", "external"] = "external"
    external_id: str = Field(min_length=1, max_length=150)
    type: Literal["deployment", "change", "incident", "alert", "recovery", "note"]
    summary: str = Field(min_length=2, max_length=300)
    occurred_at: datetime
    details: dict = Field(default_factory=dict)
    _dt = field_validator("occurred_at")(as_utc)
class EventOut(ORM):
    id: str
    project_id: str
    source: str
    external_id: str
    type: str
    summary: str
    occurred_at: datetime
    received_at: datetime
    entity_type: str | None
    entity_id: str | None
    details: dict
class LinkIn(BaseModel):
    deployment_id: str
    reason: str = Field(default="", max_length=2000)
