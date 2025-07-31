import os, json, uuid, logging, tempfile, mimetypes, re
from flask import (
    Flask, request, redirect, url_for,
    render_template_string, flash, send_file, abort
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
import PyPDF2, docx
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

# ─── Flask-Login ──────────────────────────────────────────────────
@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal()
    u = db.get(User, int(uid))
    db.close()
    return u

# ─── OpenAI helpers ──────────────────────────────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0, top_p=0.1,
        response_format={"type":"json_object"} if structured else None,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

# ─── File-to-text helpers ─────────────────────────────────────────
def pdf_to_text(path):
    return "\n".join(
        p.extract_text() or "" for p in PyPDF2.PdfReader(path).pages
    )

def docx_to_text(path):
    return "\n".join(p.text for p in docx.Document(path).paragraphs)

def file_to_text(path, mime):
    if mime == "application/pdf":
        return pdf_to_text(path)
    if mime in (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document",
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

def realism_check(rjs: dict) -> bool:
    reply = chat(
        "You are a résumé authenticity checker.",
        json.dumps(rjs) + "\n\nIs this résumé realistic? yes or no."
    )
    return reply.lower().startswith("y")

def generate_questions(rjs: dict, jd_text: str) -> list[str]:
    raw = chat(
        "You are an interviewer.",
        f"Résumé JSON:\n{json.dumps(rjs)}\n\n"
        f"Job description:\n{jd_text}\n\n"
        "Write EXACTLY FOUR probing questions as a JSON array."
    )
    try:
        arr = json.loads(raw)
        if isinstance(arr, list): return arr[:4]
    except json.JSONDecodeError:
        pass
    # fallback: grab lines
    qs = [l.strip("-• ").strip() for l in raw.splitlines() if l.strip()]
    return qs[:4]

def score_answers(rjs: dict, qs: list[str], ans: list[str]) -> list[int]:
    scores = []
    for q,a in zip(qs,ans):
        wc = len(re.findall(r"\w+",a))
        if wc < 5:
            scores.append(1)
            continue
        cap = 2 if wc < 10 else None
        prompt = (
            f"Question: {q}\nCandidate answer: {a}\nRésumé JSON:\n"
            f"{json.dumps(rjs)[:1500]}\n\nScore this answer 1-5."
        )
        raw = chat("Grade the answer.", prompt)
        try:
            s = int(re.search(r"[1-5]", raw).group())
        except:
            s = 1
        if cap: s = min(s,cap)
        scores.append(s)
    # pad
    while len(scores)<4: scores.append(1)
    return scores

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
      <a class="btn btn-outline-secondary btn-sm me-2"
         href="{{ url_for('recruiter') }}">Recruiter</a>
      <span class="text-secondary me-2">{{ current_user.username }}</span>
      <a class="btn btn-outline-danger btn-sm"
         href="{{ url_for('logout') }}">Logout</a>
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

# ─── Auth Routes ─────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u,p = request.form["username"],request.form["password"]
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

# ─── Edit / Delete JD ────────────────────────────────────────────
@app.route("/edit-jd", methods=["GET","POST"])
@login_required
def edit_jd():
    db = SessionLocal()
    jd = db.get(JobDescription,1) or JobDescription(
        id=1, code="JD01", title="", html=""
    )
    if request.method=="POST":
        jd.code  = request.form["jd_code"].strip() or "JD01"
        jd.title = request.form["jd_title"].strip()
        jd.html  = request.form["jd_text"]
        db.merge(jd); db.commit(); db.close()
        flash("Job saved"); return redirect(url_for("recruiter"))
    form = (
      "<h4>Edit Job</h4><form method=post>"
      "<label>Code</label>"
      f"<input name=jd_code value='{jd.code}' class='form-control mb-2' required>"
      "<label>Title</label>"
      f"<input name=jd_title value='{jd.title}' class='form-control mb-2' required>"
      "<label>Description (HTML)</label>"
      f"<textarea name=jd_text rows=6 class='form-control'>{jd.html}</textarea>"
      "<button class='btn btn-primary mt-2'>Save</button></form>"
    )
    db.close()
    return page("Edit JD", form)

@app.route("/delete-jd/<code>")
@login_required
def delete_jd(code):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(code=code).first()
    if jd:
        db.delete(jd); db.commit(); flash(f"Deleted {code}")
    db.close()
    return redirect(url_for("recruiter"))

# ─── Recruiter Dashboard & Candidate Lists ───────────────────────
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
            f"<td><a href='{url_for('view_candidates',code=jd.code)}'>View Apps</a></td>"
            f"<td><a class='text-danger' "
              f"href='{url_for('delete_jd',code=jd.code)}' "
              "onclick=\"return confirm('Delete JD?');\">✖</a></td>"
          "</tr>"
        )
    db.close()
    body = (
      "<h4>Job Postings</h4>"
      "<table class='table table-sm'>"
        "<thead><tr><th>Code</th><th>Title</th><th></th><th></th></tr></thead>"
        "<tbody>" + (rows or "<tr><td colspan=4>No postings</td></tr>") + "</tbody>"
      "</table>"
      f"<a class='btn btn-primary' href='{url_for('edit_jd')}'>New / Edit JD</a>"
    )
    return page("Recruiter", body)

@app.route("/recruiter/jd/<code>")
@login_required
def view_candidates(code):
    db = SessionLocal()
    apps = db.query(Candidate).filter_by(jd_code=code).order_by(Candidate.created_at.desc()).all()
    db.close()
    rows = ""
    for c in apps:
        # average question score
        qs = c.answer_scores or []
        avg = round(sum(qs)/len(qs),2) if qs else "-"
        real = "Real" if c.realism else "Fake?"
        rows += (
          "<tr>"
            f"<td>{c.id}</td>"
            f"<td>{c.name}</td>"
            f"<td>{c.fit_score}</td>"
            f"<td>{real}</td>"
            f"<td>{avg}</td>"
            f"<td><a href='{url_for('detail',cid=c.id)}'>view</a></td>"
            f"<td><a class='text-danger' href='{url_for('delete_candidate',cid=c.id)}' "
              "onclick=\"return confirm('Delete this app?');\">✖</a></td>"
          "</tr>"
        )
    body = (
      f"<h4>Applications for {code}</h4>"
      "<table class='table table-sm'>"
        "<thead>"
          "<tr><th>ID</th><th>Name</th><th>Fit</th>"
             "<th>Realism</th><th>Avg Q</th><th></th><th></th></tr>"
        "</thead>"
        "<tbody>" + (rows or "<tr><td colspan=7>No apps</td></tr>") + "</tbody>"
      "</table>"
      f"<a class='btn btn-secondary' href='{url_for('recruiter')}'>← Back</a>"
    )
    return page(f"Apps: {code}", body)

# ─── Public Apply Flow ────────────────────────────────────────────
@app.route("/apply/<code>", methods=["GET","POST"])
def apply(code):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(code=code).first()
    db.close()
    if not jd:
        return abort(404)

    if request.method=="POST" and "resume_file" in request.files:
        name = request.form.get("name","").strip()
        f    = request.files["resume_file"]
        if not name or f.filename=="":
            flash("Name & résumé required"); return redirect(request.url)

        ext = os.path.splitext(f.filename)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False,suffix=ext) as tmp:
            f.save(tmp.name); path=tmp.name

        try:
            text = file_to_text(
                path,
                mimetypes.guess_type(f.filename)[0] or f.mimetype
            )
        except ValueError:
            flash("Upload PDF or DOCX only"); return redirect(request.url)

        rjs     = resume_json(text)
        fit     = fit_score(rjs, jd.html)
        real    = realism_check(rjs)
        qs      = generate_questions(rjs, jd.html)

        cid     = str(uuid.uuid4())[:8]
        storage = upload_pdf(path)

        # store incomplete app with questions
        db = SessionLocal()
        c = Candidate(
            id            = cid,
            name          = name,
            resume_url    = storage,
            resume_json   = rjs,
            fit_score     = fit,
            realism       = real,
            questions     = qs,
            answers       = [],
            answer_scores = [],
            jd_code       = jd.code
        )
        db.add(c); db.commit(); db.close()

        # render questions form
        items = "".join(
          f"<li class='list-group-item'><strong>{q}</strong>"
          f"<textarea name='a{i}' class='form-control mt-2' rows=2 required></textarea>"
          "</li>"
          for i,q in enumerate(qs)
        )
        form = (
          f"<h4>Hi {name}, answer these:</h4>"
          f"<form method='post' action='{url_for('submit_answers',code=code,cid=cid)}'>"
          f"<ul class='list-group mb-3'>{items}</ul>"
          "<button class='btn btn-primary w-100'>Submit Answers</button>"
          "</form>"
        )
        return page(f"Questions – {code}", form)

    # GET → upload form
    form = (
      f"<h4>Apply for {jd.code} — {jd.title}</h4>"
      f"<pre class='p-3 bg-white border'>{jd.html}</pre>"
      "<form method=post enctype=multipart/form-data class='card p-4 shadow-sm'>"
        "<div class='mb-3'><label>Your Name</label>"
        "<input name=name class='form-control' required></div>"
        "<div class='mb-3'><label>Résumé (PDF or DOCX)</label>"
        "<input type=file name=resume_file accept='.pdf,.docx' "
        "class='form-control' required></div>"
        "<button class='btn btn-primary w-100'>Upload & Get Questions</button>"
      "</form>"
    )
    return page(f"Apply – {code}", form)

@app.route("/apply/<code>/<cid>/answers", methods=["POST"])
def submit_answers(code, cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    if not c:
        db.close(); flash("App not found"); return redirect(url_for("apply",code=code))
    ans = [request.form.get(f"a{i}","").strip() for i in range(4)]
    scores = score_answers(c.resume_json, c.questions, ans)
    c.answers       = ans
    c.answer_scores = scores
    db.merge(c); db.commit(); db.close()

    # show final summary
    avg = round(sum(scores)/len(scores),2)
    real = "Realistic" if c.realism else "Possibly Fake"
    rows = "".join(
      f"<tr><td><strong>{q}</strong></td>"
      f"<td>{a or '<em>(no answer)</em>'}</td>"
      f"<td>{s}</td></tr>"
      for q,a,s in zip(c.questions, c.answers, c.answer_scores)
    )
    body = (
      f"<h4>Thanks, {c.name}!</h4>"
      f"<p>Relevance: <strong>{c.fit_score}/5</strong><br>"
      f"Realism: <strong>{real}</strong><br>"
      f"Avg Q-score: <strong>{avg}</strong></p>"
      "<h5>Your answers</h5>"
      "<table class='table'><thead>"
      "<tr><th>Q</th><th>A</th><th>Score</th></tr>"
      "</thead><tbody>" + rows + "</tbody></table>"
      f"<a class='btn btn-secondary' href='{url_for('apply',code=code)}'>Apply again</a> "
      f"<a class='btn btn-primary' href='{url_for('recruiter')}'>Recruiter view</a>"
    )
    return page("Done", body)

# ─── Download / Delete Résumé ────────────────────────────────────
@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    db = SessionLocal(); c = db.get(Candidate,cid); db.close()
    if not c: abort(404)
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))
    filename = os.path.basename(c.resume_url)
    return send_file(c.resume_url, as_attachment=True,
                     download_name=filename)

@app.route("/delete/<cid>")
@login_required
def delete_candidate(cid):
    db = SessionLocal(); c = db.get(Candidate,cid)
    if c:
        if S3_ENABLED and c.resume_url.startswith("s3://"):
            b,k = c.resume_url.split("/",3)[2:]
            try: presign.delete_object(Bucket=b,Key=k)
            except: pass
        elif os.path.exists(c.resume_url):
            try: os.remove(c.resume_url)
            except: pass
        db.delete(c); db.commit(); flash("Deleted application")
    db.close()
    return redirect(url_for("view_candidates", code=c.jd_code if c else ""))

# ─── Candidate Detail ────────────────────────────────────────────
@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    db = SessionLocal()
    c  = db.get(Candidate,cid)
    jd = db.query(JobDescription).filter_by(code=c.jd_code).first() if c else None
    db.close()
    if not c:
        flash("Not found"); return redirect(url_for("recruiter"))
    avg = round(sum(c.answer_scores)/len(c.answer_scores),2) if c.answer_scores else "-"
    real = "Realistic" if c.realism else "Possibly Fake"
    rows = "".join(
      f"<tr><td><strong>{q}</strong></td>"
      f"<td>{a or '<em>(no answer)</em>'}</td>"
      f"<td>{s}</td></tr>"
      for q,a,s in zip(c.questions, c.answers, c.answer_scores)
    )
    body = (
      f"<a href='{url_for('view_candidates',code=c.jd_code)}'>&larr; Back</a>"
      f"<h4>{c.name}</h4>"
      f"<p>ID: {c.id}<br>"
      f"JD: {c.jd_code} — {jd.title if jd else ''}<br>"
      f"Fit score: <strong>{c.fit_score}/5</strong><br>"
      f"Realism: <strong>{real}</strong><br>"
      f"Avg Q-score: <strong>{avg}</strong></p>"
      "<h5>Q&A</h5>"
      "<table class='table'><thead>"
      "<tr><th>Question</th><th>Answer</th><th>Score</th></tr>"
      "</thead><tbody>" + rows + "</tbody></table>"
      f"<a class='btn btn-outline-secondary' href='{url_for('download_resume',cid=cid)}'>Download résumé</a>"
    )
    return page(f"Candidate {c.name}", body)

# ─── Entrypoint ──────────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT",5000)))
