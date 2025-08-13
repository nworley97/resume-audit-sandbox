# models.py
import os
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean,
    DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.sql import func

# Single source of truth for Base/engine in this file
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    id       = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, nullable=False)
    pw_hash  = Column(String(256), nullable=False)

    # Flask-Login helpers
    def set_pw(self, pw):
        from werkzeug.security import generate_password_hash
        self.pw_hash = generate_password_hash(pw)

    def check_pw(self, pw):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.pw_hash, pw)

    @property
    def is_active(self): return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)


class JobDescription(Base):
    __tablename__ = "job_description"

    # Core fields
    code       = Column(String, primary_key=True)              # PK
    title      = Column(String, nullable=False, default="")
    html       = Column(Text,   nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Fields added by ensure_schema()
    status          = Column(String, nullable=False, default="draft")
    department      = Column(String, nullable=True)
    team            = Column(String, nullable=True)
    location        = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    salary_range    = Column(String, nullable=True)
    updated_at      = Column(DateTime(timezone=True), nullable=True)
    start_date      = Column(DateTime(timezone=True), nullable=True)
    end_date        = Column(DateTime(timezone=True), nullable=True)

    # Relationship to candidates
    candidates = relationship("Candidate", back_populates="job", lazy="selectin")


class Candidate(Base):
    __tablename__ = "candidate"

    id            = Column(String(8), primary_key=True)
    name          = Column(String(128), nullable=False)
    resume_url    = Column(String(512), nullable=False)
    resume_json   = Column(MutableDict.as_mutable(JSON), nullable=False)
    fit_score     = Column(Integer, nullable=False)
    realism       = Column(Boolean, default=False)
    questions     = Column(MutableList.as_mutable(JSON), nullable=False)
    answers       = Column(MutableList.as_mutable(JSON), nullable=True)
    answer_scores = Column(MutableList.as_mutable(JSON), nullable=True)

    jd_code    = Column(String(20), ForeignKey("job_description.code", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Explicit two-way relationship
    job = relationship("JobDescription", back_populates="candidates")


# Create tables if they don't exist (safe for local/dev; fine on Render too)
Base.metadata.create_all(engine)
