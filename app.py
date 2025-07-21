# app.py  –  minimal "login → edit JD → upload résumé → score only"

import os, json, uuid, logging, tempfile, re
from typing import List
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    flash, send_file
)
import PyPDF2
from openai import OpenAI
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)

from db import SessionLocal
from models import Candidate, JobDescription, User
from s3util import upload_pdf, presign, get_job_description

# ─── Config ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change‑me")

# ─── Flask‑Login setup ────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal(); u = db.get(User, int(uid)); db.close(); return u

# ─── OpenAI helpers ───────────────────────────────────────────────
def chat(system: str, user: str, *, timeout=60) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0, top_p=0.1, timeout=timeout,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}]
    )
    return resp.choices[0].message.content.strip()

def pdf_to_text(path: str) -> str:
    with open(path,"rb") as f:
        return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(f).pages)

def resume_json(text: str) -> dict:
    raw = chat("You are a résumé JSON extractor.", ..., json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: ask again in JSON mode or return minimal dict
        raw2 = chat("Return ONLY valid JSON.", text, json_mode=True)
    return json.loads(raw2)

def realism_check(rjs: dict) -> bool:
    verdict = chat("You check realism.","Is this résumé realistic?\n\n"+json.dumps(rjs))
    return verdict.lower().startswith("y")

def fit_score(rjs: dict, jd_html: str) -> int:
    raw = chat("You score résumé vs job.",
               f"Résumé:\n{json.dumps(rjs,indent=2)}\n\nJob:\n{jd_html}\n\n"
               "Give one integer 1‑5.")
    try: return int(raw.strip())
    except ValueError: return 1

# ─── HTML template ────────────────────────────────────────────────
BASE = """
<!doctype html><html lang=en><head>
 <meta charset=utf-8><title>{{ title }}</title>
 <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand">Demo Sandbox</span>
    <div>
      {% if current_user.is_authenticated %}
        <span class="me-2 text-secondary">{{ current_user.username }}</span>
        <a class="btn btn-outline-danger btn-sm" href="{{ url_for('logout') }}">Logout</a>
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
def page(t,b): return render_template_string(BASE,title=t,body=b)

# ─── Auth routes ──────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u,p = request.form["username"], request.form["password"]
        db=SessionLocal(); user=db.query(User).filter_by(username=u).first(); db.close()
        if user and user.check_pw(p):
            login_user(user); return redirect(url_for("edit_jd"))
        flash("Bad credentials")
    form=("""<h4>Login</h4><form method=post>
            <input name=username class='form-control mb-2' placeholder='Username'>
            <input name=password type=password class='form-control mb-2' placeholder='Password'>
            <button class='btn btn-primary w-100'>Login</button></form>""")
    return page("Login",form)

@app.route("/logout")
@login_required
def logout():
    logout_user(); return redirect(url_for("login"))

# ─── Edit JD (first stop after login) ─────────────────────────────
@app.route("/edit-jd", methods=["GET","POST"])
@login_required
def edit_jd():
    db = SessionLocal(); jd = db.get(JobDescription,1) or JobDescription(id=1,html="")
    if request.method=="POST":
        jd.html=request.form["html"]; db.merge(jd); db.commit(); db.close()
        flash("Job description updated"); return redirect(url_for("home"))
    cur = jd.html; db.close()
    form=(f"<h4>Edit Job Description</h4><form method=post>"
          f"<textarea name=html rows=10 class='form-control'>{cur}</textarea>"
          "<button class='btn btn-primary mt-2'>Save</button></form>")
    return page("Edit JD",form)

# ─── Candidate upload & scoring ───────────────────────────────────
@app.route("/", methods=["GET","POST"])
@login_required
def home():
    jd_html = get_job_description()
    if request.method=="POST":
        name=request.form["name"].strip(); f=request.files["resume_pdf"]
        if not name or not f: flash("Name and PDF required"); return redirect("/")
        with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp:
            f.save(tmp.name); pdf=tmp.name
        txt = pdf_to_text(pdf); rjs=resume_json(txt)
        score = fit_score(rjs,jd_html); real = realism_check(rjs)
        cid = str(uuid.uuid4())[:8]; s3_url=upload_pdf(pdf)
        with SessionLocal() as db:
            db.add(Candidate(id=cid,name=name,resume_url=s3_url,
                             resume_json=rjs,realism=real,fit_score=score,
                             questions=[],answers=[],answer_scores=[]))
            db.commit()
        body=(f"<h4>Thanks, {name}!</h4>"
              f"<p>Your résumé relevance score: <strong>{score}/5</strong>.</p>")
        return page("Result",body)

    form=(f"<div class='card p-4 shadow-sm mb-4'>{jd_html}</div>"
          "<form method=post enctype=multipart/form-data class='card p-4 shadow-sm'>"
          "<div class='mb-3'><label>Your Name</label>"
          "<input name=name class='form-control' required></div>"
          "<div class='mb-3'><label>Résumé (PDF)</label>"
          "<input type=file name=resume_pdf accept=.pdf class='form-control' required></div>"
          "<button class='btn btn-primary w-100'>Upload & Score</button></form>")
    return page("Upload Résumé",form)

# ─── Recruiter views ──────────────────────────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        rows=db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    tbl="".join(f"<tr><td>{c.name}</td><td>{c.fit_score}</td>"
                f"<td><a href='{url_for('detail',cid=c.id)}'>view</a></td></tr>"
                for c in rows) or "<tr><td colspan=3>No candidates</td></tr>"
    body=(f"<h4>Candidates</h4>"
          "<table class='table'><thead><tr><th>Name</th><th>Score</th><th></th></tr></thead>"
          f"<tbody>{tbl}</tbody></table>")
    return page("Recruiter",body)

@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    with SessionLocal() as db: c=db.get(Candidate,cid)
    if not c: flash("Not found"); return redirect(url_for("recruiter"))
    body=(f"<a href='{url_for('recruiter')}'>&larr; back</a>"
          f"<h4>{c.name}</h4>"
          f"<p>Score: <strong>{c.fit_score}/5</strong><br>"
          f"Realism: {'Looks real' if c.realism else 'Possibly fake'}</p>"
          f"<a class='btn btn-outline-secondary' href='{url_for('download_resume',cid=cid)}'>Download résumé</a>")
    return page("Candidate",body)

@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    with SessionLocal() as db: c=db.get(Candidate,cid)
    if not c: return "Not found",404
    return redirect(presign(c.resume_url))

# ─── Entrypoint ───────────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0",port=int(os.getenv("PORT",5000)))
