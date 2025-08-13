import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean,
    DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base  # or however your Base is imported

DATABASE_URL = os.getenv("DATABASE_URL")

engine       = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base         = declarative_base()

class User(Base):
    __tablename__ = "user"
    id       = Column(Integer, primary_key=True)
    username = Column(String(128), unique=True, nullable=False)
    pw_hash  = Column(String(256), nullable=False)
    def set_pw(self, pw):  self.pw_hash = generate_password_hash(pw)
    def check_pw(self, pw): return check_password_hash(self.pw_hash, pw)
    # Flask-Login
    @property
    def is_active(self):   return True
    @property
    def is_authenticated(self): return True
    @property
    def is_anonymous(self):     return False
    def get_id(self):       return str(self.id)

class JobDescription(Base):
    __tablename__ = "job_description"

    # existing columns — keep your current PK and fields
    code        = Column(String, primary_key=True)        # assuming this is your PK
    title       = Column(String, nullable=False, default="")
    html        = Column(Text,   nullable=False, default="")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # NEW: map columns we add via ensure_schema()
    status          = Column(String, nullable=False, default="draft")
    department      = Column(String, nullable=True)
    team            = Column(String, nullable=True)
    location        = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    salary_range    = Column(String, nullable=True)
    updated_at      = Column(DateTime(timezone=True), nullable=True)
    start_date      = Column(DateTime(timezone=True), nullable=True)
    end_date        = Column(DateTime(timezone=True), nullable=True)

    # relationship back to candidates if you already had it
    candidates = relationship("Candidate", back_populates="job_description", lazy="selectin")
    
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
    job           = relationship("JobDescription", backref="candidates")

# Create tables (if running locally first time)
Base.metadata.create_all(engine)
