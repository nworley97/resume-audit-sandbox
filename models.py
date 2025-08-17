# models.py
import os
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from werkzeug.security import generate_password_hash, check_password_hash

# IMPORTANT: we import Base and engine from your db.py to avoid re-defining Base twice
from db import Base, engine as engine  # engine is re-exported for app.ensure_schema()

# ─── Tenant ──────────────────────────────────────────────────────
class Tenant(Base):
    __tablename__ = "tenant"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)

# ─── User ────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "user"
    id       = Column(Integer, primary_key=True)
    username = Column(String(128), nullable=False)  # (demo: not globally unique)
    pw_hash  = Column(String(256), nullable=False)

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant    = relationship("Tenant")

    def set_pw(self, pw):  self.pw_hash = generate_password_hash(pw)
    def check_pw(self, pw): return check_password_hash(self.pw_hash, pw)

    # Flask-Login
    @property
    def is_active(self):         return True
    @property
    def is_authenticated(self):  return True
    @property
    def is_anonymous(self):      return False
    def get_id(self):            return str(self.id)

# ─── JobDescription ─────────────────────────────────────────────
class JobDescription(Base):
    __tablename__ = "job_description"

    code        = Column(String, primary_key=True)
    title       = Column(String, nullable=False, default="")
    html        = Column(Text,   nullable=False, default="")
    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow)

    status          = Column(String, nullable=False, default="draft")
    department      = Column(String, nullable=True)
    team            = Column(String, nullable=True)
    location        = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    salary_range    = Column(String, nullable=True)
    updated_at      = Column(DateTime(timezone=True), nullable=True)
    start_date      = Column(DateTime(timezone=True), nullable=True)
    end_date        = Column(DateTime(timezone=True), nullable=True)

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant    = relationship("Tenant")

    candidates = relationship("Candidate", back_populates="job", lazy="selectin")

# ─── Candidate ──────────────────────────────────────────────────
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
    jd_code       = Column(String(20), ForeignKey("job_description.code", ondelete="SET NULL"))
    created_at    = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant_id = Column(Integer, ForeignKey("tenant.id", ondelete="SET NULL"), nullable=True)
    tenant    = relationship("Tenant")

    job = relationship("JobDescription", back_populates="candidates")
