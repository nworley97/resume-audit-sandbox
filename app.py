import os, json, uuid, logging, tempfile, mimetypes, re, io, csv
from datetime import datetime
from flask import (
    Flask, request, redirect, url_for,
    render_template, flash, send_file, abort, make_response
)
from pathlib import Path
from markupsafe import Markup, escape
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
import PyPDF2, docx, bleach
from bleach.css_sanitizer import CSSSanitizer
from openai import OpenAI
from sqlalchemy import or_, text, inspect
from dateutil import parser as dtparse

from db import SessionLocal
from models import User, JobDescription, Candidate, engine as models_engine
from s3util import upload_pdf, presign, S3_ENABLED, delete_s3

# ─── Config ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me")

# PDF text: 2MB limit — enforce it
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB

login_manager = LoginManager(app)
login_manager.login_view = "login"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

# ─── One-time schema upgrade (adds columns if they don't exist) ───
def ensure_schema():
    insp = inspect(models_engine)
    cols = {c["name"] for c in insp.get_columns("job_description")}
    adds = []
    if "status" not in cols:          adds.append("ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft'")
    if "department" not in cols:      adds.append("ADD COLUMN IF NOT EXISTS department TEXT")
    if "team" not in cols:            adds.append("ADD COLUMN IF NOT EXISTS team TEXT")
    if "location" not in cols:        adds.append("ADD COLUMN IF NOT EXISTS location TEXT")
    if "employment_type" not in cols: adds.append("ADD COLUMN IF NOT EXISTS employment_type TEXT")
    if "salary_range" not in cols:    adds.append("ADD COLUMN IF NOT EXISTS salary_range TEXT")
    if "updated_at" not in cols:      adds.append("ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    if "start_date" not in cols:      adds.append("ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ")
    if "end_date" not in cols:        adds.append("ADD COLUMN IF NOT EXISTS end_date TIMESTAMPTZ")
    if adds:
        ddl = "ALTER TABLE job_description " + ", ".join(adds) + ";"
        with models_engine.begin() as conn:
            conn.execute(text(ddl))
ensure_schema()

# ─── Flask-Login ──────────────────────────────────────────────────
@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal()
    u  = db.get(User, int(uid))
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

# ─── File-to-text helpers ─────────────────────────────────────────
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

def realism_check(rjs: dict) -> bool:
    reply = chat(
        "You are a résumé authenticity checker.",
        json.dumps(rjs) + "\n\nIs this résumé realistic? yes or no."
    )
    return reply.lower().startswith("y")

def generate_questions(rjs: dict, jd_text: str) -> list[str]:
    # Per requirement: base questions ONLY on résumé, ignore JD.
    raw = ""
    try:
        raw = chat(
            "You are an interviewer.",
            f"Résumé:\n{json.dumps(rjs)}\n\nWrite EXACTLY FOUR interview questions as a JSON array."
        )
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [q.strip().strip('"').strip(',') for q in parsed if isinstance(q, str) and len(q.strip()) > 10]
    except Exception as e:
        logging.warning("Fallback triggered in question generation: %s", e)

    # Fallbacks
    lines = (raw or "").splitlines()
    cleaned = []
    for line in lines:
        line = line.strip().strip("-• ").strip('"').strip(',')
        if (
            line and
            not line.lower().startswith("json") and
            not line.startswith("[") and
            not line.startswith("]") and
            not line.startswith("```") and
            len(line) > 10
        ):
            cleaned.append(line)
    if not cleaned:
        cleaned = [
            "Tell us about a project you’re most proud of and your specific contributions.",
            "Describe a time you overcame a technical challenge—what was the root cause and outcome?",
            "How do you prioritize tasks when timelines are tight and requirements change?",
            "Which skills from your résumé would make the biggest impact in this role, and why?"
        ]
    return cleaned[:4]

def score_answers(rjs: dict, qs: list[str], ans: list[str]) -> list[int]:
    scores=[]
    for q,a in zip(qs,ans):
        wc = len(re.findall(r"\w+", a))
        if wc<5:
            scores.append(1); continue
        prompt = (
            f"Question: {q}\nAnswer: {a}\nRésumé JSON:\n"
            f"{json.dumps(rjs)[:1500]}\n\nScore 1-5."
        )
        raw = chat("Grade answer.", prompt)
        m   = re.search(r"[1-5]", raw)
        s   = int(m.group()) if m else 1
        if wc<10: s = min(s,2)
        scores.append(s)
    return scores + [1]*max(0,4-len(scores))

# ─── Helpers ─────────────────────────────────────────────────────
def _parse_dt(val: str):
    try:
        return dtparse.parse(val) if val else None
    except Exception:
        return None

# --- Legal pages: load DOCX and render as simple HTML ---
BASE_DIR = Path(__file__).resolve().parent
LEGAL_DIR = BASE_DIR / "static" / "legal"

def docx_to_html_simple(docx_path: Path) -> Markup:
    """
    Very light DOCX -> HTML: headings become <h2>/<h3>, everything else <p>.
    Preserves blank lines; escapes HTML.
    """
    d = docx.Document(str(docx_path))
    parts = []
    for p in d.paragraphs:
        txt = (p.text or "").strip()
        style = getattr(getattr(p, "style", None), "name", "") or ""
        if not txt:
            parts.append("<br>")
            continue
        if style.startswith("Heading"):
            level = "".join(ch for ch in style if ch.isdigit())
            level = int(level) if level.isdigit() else 2
            level = 2 if level == 1 else 3 if level == 2 else 4
            parts.append(f"<h{level}>{escape(txt)}</h{level}>")
        else:
            parts.append(f"<p>{escape(txt)}</p>")
    return Markup("\n".join(parts))

# ─── Home ─────────────────────────────────────────────────────────
@app.route("/")
def home():
    return redirect(url_for("login")) if not current_user.is_authenticated else redirect(url_for("recruiter"))

# ─── CSV Export: Current View vs All (NEW) ───────────────────────
def _apply_candidate_filters(query, args):
    q_str = (args.get("q") or "").strip()
    if q_str:
        like = f"%{q_str}%"
        query = query.filter(or_(
            Candidate.name.ilike(like),
            Candidate.id.ilike(like)
        ))
    jd_code = (args.get("jd") or "").strip()
    if jd_code:
        query = query.join(JobDescription).filter(JobDescription.code == jd_code)
    date_from = (args.get("from") or "").strip()
    if date_from:
        query = query.filter(Candidate.created_at >= date_from)
    date_to = (args.get("to") or "").strip()
    if date_to:
        query = query.filter(Candidate.created_at <= date_to)
    return query

@app.route("/privacy")
def privacy():
    path = LEGAL_DIR / "20250811_Privacy.docx"
    body = docx_to_html_simple(path) if path.exists() else Markup("<p>Privacy policy coming soon.</p>")
    return render_template("legal.html", title="Privacy Policy", body=body)

@app.route("/terms")
def terms():
    path = LEGAL_DIR / "20250811_Terms.docx"
    body = docx_to_html_simple(path) if path.exists() else Markup("<p>Terms of Service coming soon.</p>")
    return render_template("legal.html", title="Terms of Service", body=body)

@app.route("/candidates/export.csv")
@login_required
def candidates_export_csv():
    """
    Export Current View (default) or All (?all=1) as CSV.
    Works even if Candidate has no relationship to JobDescription.
    """
    export_all = request.args.get("all") == "1"
    session = SessionLocal()
    try:
        q = (
            session.query(
                Candidate,
                JobDescription.code.label("jd_code"),
                JobDescription.title.label("jd_title"),
            )
            .outerjoin(JobDescription, JobDescription.code == Candidate.jd_code)
        )

        q_str = (request.args.get("q") or "").strip()
        if q_str:
            like = f"%{q_str}%"
            q = q.filter(or_(Candidate.name.ilike(like), Candidate.id.ilike(like)))

        jd_code = (request.args.get("jd") or "").strip()
        if jd_code and not export_all:
            q = q.filter(Candidate.jd_code == jd_code)

        date_from = (request.args.get("from") or "").strip()
        if date_from and not export_all:
            q = q.filter(Candidate.created_at >= date_from)
        date_to = (request.args.get("to") or "").strip()
        if date_to and not export_all:
            q = q.filter(Candidate.created_at <= date_to)

        rows = q.order_by(Candidate.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "JD Code", "JD Title", "Fit", "Claim Avg", "Created At"])

        for c, jd_code_val, jd_title_val in rows:
            scores = c.scores if isinstance(getattr(c, "scores", None), dict) else {}
            fit = getattr(c, "fit_score", None) or scores.get("fit") or getattr(c, "fit", None)

            claim_avg = scores.get("claim_avg")
            if claim_avg is None and getattr(c, "answer_scores", None):
                try:
                    claim_avg = round(sum(c.answer_scores) / len(c.answer_scores), 2)
                except Exception:
                    claim_avg = None

            writer.writerow([
                c.id,
                getattr(c, "name", ""),
                jd_code_val or c.jd_code or "",
                jd_title_val or "",
                fit if fit is not None else "",
                claim_avg if claim_avg is not None else "",
                c.created_at.isoformat() if getattr(c, "created_at", None) else "",
            ])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="candidates.csv",
        )
    finally:
        session.close()

# ─── Auth ────────────────────────────────────────────────────────
@app.route("/create-admin")
def create_admin():
    db = SessionLocal()
    if db.query(User).filter_by(username="james@blackboxstrategies.ai").first():
        db.close()
        return "Admin already exists."
    admin = User(username="james@blackboxstrategies.ai")
    admin.set_pw("2025@gv70!")  # hashes correctly
    db.add(admin); db.commit(); db.close()
    return "Admin user created."

@app.route("/reset-admin")
def reset_admin():
    db = SessionLocal()
    user = db.query(User).filter_by(username="james@blackboxstrategies.ai").first()
    if user:
        db.delete(user); db.commit()
    admin = User(username="james@blackboxstrategies.ai")
    admin.set_pw("2025@gv70!")
    db.add(admin); db.commit(); db.close()
    return "Admin reset complete."

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form["username"], request.form["password"]
        db = SessionLocal()
        usr = db.query(User).filter_by(username=u).first()
        db.close()
        if not usr or not usr.check_pw(p):
            flash("Bad credentials")
        else:
            login_user(usr)
            return redirect(url_for("recruiter"))
    return render_template("login.html", title="Login")

@app.route("/forgot")
def forgot():
    return render_template("forgot.html", title="Support")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ─── Camera gate ─────────────────────────────────────────────────
@app.route("/apply/<code>/<cid>/camera", methods=["GET","POST"])
def camera_gate(code, cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    db.close()
    if not c or c.jd_code != code:
        flash("Application not found"); return redirect(url_for("apply", code=code))

    if request.method == "POST":
        # Require acknowledgement checkbox. Camera permission can be denied and still proceed.
        if not request.form.get("ack"):
            flash("Please acknowledge the warning to continue.")
            return render_template("camera_gate.html", title="Camera Check", c=c)
        return redirect(url_for("question_paged", code=code, cid=cid, idx=0))

    return render_template("camera_gate.html", title="Camera Check", c=c)

# --- JD HTML sanitizer (Bleach ≥6) ---
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p","br","div","span","ul","ol","li","strong","b","em","i","u","h2","h3","h4","a"
}
ALLOWED_ATTRS = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href","rel","target"],
    "span": ["style","class"],
    "div":  ["style","class"],
    "p":    ["style","class"],
    "li":   ["style","class"],
    "ul":   ["class"],
    "ol":   ["class"],
}
CSS_ALLOWED = CSSSanitizer(
    allowed_css_properties=["font-family", "font-weight", "text-decoration"]
)
def sanitize_jd(html: str) -> str:
    linked = bleach.linkify(html or "")
    return bleach.clean(
        linked,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        css_sanitizer=CSS_ALLOWED,
        strip=True,
    )

# ─── JD Management ──────────────────────────────────────────────
@app.route("/edit-jd", methods=["GET","POST"])
@login_required
def edit_jd():
    db = SessionLocal()
    code_qs = request.args.get("code")
    jd = db.get(JobDescription, code_qs) or JobDescription(code="", title="", html="", status="draft")

    if request.method=="POST":
        posted_code     = request.form["jd_code"].strip()
        html_sanitized  = sanitize_jd(request.form.get("jd_text",""))

        if jd.code:  # editing existing JD — do not allow code change here
            jd.title           = request.form["jd_title"].strip()
            jd.html            = html_sanitized
            jd.status          = request.form.get("jd_status","draft")
            jd.department      = request.form.get("jd_department","").strip() or None
            jd.team            = request.form.get("jd_team","").strip() or None
            jd.location        = request.form.get("jd_location","").strip() or None
            jd.employment_type = request.form.get("jd_employment_type","").strip() or None
            jd.salary_range    = request.form.get("jd_salary_range","").strip() or None
            jd.start_date      = _parse_dt(request.form.get("jd_start",""))
            jd.end_date        = _parse_dt(request.form.get("jd_end",""))
            jd.updated_at      = datetime.utcnow()
        else:
            # creating new
            if not posted_code:
                db.close()
                flash("Job code is required")
                return redirect(request.url)
            jd.code            = posted_code
            jd.title           = request.form["jd_title"].strip()
            jd.html            = html_sanitized
            jd.status          = request.form.get("jd_status","draft")
            jd.department      = request.form.get("jd_department","").strip() or None
            jd.team            = request.form.get("jd_team","").strip() or None
            jd.location        = request.form.get("jd_location","").strip() or None
            jd.employment_type = request.form.get("jd_employment_type","").strip() or None
            jd.salary_range    = request.form.get("jd_salary_range","").strip() or None
            jd.start_date      = _parse_dt(request.form.get("jd_start",""))
            jd.end_date        = _parse_dt(request.form.get("jd_end",""))
            jd.updated_at      = datetime.utcnow()

        db.merge(jd); db.commit(); db.close()
        flash("JD saved")
        return redirect(url_for("recruiter"))

    out = render_template("edit_jd.html", title="Edit Job", jd=jd, has_candidates=bool(jd.code and jd.candidates))
    db.close()
    return out

@app.route("/delete-jd/<code>")
@login_required
def delete_jd(code):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(code=code).first()
    if jd:
        db.delete(jd); db.commit(); flash(f"Deleted {code}")
    db.close()
    return redirect(url_for("recruiter"))

# ─── Recruiter Dashboard ────────────────────────────────────────
@app.route("/recruiter")
@login_required
def recruiter():
    db = SessionLocal()
    jds = db.query(JobDescription).order_by(JobDescription.created_at.desc()).all()
    counts = { jd.code: len(jd.candidates) for jd in jds }
    db.close()
    return render_template("recruiter.html", title="Recruiter", jds=jds, counts=counts)

@app.route("/recruiter/jd/<code>")
@login_required
def view_candidates(code):
    db = SessionLocal()
    apps = db.query(Candidate)\
             .filter_by(jd_code=code)\
             .order_by(Candidate.created_at.desc())\
             .all()
    db.close()
    return render_template("view_candidates.html", title=f"Candidates – {code}", code=code, apps=apps)

# ─── Global Candidates + (legacy) Export ─────────────────────────
@app.route("/candidates")
@login_required
def global_candidates():
    q  = request.args.get("q","").strip()
    jd = request.args.get("jd","").strip()

    db = SessionLocal()
    apps_q = db.query(Candidate)
    if jd: apps_q = apps_q.filter(Candidate.jd_code==jd)
    if q:
        apps_q = apps_q.filter(or_(
            Candidate.name.ilike(f"%{q}%"),
            Candidate.id.ilike(f"%{q}%")
        ))
    apps = apps_q.order_by(Candidate.created_at.desc()).all()
    jd_list = db.query(JobDescription).order_by(JobDescription.code.asc()).all()
    db.close()

    export_url = url_for("export_candidates") + ("?q="+q if q else "") + ("&jd="+jd if jd else "")
    return render_template("global_candidates.html",
        title="Candidates",
        q=q, jd=jd, apps=apps, jd_list=jd_list, export_url=export_url)

@app.route("/export/candidates.csv")
@login_required
def export_candidates():
    # Legacy export: exports current filtered view only (kept for backward compatibility)
    q  = request.args.get("q","").strip()
    jd = request.args.get("jd","").strip()

    db = SessionLocal()
    apps_q = db.query(Candidate)
    if jd: apps_q = apps_q.filter(Candidate.jd_code == jd)
    if q:
        apps_q = apps_q.filter(or_(
            Candidate.name.ilike(f"%{q}%"),
            Candidate.id.ilike(f"%{q}%")
        ))
    apps = apps_q.order_by(Candidate.created_at.desc()).all()
    db.close()

    out = io.StringIO()
    out.write("id,name,jd_code,fit_score,avg_q,created_at\n")
    for c in apps:
        avg = round(sum(c.answer_scores)/len(c.answer_scores),2) if c.answer_scores else ""
        created = c.created_at.isoformat() if c.created_at else ""
        name = (c.name or "").replace('"','""')
        out.write(f'{c.id},"{name}",{c.jd_code},{c.fit_score},{avg},{created}\n')

    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=candidates.csv"
    return resp

# ─── Public Apply (paged Q&A) ────────────────────────────────────
@app.route("/apply/<code>", methods=["GET","POST"])
def apply(code):
    db = SessionLocal()
    jd = db.query(JobDescription).filter_by(code=code).first()
    db.close()
    if not jd:
        return abort(404)
    # If you want to hide drafts from public, uncomment:
    # if jd.status != "published" and not current_user.is_authenticated:
    #     abort(404)

    if request.method == "POST":
        name  = request.form.get("name","").strip()
        email = request.form.get("email","").strip()
        f     = request.files.get("resume_file")

        if not name or not f or not f.filename:
            flash("Name & file required")
            return redirect(request.url)

        ext = os.path.splitext(f.filename)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            f.save(tmp.name)
            path = tmp.name

        try:
            mime_guess = mimetypes.guess_type(f.filename)[0] or f.mimetype
            text = file_to_text(path, mime_guess)
        except ValueError:
            flash("PDF or DOCX only")
            return redirect(request.url)

        rjs = resume_json(text)
        if email:
            try:
                rjs["applicant_email"] = email
            except Exception:
                pass

        fit  = fit_score(rjs, jd.html)
        real = realism_check(rjs)
        qs   = generate_questions(rjs, jd.html)

        cid     = str(uuid.uuid4())[:8]
        storage = upload_pdf(path)

        db = SessionLocal()
        c  = Candidate(
            id            = cid,
            name          = name,
            resume_url    = storage,
            resume_json   = rjs,
            fit_score     = fit,
            realism       = real,
            questions     = qs,
            answers       = [""]*len(qs),
            answer_scores = [],
            jd_code       = jd.code,
        )
        db.add(c); db.commit(); db.close()

        # Go to camera gate before questions
        return redirect(url_for("camera_gate", code=code, cid=cid))

    return render_template("apply.html", title=f"Apply – {jd.code}", jd=jd)

@app.route("/apply/<code>/<cid>/q/<int:idx>", methods=["GET","POST"])
def question_paged(code, cid, idx):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    db.close()
    if not c or c.jd_code != code:
        flash("Application not found"); return redirect(url_for("apply", code=code))

    n = len(c.questions or [])
    if n == 0:
        flash("No questions generated"); return redirect(url_for("apply", code=code))
    idx = max(0, min(idx, n-1))

    if request.method == "POST":
        a = request.form.get("answer","").strip()
        db = SessionLocal()
        c2 = db.get(Candidate, cid)
        if c2:
            ans = list(c2.answers or [""]*n)
            ans[idx] = a
            c2.answers = ans
            db.merge(c2); db.commit()
        db.close()

        action = request.form.get("action","next")
        if action == "prev" and idx > 0:
            return redirect(url_for("question_paged", code=code, cid=cid, idx=idx-1))
        if action == "next" and idx < n-1:
            return redirect(url_for("question_paged", code=code, cid=cid, idx=idx+1))
        return redirect(url_for("finish_application", code=code, cid=cid))

    current_q = c.questions[idx]
    current_a = (c.answers or [""]*n)[idx] if c.answers else ""
    progress  = f"Question {idx+1} of {n}"
    return render_template("question_paged.html",
                           title="Questions",
                           name=c.name, code=code, cid=cid,
                           q=current_q, a=current_a, idx=idx, n=n, progress=progress)

@app.route("/apply/<code>/<cid>/finish")
def finish_application(code, cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    if not c:
        db.close(); flash("App not found"); return redirect(url_for("apply", code=code))
    scores = score_answers(c.resume_json, c.questions, c.answers or [])
    c.answer_scores = scores
    c.created_at    = c.created_at or datetime.utcnow()
    db.merge(c); db.commit(); db.close()

    if not current_user.is_authenticated:
        return render_template("submit_thanks.html", title="Thanks", name=c.name)

    avg  = round(sum(scores)/len(scores),2)
    qa   = list(zip(c.questions, c.answers, c.answer_scores))
    return render_template("answers_admin.html", title="Done", c=c, avg=avg, qa=qa)

# Legacy bulk submit kept (redirects to finish)
@app.route("/apply/<code>/<cid>/answers", methods=["POST"])
def submit_answers(code, cid):
    return redirect(url_for("finish_application", code=code, cid=cid))

# ─── Download & Delete résumé ────────────────────────────────────
@app.route("/resume/<cid>")
@login_required
def download_resume(cid):
    db = SessionLocal(); c = db.get(Candidate,cid); db.close()
    if not c: abort(404)
    fn = os.path.basename(c.resume_url)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" \
        if fn.lower().endswith(".docx") else "application/pdf"
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))
    return send_file(c.resume_url, as_attachment=True, download_name=fn, mimetype=mime)

@app.route("/delete/<cid>")
@login_required
def delete_candidate(cid):
    db = SessionLocal(); c = db.get(Candidate,cid)
    code = ""
    if c:
        code = c.jd_code
        try:
            if S3_ENABLED and c.resume_url.startswith("s3://"):
                delete_s3(c.resume_url)
            elif os.path.exists(c.resume_url):
                os.remove(c.resume_url)
        except Exception:
            pass
        db.delete(c); db.commit(); flash("Deleted app")
    db.close()
    return redirect(url_for("view_candidates",code=code or ""))

# ─── Candidate Detail ───────────────────────────────────────────
@app.route("/recruiter/<cid>")
@login_required
def detail(cid):
    db = SessionLocal()
    c  = db.get(Candidate, cid)
    jd = db.query(JobDescription).filter_by(code=c.jd_code).first() if c else None
    db.close()
    if not c:
        flash("Not found"); return redirect(url_for("recruiter"))

    qa = list(zip(c.questions, c.answers, c.answer_scores))
    return render_template("candidate_detail.html",
                           title=f"Candidate – {c.name}", c=c, jd=jd, qa=qa)

# ─── Entrypoint ──────────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT",5000)))
