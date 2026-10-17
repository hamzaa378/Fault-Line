import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.main import app

@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    def override_db():
        with factory() as session: yield session
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()
    engine.dispose()

@pytest.fixture
def owner(client):
    r = client.post("/api/auth/register", json={"email": "owner@test.dev", "name": "Test Owner", "password": "LongPassword123!"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    head = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/projects", headers=head, json={"name": "Test System", "slug": "test-system"})
    assert r.status_code == 201, r.text
    return head, r.json()["id"]
