# models.py
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    JSON,
    Text,
)
from sqlalchemy.orm import declarative_base
from flask_login import UserMixin          # ← added
import bcrypt

Base = declarative_base()


class Candidate(Base):
    __tablename__ = "candidates"

    id            = Column(String,  primary_key=True)          # short uuid
    created_at    = Column(DateTime, default=datetime.utcnow)
    name          = Column(String)
    resume_url    = Column(String)                             # s3://bucket/key
    resume_json   = Column(JSON)
    realism       = Column(Boolean)
    fit_score     = Column(Integer)
    questions     = Column(JSON)        # list[str]
    answers       = Column(JSON)        # list[str]
    answer_scores = Column(JSON)        # list[int | "ERR"]


class JobDescription(Base):
    __tablename__ = "job_description"

    id   = Column(Integer, primary_key=True, default=1)
    html = Column(Text, nullable=False)


class User(Base, UserMixin):            # ← now inherits UserMixin
    __tablename__ = "users"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    pw_hash  = Column(String, nullable=False)

    # class‑method helper to create users with hashed passwords
    @classmethod
    def create(cls, session, username: str, plain_pw: str):
        pw_hash = bcrypt.hashpw(plain_pw.encode(), bcrypt.gensalt()).decode()
        user = cls(username=username, pw_hash=pw_hash)
        session.add(user)
        session.commit()
        return user

    # password check
    def check_pw(self, plain_pw: str) -> bool:
        return bcrypt.checkpw(plain_pw.encode(), self.pw_hash.encode())
