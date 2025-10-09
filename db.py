# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # ET-12: Local default to sqlite dev.db when env is not configured
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'dev.db')}"

# SQLite requires special connect args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)

SessionLocal = scoped_session(
    sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)
)

# IMPORTANT: models.py imports this
Base = declarative_base()

__all__ = ["engine", "SessionLocal", "Base"]
