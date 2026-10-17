import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Membership

SECRET = os.getenv("JWT_SECRET", "LOCAL-DEV-ONLY-CHANGE-THIS-SECRET")
ALG = "HS256"
ph = PasswordHasher(time_cost=2, memory_cost=32768, parallelism=2)
bearer = HTTPBearer(auto_error=False)

def hash_password(p: str) -> str: return ph.hash(p)
def verify_password(hash_: str, password: str) -> bool:
    try: return ph.verify(hash_, password)
    except (VerifyMismatchError, InvalidHashError): return False

def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + timedelta(hours=12)}, SECRET, algorithm=ALG)

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=[ALG])
        user = db.get(User, payload["sub"])
        if user: return user
    except (jwt.InvalidTokenError, KeyError): pass
    raise HTTPException(401, "Invalid or expired token")

ROLE_LEVEL = {"viewer": 0, "responder": 1, "maintainer": 2, "owner": 3}

def require_member(db: Session, project_id: str, user: User, min_role: str = "viewer") -> Membership:
    member = db.query(Membership).filter_by(project_id=project_id, user_id=user.id).first()
    # deliberately return 404 instead of revealing the existence of a private project
    if not member: raise HTTPException(404, "Project not found")
    if ROLE_LEVEL[member.role] < ROLE_LEVEL[min_role]: raise HTTPException(403, "Insufficient project permissions")
    return member
