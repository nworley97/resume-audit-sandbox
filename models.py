import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean,
    DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.ext.mutable import MutableDict, MutableList
from werkzeug.security import generate_password_hash, check_password_hash

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
    code       = Column(String(20), primary_key=True)
    title      = Column(String(256), nullable=False)
    html       = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

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

# Create tables (if running locally)
Base.metadata.create_all(engine)
