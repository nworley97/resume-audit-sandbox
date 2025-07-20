from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime
import bcrypt
Base = declarative_base()

class Candidate(Base):
    __tablename__ = "candidates"
    id            = Column(String, primary_key=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    name          = Column(String)
    resume_url    = Column(String)
    resume_json   = Column(JSON)
    realism       = Column(Boolean)
    fit_score     = Column(Integer)
    questions     = Column(JSON)
    answers       = Column(JSON)
    answer_scores = Column(JSON)

class JobDescription(Base):
    __tablename__ = "job_description"
    id   = Column(Integer, primary_key=True, default=1)
    html = Column(Text, nullable=False)

class User(Base):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    pw_hash  = Column(String, nullable=False)

    @classmethod
    def create(cls, session, username, plain_pw):
        h = bcrypt.hashpw(plain_pw.encode(), bcrypt.gensalt()).decode()
        u = cls(username=username, pw_hash=h)
        session.add(u); session.commit(); return u

    def check_pw(self, plain_pw):
        return bcrypt.checkpw(plain_pw.encode(), self.pw_hash.encode())
