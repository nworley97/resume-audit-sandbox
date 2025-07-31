import os, json, uuid, logging, tempfile, mimetypes, re, textwrap
import PyPDF2, docx
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    flash, send_file
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openai import OpenAI

from models import Base, Candidate, JobDescription, User

# ── config ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

DATABASE_URL = os.getenv("DATABASE_URL")
engine       = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me-secret")

# ── flask-login ───────────────────────────────────────────
lm = LoginManager(app); lm.login_view = "login"
@lm.user_loader
def load_user(uid): db=SessionLocal(); u=db.get(User,int(uid)); db.close(); return u

# ── helper: chat wrapper ─────────────────────────────────
def chat(system, user, *, json_mode=False, timeout=60):
    resp = client.chat.completions.create(
        model=MODEL, temperature=0, top_p=0.1,
        response_format={"type":"json_object"} if json_mode else None,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

# ── file → text converters ───────────────────────────────
def pdf_to_text(p): return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(p).pages)
def docx_to_text(path): return "\n".join(p.text for p in docx.Document(path).paragraphs)
def file_to_text(path,mime):
    if mime=="application/pdf": return pdf_to_text(open(path,"rb"))
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword"): return docx_to_text(path)
    raise ValueError("Unsupported file type")

# ── AI helpers ───────────────────────────────────────────
def resume_json(text:str)->dict:
    raw = chat("Extract résumé to JSON.", text, json_mode=True)
    try: return json.loads(raw)
    except json.JSONDecodeError:
        raw2 = chat("Return ONLY JSON.", text, json_mode=True)
        return json.loads(raw2)

def fit_score(rjs, jd_text):
    prompt=f"{json.dumps(rjs,indent=2)}\n\nJob description:\n{jd_text}\n\nReturn 1-5 only."
    reply=chat("Score résumé vs JD.", prompt).strip()
    m=re.search(r"[1-5]", reply); return int(m.group()) if m else 1

def generate_questions(rjs, jd_text):
    prompt = (
        "Write EXACTLY four verification questions (array of strings) "
        "about candidate's skills/claims only. Do NOT mention the job posting."
        f"\nRésumé JSON:\n{json.dumps(rjs,indent=2)}\n"
        "Return JSON."
    )
    raw = chat("Make questions", prompt, json_mode=True)
    data = json.loads(raw)
    if isinstance(data, list): return data[:4]
    if isinstance(data, dict) and "questions" in data: return data["questions"][:4]
    return [l.strip("-• ").strip() for l in raw.splitlines() if l.strip()][:4]

def score_answers(rjs, qs, ans):
    out=[]
    for q,a in zip(qs,ans):
        wc=len(re.findall(r"\w+",a)); cap=2 if wc<10 else None
        if wc<5: out.append(1); continue
        p=(f"Question: {q}\nAnswer: {a}\nRésumé (JSON): {json.dumps(rjs)[:1500]}"
           "\nScore 1-5 (5 precise).\nReturn digit only.")
        reply=chat("Grade answer strictly",p)
        m=re.search(r"[1-5]",reply); score=int(m.group()) if m else 1
        out.append(min(score,cap) if cap else score)
    return out or [ ]

# ── html template helper ─────────────────────────────────
BASE = """
<!doctype html><html lang=en><head>
<meta charset=utf-8><title>{{ title }}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
<style>body{background:#f8f9fa}</style></head><body>
<nav class="navbar navbar-light bg-white border-bottom mb-4 px-3">
  <span class="navbar-brand">Blackbox Strategies Alpha</span>
  {% if current_user.is_authenticated %}
    <div>
      <a class="btn btn-sm btn-outline-primary me-2" href="{{ url_for('recruiter') }}">Recruiter</a>
      <span class="text-muted me-2">{{ current_user.username }}</span>
      <a class="btn btn-sm btn-outline-danger" href="{{ url_for('logout') }}">Logout</a>
    </div>
  {% endif %}
</nav>
<div class="container" style="max-width:800px">
 {% with m=get_flashed_messages()%}{% if m %}<div class="alert alert-danger">{{m[0]}}</div>{%endif%}{%endwith%}
 {{ body|safe }}
</div></body></html>"""
def page(t,b): return render_template_string(BASE,title=t,body=b)

# ── authentication routes ───────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u,p=request.form["username"],request.form["password"]
        with SessionLocal() as db:
            usr=db.query(User).filter_by(username=u).first()
        if usr and usr.check_pw(p):
            login_user(usr); return redirect(url_for("recruiter"))
        flash("Bad credentials")
    body="""<h4>Login</h4><form method=post>
        <input name=username class='form-control mb-2' placeholder='User' required>
        <input name=password type=password class='form-control mb-3' placeholder='Password' required>
        <button class='btn btn-primary w-100'>Sign in</button></form>"""
    return page("Login",body)

@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("login"))

# ── recruiter dashboard: list all JDs ───────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    with SessionLocal() as db:
        jds=db.query(JobDescription).order_by(JobDescription.id.desc()).all()
    rows = "".join(
    f"<tr><td>{jd.code}</td><td>{jd.title}</td>"
    f"<td><a href='{url_for('jd_detail', slug=jd.slug)}'>open</a></td>"
    f"<td><a class='text-danger' href='{url_for('delete_jd', slug=jd.slug)}'"
    f" onclick=\"return confirm('Delete JD?');\">✖</a></td></tr>"
    for jd in jds) or "<tr><td colspan=4>No postings</td></tr>"
    body = ("""<h4>Job Postings</h4><table class='table table-sm'>
    <thead><tr><th>Code</th><th>Title</th><th></th><th></th></tr></thead>
    <tbody>"""+rows+"</tbody></table>" +
    "<a class='btn btn-success' href='/new-jd'>+ New JD</a>")
    return page("Dashboard",body)

# ── create JD ────────────────────────────────────────────
@app.route("/new-jd", methods=["GET","POST"])
@login_required
def new_jd():
    if request.method=="POST":
        code=request.form["code"].strip()
        slug=request.form["slug"].strip()
        title=request.form["title"].strip()
        html=request.form["html"].strip()
        with SessionLocal() as db:
            if db.query(JobDescription).filter_by(code=code).first():
                flash("Code already exists"); return redirect("/new-jd")
            jd=JobDescription(code=code,slug=slug,title=title,html=html)
            db.add(jd); db.commit()
        flash("JD created"); return redirect(url_for("recruiter"))
    body = """<h4>New Job Description</h4><form method=post>
    <input name=code  class='form-control mb-2' placeholder='Code (JD01)' required>
    <input name=slug  class='form-control mb-2' placeholder='Public slug (frontend-eng)' required>
    <input name=title class='form-control mb-2' placeholder='Display title' required>
    <textarea name=html rows=8 class='form-control mb-3' placeholder='Description (HTML or text)' required></textarea>
    <button class='btn btn-primary w-100'>Create</button></form>"""
    return page("New JD",body)

# AFTER your /new-jd route add:
@app.route("/jd/<slug>")
@login_required
def jd_detail(slug):
    with SessionLocal() as db:
        jd = db.query(JobDescription).filter_by(slug=slug).first()
        if not jd:
            flash("Job description not found")
            return redirect(url_for("recruiter"))

        cands = db.query(Candidate).filter_by(jd_code=jd.code).all()

    rows = "".join(
        f"<tr><td>{c.name}</td><td>{c.fit_score}</td>"
        f"<td><a href='{url_for('candidate_detail', cid=c.id)}'>view</a></td></tr>"
        for c in cands
    ) or "<tr><td colspan=3>No applicants yet</td></tr>"

    body = (
        f"<h4>{jd.title} ({jd.code})</h4>"
        f"<pre class='p-3 bg-light'>{jd.html}</pre>"
        "<h5 class='mt-4'>Applicants</h5>"
        "<table class='table table-sm'><thead><tr><th>Name</th><th>Score</th><th></th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"<a class='btn btn-secondary mt-3' href='{url_for('recruiter')}'>← back</a>"
    )
    return page("Job Detail", body)

@app.route("/delete-jd/<slug>")
@login_required
def delete_jd(slug):
    with SessionLocal() as db:
        jd=db.query(JobDescription).filter_by(slug=slug).first()
        if jd: db.delete(jd); db.commit()
    flash("JD deleted"); return redirect(url_for("recruiter"))

# ── JD detail: list candidates ───────────────────────────
@app.route("/recruiter/<slug>")
@login_required
def jd_detail(slug):
    with SessionLocal() as db:
        jd  = db.query(JobDescription).filter_by(slug=slug).first()
        cns = db.query(Candidate).filter_by(jd_code=jd.code).order_by(Candidate.created_at.desc()).all()
    rows="".join(
        f"<tr><td>{c.name}</td><td>{c.fit_score}</td><td>{c.avg_validity}</td>"
        f"<td><a href='{url_for('candidate_detail',cid=c.id)}'>view</a></td></tr>"
        for c in cns) or "<tr><td colspan=4>No applicants yet</td></tr>"
    body=(f"<a href='{url_for('recruiter')}'>&larr; All JDs</a>"
          f"<h4>{jd.code} – {jd.title}</h4>"
          f"<pre class='p-3 bg-white border'>{jd.html}</pre>"
          f"<p><strong>Public link:</strong> "
          f"<a href='{url_for('apply',slug=slug,_external=True)}'>{url_for('apply',slug=slug,_external=True)}</a></p>"
          "<h5>Applicants</h5>"
          "<table class='table table-sm'><thead><tr><th>Name</th><th>Fit</th><th>Avg Valid</th><th></th></tr></thead>"
          f"<tbody>{rows}</tbody></table>")
    return page(jd.title,body)

# ── candidate detail ─────────────────────────────────────
@app.route("/c/<cid>")
@login_required
def candidate_detail(cid):
    with SessionLocal() as db: c=db.get(Candidate,cid)
    if not c: flash("Not found"); return redirect(url_for("recruiter"))
    qa="".join(f"<tr><td>{q}</td><td>{a}</td><td>{s}</td></tr>"
               for q,a,s in zip(c.resume_json.get('questions',[]),c.resume_json.get('answers',[]),c.answer_scores or []))
    body=(f"<a href='{url_for('jd_detail',slug=c.jd.slug)}'>&larr; back</a>"
          f"<h4>{c.name}</h4><p>Fit: {c.fit_score}/5 &nbsp; Avg Validity: {c.avg_validity}</p>"
          "<table class='table table-sm'><thead><tr><th>Q</th><th>A</th><th>S</th></tr></thead>"
          f"<tbody>{qa or '<tr><td colspan=3>No Q data</td></tr>'}</tbody></table>")
    return page("Candidate",body)

# ── public apply page ────────────────────────────────────
@app.route("/apply/<slug>", methods=["GET","POST"])
def apply(slug):
    with SessionLocal() as db:
        jd=db.query(JobDescription).filter_by(slug=slug).first()
    if not jd: return "JD not found",404

    if request.method=="POST":
        name=request.form["name"].strip(); f=request.files["resume"]
        if not name or not f.filename: flash("Name & file required"); return redirect(request.url)
        mime=mimetypes.guess_type(f.filename)[0] or f.mimetype
        with tempfile.NamedTemporaryFile(delete=False) as tmp: f.save(tmp.name); path=tmp.name
        try: text=file_to_text(path,mime)
        except ValueError: flash("Upload PDF or DOCX"); return redirect(request.url)
        rjs=resume_json(text)
        fit=fit_score(rjs,jd.html)
        qs=generate_questions(rjs,jd.html)
        cid=str(uuid.uuid4())[:8]
        # store candidate
        with SessionLocal() as db:
            db.add(Candidate(id=cid,name=name,resume_url=path,resume_json=rjs,
                             fit_score=fit,jd_code=jd.code))
            db.commit()
        # show questions form
        q_inputs="".join(
            f"<li class='list-group-item'><strong>{q}</strong><br>"
            f"<textarea name='a{i}' rows=2 class='form-control mt-2' required></textarea></li>"
            for i,q in enumerate(qs))
        body=(f"<h4>Thanks, {name}!</h4><p>Please answer these questions:</p>"
              f"<form method=post action='{url_for('submit_answers',cid=cid)}'>"
              f"<ol class='list-group list-group-numbered mb-3'>{q_inputs}</ol>"
              "<button class='btn btn-primary w-100'>Submit</button></form>")
        # temporarily stash Qs in résumé_json to recall later
        with SessionLocal.begin() as db:
            c=db.get(Candidate,cid); c.resume_json["questions"]=qs
        return page("Questions",body)

    body=(f"<h4>Apply – {jd.title}</h4>"
          f"<pre class='p-3 bg-white border'>{jd.html}</pre>"
          "<form method=post enctype=multipart/form-data class='card p-4'>"
          "<input name=name class='form-control mb-2' placeholder='Your name' required>"
          "<input type=file name=resume accept='.pdf,.docx' class='form-control mb-3' required>"
          "<button class='btn btn-success w-100'>Upload résumé</button></form>")
    return page("Apply",body)

# ── submit answers & score ───────────────────────────────
@app.route("/answers/<cid>", methods=["POST"])
def submit_answers(cid):
    with SessionLocal() as db: c=db.get(Candidate,cid)
    if not c: flash("Not found"); return redirect("/")
    ans=[request.form.get(f"a{i}","") for i in range(4)]
    qs=c.resume_json.get("questions",[])
    scores=score_answers(c.resume_json,qs,ans)
    with SessionLocal.begin() as db:
        c=db.get(Candidate,cid)
        c.resume_json["answers"]=ans
        c.answer_scores=scores
    return page("Done", "<h4>Thank you – your answers were submitted.</h4>")

# ── run local ────────────────────────────────────────────
if __name__=="__main__":
    Base.metadata.create_all(engine)    # local dev convenience
    app.run(debug=True,port=5000)
