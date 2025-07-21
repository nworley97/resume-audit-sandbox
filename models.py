from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, Text
)
from sqlalchemy.orm import declarative_base
from flask_login import UserMixin
import bcrypt

Base = declarative_base()

# ─────────── Candidate ───────────────────────────────────────────
class Candidate(Base):
    __tablename__ = "candidates"

    id            = Column(String, primary_key=True)            # short UUID
    created_at    = Column(DateTime, default=datetime.utcnow)
    name          = Column(String, nullable=False)
    resume_url    = Column(String, nullable=False)              # s3://… or local path
    resume_json   = Column(JSON)
    realism       = Column(Boolean)
    fit_score     = Column(Integer)
    jd_code       = Column(String)                              # links to JobDescription.code
    questions     = Column(JSON)        # kept for future use
    answers       = Column(JSON)
    answer_scores = Column(JSON)

# ─────────── Job Description ─────────────────────────────────────
class JobDescription(Base):
    __tablename__ = "job_description"

    id   = Column(Integer, primary_key=True, default=1)
    code = Column(String, nullable=False)   # e.g. JD01
    html = Column(Text,    nullable=False)

# ─────────── User accounts (recruiter login) ─────────────────────
class User(Base, UserMixin):
    __tablename__ = "users"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    pw_hash  = Column(String, nullable=False)

    # helper to create user with hashed password
    @classmethod
    def create(cls, session, username: str, plain_pw: str):
        pw_hash = bcrypt.hashpw(plain_pw.encode(), bcrypt.gensalt()).decode()
        user = cls(username=username, pw_hash=pw_hash)
        session.add(user)
        session.commit()
        return user

    def check_pw(self, plain_pw: str) -> bool:
        return bcrypt.checkpw(plain_pw.encode(), self.pw_hash.encode())
