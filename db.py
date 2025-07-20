import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

engine = create_engine(os.getenv("DATABASE_URL"), pool_pre_ping=True)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, expire_on_commit=False)
)
