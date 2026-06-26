"""
ThreatTron AI — Database Engine & Session Factory
===================================================
Supports SQLite (default) and MySQL (via DATABASE_URL env var).
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Always resolve DB path relative to this file so it works regardless of
# which directory the server is launched from.
_HERE = Path(__file__).resolve().parent          # .../Hck/backend/
_DEFAULT_DB = _HERE / "threattron.db"            # .../Hck/backend/threattron.db

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{_DEFAULT_DB}",
)

# SQLite needs check_same_thread=False for FastAPI's async workers
connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables that don't already exist."""
    import backend.models  # noqa: F401 — ensure models are imported before create_all
    Base.metadata.create_all(bind=engine)
