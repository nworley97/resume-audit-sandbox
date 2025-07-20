import os, json, uuid, logging, tempfile, re
from json import JSONDecodeError
from typing import List
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    flash, send_file
)
import PyPDF2
from openai import OpenAI, APIError, BadRequestError

from db import SessionLocal
from models import Candidate, JobDescription, User
from s3util import upload_pdf, presign, get_job_description
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)

# ─────────── CONFIG ───────────
logging.basicConfig(level=logging.INFO)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL          = "gpt-4o"
client         = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "demo‑key")

# Flask‑Login
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal()
    u = db.get(User, int(uid))
    db.close()
    return u

# ─────────── OPENAI wrapper ───────────
def chat(system: str, user: str, *, json_mode=False, timeout=60) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            top_p=0.1,
            response_format={"type": "json_object"} if json_mode else None,
            messages=[{"role": "system", "content": system},
                      {"role": "user",   "content": user}],
            timeout=timeout,
        )
        return resp.choices[0].message.content.strip()
    except (APIError, BadRequestError) as e:
        raise RuntimeError(f"OpenAI error: {e}") from e

# ─────────── Helper functions ───────────
def pdf_to_text(path: str) -> str:
    with open(path, "rb") as f:
        return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(f).pages)

def resume_json(text: str) -> dict:
    raw = chat(
        "You are a résumé JSON extractor.",
        "Convert this résumé text into JSON with fields: "
        "name, contact, education, work_experience, skills, certifications.\n\n"
        + text,
        json_mode=True,
    )
    return json.loads(raw)

def realism_check(rjs: dict) -> bool:
    verdict = chat(
        "You are a résumé authenticity checker.",
        f"{json.dumps(rjs)}\n\nIs this résumé realistic? answer yes or no."
    )
    return verdict.lower().startswith("y")

def fit_score(rjs: dict, jd: str) -> int:
    raw = chat(
        "You are a technical recruiter.",
        f"Résumé:\n{json.dumps(rjs, indent=2)}\n\nJob Description:\n{jd}\n\n"
        "Rate résumé–JD fit on a 1‑5 integer scale. Return only the number."
    )
    try: return int(raw.strip())
    except ValueError: return 1

def make_questions(rjs: dict) -> List[str]:
    raw = chat(
        "You are an interviewer verifying a résumé.",
        "Write exactly FOUR probing questions (strings only) that confirm the "
        "candidate's listed skills/achievements. Return JSON array or "
        "object {'questions':[...]}.\n\n" + json.dumps(rjs),
        json_mode=True,
    )
    try:
        data = json.loads(raw)
        if isinstance(data, list): return [str(q) for q in data][:4]
        if isinstance(data, dict) and "questions" in data:
            return [str(q) for q in data["questions"]][:4]
    except JSONDecodeError:
        pass
    return [l.strip("-• ").strip() for l in raw.splitlines() if l.strip()][:4]

def score_answers(rjs: dict, qs: List[str], ans: List[str]) -> List[int]:
    scores: List[int | str] = []
    for q, a in zip(qs, ans):
        wc = len(re.findall(r"\w+", a))
        if wc < 5: scores.append(1); continue
        provisional_cap = 2 if wc < 10 else None
        prompt = (
            "You are a strict interviewer.\n"
            f"Question: {q}\nCandidate answer: {a}\n"
            f"Résumé snippet:\n{json.dumps(rjs)[:1500]}\n\n"
            "Score 1‑5 (5 exact, 1 wrong). Return only the number."
        )
        try:
            sc = int(chat("Grade", prompt).strip())
            sc = max(1, min(5, sc))
            if provisional_cap: sc = min(sc, provisional_cap)
            scores.append(sc)
        except Exception as e:
            logging.exception("Scoring failed: %s", e)
            scores.append("ERR")
    while len(scores) < 4: scores.append("ERR")
    return scores

# ─────────── HTML template ───────────
BASE = """
<!doctype html><html lang=en><head>
 <meta charset=utf-8><title>{{ title }}</title>
 <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
 <style>.centered{text-align:center}</style>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand mb-0 h4">Demo Sandbox</span>
    <div>
      {% if current_user.is_authenticated %}
        <span class="me-2 text-secondary">{{ current_user.username }}</span>
        <a class="btn btn-outline-danger btn-sm" href="{{ url_for('logout') }}">Logout</a>
      {% else %}
        <a class="btn btn-outline-primary btn-sm" href="{{ url_for('login') }}">Login</a>
      {% endif %}
    </div>
  </div>
</nav>
<div class="container" style="max-width:720px;">
  {% with m = get_flashed_messages() %}
    {% if m %}<div class="alert alert-danger">{{ m[0] }}</div>{% endif %}
  {% endwith %}
  {{ body|safe }}
</div></body></html>"""
def page(t,r,b): return render_template_string(BASE,title=t,role=r,body=b)

# ─────────── Candidate routes ───────────
@app.route("/", methods=["GET", "POST"])
def home():
    job_desc_html = get_job_description()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        rf   = request.files.get("resume_pdf")
        if not name or not rf or rf.filename=="": flash("Name and résumé PDF required"); return redirect("/")
        with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp:
            rf.save(tmp.name); pdf_path = tmp.name
        try:
            txt = pdf_to_text(pdf_path); rjs = resume_json(txt)
            real = realism_check(rjs); fs = fit_score(rjs, job_desc_html)
            qs  = make_questions(rjs); cid = str(uuid.uuid4())[:8]
            s3_url = upload_pdf(pdf_path)
            with SessionLocal() as db:
                db.add(Candidate(
                    id=cid, name=name, resume_url=s3_url,
                    resume_json=rjs, realism=real, fit_score=fs,
                    questions=qs, answers=[], answer_scores=[]
                )); db.commit()
            inputs="".join(
                f"<li class='list-group-item centered'><strong>{q}</strong><br>"
                f"<textarea class='form-control mt-2' name='a{i}' rows='2' required></textarea></li>"
                for i,q in enumerate(qs)
            )
            body=(f"<h4>Hi {name}, thanks for applying!</h4>"
                  "<h5 class='mt-4 centered'>Interview Questions</h5>"
                  f"<form method='post' action='{url_for('submit_answers',cid=cid)}'>"
                  f"<ol class='list-group list-group-numbered mb-3'>{inputs}</ol>"
                  "<button class='btn btn-primary w-100'>Submit answers</button></form>")
            return page("Answer Questions","candidate",body)
        except RuntimeError as e:
            flash(str(e)); return redirect("/")
    body=(f"<div class='card p-4 shadow-sm mb-4'>{job_desc_html}</div>"
          "<form method='post' enctype='multipart/form-data' class='card p-4 shadow-sm'>"
          "<div class='mb-3'><label class='form-label'>Your Name</label>"
          "<input class='form-control' name='name' required></div>"
          "<div class='mb-3'><label class='form-label'>Upload Résumé (PDF)</label>"
          "<input type='file' class='form-control' name='resume_pdf' accept='.pdf' required></div>"
          "<button class='btn btn-primary w-100'>Analyze & Get Questions</button></form>")
    return page("Apply – Candidate","candidate",body)

@app.route("/answers/<cid>", methods=["POST"])
def submit_answers(cid):
    ans = [request.form.get(f"a{i}","").strip() for i in range(4)]
    with SessionLocal() as db:
        c = db.get(Candidate, cid)
        if not c: flash("Candidate not found"); return redirect("/")
        c.answers = ans
        c.answer_scores = score_answers(c.resume_json, c.questions, ans)
        db.commit()
    flash("Answers submitted!"); return redirect("/")

# ─────────── Recruiter routes ───────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        rows = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    table="".join(
        f"<tr><td>{c.name}</td><td>{c.fit_score}</td>"
        f"<td><a href='{url_for('detail',cid=c.id)}'>view</a></td></tr>"
        for c in rows) or "<tr><td colspan=3>No candidates</td></tr>"
    body=(f"<h4>Job Listing</h4>{get_job_description()}<hr>"
          "<h4>Candidates</h4>"
          "<table class='table table-sm'><thead><tr><th>Name</th><th>Score</th><th></th></tr></thead>"
          f"<tbody>{table}</tbody></table>")
    return page("Recruiter Dashboard","recruiter",body)

@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    with SessionLocal() as db:
        c=db.get(Candidate,cid)
    if not c: flash("Not found"); return redirect(url_for("recruiter"))
    numeric=[s for s in c.answer_scores if isinstance(s,int)]
    avg_q = round(sum(numeric)/len(numeric),2) if numeric else "-"
    rows=""
    for i,q in enumerate(c.questions):
        ans = c.answers[i] if i<len(c.answers) and c.answers[i] else "<em>no answer</em>"
        sc  = c.answer_scores[i] if i<len(c.answer_scores) else "-"
        rows+=f"<tr><td><strong>{q}</strong></td><td>{ans}</td><td>{sc}</td></tr>"
    body=(f"<a class='btn btn-link mb-3' href='{url_for('recruiter')}'>← back</a>"
          f"<h4>{c.name} — Fit Score {c.fit_score}/5 "
          f"<span class='text-muted' style='font-size:0.9em'>(Avg Q: {avg_q})</span></h4>"
          f"<p><strong>Résumé realism:</strong> {'Looks Real' if c.realism else 'Possibly Fake'}</p>"
          f"<a class='btn btn-sm btn-outline-secondary mb-4' href='{url_for('download_resume',cid=cid)}'>"
          "Download résumé PDF</a>"
          "<h5>Interview Q&amp;A</h5>"
          "<table class='table table-sm'><thead><tr><th>Question</th><th>Answer</th>"
          "<th>Validity</th></tr></thead><tbody>"+rows+"</tbody></table>")
    return page("Candidate Detail","recruiter",body)

@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    with SessionLocal() as db:
        c=db.get(Candidate,cid); 
    if not c: return "Not found",404
    return redirect(presign(c.resume_url))

# ─────────── Auth routes ───────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        usern=request.form["username"]; pw=request.form["password"]
        db=SessionLocal(); u=db.query(User).filter_by(username=usern).first(); db.close()
        if u and u.check_pw(pw):
            login_user(u); return redirect(request.args.get("next") or url_for("recruiter"))
        flash("Invalid credentials")
    form=("<h4>Login</h4><form method='post'>"
          "<input name='username' class='form-control mb-2' placeholder='Username'>"
          "<input type='password' name='password' class='form-control mb-2' placeholder='Password'>"
          "<button class='btn btn-primary w-100'>Login</button></form>")
    return page("Login","candidate",form)

@app.route("/logout")
@login_required
def logout():
    logout_user(); flash("Logged out"); return redirect(url_for("home"))

# ─────────── JD editor (token) ───────────
from functools import wraps
def admin_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if request.args.get("token")!=os.getenv("ADMIN_TOKEN"): return "Forbidden",403
        return fn(*a,**kw)
    return wrapper

@app.route("/edit-jd", methods=["GET","POST"])
@admin_required
def edit_jd():
    db=SessionLocal(); jd=db.get(JobDescription,1) or JobDescription(id=1,html="")
    if request.method=="POST":
        jd.html=request.form["html"]; db.merge(jd); db.commit(); db.close()
        flash("Job description updated"); return redirect(url_for("home"))
    cur=jd.html; db.close()
    form=("<h4>Edit Job Description</h4><form method='post'>"
          f"<textarea name='html' rows='10' class='form-control'>{cur}</textarea>"
          "<button class='btn btn-primary mt-2'>Save</button></form>")
    return page("Edit JD","recruiter",form)

# ─────────── Entrypoint ───────────
if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0",port=int(os.getenv("PORT",5000)))
