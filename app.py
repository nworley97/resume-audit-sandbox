import os
import json
import uuid
import logging
import tempfile
import mimetypes
import re

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    flash, send_file
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
from openai import OpenAI
import PyPDF2
import docx

from db import SessionLocal
from models import Candidate, JobDescription, User
from s3util import upload_pdf, presign, S3_ENABLED, s3, BUCKET

# ─── Configuration ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me")

# ─── Flask-Login setup ──────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id: str):
    db = SessionLocal()
    user = db.get(User, int(user_id))
    db.close()
    return user

# ─── OpenAI helper ──────────────────────────────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        top_p=0.1,
        response_format={"type":"json_object"} if structured else None,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

# ─── File‐to‐text helpers ────────────────────────────────────────
def pdf_to_text(path):
    return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(path).pages)

def docx_to_text(path):
    return "\n".join(p.text for p in docx.Document(path).paragraphs)

def file_to_text(path, mime):
    if mime == "application/pdf":
        return pdf_to_text(path)
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword"
    ):
        return docx_to_text(path)
    raise ValueError("Unsupported file type")

# ─── AI helpers ─────────────────────────────────────────────────
def resume_json(text: str) -> dict:
    raw = chat("Extract résumé to JSON.", text, structured=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # fallback
        raw2 = chat("Return ONLY valid JSON résumé.", text, structured=True)
        return json.loads(raw2)

def fit_score(rjs: dict, jd_text: str) -> int:
    prompt = (
        f"Résumé JSON:\n{json.dumps(rjs, indent=2)}\n\n"
        f"Job description:\n{jd_text}\n\n"
        "Score 1-5 (5 best). Return ONLY the integer."
    )
    reply = chat("Score résumé vs JD.", prompt).strip()
    try:
        return int(reply)
    except ValueError:
        m = re.search(r"[1-5]", reply)
        return int(m.group()) if m else 1

# ─── Base HTML template ─────────────────────────────────────────
BASE = """
<!doctype html><html lang=en><head>
  <meta charset=utf-8><title>{{ title }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand">Blackboxstrategiesalpha</span>
    {% if current_user.is_authenticated %}
      <div class="d-flex">
        <a class="btn btn-outline-secondary btn-sm me-2" href="{{ url_for('recruiter') }}">Recruiter</a>
        <span class="align-self-center me-2 text-secondary">{{ current_user.username }}</span>
        <a class="btn btn-outline-danger btn-sm" href="{{ url_for('logout') }}">Logout</a>
      </div>
    {% endif %}
  </div>
</nav>
<div class="container" style="max-width:720px;">
  {% with m = get_flashed_messages() %}
    {% if m %}<div class="alert alert-danger">{{ m[0] }}</div>{% endif %}
  {% endwith %}
  {{ body|safe }}
</div>
</body></html>
"""
def page(title, body):
    return render_template_string(BASE, title=title, body=body)

# ─── Auth routes ─────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        db = SessionLocal()
        usr = db.query(User).filter_by(username=u).first()
        db.close()
        if usr and usr.check_pw(p):
            login_user(usr)
            return redirect(url_for("recruiter"))
        flash("Bad credentials")
    form = """
      <h4>Login</h4>
      <form method=post>
        <input name=username class='form-control mb-2' placeholder='Username' required>
        <input name=password type=password class='form-control mb-2' placeholder='Password' required>
        <button class='btn btn-primary w-100'>Login</button>
      </form>
    """
    return page("Login", form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ─── Job Description edit ────────────────────────────────────────
@app.route("/edit-jd", methods=["GET","POST"])
@login_required
def edit_jd():
    db = SessionLocal()
    jd = db.get(JobDescription, 1) or JobDescription(id=1, code="JD01", title="", html="")
    if request.method == "POST":
        jd.code  = request.form["jd_code"].strip() or jd.code
        jd.title = request.form["jd_title"].strip()
        jd.html  = request.form["jd_text"]
        db.merge(jd)
        db.commit()
        db.close()
        flash("Job description saved")
        return redirect(url_for("home"))
    form = (
      "<h4>Edit Job Description</h4>"
      "<form method=post>"
      " <label>Job Code</label>"
      f" <input name=jd_code value='{jd.code}' class='form-control mb-2' required>"
      " <label>Title</label>"
      f" <input name=jd_title value='{jd.title}' class='form-control mb-2' required>"
      " <label>Description (plain text)</label>"
      f" <textarea name=jd_text rows=6 class='form-control mb-2'>{jd.html}</textarea>"
      " <button class='btn btn-primary'>Save</button>"
      "</form>"
    )
    db.close()
    return page("Edit JD", form)

def current_jd():
    db = SessionLocal()
    jd = db.get(JobDescription, 1)
    db.close()
    return jd

# ─── Candidate upload & scoring ─────────────────────────────────
@app.route("/", methods=["GET","POST"])
@login_required
def home():
    jd = current_jd()
    jd_text = jd.html if jd else "(no JD set)"
    if request.method == "POST":
        name = request.form["name"].strip()
        f    = request.files["resume_file"]
        if not name or not f or f.filename == "":
            flash("Name & file required")
            return redirect(url_for("home"))

        mime = mimetypes.guess_type(f.filename)[0] or f.mimetype
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            f.save(tmp.name)
            path = tmp.name

        try:
            text = file_to_text(path, mime)
        except ValueError:
            flash("Upload PDF or DOCX only")
            return redirect(url_for("home"))

        rjs   = resume_json(text)
        score = fit_score(rjs, jd_text)

        cid      = str(uuid.uuid4())[:8]
        storage  = upload_pdf(path)
        with SessionLocal() as db:
            db.add(Candidate(
                id=cid,
                name=name,
                resume_url=storage,
                resume_json=rjs,
                fit_score=score,
                jd_code=jd.code if jd else None
            ))
            db.commit()

        body = (
          f"<h4>Thanks, {name}!</h4>"
          f"<p>Relevance score: <strong>{score}/5</strong>.</p>"
          f"<a class='btn btn-secondary mt-3' href='{url_for('home')}'>Upload another résumé</a>"
        )
        return page("Result", body)

    form = (
      f"<h4>Current Job ({jd.code if jd else 'N/A'}): {jd.title if jd else ''}</h4>"
      f"<pre class='p-3 bg-white border'>{jd_text}</pre>"
      "<form method=post enctype=multipart/form-data class='card p-4 shadow-sm'>"
      "<div class='mb-3'><label>Your Name</label>"
      "<input name=name class='form-control' required></div>"
      "<div class='mb-3'><label>Résumé (PDF or DOCX)</label>"
      "<input type=file name=resume_file accept='.pdf,.docx' class='form-control' required></div>"
      "<button class='btn btn-primary w-100'>Upload & Score</button>"
      "</form>"
    )
    return page("Upload Résumé", form)

# ─── Recruiter dashboard (list JDs) ────────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        jds = db.query(JobDescription).order_by(JobDescription.id.desc()).all()

    rows = "".join(
      "<tr>"
      f"<td>{jd.code}</td>"
      f"<td>{jd.title}</td>"
      f"<td><a href='{url_for('jd_detail', code=jd.code)}'>open</a></td>"
      f"<td><a class='text-danger' href='{url_for('delete_jd', code=jd.code)}' "
      "onclick=\"return confirm('Delete this JD?');\">✖</a></td>"
      "</tr>"
      for jd in jds
    ) or "<tr><td colspan=4>No postings</td></tr>"

    body = (
      "<h4>Job Postings</h4>"
      "<a class='btn btn-sm btn-outline-primary mb-3' href='#' "
      "onclick=\"location.href='/edit-jd';return false;\">+ New / Edit JD</a>"
      "<table class='table table-sm'>"
      "<thead><tr><th>Code</th><th>Title</th><th></th><th></th></tr></thead>"
      f"<tbody>{rows}</tbody>"
      "</table>"
    )
    return page("Recruiter Dashboard", body)

# ─── JD‐specific detail & its applications ───────────────────────
@app.route("/recruiter/<code>")
@login_required
def jd_detail(code):
    with SessionLocal() as db:
        jd = db.query(JobDescription).filter_by(code=code).first()
        apps = db.query(Candidate)\
                 .filter_by(jd_code=code)\
                 .order_by(Candidate.created_at.desc())\
                 .all()
    if not jd:
        flash("Job posting not found.")
        return redirect(url_for("recruiter"))

    rows = "".join(
      "<tr>"
      f"<td>{c.id}</td>"
      f"<td>{c.name}</td>"
      f"<td>{c.fit_score}</td>"
      f"<td><a href='{url_for('download_resume', cid=c.id)}'>📄</a></td>"
      f"<td><a class='text-danger' href='{url_for('delete_candidate', cid=c.id)}' "
      "onclick=\"return confirm('Delete this candidate?');\">✖</a></td>"
      "</tr>"
      for c in apps
    ) or "<tr><td colspan=5>No applications</td></tr>"

    body = (
      f"<a href='{url_for('recruiter')}'>&larr; back</a>"
      f"<h4>Job {jd.code}: {jd.title}</h4>"
      f"<pre class='p-3 bg-white border'>{jd.html}</pre><hr>"
      "<h5>Applications</h5>"
      "<table class='table table-sm'>"
      "<thead><tr><th>ID</th><th>Name</th><th>Score</th><th>Resume</th><th></th></tr></thead>"
      f"<tbody>{rows}</tbody></table>"
    )
    return page(f"Job {jd.code}", body)

# ─── Download or delete résumé ───────────────────────────────────
@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    with SessionLocal() as db:
        c = db.get(Candidate, cid)
    if not c:
        return "Not found", 404
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))
    return send_file(c.resume_url, as_attachment=True, download_name=f"{c.name}.pdf")

@app.route("/delete/<cid>")
@login_required
def delete_candidate(cid):
    with SessionLocal() as db:
        c = db.get(Candidate, cid)
        if c:
            # delete S3 or local file
            if S3_ENABLED and c.resume_url.startswith("s3://"):
                b, k = c.resume_url.split("/",3)[2:]
                try: s3.delete_object(Bucket=b, Key=k)
                except: pass
            elif os.path.exists(c.resume_url):
                try: os.remove(c.resume_url)
                except: pass
            db.delete(c)
            db.commit()
            flash("Candidate deleted")
    return redirect(url_for("jd_detail", code=c.jd_code))

@app.route("/delete-jd/<code>")
@login_required
def delete_jd(code):
    with SessionLocal() as db:
        jd = db.query(JobDescription).filter_by(code=code).first()
        if jd:
            # cascade‐null children
            db.delete(jd)
            db.commit()
            flash("Job description deleted")
    return redirect(url_for("recruiter"))

# ─── Entrypoint ─────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
