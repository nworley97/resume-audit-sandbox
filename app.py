import os
import json
import uuid
import logging
import tempfile
import mimetypes
import re

from flask import (
    Flask, request, redirect, url_for,
    render_template_string, flash, send_file, abort
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
import PyPDF2
import docx
from openai import OpenAI

from db import SessionLocal
from models import User, JobDescription, Candidate
from s3util import upload_pdf, presign, S3_ENABLED

# ─── Config ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me")

login_manager = LoginManager(app)
login_manager.login_view = "login"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

# ─── User Loader ─────────────────────────────────────────────────
@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal()
    u = db.get(User, int(uid))
    db.close()
    return u

# ─── OpenAI helper ────────────────────────────────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0, top_p=0.1,
        response_format={"type":"json_object"} if structured else None,
        messages=[
            {"role":"system","content":system},
            {"role":"user","content":user}
        ],
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

# ─── File→Text helpers ────────────────────────────────────────────
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

# ─── AI scoring helpers ───────────────────────────────────────────
def resume_json(text: str) -> dict:
    raw = chat("Extract résumé to JSON.", text, structured=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw2 = chat("Return ONLY valid JSON résumé.", text, structured=True)
        return json.loads(raw2)

def fit_score(rjs: dict, jd_text: str) -> int:
    prompt = (
        f"Résumé JSON:\n{json.dumps(rjs,indent=2)}\n\n"
        f"Job description:\n{jd_text}\n\n"
        "Score 1-5 (5 best). Return ONLY the integer."
    )
    reply = chat("Score résumé vs JD.", prompt).strip()
    m = re.search(r"[1-5]", reply)
    return int(m.group()) if m else 1

def generate_questions(rjs: dict, jd_text: str) -> list[str]:
    raw = chat(
        "You are an interviewer.",
        f"Résumé JSON:\n{json.dumps(rjs)}\n\nJob:\n{jd_text}\n\n"
        "Write EXACTLY FOUR probing questions as a JSON array."
    )
    arr = json.loads(raw)
    return arr[:4]

# ─── Base HTML Template ──────────────────────────────────────────
BASE = """
<!doctype html><html lang=en><head>
  <meta charset=utf-8>
  <title>{{ title }}</title>
  <link
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
    rel="stylesheet">
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand">Blackboxstrategiesalpha</span>
    {% if current_user.is_authenticated %}
      <div>
        <a class="btn btn-outline-secondary btn-sm me-2"
           href="{{ url_for('recruiter') }}">Recruiter</a>
        <span class="me-2 text-secondary">{{ current_user.username }}</span>
        <a class="btn btn-outline-danger btn-sm"
           href="{{ url_for('logout') }}">Logout</a>
      </div>
    {% endif %}
  </div>
</nav>
<div class="container" style="max-width:720px;">
  {% for m in get_flashed_messages() %}
    <div class="alert alert-danger">{{ m }}</div>
  {% endfor %}
  {{ body|safe }}
</div></body></html>
"""
def page(title, body):
    return render_template_string(BASE, title=title, body=body)

# ─── Auth ─────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u = request.form["username"]
        p = request.form["password"]
        db = SessionLocal()
        user = db.query(User).filter_by(username=u).first()
        db.close()
        if user and user.check_pw(p):
            login_user(user)
            return redirect(url_for("recruiter"))
        flash("Bad credentials")
    form = """
      <h4>Login</h4>
      <form method=post>
        <input name=username class='form-control mb-2'
               placeholder='Username' required>
        <input name=password type=password class='form-control mb-2'
               placeholder='Password' required>
        <button class='btn btn-primary w-100'>Login</button>
      </form>
    """
    return page("Login", form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ─── Edit Job Description ─────────────────────────────────────────
@app.route("/edit-jd", methods=["GET","POST"])
@login_required
def edit_jd():
    db = SessionLocal()
    jd = db.get(JobDescription, 1) or JobDescription(id=1, code="JD01",
                                                     title="", html="")
    if request.method=="POST":
        jd.code  = request.form["jd_code"].strip() or "JD01"
        jd.title = request.form["jd_title"].strip()
        jd.html  = request.form["jd_text"]
        db.merge(jd)
        db.commit()
        db.close()
        flash("Job description saved")
        return redirect(url_for("recruiter"))

    form = (
      "<h4>Edit Job Description</h4>"
      "<form method=post>"
        "<label>Code</label>"
        f"<input name=jd_code value='{jd.code}' class='form-control mb-2' required>"
        "<label>Title</label>"
        f"<input name=jd_title value='{jd.title}' class='form-control mb-2' required>"
        "<label>Description (plain HTML)</label>"
        f"<textarea name=jd_text rows=6 class='form-control' required>{jd.html}</textarea>"
        "<button class='btn btn-primary mt-2'>Save</button>"
      "</form>"
    )
    db.close()
    return page("Edit JD", form)

# ─── Recruiter Dashboard ──────────────────────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    db = SessionLocal()
    jds = db.query(JobDescription).order_by(JobDescription.id).all()
    rows = ""
    for jd in jds:
        rows += (
          "<tr>"
            f"<td>{jd.code}</td>"
            f"<td>{jd.title}</td>"
            f"<td><a href='{url_for('apply', code=jd.code)}'>Apply Link</a></td>"
            f"<td><a href='{url_for('delete_jd', code=jd.code)}'"
              " onclick=\"return confirm('Delete JD?');\">✖</a></td>"
          "</tr>"
        )
    db.close()
    body = (
      "<h4>Job Postings</h4>"
      "<table class='table table-sm'><thead>"
        "<tr><th>Code</th><th>Title</th><th></th><th></th></tr>"
      "</thead><tbody>"
      f"{rows or '<tr><td colspan=4>No postings</td></tr>'}"
      "</tbody></table>"
      f"<a class='btn btn-primary' href='{url_for('edit_jd')}'>New / Edit JD</a>"
    )
    return page("Recruiter", body)

@app.route("/delete-jd/<code>")
@login_required
def delete_jd(code):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(code=code).first()
    if jd:
        db.delete(jd)
        db.commit()
        flash(f"Deleted {code}")
    db.close()
    return redirect(url_for("recruiter"))

# ─── Candidate Upload & Score ────────────────────────────────────
@app.route("/", methods=["GET","POST"])
@login_required
def home():
    # show posting list or redirect to /recruiter if none
    return redirect(url_for("recruiter"))

# ─── Public Apply Page ───────────────────────────────────────────
@app.route("/apply/<code>", methods=["GET","POST"])
def apply(code):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(code=code).first()
    db.close()
    if not jd:
        abort(404)

    if request.method == "POST":
        name = request.form.get("name","").strip()
        f    = request.files.get("resume_file")
        if not name or not f or f.filename=="":
            flash("Name & résumé required")
            return redirect(request.url)

        # preserve extension
        ext  = os.path.splitext(f.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            f.save(tmp.name)
            path = tmp.name

        try:
            text = file_to_text(path, mimetypes.guess_type(f.filename)[0] or f.mimetype)
        except ValueError:
            flash("Upload PDF or DOCX only")
            return redirect(request.url)

        rjs   = resume_json(text)
        score = fit_score(rjs, jd.html)
        qs    = generate_questions(rjs, jd.html)

        cid     = str(uuid.uuid4())[:8]
        storage = upload_pdf(path)
        db = SessionLocal()
        db.add(Candidate(
            id          = cid,
            name        = name,
            resume_url  = storage,
            resume_json = rjs,
            fit_score   = score,
            jd_code     = jd.code
        ))
        db.commit()
        db.close()

        # redirect to answers page or show immediate result
        body = (
          f"<h4>Thanks, {name}!</h4>"
          f"<p>Relevance score: <strong>{score}/5</strong></p>"
          f"<p><a class='btn btn-secondary' href='{url_for('apply',code=code)}'>Apply another</a></p>"
          f"<p><a class='btn btn-primary' href='{url_for('recruiter')}'>Recruiter View</a></p>"
        )
        return page(f"Applied – {code}", body)

    form = (
      f"<h4>Apply for {jd.code} — {jd.title}</h4>"
      f"<pre class='p-3 bg-white border'>{jd.html}</pre>"
      "<form method=post enctype=multipart/form-data class='card p-4 shadow-sm'>"
        "<div class='mb-3'><label>Your Name</label>"
        "<input name=name class='form-control' required></div>"
        "<div class='mb-3'><label>Résumé (PDF or DOCX)</label>"
        "<input type=file name=resume_file accept='.pdf,.docx' class='form-control' required></div>"
        "<button class='btn btn-primary w-100'>Submit & Score</button>"
      "</form>"
    )
    return page(f"Apply – {jd.code}", form)

# ─── Download or Delete Résumé ───────────────────────────────────
@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    db.close()
    if not c:
        abort(404)

    # S3
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))

    # local file → serve with its real extension
    filename = os.path.basename(c.resume_url)
    return send_file(
        c.resume_url,
        as_attachment=True,
        download_name=filename
    )

@app.route("/delete/<cid>")
@login_required
def delete_candidate(cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    if c:
        if S3_ENABLED and c.resume_url.startswith("s3://"):
            # delete in S3
            b,k = c.resume_url.split("/",3)[2:]
            try: presign.delete_object(Bucket=b, Key=k)
            except: pass
        elif os.path.exists(c.resume_url):
            try: os.remove(c.resume_url)
            except: pass
        db.delete(c)
        db.commit()
        flash("Candidate deleted")
    db.close()
    return redirect(url_for("recruiter"))

# ─── Candidate Detail (Recruiter) ───────────────────────────────
@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    jd = db.query(JobDescription).filter_by(code=c.jd_code).first() if c else None
    db.close()
    if not c:
        flash("Not found")
        return redirect(url_for("recruiter"))

    jd_html = jd.html if jd else "(JD not found)"
    body = (
      f"<a href='{url_for('recruiter')}'>&larr; Back</a>"
      f"<h4>{c.name}</h4>"
      f"<p>ID: {c.id}<br>JD: {c.jd_code}<br>"
        f"Score: <strong>{c.fit_score}/5</strong></p>"
      f"<details class='mb-3'><summary>Job Description</summary>"
        f"<pre>{jd_html}</pre></details>"
      f"<a class='btn btn-outline-secondary' "
        f"href='{url_for('download_resume',cid=cid)}'>Download Résumé</a>"
    )
    return page(f"Candidate {c.name}", body)

# ─── Entrypoint ──────────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0",
            port=int(os.getenv("PORT",5000)))
