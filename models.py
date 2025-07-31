import os
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
import bcrypt
from flask_login import UserMixin

DATABASE_URL = os.getenv("DATABASE_URL")
engine       = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

class User(Base, UserMixin):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, index=True)
    username = Column(String(120), unique=True, nullable=False)
    pw_hash  = Column(String(128), nullable=False)

    @classmethod
    def create(cls, db, username: str, password: str):
        user = cls(
            username=username,
            pw_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        )
        db.add(user)
        db.commit()
        return user

    def check_pw(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.pw_hash.encode())

class JobDescription(Base):
    __tablename__ = "job_description"
    id         = Column(Integer, primary_key=True)  
    code       = Column(String(20), unique=True, nullable=False)
    slug       = Column(String(120), unique=True, nullable=False)
    title      = Column(String(120), nullable=False)
    html       = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    # optional: applications relationship
    candidates = relationship("Candidate", back_populates="job")

class Candidate(Base):
    __tablename__ = "candidate"
    id           = Column(String(8), primary_key=True, index=True)
    name         = Column(String(120), nullable=False)
    resume_url   = Column(String(500), nullable=False)
    resume_json  = Column(JSON, nullable=False)
    fit_score    = Column(Integer, nullable=False)
    realism      = Column(Integer, nullable=True)
    jd_code      = Column(String(20), ForeignKey("job_description.code"), nullable=True)
    created_at   = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    job = relationship("JobDescription", back_populates="candidates")
