"""
app.py  –  Blackboxstrategiesalpha résumé-scoring portal
"""
import os, json, uuid, logging, tempfile, mimetypes, re, bcrypt
from datetime import datetime
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Candidate, JobDescription, User
from s3util import upload_pdf, presign, S3_ENABLED, s3

# ─────────────────────────── Config ─────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me-in-prod")

# ──────────────── Flask-Login bootstrap ─────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(uid: str):
    with SessionLocal() as db:
        return db.get(User, int(uid))

# ─────────────── OpenAI helper ──────────────────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        top_p=0.1,
        response_format={"type": "json_object"} if structured else None,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

# ───────────── File-to-text helpers ─────────────────────────────
def pdf_to_text(path):  return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(path).pages)
def docx_to_text(path): return "\n".join(p.text for p in docx.Document(path).paragraphs)
def file_to_text(path, mime):
    if mime == "application/pdf": return pdf_to_text(path)
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return docx_to_text(path)
    raise ValueError("Unsupported file type")

# ───────────── AI helpers ───────────────────────────────────────
def resume_json(text: str) -> dict:
    raw = chat("Extract this résumé into JSON.", text, structured=True)
    try: return json.loads(raw)
    except json.JSONDecodeError:
        raw2 = chat("Return ONLY valid JSON for this résumé.", text, structured=True)
        return json.loads(raw2)

def fit_score(rjs: dict, jd_text: str) -> int:
    prompt = (
        f"Résumé JSON:\n{json.dumps(rjs, indent=2)}\n\n"
        f"Job description:\n{jd_text}\n\n"
        "Score the résumé's relevance on a 1-5 scale. "
        "Return ONLY the integer."
    )
    reply = chat("Score résumé vs JD.", prompt).strip()
    try: return int(reply)
    except ValueError:
        m=re.search(r"[1-5]",reply); return int(m.group()) if m else 1

def realism_check(rjs: dict) -> bool:
    verdict = chat(
        "Does this résumé appear human & realistic? Answer yes or no.",
        json.dumps(rjs)
    )
    return verdict.lower().startswith("y")

def generate_questions(rjs: dict, jd_text: str) -> list[str]:
    raw = chat(
        "Write exactly FOUR probing questions to verify the candidate's "
        "skills/experience for this job. Return JSON array of strings.",
        f"Résumé:\n{json.dumps(rjs)}\n\nJob:\n{jd_text}",
        structured=True,
    )
    return json.loads(raw)[:4]

def score_answers(rjs: dict, qs: list[str], ans: list[str]) -> list[int]:
    scores=[]
    for q,a in zip(qs,ans):
        wc=len(re.findall(r"\w+",a))
        if wc<5: scores.append(1); continue
        prompt=("Question: {q}\nAnswer: {a}\nRésumé snippet:\n{r}\n\n"
                "Score this answer 1-5 (5 perfect, 1 wrong). "
                "Return ONLY the integer."
               ).format(q=q,a=a,r=json.dumps(rjs)[:1500])
        try: s=int(chat("Grade answer.",prompt).strip())
        except: s=1
        scores.append(max(1,min(5,s)))
    while len(scores)<4: scores.append(1)
    return scores

# ───────────── HTML base template ───────────────────────────────
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
        <a class="btn btn-outline-secondary btn-sm me-2" href="{{ url_for('recruiter') }}">Dashboard</a>
        <a class="btn btn-outline-secondary btn-sm me-2" href="{{ url_for('new_jd') }}">New JD</a>
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
</div></body></html>"""
def page(t,body): return render_template_string(BASE,title=t,body=body)

# ───────────── Auth routes ───────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        uname,pw=request.form["username"],request.form["password"]
        with SessionLocal() as db:
            u=db.query(User).filter_by(username=uname).first()
        if u and u.check_pw(pw):
            login_user(u); return redirect(url_for("recruiter"))
        flash("Bad credentials")
    body=("""<h4>Login</h4><form method=post>
         <input name=username class='form-control mb-2' placeholder='Username' required>
         <input name=password type=password class='form-control mb-2' placeholder='Password' required>
         <button class='btn btn-primary w-100'>Login</button></form>""")
    return page("Login",body)

@app.route("/logout")
@login_required
def logout():
    logout_user(); return redirect(url_for("login"))

# ───────────── Job Posting CRUD (Recruiter) ──────────────────────
@app.route("/new-jd", methods=["GET","POST"])
@login_required
def new_jd():
    if request.method=="POST":
        code=request.form["code"].strip()
        slug=request.form["slug"].strip()
        title=request.form["title"].strip()
        html=request.form["html"]
        with SessionLocal() as db:
            if db.query(JobDescription).filter_by(code=code).first():
                flash("Code already exists"); return redirect(url_for("new_jd"))
            if db.query(JobDescription).filter_by(slug=slug).first():
                flash("Slug already exists"); return redirect(url_for("new_jd"))
            db.add(JobDescription(code=code, slug=slug, title=title, html=html))
            db.commit()
        flash("Posting created"); return redirect(url_for("recruiter"))
    body=("""<h4>New Job Posting</h4><form method=post>
        <input name=code class='form-control mb-2' placeholder='JD code (e.g. JD03)' required>
        <input name=slug class='form-control mb-2' placeholder='Public slug (e.g. data-eng)' required>
        <input name=title class='form-control mb-2' placeholder='Title' required>
        <textarea name=html rows=8 class='form-control mb-2' placeholder='Description' required></textarea>
        <button class='btn btn-primary'>Save</button></form>""")
    return page("New JD",body)

# ───────────── Public apply route ───────────────────────────────
@app.route("/apply/<slug>", methods=["GET","POST"])
def apply(slug):
    with SessionLocal() as db:
        jd=db.query(JobDescription).filter_by(slug=slug).first()
    if not jd: return "Job not found",404

    # ----- Upload flow -----
    if request.method=="POST" and "resume_file" in request.files:
        name=request.form["name"].strip(); f=request.files["resume_file"]
        if not name or not f.filename: flash("Name & file required"); return redirect(request.url)
        mime=mimetypes.guess_type(f.filename)[0] or f.mimetype
        with tempfile.NamedTemporaryFile(delete=False) as tmp: f.save(tmp.name); path=tmp.name
        try: text=file_to_text(path,mime)
        except ValueError: flash("PDF or DOCX only"); return redirect(request.url)
        rjs=resume_json(text)
        fit=fit_score(rjs,jd.html)
        real=realism_check(rjs)
        qs=generate_questions(rjs,jd.html)
        cid=str(uuid.uuid4())[:8]
        storage=upload_pdf(path)
        with SessionLocal() as db:
            db.add(Candidate(
                id=cid, jd_code=jd.code, name=name,
                resume_url=storage, resume_json=rjs,
                fit_score=fit, realism=real,
                questions=qs, answers=[], answer_scores=[]
            )); db.commit()
        # show questions form
        q_inputs="".join(
           f"<li class='list-group-item'><strong>{q}</strong><br>"
           f"<textarea name=a{i} rows=2 class='form-control mt-1' required></textarea></li>"
           for i,q in enumerate(qs))
        return page("Answer Questions", f"""
           <h4>Hi {name}! Please answer:</h4>
           <form method=post action='{url_for('submit_answers',cid=cid)}'>
             <ol class='list-group list-group-numbered'>{q_inputs}</ol>
             <button class='btn btn-primary w-100 mt-3'>Submit answers</button>
           </form>""")

    # ----- Show JD + upload form -----
    jd_block=(f"<h3>{jd.title or jd.code}</h3><div class='mb-3'>{jd.html}</div>")
    form=("""<form method=post enctype=multipart/form-data class='card p-4 shadow-sm'>
         <div class='mb-3'><label>Candidate Name</label>
         <input name=name class='form-control' required></div>
         <div class='mb-3'><label>Résumé (PDF or DOCX)</label>
         <input type=file name=resume_file accept='.pdf,.docx' class='form-control' required></div>
         <button class='btn btn-primary w-100'>Submit résumé</button></form>""")
    return page(jd.title or "Apply", jd_block+form)

# ───────────── Submit answers route ──────────────────────────────
@app.route("/answers/<cid>", methods=["POST"])
def submit_answers(cid):
    with SessionLocal() as db:
        c=db.get(Candidate,cid)
        if not c: flash("Not found"); return redirect("/")
        answers=[request.form.get(f"a{i}","").strip() for i in range(4)]
        scores=score_answers(c.resume_json,c.questions,answers)
        c.answers=answers; c.answer_scores=scores; db.commit()
    return page("Thank you","<h4>Your application is complete.</h4>")

# ───────────── Recruiter dashboard ───────────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        rows=db.query(Candidate).order_by(Candidate.created_at.desc()).all()
    table="".join(
        f"<tr><td>{c.jd_code}</td><td>{c.name}</td><td>{c.fit_score}</td>"
        f"<td>{'✅' if c.realism else '⚠'}</td>"
        f"<td><a href='{url_for('detail',cid=c.id)}'>view</a></td>"
        f"<td><a class='text-danger' href='{url_for('delete_candidate',cid=c.id)}' "
        "onclick=\"return confirm('Delete this candidate?');\">✖</a></td></tr>"
        for c in rows) or "<tr><td colspan=6>No candidates</td></tr>"
    body=("""<h4>Candidates</h4><table class='table table-sm'>
         <thead><tr><th>Job</th><th>Name</th><th>Fit</th><th>Real?</th><th></th><th></th></tr></thead>
         <tbody>"""+table+"</tbody></table>")
    return page("Recruiter",body)

# ───────────── Candidate detail ──────────────────────────────────
@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    with SessionLocal() as db:
        c=db.get(Candidate,cid)
        jd=db.query(JobDescription).filter_by(code=c.jd_code).first() if c else None
    if not c: flash("Not found"); return redirect(url_for("recruiter"))
    qa_rows="".join(
       f"<tr><td>{q}</td><td>{(c.answers[i] if i<len(c.answers) else '')}</td>"
       f"<td>{(c.answer_scores[i] if i<len(c.answer_scores) else '-')}</td></tr>"
       for i,q in enumerate(c.questions))
    body=(f"<a href='{url_for('recruiter')}'>&larr; back</a>"
          f"<h4>{c.name}</h4><p>ID: {c.id}<br>Job: {c.jd_code}<br>"
          f"Fit: <strong>{c.fit_score}/5</strong><br>"
          f"Realism: {'✅' if c.realism else '⚠'}</p>"
          f"<details class='mb-3'><summary>Job Description</summary><pre>{jd.html if jd else '(missing)'}</pre></details>"
          f"<a class='btn btn-outline-secondary mb-3' href='{url_for('download_resume',cid=cid)}'>Download résumé</a>"
          "<h5>Interview Q&A</h5><table class='table table-sm'>"
          "<thead><tr><th>Question</th><th>Answer</th><th>Score</th></tr></thead>"
          f"<tbody>{qa_rows}</tbody></table>")
    return page("Candidate",body)

# ───────────── Resume download / delete ─────────────────────────
@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    with SessionLocal() as db: c=db.get(Candidate,cid)
    if not c: flash("Not found"); return redirect(url_for("recruiter"))
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))
    return send_file(c.resume_url, as_attachment=True, download_name=f"{c.name}.pdf")

@app.route("/delete/<cid>")
@login_required
def delete_candidate(cid):
    with SessionLocal() as db:
        c=db.get(Candidate,cid)
        if not c: flash("Not found")
        else:
            if S3_ENABLED and c.resume_url.startswith("s3://"):
                b,k=c.resume_url.split("/",3)[2],c.resume_url.split("/",3)[3]
                try: s3.delete_object(Bucket=b,Key=k)
                except Exception as e: logging.warning("S3 delete failed: %s",e)
            elif os.path.exists(c.resume_url):
                try: os.remove(c.resume_url)
                except: pass
            db.delete(c); db.commit(); flash("Deleted")
    return redirect(url_for("recruiter"))

# ───────────── Entrypoint ───────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0",port=int(os.getenv("PORT",5000)))
