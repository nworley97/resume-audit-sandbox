import os, json, uuid, logging, tempfile, re, mimetypes
from datetime import datetime
from flask import (
    Flask, request, redirect, url_for, flash,
    render_template_string, send_file
)
from flask_login import (
    LoginManager, login_user, login_required, current_user, logout_user
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import PyPDF2, docx
from openai import OpenAI, APIError

# ──────────────────────────────────────────────────────
#  CONFIG ──────────────────────────────────────────────
# ──────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

from models import JobDescription, Candidate, User  # after SessionLocal exists

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "replace-me-in-prod")

# ──────────────────────────────────────────────────────
#  LOGIN ───────────────────────────────────────────────
# ──────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(uid: str):
    with SessionLocal() as db:
        return db.get(User, int(uid))

# ──────────────────────────────────────────────────────
#  OPENAI WRAPPER  ─────────────────────────────────────
# ──────────────────────────────────────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    """one-shot chat request."""
    kwargs = dict(
        model=MODEL,
        temperature=0,
        top_p=0.1,
        messages=[{"role": "system", "content": system},
                  {"role": "user",   "content": user}],
        timeout=timeout
    )
    if structured:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()
    except APIError as e:
        logging.error("OpenAI API error %s", e)
        raise RuntimeError("OpenAI failure") from e

# ──────────────────────────────────────────────────────
#  FILE → TEXT HELPERS ─────────────────────────────────
# ──────────────────────────────────────────────────────
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

# ──────────────────────────────────────────────────────
#  AI UTILS  ───────────────────────────────────────────
# ──────────────────────────────────────────────────────
def resume_json(txt):
    raw = chat("Extract résumé JSON with keys name, education, work_experience, skills.",
               txt, structured=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # second attempt (rare)
        raw = chat("Return only valid JSON.", txt, structured=True)
        return json.loads(raw)

def fit_score(rjs, jd_html):
    prompt = (
        f"Résumé JSON:\n{json.dumps(rjs, indent=2)}\n\n"
        f"Job description:\n{jd_html}\n\n"
        "Rate fit 1-5 (integer only)."
    )
    reply = chat("Score résumé vs JD.", prompt)
    m = re.search(r"[1-5]", reply)
    return int(m.group()) if m else 1

def generate_questions(rjs, jd_html):
    raw = chat(
        "Create exactly FOUR verification questions JSON-array.",
        f"{json.dumps(rjs)}\n\nJD:\n{jd_html}", structured=True
    )
    try: data = json.loads(raw)
    except json.JSONDecodeError: data = []
    if isinstance(data, list) and data:
        return [str(q) for q in data][:4]
    # fallback to bullet-list text
    return [l.strip("•- ").strip() for l in raw.splitlines() if l.strip()][:4]

def score_answers(rjs, qs, ans):
    scores = []
    for q, a in zip(qs, ans):
        wc = len(re.findall(r"\w+", a))
        if wc < 5:
            scores.append(1); continue
        cap = 2 if wc < 10 else 5
        prompt = (
            "Question: {q}\nAnswer: {a}\n"
            "Résumé snippet:\n{r}\n\n"
            "Score 1-5 where 5 = precise & matches résumé."
        ).format(q=q, a=a, r=json.dumps(rjs)[:1000])
        try:
            val = int(chat("Score answer.", prompt).strip())
        except ValueError:
            val = 1
        scores.append(max(1, min(cap, val)))
    while len(scores) < 4:
        scores.append(1)
    return scores

# ──────────────────────────────────────────────────────
#  HTML BASE  ──────────────────────────────────────────
# ──────────────────────────────────────────────────────
BASE = """<!doctype html><html lang=en><head>
<meta charset=utf-8><title>{{ title }}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand">Blackbox&nbsp;Strategies</span>
    {% if current_user.is_authenticated %}
      <span class="text-muted me-2">{{ current_user.username }}</span>
      <a class="btn btn-outline-secondary btn-sm me-2" href="{{ url_for('recruiter') }}">Dashboard</a>
      <a class="btn btn-outline-danger btn-sm" href="{{ url_for('logout') }}">Logout</a>
    {% endif %}
  </div>
</nav>
<div class="container" style="max-width:760px;">
  {% with m = get_flashed_messages() %}
    {% if m %}<div class="alert alert-danger">{{ m[0] }}</div>{% endif %}
  {% endwith %}
  {{ body|safe }}
</div></body></html>"""
def page(t,b): return render_template_string(BASE, title=t, body=b)

# ──────────────────────────────────────────────────────
#  AUTH ROUTES  ────────────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u, p = request.form["username"], request.form["password"]
        with SessionLocal() as db:
            user = db.query(User).filter_by(username=u).first()
        if user and user.check_pw(p):
            login_user(user)
            return redirect(url_for("recruiter"))
        flash("Bad credentials")
    body = """
    <h4>Login</h4>
    <form method=post>
      <input name=username class='form-control mb-2' placeholder='Email' required>
      <input name=password type=password class='form-control mb-2' placeholder='Password' required>
      <button class='btn btn-primary w-100'>Login</button>
    </form>"""
    return page("Login", body)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ──────────────────────────────────────────────────────
#  RECRUITER DASHBOARD  ────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        jds = db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()
    rows = "".join(
        f"<tr><td>{jd.code}</td><td>{jd.title}</td>"
        f"<td><a href='{url_for('jd_detail', slug=jd.slug)}'>open</a></td>"
        f"<td><a class='text-danger' href='{url_for('delete_jd', slug=jd.slug)}'"
        f" onclick=\"return confirm('Delete JD?');\">✖</a></td></tr>"
        for jd in jds
    ) or "<tr><td colspan=4>No postings</td></tr>"
    body = (
        "<a class='btn btn-success btn-sm float-end' href='/new-jd'>+ new JD</a>"
        "<h4 class='mb-3'>Job Postings</h4>"
        "<table class='table table-sm'><thead><tr><th>Code</th><th>Title</th><th></th><th></th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
    return page("Dashboard", body)

# ──────────────────────────────────────────────────────
#  CREATE NEW JD  ──────────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/new-jd", methods=["GET","POST"])
@login_required
def new_jd():
    if request.method == "POST":
        code  = request.form["code"].strip().upper()[:20]
        title = request.form["title"].strip()[:100]
        html  = request.form["desc"].strip()
        slug  = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or code.lower()
        with SessionLocal() as db:
            if db.query(JobDescription).filter_by(code=code).first():
                flash("Code already used"); return redirect("/new-jd")
            jd = JobDescription(code=code, slug=slug, title=title, html=html,
                                created_at=datetime.utcnow())
            db.add(jd); db.commit()
        return redirect(url_for("recruiter"))
    body = """
    <h4>New Job Description</h4>
    <form method=post>
      <label>Code (e.g. JD01)</label>
      <input name=code class='form-control mb-2' required>
      <label>Title</label>
      <input name=title class='form-control mb-2' required>
      <label>Description (HTML or plain text)</label>
      <textarea name=desc rows=8 class='form-control mb-2' required></textarea>
      <button class='btn btn-primary'>Save</button>
    </form>"""
    return page("New JD", body)

# ──────────────────────────────────────────────────────
#  JD DETAIL (lists its candidates)  ───────────────────
# ──────────────────────────────────────────────────────
@app.route("/jd/<slug>")
@login_required
def jd_detail(slug):
    with SessionLocal() as db:
        jd = db.query(JobDescription).filter_by(slug=slug).first()
        if not jd:
            flash("JD not found"); return redirect(url_for("recruiter"))
        cands = db.query(Candidate).filter_by(jd_code=jd.code).all()

    cand_rows = "".join(
        f"<tr><td>{c.name}</td><td>{c.fit_score}</td>"
        f"<td><a href='{url_for('candidate_detail', cid=c.id)}'>view</a></td></tr>"
        for c in cands
    ) or "<tr><td colspan=3>No applicants yet</td></tr>"

    body = (
        f"<a href='{url_for('recruiter')}'>&larr; back</a>"
        f"<h4>{jd.title} ({jd.code})</h4>"
        f"<pre class='p-3 bg-light'>{jd.html}</pre>"
        "<h5 class='mt-4'>Applicants</h5>"
        "<table class='table table-sm'><thead><tr><th>Name</th><th>Score</th><th></th></tr></thead>"
        f"<tbody>{cand_rows}</tbody></table>"
        f"<a class='btn btn-outline-primary mt-3' href='{url_for('apply', slug=jd.slug)}' target='_blank'>Public apply link</a>"
    )
    return page("Job Detail", body)

# ──────────────────────────────────────────────────────
#  DELETE JD  ──────────────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/delete-jd/<slug>")
@login_required
def delete_jd(slug):
    with SessionLocal() as db:
        jd = db.query(JobDescription).filter_by(slug=slug).first()
        if jd:
            db.delete(jd); db.commit()
            flash("Job deleted (candidates retained)")
    return redirect(url_for("recruiter"))

# ──────────────────────────────────────────────────────
#  PUBLIC APPLY PAGE  ──────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/apply/<slug>", methods=["GET","POST"])
def apply(slug):
    with SessionLocal() as db:
        jd = db.query(JobDescription).filter_by(slug=slug).first()
    if not jd:
        return "Job not found", 404

    if request.method == "POST":
        name = request.form["name"].strip()
        f = request.files["resume"]
        if not name or not f or f.filename == "":
            flash("Name & file required"); return redirect(request.url)

        mime = mimetypes.guess_type(f.filename)[0] or f.mimetype
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            f.save(tmp.name); path = tmp.name

        try:
            text = file_to_text(path, mime)
        except ValueError:
            flash("PDF or DOCX only"); return redirect(request.url)

        rjs = resume_json(text)
        score = fit_score(rjs, jd.html)
        qs = generate_questions(rjs, jd.html)
        cid = str(uuid.uuid4())[:8]

        # persist
        with SessionLocal() as db:
            db.add(Candidate(
                id=cid, name=name, resume_json=rjs, fit_score=score,
                jd_code=jd.code, created_at=datetime.utcnow()
            ))
            db.commit()

        # render Q-and-A form
        q_inputs = "".join(
            f"<li class='list-group-item'><strong>{q}</strong><br>"
            f"<textarea name='a{i}' class='form-control mt-2' rows=2 required></textarea></li>"
            for i, q in enumerate(qs)
        )
        body = (
            f"<h4>Thanks, {name}!</h4>"
            "<h5 class='mt-3'>Please answer:</h5>"
            f"<form method=post action='{url_for('submit_answers', cid=cid)}'>"
            f"<ol class='list-group list-group-numbered mb-3'>{q_inputs}</ol>"
            "<button class='btn btn-primary w-100'>Submit answers</button>"
            "</form>"
        )
        return page("Questions", body)

    body = (
        f"<h4>{jd.title}</h4><pre class='p-3 bg-light'>{jd.html}</pre>"
        "<form method=post enctype=multipart/form-data class='card p-4 shadow-sm mt-3'>"
        "<div class='mb-2'><label>Your name</label><input name=name class='form-control' required></div>"
        "<div class='mb-2'><label>Résumé (PDF or DOCX)</label>"
        "<input type=file name=resume accept='.pdf,.docx' class='form-control' required></div>"
        "<button class='btn btn-primary w-100'>Apply</button></form>"
    )
    return page("Apply", body)

# ──────────────────────────────────────────────────────
#  SUBMIT ANSWERS  ─────────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/answers/<cid>", methods=["POST"])
def submit_answers(cid):
    with SessionLocal() as db:
        c = db.get(Candidate, cid)
        if not c:
            flash("Candidate not found"); return redirect("/")
        ans = [request.form.get(f"a{i}", "").strip() for i in range(4)]
        c.answer_scores = score_answers(c.resume_json, c.questions, ans)
        c.answers = ans
        db.commit()
    return page("Submitted", "<h4>Answers received – thank you!</h4>")

# ──────────────────────────────────────────────────────
#  CANDIDATE DETAIL  ───────────────────────────────────
# ──────────────────────────────────────────────────────
@app.route("/candidate/<cid>")
@login_required
def candidate_detail(cid):
    with SessionLocal() as db:
        c = db.get(Candidate, cid)
    if not c: flash("Not found"); return redirect(url_for("recruiter"))
    avg = (sum(c.answer_scores) / len(c.answer_scores)
           if c.answer_scores else "-")
    qa = "".join(
        f"<tr><td>{q}</td><td>{a or '<em>—</em>'}</td><td>{s or '-'}</td></tr>"
        for q, a, s in zip(c.questions, c.answers or [], c.answer_scores or [])
    )
    body = (
        f"<a href='{url_for('jd_detail', slug=c.jd.slug)}'>&larr; back</a>"
        f"<h4>{c.name}</h4><p>Fit {c.fit_score}/5 &nbsp; Avg answer {avg}</p>"
        "<table class='table table-sm'><thead><tr><th>Q</th><th>Answer</th><th>Score</th></tr></thead>"
        f"<tbody>{qa}</tbody></table>"
    )
    return page("Candidate", body)

# ──────────────────────────────────────────────────────
#  MAIN  ───────────────────────────────────────────────
# ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
