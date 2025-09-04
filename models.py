# models.py
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from werkzeug.security import generate_password_hash, check_password_hash

# Use the same Base/engine your app already relies on
from db import Base, engine as engine  # engine is imported for ensure_schema() in app.py


class Tenant(Base):
    __tablename__ = "tenant"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)   # email for tenant users; "Altera" for super
    pw_hash = Column(String, nullable=False)
    is_super = Column(Boolean, default=False)

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant = relationship("Tenant")

    def set_pw(self, pw: str) -> None:
        self.pw_hash = generate_password_hash(pw)

    def check_pw(self, pw: str) -> bool:
        return check_password_hash(self.pw_hash, pw)


class JobDescription(Base):
    __tablename__ = "job_description"
    id = Column(Integer, primary_key=True)

    # App uses code as the external identifier and FK target
    code = Column(String(20), unique=True, nullable=False)

    title = Column(String(200), nullable=False)
    html = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # These columns are created/kept in ensure_schema() too; defined here for ORM completeness
    status = Column(String, nullable=True)             # e.g. "draft", "published", "open", "closed"
    department = Column(String, nullable=True)
    team = Column(String, nullable=True)
    location = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    salary_range = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)

    # NEW: per-JD controls (defaults preserve current behavior)
    id_surveys_enabled = Column(Boolean, default=True)  # toggle veteran/disability surveys
    question_count = Column(Integer, default=4)         # 1..5 questions

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant = relationship("Tenant")


class Candidate(Base):
    __tablename__ = "candidate"

    # IMPORTANT: your app uses 8-char UUID strings and ilike() searches on id
    id = Column(String(32), primary_key=True)

    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)

    resume_url = Column(String(512), nullable=False)
    resume_json = Column(MutableDict.as_mutable(JSON), nullable=False)

    fit_score = Column(Integer, nullable=False)
    realism = Column(Boolean, default=False)

    # LLM question/answer payloads
    questions = Column(MutableList.as_mutable(JSON), nullable=False)
    answers = Column(MutableList.as_mutable(JSON), nullable=True)
    answer_scores = Column(MutableList.as_mutable(JSON), nullable=True)

    # Link to JD by code (your app queries on Candidate.jd_code == JobDescription.code)
    jd_code = Column(String(20), ForeignKey("job_description.code", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # NEW: lightweight anti-cheat signal (tab/window switches during Q&A)
    left_tab_count = Column(Integer, default=0)

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant = relationship("Tenant")
