"""Database configuration. PostgreSQL in Compose, SQLite only for local quick starts/tests."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///./faultline.db")
engine = create_engine(
    URL, pool_pre_ping=True, pool_size=5 if not URL.startswith("sqlite") else 5,
    connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
