import datetime, json, bcrypt
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, Session
from sqlalchemy.ext.mutable import MutableDict

Base = declarative_base()

class JobDescription(Base):
    __tablename__ = "job_description"
    id    = Column(Integer, primary_key=True)         # now SERIAL
    code  = Column(String(20), unique=True, nullable=False)
    slug  = Column(String(50), unique=True, nullable=False)
    title = Column(String(120))
    html  = Column(Text,   nullable=False)

class Candidate(Base):
    __tablename__ ="candidate"
    id          = Column(String(8), primary_key=True)
    name        = Column(String(80))
    resume_url  = Column(Text)
    resume_json = Column(MutableDict.as_mutable(JSON))
    fit_score   = Column(Integer)
    answer_scores = Column(MutableDict.as_mutable(JSON))   # list[int] | list["ERR"]
    jd_code     = Column(String(20), ForeignKey("job_description.code"))
    created_at  = Column(DateTime, default=datetime.datetime.utcnow)

    jd = relationship(JobDescription, lazy="joined")

    # handy property for dashboard
    @property
    def avg_validity(self) -> str:
        if not self.answer_scores:
            return "-"
        nums = [s for s in self.answer_scores if isinstance(s, int)]
        return f"{sum(nums)/len(nums):.1f}" if nums else "-"

class User(Base):
    __tablename__ = "user"
    id       = Column(Integer, primary_key=True)
    username = Column(String(120), unique=True, nullable=False)
    pw_hash  = Column(String(128), nullable=False)

    # ── auth helpers ───────────────────────────
    @staticmethod
    def create(db: Session, username: str, password: str):
        h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        u = User(username=username, pw_hash=h)
        db.add(u); db.commit(); return u
    def check_pw(self, pw:str)->bool:
        return bcrypt.checkpw(pw.encode(), self.pw_hash.encode())

    # flask-login required attrs
    @property
    def is_authenticated(self): return True
    @property
    def is_active(self): return True
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)
