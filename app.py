"""
app.py  –  Blackboxstrategiesalpha résumé‑scoring portal
Author:  (Your name)   •   Last updated: 2025‑07‑23

Key features
------------
* Flask‑Login for recruiter auth
* Edit‑able Job Description (code + free text); stored in Postgres
* Upload résumé (PDF or DOCX) → extract → send to GPT‑4o → relevance score
* Results persisted with JD code for traceability
* Optional S3 storage (local fallback for Render free tier)
"""

import os, json, uuid, logging, tempfile, mimetypes, re
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    flash, send_file
)
import PyPDF2, docx
from openai import OpenAI
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)

from db import SessionLocal
from models import Candidate, JobDescription, User
from s3util import upload_pdf, presign, S3_ENABLED, s3, BUCKET

# ─────────────────────────── Configuration ────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change‑me‑in‑prod")

# ──────────────────────── Flask‑Login bootstrap ───────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal()
    user = db.get(User, int(uid))
    db.close()
    return user

# ────────────────────── Tiny OpenAI chat wrapper ──────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    """
    Thin wrapper around openai.ChatCompletion.create
    * structured=True  →  requests JSON response (used for résumé extraction)
    """
    resp = client.chat.completions.create(
        model            = MODEL,
        temperature      = 0,
        top_p            = 0.1,
        response_format  = {"type": "json_object"} if structured else None,
        messages         = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
        timeout          = timeout,
    )
    return resp.choices[0].message.content.strip()

# ──────────────────────── File‑to‑text helpers ────────────────────────
def pdf_to_text(path):
    return "\n".join(
        page.extract_text() or "" for page in PyPDF2.PdfReader(path).pages
    )

def docx_to_text(path):
    return "\n".join(p.text for p in docx.Document(path).paragraphs)

def file_to_text(path, mime):
    if mime == "application/pdf":
        return pdf_to_text(path)
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return docx_to_text(path)
    raise ValueError("Unsupported file type")

# ───────────────── AI helpers (JSON extract + relevance score) ─────────
def resume_json(text: str) -> dict:
    raw = chat("Extract this résumé into JSON.", text, structured=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw2 = chat(
            "Return ONLY valid JSON for this résumé. No extra keys.",
            text,
            structured=True,
        )
        return json.loads(raw2)

def fit_score(rjs: dict, jd_text: str) -> int:
    """
    Returns an integer 1‑5. We constrain the model and defensively
    extract a digit if it tries to explain.
    """
    prompt = (
        f"Résumé JSON:\n{json.dumps(rjs, indent=2)}\n\n"
        f"Job description:\n{jd_text}\n\n"
        "Score how well the résumé matches the job on a 1‑5 scale."
        " Reply with ONLY the integer."
    )
    reply = chat("Score résumé vs JD.", prompt).strip()
    try:
        return int(reply)
    except ValueError:
        m = re.search(r"[1-5]", reply)
        return int(m.group()) if m else 1

# ────────────────────────── Base HTML template ─────────────────────────
BASE = """
<!doctype html><html lang=en><head>
 <meta charset=utf-8><title>{{ title }}</title>
 <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
</head><body class="bg-light">

<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand">Blackboxstrategiesalpha</span>
    <div>
      {% if current_user.is_authenticated %}
        <a class="btn btn-outline-secondary btn-sm me-2" href="{{ url_for('home') }}">Upload</a>
        <a class="btn btn-outline-secondary btn-sm me-2" href="{{ url_for('recruiter') }}">Recruiter</a>
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
</div>
</body></html>"""

def page(title: str, body_html: str):
    return render_template_string(BASE, title=title, body=body_html)

# ──────────────────────────── Auth routes ─────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"]
        pw    = request.form["password"]
        with SessionLocal() as db:
            u = db.query(User).filter_by(username=uname).first()
        if u and u.check_pw(pw):
            login_user(u)
            return redirect(url_for("edit_jd"))
        flash("Bad credentials")
    form = """
    <h4>Login</h4>
    <form method=post>
      <input name=username class='form-control mb-2' placeholder='Username' required>
      <input name=password type=password class='form-control mb-2' placeholder='Password' required>
      <button class='btn btn-primary w-100'>Login</button>
    </form>"""
    return page("Login", form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ───────────── Job Description editor (code + free text) ──────────────
@app.route("/edit-jd", methods=["GET", "POST"])
@login_required
def edit_jd():
    db = SessionLocal()
    jd = db.get(JobDescription, 1) or JobDescription(id=1, code="", html="")
    if request.method == "POST":
        jd.code = request.form["jd_code"].strip() or "JD01"
        jd.html = request.form["jd_text"]
        db.merge(jd)
        db.commit()
        db.close()
        flash("Job description saved")
        return redirect(url_for("home"))
    form = f"""
    <h4>Edit Job Description</h4>
    <form method=post>
      <label>Job Code</label>
      <input name=jd_code value="{jd.code}" class='form-control mb-2' required>
      <label>Description</label>
      <textarea name=jd_text rows=8 class='form-control' required>{jd.html}</textarea>
      <button class='btn btn-primary mt-2'>Save</button>
    </form>"""
    db.close()
    return page("Edit JD", form)

def current_jd():
    db = SessionLocal()
    jd = db.get(JobDescription, 1)
    db.close()
    return jd

# ─────────────────────── Upload résumé & score ───────────────────────
@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    jd = current_jd()
    jd_text = jd.html if jd else "(no JD set)"
    if request.method == "POST":
        name = request.form["name"].strip()
        f    = request.files["resume_file"]
        if not name or not f or f.filename == "":
            flash("Name & file required")
            return redirect("/")
        mime = mimetypes.guess_type(f.filename)[0] or f.mimetype
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            f.save(tmp.name)
            path = tmp.name
        # convert file → text
        try:
            text = file_to_text(path, mime)
        except ValueError:
            flash("Upload PDF or DOCX")
            return redirect("/")
        # AI calls
        rjs   = resume_json(text)
        score = fit_score(rjs, jd_text)
        cid   = str(uuid.uuid4())[:8]
        storage_path = upload_pdf(path)  # s3://… or local path
        with SessionLocal() as db:
            db.add(
                Candidate(
                    id=cid,
                    name=name,
                    resume_url=storage_path,
                    resume_json=rjs,
                    fit_score=score,
                    jd_code=jd.code if jd else "",
                )
            )
            db.commit()
        body = (
            f"<h4>Thanks, {name}!</h4>"
            f"<p>Relevance score: <strong>{score}/5</strong>.</p>"
            f"<a class='btn btn-secondary mt-3' href='{url_for('home')}'>Upload another résumé</a>"
        )
        return page("Result", body)

    form = f"""
    <h4>Current Job Description ({jd.code if jd else 'N/A'})</h4>
    <pre class='p-3 bg-white border'>{jd_text}</pre>
    <form method=post enctype=multipart/form-data class='card p-4 shadow-sm'>
      <div class='mb-3'>
        <label>Candidate Name</label>
        <input name=name class='form-control' required>
      </div>
      <div class='mb-3'>
        <label>Résumé (PDF or DOCX)</label>
        <input type=file name=resume_file accept='.pdf,.docx' class='form-control' required>
      </div>
      <button class='btn btn-primary w-100'>Upload & Score</button>
    </form>"""
    return page("Upload Résumé", form)

# ─────────────────────── Recruiter dashboard ─────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        rows = db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    table = (
        "".join(
            f"<tr>"
            f"<td>{c.jd_code}</td>"
            f"<td>{c.name}</td>"
            f"<td>{c.fit_score}</td>"
            f"<td><a href='{url_for('detail', cid=c.id)}'>view</a></td>"
            f"<td><a class='text-danger' href='{url_for('delete_candidate', cid=c.id)}' "
            f"onclick=\"return confirm('Delete this candidate?');\">✖</a></td>"
            f"</tr>"
            for c in rows
        )
        or "<tr><td colspan=5>No candidates</td></tr>"
    )
    body = (
        "<h4>Candidates</h4>"
        "<table class='table table-sm'>"
        "<thead>"
        "<tr><th>Job Code</th><th>Name</th><th>Score</th><th></th><th></th></tr>"
        "</thead><tbody>"
        + table
        + "</tbody></table>"
    )
    return page("Recruiter", body)

# ────────────────────── Candidate detail view ────────────────────────
@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    with SessionLocal() as db:
        c  = db.get(Candidate, cid)
        jd = db.query(JobDescription).filter_by(code=c.jd_code).first() if c else None
    if not c:
        flash("Not found")
        return redirect(url_for("recruiter"))
    jd_html = jd.html if jd else "(job description not found)"
    body = (
        f"<a href='{url_for('recruiter')}'>&larr; back</a>"
        f"<h4>{c.name}</h4>"
        f"<p>ID: {c.id}<br>Job Code: {c.jd_code}<br>"
        f"Score: <strong>{c.fit_score}/5</strong></p>"
        f"<details class='mb-3'><summary>View Job Description</summary><pre>{jd_html}</pre></details>"
        f"<a class='btn btn-outline-secondary' href='{url_for('download_resume', cid=cid)}'>Download résumé</a>"
    )
    return page("Candidate", body)

# ─────────────── Resumé download & candidate delete ──────────────────
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
        if not c:
            flash("Not found")
        else:
            # delete object from S3
            if S3_ENABLED and c.resume_url.startswith("s3://"):
                bucket, key = c.resume_url.split("/", 3)[2], c.resume_url.split("/", 3)[3]
                try:
                    s3.delete_object(Bucket=bucket, Key=key)
                except Exception as e:
                    logging.warning("S3 delete failed: %s", e)
            # local file cleanup (best effort)
            elif os.path.exists(c.resume_url):
                try:
                    os.remove(c.resume_url)
                except Exception:
                    pass
            db.delete(c)
            db.commit()
            flash("Candidate deleted")
    return redirect(url_for("recruiter"))

# ───────────────────────────── Entrypoint ────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
