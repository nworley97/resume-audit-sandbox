# models.py
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, Text, Time
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Base and engine come from db.py
from db import Base, engine as engine


class Tenant(Base):
    __tablename__ = "tenant"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class User(Base, UserMixin):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True)   # email or "Altera"
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
    code = Column(String(20), unique=True, nullable=False)

    title = Column(String(200), nullable=False)
    # ET-23: Raw Markdown (source of truth) and sanitized HTML (rendered)
    markdown = Column(Text, nullable=True)
    html = Column(Text, nullable=True)
    markdown = Column(Text, nullable=True) # job description in markdown format
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Columns also checked by ensure_schema()
    status = Column(String, nullable=True)
    department = Column(String, nullable=True)
    team = Column(String, nullable=True)
    location = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    salary_range = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    start_time = Column(Time, nullable=True) # 2025-10-01: added (Jen)
    end_time = Column(Time, nullable=True) # 2025-10-01: added (Jen)
    work_arrangement = Column(String, nullable=True) # 2025-10-01: added (Jen)

    # NEW controls
    id_surveys_enabled = Column(Boolean, default=True)   # toggle surveys
    question_count = Column(Integer, default=4)          # 1–5 questions

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant = relationship("Tenant")


class Candidate(Base):
    __tablename__ = "candidate"

    # IMPORTANT: Candidate IDs are 8-char strings in app.py
    id = Column(String(32), primary_key=True)

    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)

    resume_url = Column(String(512), nullable=False)
    resume_json = Column(MutableDict.as_mutable(JSON), nullable=False)

    fit_score = Column(Integer, nullable=False)
    realism = Column(Boolean, default=False)

    questions = Column(MutableList.as_mutable(JSON), nullable=False)
    answers = Column(MutableList.as_mutable(JSON), nullable=True)
    answer_scores = Column(MutableList.as_mutable(JSON), nullable=True)

    jd_code = Column(String(20), ForeignKey("job_description.code", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # NEW: anti-cheat flag counter
    left_tab_count = Column(Integer, default=0)

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant = relationship("Tenant")
