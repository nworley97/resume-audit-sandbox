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
from models import SessionLocal, engine, Base, User, JobDescription, Candidate
from s3util import upload_pdf, presign, S3_ENABLED

# ─── App + OpenAI setup ───────────────────────────────
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me")

# ─── Flask-Login ───────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(uid):
    db = SessionLocal(); u = db.get(User, int(uid)); db.close(); return u

# ─── AI helper ────────────────────────────────────────
def chat(system, user, *, structured=False, timeout=60):
    resp = client.chat.completions.create(
        model=MODEL, temperature=0, top_p=0.1,
        response_format={"type":"json_object"} if structured else None,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":user}],
        timeout=timeout
    )
    return resp.choices[0].message.content.strip()

# ─── File → text ──────────────────────────────────────
def pdf_to_text(p):  return "\n".join(page.extract_text() or "" for page in PyPDF2.PdfReader(p).pages)
def docx_to_text(p): return "\n".join(para.text for para in docx.Document(p).paragraphs)
def file_to_text(path, mime):
    if mime=="application/pdf": return pdf_to_text(path)
    if mime in (
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword"
    ): return docx_to_text(path)
    raise ValueError("Unsupported file type")

# ─── Scoring ──────────────────────────────────────────
def resume_json(text):
    raw = chat("Extract résumé to JSON.", text, structured=True)
    try: return json.loads(raw)
    except: return json.loads(chat("Return valid JSON résumé.", text, structured=True))

def fit_score(rjs, jd_text):
    prompt = (
        f"Résumé JSON:\n{json.dumps(rjs,indent=2)}\n\n"
        f"Job description:\n{jd_text}\n\n"
        "Score 1-5 (5 best). Return only the integer."
    )
    r = chat("Score résumé vs JD.", prompt)
    m = re.search(r"[1-5]", r)
    return int(m.group()) if m else 1

# ─── HTML base ───────────────────────────────────────
BASE = """
<!doctype html><html lang=en><head>
 <meta charset=utf-8><title>{{title}}</title>
 <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid d-flex justify-content-between">
    <span class="navbar-brand">Blackboxstrategiesalpha</span>
    {% if current_user.is_authenticated %}
      <div class="d-flex gap-2">
        <a class="btn btn-outline-primary btn-sm" href="{{url_for('recruiter')}}">Recruiter</a>
        <a class="btn btn-outline-danger  btn-sm" href="{{url_for('logout')}}">Logout</a>
      </div>
    {% endif %}
  </div>
</nav>
<div class="container" style="max-width:720px;">
  {% with m=get_flashed_messages() %}
    {% if m %}<div class="alert alert-danger">{{m[0]}}</div>{% endif %}
  {% endwith %}
  {{body|safe}}
</div>
</body></html>
"""

def page(title, body):
    return render_template_string(BASE, title=title, body=body)

# ─── Auth ────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u,p = request.form["username"], request.form["password"]
        db  = SessionLocal(); usr = db.query(User).filter_by(username=u).first(); db.close()
        if usr and usr.check_pw(p):
            login_user(usr)
            return redirect(request.args.get("next") or url_for("recruiter"))
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

# ─── New JD ──────────────────────────────────────────
@app.route("/new-jd", methods=["GET","POST"])
@login_required
def new_jd():
    db = SessionLocal()
    if request.method=="POST":
        code,slug,title,html = (
          request.form["code"].strip(),
          request.form["slug"].strip(),
          request.form["title"].strip(),
          request.form["html"]
        )
        if db.query(JobDescription).filter_by(code=code).first():
            flash("Code exists"); db.close(); return redirect("/new-jd")
        jd = JobDescription(code=code, slug=slug, title=title, html=html)
        db.add(jd); db.commit(); db.close()
        return redirect(url_for("recruiter"))
    form = """
      <h4>New Posting</h4>
      <form method=post>
        <label>Code</label><input name=code class='form-control mb-2' required>
        <label>Slug</label><input name=slug class='form-control mb-2' required>
        <label>Title</label><input name=title class='form-control mb-2' required>
        <label>Description (HTML)</label>
        <textarea name=html rows=6 class='form-control mb-2' required></textarea>
        <button class='btn btn-primary'>Create</button>
      </form>
    """
    db.close(); return page("New JD", form)

# ─── Recruiter Dashboard ───────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    db = SessionLocal()
    # safe ordering
    order_col = getattr(JobDescription, "created_at", JobDescription.code)
    jds = db.query(JobDescription).order_by(order_col.desc()).all()
    db.close()

    if not jds:
        rows = "<tr><td colspan=4>No postings</td></tr>"
    else:
        rows = "".join(
          "<tr>"
          f"<td>{jd.code}</td>"
          f"<td>{jd.title}</td>"
          f"<td><a href='{url_for('jd_detail', slug=jd.slug)}'>open</a></td>"
          f"<td><a class='text-danger' href='{url_for('delete_jd', slug=jd.slug)}'"
          " onclick=\"return confirm('Delete?');\">✖</a></td>"
          "</tr>"
          for jd in jds
        )

    table = (
      "<h4>Postings</h4>"
      "<table class='table table-sm'>"
      "<thead><tr><th>Code</th><th>Title</th><th></th><th></th></tr></thead>"
      f"<tbody>{rows}</tbody></table>"
      "<a class='btn btn-outline-primary' href='/new-jd'>+ New JD</a>"
    )
    return page("Dashboard", table)

@app.route("/recruiter/<slug>")
@login_required
def jd_detail(slug):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(slug=slug).first()
    apps = db.query(Candidate).filter_by(jd_code=jd.code).order_by(Candidate.created_at.desc()).all()
    db.close()
    if not jd:
        flash("Not found"); return redirect("/recruiter")

    rows = "".join(
      "<tr>"
      f"<td>{c.id}</td>"
      f"<td>{c.name}</td>"
      f"<td>{c.fit_score}</td>"
      f"<td><a href='{url_for('download_resume', cid=c.id)}'>PDF</a></td>"
      "</tr>"
      for c in apps
    ) or "<tr><td colspan=4>No applications</td></tr>"

    body = (
      f"<h4>{jd.title} ({jd.code})</h4>"
      f"<p><small>Created: {jd.created_at.strftime('%Y-%m-%d %H:%M')}</small></p>"
      "<h5>Applications</h5>"
      "<table class='table table-sm'>"
      "<thead><tr><th>ID</th><th>Name</th><th>Score</th><th>Resume</th></tr></thead>"
      f"<tbody>{rows}</tbody></table>"
      "<a class='btn btn-link' href='/recruiter'>&larr; Back</a>"
    )
    return page("Posting", body)

@app.route("/delete-jd/<slug>")
@login_required
def delete_jd(slug):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(slug=slug).first()
    if jd:
        db.delete(jd)
        db.commit()
    db.close()
    return redirect("/recruiter")

# ─── Candidate Apply ─────────────────────────────────
@app.route("/apply/<slug>", methods=["GET","POST"])
def apply(slug):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(slug=slug).first()
    db.close()
    if not jd:
        return "Posting not found", 404

    if request.method=="POST":
        name = request.form["name"].strip()
        f    = request.files["resume_file"]
        if not name or not f or f.filename=="":
            flash("Name & file required"); return redirect(request.url)

        mime = mimetypes.guess_type(f.filename)[0] or f.mimetype
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            f.save(tmp.name); path=tmp.name

        try:
            text = file_to_text(path, mime)
        except ValueError:
            flash("Upload PDF or DOCX"); return redirect(request.url)

        rjs   = resume_json(text)
        score = fit_score(rjs, jd.html)
        cid   = str(uuid.uuid4())[:8]
        url   = upload_pdf(path)

        db = SessionLocal()
        db.add(Candidate(
            id=cid, name=name,
            resume_url=url, resume_json=rjs,
            fit_score=score, jd_code=jd.code
        ))
        db.commit(); db.close()

        return page("Thank you", f"""
           <h4>Thanks, {name}!</h4>
           <p>Relevance score: <strong>{score}/5</strong>.</p>
           <a class='btn btn-secondary' href='{url_for('apply',slug=slug)}'>
             Upload another résumé
           </a>
        """)

    return page("Apply", f"""
      <h4>Apply: {jd.title} ({jd.code})</h4>
      <div class='border p-3 mb-3'>{jd.html}</div>
      <form method=post enctype=multipart/form-data>
        <div class='mb-3'><label>Your Name</label>
          <input name=name class='form-control' required></div>
        <div class='mb-3'><label>Résumé (PDF or DOCX)</label>
          <input type=file name=resume_file accept='.pdf,.docx' class='form-control' required></div>
        <button class='btn btn-primary'>Submit</button>
      </form>
    """)

# ─── Download résumé ───────────────────────────────────
@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    db = SessionLocal(); c = db.get(Candidate, cid); db.close()
    if not c: return "Not found", 404
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))
    return send_file(c.resume_url, as_attachment=True, download_name=f"{c.name}.pdf")

# ─── Run ───────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT",5000)))
