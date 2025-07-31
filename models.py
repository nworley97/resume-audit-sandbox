# models.py  –  SQLAlchemy ORM definitions
# ---------------------------------------------------
import bcrypt, json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, JSON
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ─────────────── Helper mixin for password hashing ──────────────
class PWMixin:
    pw_hash = Column(String)

    def set_pw(self, raw: str):
        self.pw_hash = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()

    def check_pw(self, raw: str) -> bool:
        if not self.pw_hash:
            return False
        return bcrypt.checkpw(raw.encode(), self.pw_hash.encode())

# ─────────────────────────  Tables  ─────────────────────────────
from flask_login import UserMixin

class User(Base, PWMixin, UserMixin):
    __tablename__ = "user"
    id       = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)

class JobDescription(Base):
    __tablename__ = "job_description"
    id    = Column(Integer, primary_key=True, autoincrement=True)
    code  = Column(String, unique=True, index=True)    # internal ID
    slug  = Column(String, unique=True, index=True)    # public URL slug
    title = Column(String, default="")
    html  = Column(Text)

class Candidate(Base):
    __tablename__ = "candidate"
    id            = Column(String, primary_key=True)   # 8-char uuid
    jd_code       = Column(String, index=True)         # ties back to JobDescription.code
    name          = Column(String)
    resume_url    = Column(String)
    resume_json   = Column(JSON)
    fit_score     = Column(Integer)
    realism       = Column(Boolean)
    questions     = Column(JSON)                       # list[str]
    answers       = Column(JSON)                       # list[str]
    answer_scores = Column(JSON)                       # list[int]
    created_at    = Column(DateTime, default=datetime.utcnow)
