# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = scoped_session(
    sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)
)

# IMPORTANT: models.py imports this
Base = declarative_base()

__all__ = ["engine", "SessionLocal", "Base"]
