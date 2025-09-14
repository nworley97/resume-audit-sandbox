# app.py
import os, json, uuid, logging, tempfile, mimetypes, re, io, csv
from datetime import datetime
from pathlib import Path
from functools import wraps
import math
from io import StringIO
from flask import current_app
from flask import (
    Flask, request, redirect, url_for,
    render_template, flash, send_file, abort, make_response, session, g
)
from markupsafe import Markup, escape
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)

import PyPDF2, docx, bleach
from bleach.css_sanitizer import CSSSanitizer
from openai import OpenAI
from sqlalchemy import or_, text, inspect, func, literal_column
from sqlalchemy.exc import SQLAlchemyError
from dateutil import parser as dtparse

from db import SessionLocal
from models import (
    Tenant, User, JobDescription, Candidate,
    engine as models_engine
)
from s3util import upload_pdf, presign, S3_ENABLED, delete_s3

# ─── Config ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me")

# Superadmin credentials (simple form)
SUPERADMIN_USER = os.getenv("SUPERADMIN_USER", "Altera")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "175050")

# PDF text: bump to 20MB (was 2MB)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

login_manager = LoginManager(app)
login_manager.login_view = "login"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL  = "gpt-4o"

# ─── One-time schema upgrade (idempotent) ─────────────────────────
def ensure_schema():
    insp = inspect(models_engine)
    # Existing JD upgrade block
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
    # NEW: per-JD toggles
    if "id_surveys_enabled" not in cols: adds.append("ADD COLUMN IF NOT EXISTS id_surveys_enabled BOOLEAN DEFAULT TRUE")
    if "question_count" not in cols:     adds.append("ADD COLUMN IF NOT EXISTS question_count INTEGER DEFAULT 4")
    if adds:
        ddl = "ALTER TABLE job_description " + ", ".join(adds) + ";"
        with models_engine.begin() as conn:
            conn.execute(text(ddl))

    # NEW: candidate anti-cheat counter
    ccols = {c["name"] for c in insp.get_columns("candidate")}
    cadds = []
    if "left_tab_count" not in ccols:
        cadds.append("ADD COLUMN IF NOT EXISTS left_tab_count INTEGER DEFAULT 0")
    if cadds:
        ddl2 = "ALTER TABLE candidate " + ", ".join(cadds) + ";"
        with models_engine.begin() as conn:
            conn.execute(text(ddl2))

ensure_schema()

# ─── Tenant helpers ───────────────────────────────────────────────
def load_tenant_by_slug(slug: str):
    if not slug:
        return None
    db = SessionLocal()
    try:
        return db.query(Tenant).filter(Tenant.slug == slug).first()
    finally:
        db.close()

def current_tenant():
    slug = getattr(g, "route_tenant_slug", None) or session.get("tenant_slug")
    return load_tenant_by_slug(slug) if slug else None

@app.before_request
def _capture_route_tenant():
    va = getattr(request, "view_args", None) or {}
    if "tenant" in va:
        g.route_tenant_slug = va.get("tenant")
    elif "tenant" in request.args:
        g.route_tenant_slug = request.args.get("tenant")

@app.context_processor
def inject_brand():
    t = current_tenant()
    slug = t.slug if t else None
    display = t.display_name if t else "Altera"
    return {
        "tenant": t,
        "tenant_slug": slug,
        "brand_name": display,
    }

# ─── Unauthorized redirect respects tenant ───────────────────────
@login_manager.unauthorized_handler
def _unauthorized():
    slug = session.get("tenant_slug")
    if slug:
        return redirect(url_for("login", tenant=slug))
    return redirect(url_for("login"))

# ─── Superadmin-only decorator ────────────────────────────────────
def super_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_superadmin"):
            return redirect(url_for("super_login"))
        return f(*args, **kwargs)
    return wrapper

# ─── Flask-Login ─────────────────────────────────────────────────
@login_manager.user_loader
def load_user(uid: str):
    db = SessionLocal()
    try:
        return db.get(User, int(uid))
    finally:
        db.close()

# ─── OpenAI helper ───────────────────────────────────────────────
def chat(system: str, user: str, *, structured=False, timeout=60) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0, top_p=0.1,
        response_format={"type":"json_object"} if structured else None,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

# ─── File-to-text helpers ────────────────────────────────────────
def pdf_to_text(path):
    return "\n".join(p.extract_text() or "" for p in PyPDF2.PdfReader(path).pages)

def docx_to_text(path):
    return "\n".join(p.text for p in docx.Document(path).paragraphs)

def file_to_text(path, mime):
    if mime == "application/pdf":
        return pdf_to_text(path)
    if mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/msword"):
        return docx_to_text(path)
    raise ValueError("Unsupported file type")

# ─── AI helpers ──────────────────────────────────────────────────
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
    reply = chat("You are a résumé authenticity checker.", json.dumps(rjs) + "\n\nIs this résumé realistic? yes or no.")
    return reply.lower().startswith("y")

def _normalize_quotes(s: str) -> str:
    return (s or "").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

def generate_questions(rjs: dict, jd_text: str, *, count: int = 4) -> list[str]:
    """Generate exactly `count` questions; robust to curly quotes."""
    count = max(1, min(5, int(count or 4)))

    def _tidy_q(s: str) -> str:
        s = _normalize_quotes(s)
        s = s.strip()
        s = re.sub(r'^[\'"`\s]+', '', s)
        s = re.sub(r'[\'"`\s]+$', '', s)
        s = re.sub(r'[,\s]+$', '', s)
        return s

    raw = ""
    try:
        raw = chat(
            "You are an interviewer.",
            f"Résumé:\n{json.dumps(rjs)}\n\nWrite EXACTLY {count} interview questions as a JSON array of strings."
        )
        parsed = json.loads(_normalize_quotes(raw))
        if isinstance(parsed, list):
            cleaned = []
            for q in parsed:
                if isinstance(q, str) and len(q.strip()) > 10:
                    cleaned.append(_tidy_q(q))
            cleaned = cleaned[:count]
            while len(cleaned) < count:
                cleaned.append("Please share a relevant experience.")
            return cleaned
    except Exception as e:
        logging.warning("Fallback in question generation: %s", e)

    # Fallback: parse lines
    lines = (_normalize_quotes(raw) or "").splitlines()
    cleaned = []
    for line in lines:
        line = line.strip().lstrip("-• ").strip()
        if line and not line.lower().startswith("json") and line not in ("[","]","```") and len(line) > 10:
            cleaned.append(_tidy_q(line))
    if not cleaned:
        cleaned = [
            "Tell us about a project you’re most proud of and your specific contributions.",
            "Describe a time you overcame a technical challenge—what was the root cause and outcome?",
            "How do you prioritize tasks when timelines are tight and requirements change?",
            "Which skills from your résumé would make the biggest impact in this role, and why?"
        ]
    cleaned = cleaned[:count]
    while len(cleaned) < count:
        cleaned.append("Please share a relevant experience.")
    return cleaned

def score_answers(rjs: dict, qs: list[str], ans: list[str]) -> list[int]:
    scores=[]
    for q,a in zip(qs,ans):
        wc = len(re.findall(r"\w+", a))
        if wc<5:
            scores.append(1); continue
        prompt = f"Question: {q}\nAnswer: {a}\nRésumé JSON:\n{json.dumps(rjs)[:1500]}\n\nScore 1-5."
        raw = chat("Grade answer.", prompt)
        m   = re.search(r"[1-5]", raw)
        s   = int(m.group()) if m else 1
        if wc<10: s = min(s,2)
        scores.append(s)
    # pad to length of qs
    while len(scores) < len(qs):
        scores.append(1)
    return scores

def _parse_dt(val: str):
    try:
        return dtparse.parse(val) if val else None
    except Exception:
        return None

# --- Legal files (download DOCX) ---------------------------------
BASE_DIR = Path(__file__).resolve().parent
LEGAL_DIR = BASE_DIR / "static" / "legal"

def docx_to_html_simple(docx_path: Path) -> Markup:
    d = docx.Document(str(docx_path))
    parts = []
    for p in d.paragraphs:
        txt = (p.text or "").strip()
        style = getattr(getattr(p, "style", None), "name", "") or ""
        if not txt:
            parts.append("<br>"); continue
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
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    slug = session.get("tenant_slug")
    if not slug and current_user and current_user.tenant_id:
        db = SessionLocal()
        try:
            t = db.get(Tenant, current_user.tenant_id)
            if t: slug = t.slug
        finally:
            db.close()
    if slug:
        return redirect(url_for("recruiter", tenant=slug))
    return redirect(url_for("login"))

# ─── Privacy / Terms — download DOCX (plus tenant variants) ─────
@app.route("/privacy")
def privacy():
    path = LEGAL_DIR / "20250811_Privacy.docx"
    if not path.exists():
        return make_response("Privacy policy coming soon.", 200)
    return send_file(str(path),
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     as_attachment=True,
                     download_name="Privacy.docx")

@app.route("/<tenant>/privacy")
def privacy_t(tenant):
    return privacy()

@app.route("/terms")
def terms():
    path = LEGAL_DIR / "20250811_Terms.docx"
    if not path.exists():
        return make_response("Terms of Service coming soon.", 200)
    return send_file(str(path),
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     as_attachment=True,
                     download_name="Terms.docx")

@app.route("/<tenant>/terms")
def terms_t(tenant):
    return terms()

# ─── CSV Export (All or Current View), tenant-scoped ─────────────
@app.route("/candidates/export.csv")
@app.route("/<tenant>/candidates/export.csv")
@login_required
def candidates_export_csv(tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug: return redirect(url_for("candidates_export_csv", tenant=slug))
        return redirect(url_for("login"))

    export_all = request.args.get("all") == "1"
    session_db = SessionLocal()
    try:
        q = (
            session_db.query(
                Candidate,
                JobDescription.code.label("jd_code"),
                JobDescription.title.label("jd_title"),
            )
            .outerjoin(JobDescription, JobDescription.code == Candidate.jd_code)
            .filter(Candidate.tenant_id == t.id)
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
            fit = getattr(c, "fit_score", None)
            claim_avg = None
            if getattr(c, "answer_scores", None):
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
        session_db.close()

# ─── Auth (Recruiter) ────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
@app.route("/<tenant>/login", methods=["GET","POST"])
def login(tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else None

    if request.method == "POST":
        u, p = request.form["username"], request.form["password"]
        db = SessionLocal()
        try:
            user_q = db.query(User).filter(User.username == u)
            if t:
                user_q = user_q.filter(User.tenant_id == t.id)
            usr = user_q.first()
            if not usr or not usr.check_pw(p):
                flash("Bad credentials")
            else:
                login_user(usr)
                if usr.tenant_id:
                    tt = db.get(Tenant, usr.tenant_id)
                    if tt:
                        session["tenant_slug"] = tt.slug
                        return redirect(url_for("recruiter", tenant=tt.slug))
                return redirect(url_for("recruiter"))
        finally:
            db.close()
    return render_template("login.html", title="Login")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ─── Superadmin (web UI) ─────────────────────────────────────────
@app.route("/super/login", methods=["GET", "POST"])
def super_login():
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        if u == SUPERADMIN_USER and p == SUPERADMIN_PASSWORD:
            session["is_superadmin"] = True
            flash("Welcome, superadmin!")
            return redirect(url_for("super_tenants"))
        else:
            flash("Bad credentials")
    return render_template("super_login.html", title="Superadmin Login")

@app.route("/super/logout")
def super_logout():
    session.pop("is_superadmin", None)
    flash("Signed out")
    return redirect(url_for("super_login"))

@app.route("/super/tenants", methods=["GET", "POST"])
@super_required
def super_tenants():
    db = SessionLocal()
    try:
        if request.method == "POST":
            slug = (request.form.get("slug") or "").strip().lower()
            display = (request.form.get("display_name") or "").strip()
            logo = (request.form.get("logo_url") or "").strip() or None
            username = (request.form.get("username") or "").strip()
            password = (request.form.get("password") or "").strip()

            if not slug or not re.match(r"^[a-z0-9-]+$", slug):
                flash("Slug must be lowercase letters, numbers, and hyphens only.")
                return redirect(url_for("super_tenants"))
            if not display:
                flash("Display name is required.")
                return redirect(url_for("super_tenants"))
            if not username or not password:
                flash("Username and password are required.")
                return redirect(url_for("super_tenants"))

            if db.query(Tenant).filter_by(slug=slug).first():
                flash(f"Tenant '{slug}' already exists.")
                return redirect(url_for("super_tenants"))

            t = Tenant(slug=slug, display_name=display, logo_url=logo)
            db.add(t); db.flush()

            u = User(username=username, tenant_id=t.id)
            u.set_pw(password)
            db.add(u); db.commit()

            flash(f"Tenant '{slug}' created with user '{username}'.")
            return redirect(url_for("super_tenants"))

        tenants = db.query(Tenant).order_by(Tenant.slug.asc()).all()
        return render_template("super_tenants.html", title="Tenants", tenants=tenants)
    finally:
        db.close()

# NEW: add additional user to a tenant
@app.post("/super/tenants/<int:tid>/users")
@super_required
def super_tenant_add_user(tid):
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()

    db = SessionLocal()
    try:
        t = db.get(Tenant, tid)
        if not t:
            flash("Tenant not found")
            return redirect(url_for("super_tenants"))

        if not username or not password:
            flash("Username and password are required to add a user.")
            return redirect(url_for("super_tenants") + f"#t-{tid}")

        # Enforce global username uniqueness to avoid ambiguous logins
        if db.query(User).filter(User.username == username).first():
            flash(f"User '{username}' already exists.")
            return redirect(url_for("super_tenants") + f"#t-{tid}")

        u = User(username=username, tenant_id=t.id)
        u.set_pw(password)
        db.add(u); db.commit()
        flash(f"Added user '{username}' to tenant '{t.slug}'.")
        return redirect(url_for("super_tenants") + f"#t-{tid}")
    finally:
        db.close()

# Confirm delete
@app.get("/super/tenants/<int:tid>/delete")
@super_required
def super_tenant_delete_confirm(tid):
    db = SessionLocal()
    try:
        t = db.get(Tenant, tid)
        if not t:
            flash("Tenant not found")
            return redirect(url_for("super_tenants"))

        counts = {
            "users": db.query(func.count(User.id)).filter(User.tenant_id == tid).scalar(),
            "jobs":  db.query(func.count(JobDescription.code)).filter(JobDescription.tenant_id == tid).scalar(),
            "cands": db.query(func.count(Candidate.id)).filter(Candidate.tenant_id == tid).scalar(),
        }
        return render_template("super_tenant_delete.html",
                               title=f"Delete {t.display_name}",
                               t=t, counts=counts)
    finally:
        db.close()

# Perform delete
@app.post("/super/tenants/<int:tid>/delete")
@super_required
def super_tenant_delete(tid):
    confirm_slug = (request.form.get("confirm_slug") or "").strip().lower()
    confirm_text = (request.form.get("confirm_text") or "").strip().upper()

    db = SessionLocal()
    try:
        t = db.get(Tenant, tid)
        if not t:
            flash("Tenant not found")
            return redirect(url_for("super_tenants"))

        if confirm_slug != (t.slug or "").lower() or confirm_text != "DELETE":
            flash("Confirmation values did not match. Nothing was deleted.")
            return redirect(url_for("super_tenant_delete_confirm", tid=tid))

        # Manual cascade delete (models set NULL ondelete)
        db.query(Candidate).filter(Candidate.tenant_id == tid).delete(synchronize_session=False)
        db.query(JobDescription).filter(JobDescription.tenant_id == tid).delete(synchronize_session=False)
        db.query(User).filter(User.tenant_id == tid).delete(synchronize_session=False)

        db.delete(t)
        db.commit()
        flash(f"Tenant '{t.slug}' and all associated data were deleted.")
        return redirect(url_for("super_tenants"))
    finally:
        db.close()

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
CSS_ALLOWED = CSSSanitizer(allowed_css_properties=["font-family","font-weight","text-decoration"])
def sanitize_jd(html: str) -> str:
    linked = bleach.linkify(html or "")
    return bleach.clean(linked, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, css_sanitizer=CSS_ALLOWED, strip=True)

# ─── JD Management ───────────────────────────────────────────────
@app.route("/edit-jd", methods=["GET","POST"])
@app.route("/<tenant>/edit-jd", methods=["GET","POST"])
@login_required
def edit_jd(tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug: return redirect(url_for("edit_jd", tenant=slug, **request.args))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        code_qs = request.args.get("code")
        existing = db.query(JobDescription).filter_by(code=code_qs, tenant_id=t.id).first() if code_qs else None
        jd = existing or JobDescription(code="", title="", html="", status="draft", tenant_id=t.id)
        has_candidates = False
        if existing:
            has_candidates = db.query(func.count(Candidate.id)).filter(Candidate.jd_code == existing.code, Candidate.tenant_id == t.id).scalar() > 0

        if request.method=="POST":
            posted_code     = request.form["jd_code"].strip()
            html_sanitized  = sanitize_jd(request.form.get("jd_text",""))
            title           = request.form.get("jd_title","").strip()
            status          = request.form.get("jd_status","draft")
            department      = (request.form.get("jd_department","") or "").strip() or None
            team            = (request.form.get("jd_team","") or "").strip() or None
            location        = (request.form.get("jd_location","") or "").strip() or None
            employment_type = (request.form.get("jd_employment_type","") or "").strip() or None
            salary_range    = (request.form.get("jd_salary_range","") or "").strip() or None
            start_date      = _parse_dt(request.form.get("jd_start",""))
            end_date        = _parse_dt(request.form.get("jd_end",""))

            # NEW fields
            id_surveys_enabled = "id_surveys_enabled" in request.form
            try:
                question_count = min(5, max(1, int(request.form.get("question_count", 4))))
            except (TypeError, ValueError):
                question_count = 4

            if existing:
                if posted_code != existing.code:
                    if has_candidates:
                        flash("Job code can’t be changed because candidates already exist for this job.")
                        return redirect(url_for("edit_jd", tenant=t.slug, code=existing.code))
                    conflict = db.query(JobDescription).filter_by(code=posted_code, tenant_id=t.id).first()
                    if conflict:
                        flash(f"Code {posted_code} is already in use for this tenant.")
                        return redirect(url_for("edit_jd", tenant=t.slug, code=existing.code))
                    existing.code = posted_code

                existing.title           = title
                existing.html            = html_sanitized
                existing.status          = status
                existing.department      = department
                existing.team            = team
                existing.location        = location
                existing.employment_type = employment_type
                existing.salary_range    = salary_range
                existing.start_date      = start_date
                existing.end_date        = end_date
                existing.updated_at      = datetime.utcnow()
                # NEW
                existing.id_surveys_enabled = id_surveys_enabled
                existing.question_count     = question_count

                db.add(existing); db.commit()
                flash("JD saved")
                return redirect(url_for("recruiter", tenant=t.slug))

            else:
                if not posted_code:
                    flash("Job code is required"); return redirect(request.url)
                conflict = db.query(JobDescription).filter_by(code=posted_code, tenant_id=t.id).first()
                if conflict:
                    flash(f"Code {posted_code} is already in use for this tenant.")
                    return redirect(url_for("edit_jd", tenant=t.slug, code=conflict.code))

                jd.code            = posted_code
                jd.title           = title
                jd.html            = html_sanitized
                jd.status          = status
                jd.department      = department
                jd.team            = team
                jd.location        = location
                jd.employment_type = employment_type
                jd.salary_range    = salary_range
                jd.start_date      = start_date
                jd.end_date        = end_date
                jd.updated_at      = datetime.utcnow()
                jd.tenant_id       = t.id
                # NEW
                jd.id_surveys_enabled = id_surveys_enabled
                jd.question_count     = question_count

                db.add(jd); db.commit()
                flash("JD saved")
                return redirect(url_for("recruiter", tenant=t.slug))

        return render_template("edit_jd.html", title="Edit Job", jd=jd, has_candidates=has_candidates)
    finally:
        db.close()

@app.route("/delete-jd/<code>")
@app.route("/<tenant>/delete-jd/<code>")
@login_required
def delete_jd(code, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug: return redirect(url_for("delete_jd", tenant=slug, code=code))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            flash("Job not found"); return redirect(url_for("recruiter", tenant=t.slug))

        cnt = db.query(func.count(Candidate.id)).filter(Candidate.jd_code == jd.code, Candidate.tenant_id == t.id).scalar()
        if cnt > 0:
            flash("You can’t delete this job because candidates already exist for it.")
            return redirect(url_for("recruiter", tenant=t.slug))

        db.delete(jd); db.commit(); flash(f"Deleted {code}")
        return redirect(url_for("recruiter", tenant=t.slug))
    finally:
        db.close()

# ─── Recruiter Dashboard ─────────────────────────────────────────
@app.route("/recruiter")
@app.route("/<tenant>/recruiter")
@login_required
def recruiter(tenant=None):
    # Resolve tenant or bounce to login
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("recruiter", tenant=slug))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        # Query params
        q_str     = (request.args.get("q") or "").strip()
        status    = (request.args.get("status") or "").strip().lower()
        sort      = (request.args.get("sort") or "created").lower()
        direction = (request.args.get("dir")  or "desc").lower()
        page      = max(int(request.args.get("page", 1)), 1)
        per_page  = min(max(int(request.args.get("per_page", 25)), 5), 100)

        # Base query
        q = db.query(JobDescription).filter_by(tenant_id=t.id)

        # Search filter (title / code)
        if q_str:
            like = f"%{q_str}%"
            q = q.filter(or_(JobDescription.title.ilike(like),
                             JobDescription.code.ilike(like)))

        # Status filter (only if provided)
        if status in ("open", "pending", "draft", "closed", "published"):
            q = q.filter(JobDescription.status.ilike(status))

        # Sort
        sortable = {
            "job_id":     JobDescription.code,
            "job_title":  JobDescription.title,
            "department": JobDescription.department,
            "start_date": JobDescription.start_date,
            "end_date":   JobDescription.end_date,
            "status":     JobDescription.status,
            "created":    JobDescription.created_at,
        }
        col = sortable.get(sort, JobDescription.created_at)
        q = q.order_by(col.asc() if direction == "asc" else col.desc())

        # Pagination
        total = q.count()
        pages = max((total + per_page - 1) // per_page, 1)
        if page > pages:
            page = pages
        items = q.offset((page - 1) * per_page).limit(per_page).all()

        # Status counts (Open / Pending / Draft)
        status_counts = {"open": 0, "pending": 0, "draft": 0}
        for s, c in (
            db.query(JobDescription.status, func.count(JobDescription.id))
              .filter_by(tenant_id=t.id)
              .group_by(JobDescription.status)
              .all()
        ):
            key = (s or "").lower()
            if key in status_counts:
                status_counts[key] = c

        # === NEW: initials bubbles (+N) for the "View Candidates" column ===
        def _initials_from_candidate(c):
            fn = getattr(c, "first_name", None) or ""
            ln = getattr(c, "last_name", None) or ""
            if fn or ln:
                return (fn[:1] + ln[:1]).upper()

            name = (getattr(c, "name", "") or "").strip()
            if not name:
                return "?"
            parts = [p for p in name.split() if p]
            if not parts:
                return "?"
            if len(parts) == 1:
                return parts[0][:1].upper()
            return (parts[0][:1] + parts[-1][:1]).upper()

        cand_peeks = {}
        cand_more  = {}

        for jd in items:
            cq = (
                db.query(Candidate)
                  .filter_by(tenant_id=t.id, jd_code=jd.code)
                  .order_by(Candidate.created_at.desc())
            )
            cands = cq.all()
            initials = [_initials_from_candidate(c) for c in cands]
            cand_peeks[jd.code] = initials[:3]            # up to 3 circles
            extra = max(0, len(initials) - 3)             # remainder as +N
            if extra:
                cand_more[jd.code] = extra

        brand_name = (
            getattr(t, "display_name", None) or getattr(t, "name", None) or t.slug
        )

        return render_template(
            "recruiter.html",
            tenant=t,
            brand_name=brand_name,
            q=q_str, status=status, sort=sort, dir=direction,
            page=page, pages=pages, per_page=per_page,
            items=items, total=total,
            status_counts=status_counts,
            cand_peeks=cand_peeks, cand_more=cand_more,
        )
    finally:
        db.close()

# ---- Candidates Overview (all candidates across tenant) ----
@app.route("/recruiter/candidates")
@app.route("/<tenant>/recruiter/candidates")
@login_required
def candidates_overview(tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("candidates_overview", tenant=slug))
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "applied")      # name | job | dept | score | relevancy | applied
    dir_ = request.args.get("dir", "desc")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 10

    db = SessionLocal()
    try:
        qry = db.query(Candidate).filter_by(tenant_id=t.id)

        if q:
            like = f"%{q}%"
            qry = qry.filter(or_(
                Candidate.first_name.ilike(like),
                Candidate.last_name.ilike(like),
                Candidate.job_title.ilike(like),
                Candidate.jd_code.ilike(like),
                Candidate.department.ilike(like)
            ))

        rows = list(qry.all())

        # Precompute Claim Validity (avg answer_scores) and safe Relevancy
        for c in rows:
            scores = getattr(c, "answer_scores", None) or []
            c.score = (sum(scores)/len(scores)) if scores else None
            c.relevancy = getattr(c, "relevancy", None) or 0.0
            c.applied_at = getattr(c, "created_at", None)

        reverse = (dir_ == "desc")
        key_map = {
            "name":    lambda x: (((x.first_name or "") + " " + (x.last_name or "")).lower()),
            "job":     lambda x: (x.job_title or ""),
            "dept":    lambda x: (x.department or ""),
            "score":   lambda x: (x.score is None, x.score or 0),
            "relevancy": lambda x: (x.relevancy is None, x.relevancy or 0),
            "applied": lambda x: (x.applied_at or datetime.min)
        }
        rows.sort(key=key_map.get(sort, key_map["applied"]), reverse=reverse)

        total = len(rows)
        pages = max(1, math.ceil(total / per_page))
        start = (page - 1) * per_page
        end = start + per_page
        items = rows[start:end]

        return render_template(
            "candidates.html",
            tenant=t,
            brand_name=(t.brand_name if hasattr(t, "brand_name") else "ALTERA"),
            tenant_slug=t.slug,
            jd=None,
            items=items,
            total=total,
            page=page,
            pages=pages,
            q=q, sort=sort, dir=dir_,
            SCORE_GREEN=3.8, SCORE_YELLOW=3.3,
            REL_GREEN=65, REL_YELLOW=40,
            has_candidate_detail=True,
        )
    finally:
        db.close()

# ---- Export CSV for candidates ----
@app.route("/recruiter/candidates/export")
@app.route("/<tenant>/recruiter/candidates/export")
@login_required
def export_candidates_csv(tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("export_candidates_csv", tenant=slug))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        C = Candidate
        J = JobDescription
        qset = (
            db.query(
                C.id, C.name, C.jd_code, C.fit_score, C.answer_scores,
                getattr(C, "relevancy", None).label("relevancy") if hasattr(C, "relevancy") else literal_column("NULL").label("relevancy"),
                C.created_at,
                J.title.label("job_title"),
                J.department.label("department"),
            ).join(J, J.code == C.jd_code, isouter=True)
             .filter(C.tenant_id == t.id)
        )

        # optional search filter
        q = (request.args.get("q") or "").strip()
        if q:
            like = f"%{q}%"
            qset = qset.filter(or_(C.name.ilike(like), J.title.ilike(like), C.jd_code.ilike(like), J.department.ilike(like)))

        rows = qset.all()

        # build CSV
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["ID", "Name", "Job Title", "Department", "JD Code", "Score", "Relevancy", "Applied At"])
        for r in rows:
            # score calc mirrors view
            score = r.fit_score
            if score is None and r.answer_scores:
                try:
                    vals = [float(x) for x in r.answer_scores]
                    score = (sum(vals) / len(vals)) if vals else None
                except Exception:
                    score = None
            w.writerow([
                r.id, r.name or "", r.job_title or "", r.department or "",
                r.jd_code or "", f"{score:.2f}" if score is not None else "",
                r.relevancy if r.relevancy is not None else "",
                r.created_at.isoformat() if r.created_at else "",
            ])

        mem = io.BytesIO(out.getvalue().encode("utf-8"))
        filename = f"candidates_{t.slug}.csv"
        return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=filename)
    finally:
        db.close()


@app.route("/export/jobs.csv")
@app.route("/<tenant>/export/jobs.csv")
@login_required
def export_jobs(tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        return redirect(url_for("export_jobs", tenant=slug)) if slug else redirect(url_for("login"))

    q         = (request.args.get("q") or "").strip()
    status    = (request.args.get("status") or "").strip().lower()
    sort      = (request.args.get("sort") or "created").lower()
    direction = (request.args.get("dir") or "desc").lower()

    db = SessionLocal()
    try:
        qset = db.query(JobDescription).filter(JobDescription.tenant_id == t.id)

        if q:
            like = f"%{q}%"
            qset = qset.filter(
                or_(JobDescription.title.ilike(like),
                    JobDescription.code.ilike(like),
                    JobDescription.department.ilike(like))
            )
        if status in {"open","pending","draft","closed"}:
            qset = qset.filter(JobDescription.status == status)

        sortables = {
            "job_id":     JobDescription.code,
            "job_title":  JobDescription.title,
            "department": JobDescription.department,
            "start_date": JobDescription.start_date,
            "end_date":   JobDescription.end_date,
            "status":     JobDescription.status,
            "created":    JobDescription.created_at if hasattr(JobDescription, "created_at") else JobDescription.id,
        }
        col = sortables.get(sort, sortables["created"])
        qset = qset.order_by(col.asc() if direction == "asc" else col.desc())

        rows = qset.all()

        out = StringIO()
        w   = csv.writer(out)
        w.writerow(["Job ID","Title","Department","Start Date","End Date","Status","Updated At"])
        for jd in rows:
            w.writerow([
                jd.code or "",
                jd.title or "",
                jd.department or "",
                jd.start_date.isoformat() if jd.start_date else "",
                jd.end_date.isoformat() if jd.end_date else "",
                (jd.status or "").capitalize(),
                jd.updated_at.isoformat() if getattr(jd, "updated_at", None) else "",
            ])
        out.seek(0)
        return send_file(
            io.BytesIO(out.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="jobs.csv",
        )
    finally:
        db.close()



# ---------- JD-scoped candidates list (keeps endpoint name: view_candidates) ----------
# ---------- JD-scoped candidates list (keeps endpoint name: view_candidates) ----------
@app.route("/recruiter/jd/<code>")
@app.route("/<tenant>/recruiter/jd/<code>")
@login_required
def view_candidates(code, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("view_candidates", tenant=slug, code=code))
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "applied")
    dir_ = request.args.get("dir", "desc")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 10

    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()

        qry = db.query(Candidate).filter_by(tenant_id=t.id, jd_code=code)
        if q:
            like = f"%{q}%"
            qry = qry.filter(or_(
                Candidate.first_name.ilike(like),
                Candidate.last_name.ilike(like),
                Candidate.job_title.ilike(like),
                Candidate.department.ilike(like)
            ))

        rows = list(qry.all())
        for c in rows:
            scores = getattr(c, "answer_scores", None) or []
            c.score = (sum(scores)/len(scores)) if scores else None
            c.relevancy = getattr(c, "relevancy", None) or 0.0
            c.applied_at = getattr(c, "created_at", None)

        reverse = (dir_ == "desc")
        key_map = {
            "name":    lambda x: (((x.first_name or "") + " " + (x.last_name or "")).lower()),
            "job":     lambda x: (x.job_title or ""),
            "dept":    lambda x: (x.department or ""),
            "score":   lambda x: (x.score is None, x.score or 0),
            "relevancy": lambda x: (x.relevancy is None, x.relevancy or 0),
            "applied": lambda x: (x.applied_at or datetime.min)
        }
        rows.sort(key=key_map.get(sort, key_map["applied"]), reverse=reverse)

        total = len(rows)
        pages = max(1, math.ceil(total / per_page))
        start = (page - 1) * per_page
        end = start + per_page
        items = rows[start:end]

        return render_template(
            "candidates.html",
            tenant=t,
            brand_name=(t.brand_name if hasattr(t, "brand_name") else "ALTERA"),
            tenant_slug=t.slug,
            jd=jd,
            items=items,
            total=total,
            page=page,
            pages=pages,
            q=q, sort=sort, dir=dir_,
            SCORE_GREEN=3.8, SCORE_YELLOW=3.3,
            REL_GREEN=65, REL_YELLOW=40,
            has_candidate_detail=True,
        )
    finally:
        db.close()

# ---------- Candidate Detail ----------
# ---------- Candidate Detail ----------
@app.route("/recruiter/candidate/<id>")
@app.route("/<tenant>/recruiter/candidate/<id>")
@login_required
def candidate_detail(id, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("candidate_detail", tenant=slug, id=id))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=id, tenant_id=t.id).first()
        if not c:
            abort(404)

        jd = None
        if getattr(c, "jd_code", None):
            jd = db.query(JobDescription).filter_by(code=c.jd_code, tenant_id=t.id).first()

        # Compute claim validity (average of answer_scores if present)
        scores = list(getattr(c, "answer_scores", None) or [])
        claim_validity = (sum(scores) / len(scores)) if scores else None

        # Build zipped Q&A: list of {q, a, s}
        qs = list(getattr(c, "questions", None) or [])
        ans = list(getattr(c, "answers", None) or [])
        scs = list(getattr(c, "answer_scores", None) or [])
        qa = []
        n = max(len(qs), len(ans), len(scs))
        for i in range(n):
            qa.append({
                "q": qs[i] if i < len(qs) else "",
                "a": ans[i] if i < len(ans) else "",
                "s": scs[i] if i < len(scs) else None,
            })

        # Thresholds for chips
        SCORE_GREEN = 3.8
        SCORE_YELLOW = 3.3
        REL_GREEN = 65
        REL_YELLOW = 40

        # Resume preview URL
        resume_url = getattr(c, "resume_url", None) or getattr(c, "resume_pdf", None) or ""

        # Optional relevancy (default to 0.0 if None)
        relevancy = getattr(c, "relevancy", None)
        if relevancy is None:
            relevancy = 0.0

        # Focus/tab switches (anti-cheat counter)
        focus_changes = getattr(c, "left_tab_count", 0) or 0

        return render_template(
            "candidate_detail.html",
            tenant=t,
            jd=jd,
            c=c,
            relevancy=relevancy,
            resume_url=resume_url,
            claim_validity=claim_validity,
            qa=qa,  # <-- use this in template instead of plain answers
            focus_changes=focus_changes,
            SCORE_GREEN=SCORE_GREEN, SCORE_YELLOW=SCORE_YELLOW,
            REL_GREEN=REL_GREEN, REL_YELLOW=REL_YELLOW,
        )
    finally:
        db.close()



# ─── Global Candidates (legacy) ──────────────────────────────────
@app.route("/candidates")
@app.route("/<tenant>/candidates")
@login_required
def candidates_overview_legacy(tenant):
    tenant_obj = load_tenant_by_slug(tenant)
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "applied_at")
    dir_ = request.args.get("dir", "desc")
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 25

    # Build filters safely
    filters = {}
    if q:
        filters["q"] = q  # your DAO should interpret across name/title/jd_code

    rows, total = Candidate.search_for_tenant(
        tenant_slug=tenant_obj.slug,
        filters=filters,
        sort=sort,
        direction=dir_,
        page=page,
        per_page=per_page,
    )

    def _page_url(p):
        args = dict(request.args)
        args["page"] = p
        return url_for("candidates_overview", tenant=tenant_obj.slug, **args)

    def _sort_url(key):
        args = dict(request.args)
        if args.get("sort") == key:
            args["dir"] = "asc" if args.get("dir") == "desc" else "desc"
        else:
            args["sort"] = key
            args["dir"] = "asc"
        return url_for("candidates_overview", tenant=tenant_obj.slug, **args)

    return render_template(
        "candidates.html",
        tenant=tenant_obj,
        tenant_slug=tenant_obj.slug if tenant_obj else None,
        brand_name=current_tenant().brand_name if current_tenant() else "ALTERA",
        rows=rows,
        total=total,
        page=page,
        pages=math.ceil(total / per_page) if total else 1,
        q=q,
        sort=sort,
        dir=dir_,
        sort_url=_sort_url,
        page_url=_page_url,
        export_endpoint="export_candidates_csv",  # optional
        has_candidate_detail=True,
    )


@app.route("/export/candidates.csv")
@app.route("/<tenant>/export/candidates.csv")
@login_required
def export_candidates(tenant=None):
    return redirect(url_for("candidates_export_csv", tenant=tenant, **request.args))

# ─── Public Apply (legacy redirect) ──────────────────────────────
@app.route("/apply/<code>", methods=["GET","POST"])
def apply_legacy(code):
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code).first()
        if not jd:
            return abort(404)
        t = db.get(Tenant, jd.tenant_id)
        slug = t.slug if t else "blackbox"
        return redirect(url_for("apply", tenant=slug, code=code))
    finally:
        db.close()

# ─── Public Apply (paged Q&A) ────────────────────────────────────
@app.route("/<tenant>/apply/<code>", methods=["GET","POST"])
def apply(tenant, code):
    t = load_tenant_by_slug(tenant)
    if not t: abort(404)

    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
    finally:
        db.close()
    if not jd:
        return abort(404)

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
            try: rjs["applicant_email"] = email
            except Exception: pass

        fit  = fit_score(rjs, jd.html)
        real = realism_check(rjs)
        count = getattr(jd, "question_count", 4) or 4
        qs   = generate_questions(rjs, jd.html, count=count)

        cid     = str(uuid.uuid4())[:8]
        storage = upload_pdf(path)

        db = SessionLocal()
        try:
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
                tenant_id     = t.id,
            )
            db.add(c); db.commit()
        finally:
            db.close()

        return redirect(url_for("camera_gate", tenant=t.slug, code=code, cid=cid))

    return render_template("apply.html", title=f"Apply – {jd.code}", jd=jd, tenant_slug=t.slug)

# ─── Camera gate ─────────────────────────────────────────────────
@app.route("/<tenant>/apply/<code>/<cid>/camera", methods=["GET","POST"])
def camera_gate(tenant, code, cid):
    t = load_tenant_by_slug(tenant)
    if not t: abort(404)

    db = SessionLocal()
    try:
        c  = db.get(Candidate, cid)
    finally:
        db.close()
    if not c or c.jd_code != code or c.tenant_id != t.id:
        flash("Application not found"); return redirect(url_for("apply", tenant=t.slug, code=code))

    if request.method == "POST":
        if not request.form.get("ack"):
            flash("Please acknowledge the warning to continue.")
            return render_template("camera_gate.html", title="Camera Check", c=c)
        return redirect(url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=0))

    return render_template("camera_gate.html", title="Camera Check", c=c)

# ─── Questions (paged) ───────────────────────────────────────────
@app.route("/<tenant>/apply/<code>/<cid>/q/<int:idx>", methods=["GET","POST"])
def question_paged(tenant, code, cid, idx):
    t = load_tenant_by_slug(tenant)
    if not t: abort(404)

    db = SessionLocal()
    try:
        c  = db.get(Candidate, cid)
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
    finally:
        db.close()
    if not c or c.jd_code != code or c.tenant_id != t.id:
        flash("Application not found"); return redirect(url_for("apply", tenant=t.slug, code=code))

    n = len(c.questions or [])
    if n == 0:
        flash("No questions generated"); return redirect(url_for("apply", tenant=t.slug, code=code))
    idx = max(0, min(idx, n-1))

    if request.method == "POST":
        a = request.form.get("answer","").strip()
        db = SessionLocal()
        try:
            c2 = db.get(Candidate, cid)
            if c2:
                ans = list(c2.answers or [""]*n)
                ans[idx] = a
                c2.answers = ans
                db.merge(c2); db.commit()
        finally:
            db.close()

        action = request.form.get("action","next")
        if action == "prev" and idx > 0:
            return redirect(url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=idx-1))
        if action == "next" and idx < n-1:
            return redirect(url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=idx+1))

        # LAST: branch based on JD toggle (NEW)
        if jd and getattr(jd, "id_surveys_enabled", True):
            return redirect(url_for("self_id", tenant=t.slug, code=code, cid=cid))
        else:
            return redirect(url_for("finish_application", tenant=t.slug, code=code, cid=cid))

    current_q = c.questions[idx]
    current_a = (c.answers or [""]*n)[idx] if c.answers else ""
    progress  = f"Question {idx+1} of {n}"
    return render_template("question_paged.html",
                           title="Questions",
                           name=c.name, code=code, cid=cid,
                           q=current_q, a=current_a, idx=idx, n=n, progress=progress)

# Support page (global)
@app.route("/forgot-password")
def forgot():
    return render_template("forgot.html", title="Forgot Password")

# Optional: tenant-scoped support page
@app.route("/<tenant>/forgot")
def forgot_tenant(tenant):
    return render_template("forgot.html", title="Support")

# ─── Self-ID page (one page) ─────────────────────────────────────
@app.route("/<tenant>/apply/<code>/<cid>/self-id", methods=["GET", "POST"])
def self_id(tenant, code, cid):
    t = load_tenant_by_slug(tenant)
    if not t: abort(404)
    db = SessionLocal()
    try:
        c = db.get(Candidate, cid)
        if not c or c.jd_code != code or c.tenant_id != t.id:
            flash("Application not found")
            return redirect(url_for("apply", tenant=t.slug, code=code))

        if request.method == "POST":
            data = {
                "gender":     (request.form.get("gender") or "Decline to self-identify").strip(),
                "hispanic":   (request.form.get("hispanic") or "Decline to self-identify").strip(),
                "veteran":    (request.form.get("veteran") or "I don't wish to answer").strip(),
                "disability": (request.form.get("disability") or "I don't want to answer").strip(),
                "ts_utc":     datetime.utcnow().isoformat() + "Z",
            }
            rjs = dict(c.resume_json or {})
            rjs["_self_id"] = data
            c.resume_json = rjs
            db.merge(c); db.commit()
            return redirect(url_for("finish_application", tenant=t.slug, code=code, cid=cid))

        existing = (c.resume_json or {}).get("_self_id", {})
        return render_template("self_id.html", title="Voluntary Self-Identification", c=c, data=existing)
    finally:
        db.close()

# ─── Finish (thank you) ──────────────────────────────────────────
@app.route("/<tenant>/apply/<code>/<cid>/finish")
def finish_application(tenant, code, cid):
    t = load_tenant_by_slug(tenant)
    if not t: abort(404)

    db = SessionLocal()
    try:
        c  = db.get(Candidate, cid)
        if not c or c.tenant_id != t.id or c.jd_code != code:
            flash("App not found"); return redirect(url_for("apply", tenant=t.slug, code=code))
        scores = score_answers(c.resume_json, c.questions, c.answers or [])
        c.answer_scores = scores
        c.created_at    = c.created_at or datetime.utcnow()
        db.merge(c); db.commit()
    finally:
        db.close()

    if not current_user.is_authenticated:
        return render_template("submit_thanks.html", title="Thanks", name=c.name, code=code, tenant_slug=t.slug)

    avg  = round(sum(scores)/len(scores),2)
    qa   = list(zip(c.questions, c.answers, c.answer_scores))
    return render_template("answers_admin.html", title="Done", c=c, avg=avg, qa=qa, tenant_slug=t.slug)

# Legacy bulk submit kept (redirects to finish)
@app.route("/<tenant>/apply/<code>/<cid>/answers", methods=["POST"])
def submit_answers(tenant, code, cid):
    return redirect(url_for("finish_application", tenant=tenant, code=code, cid=cid))

# ─── Anti-cheat flag (tab/window switches) ───────────────────────
@app.route("/<tenant>/apply/<code>/<cid>/flag", methods=["POST"])
def flag_tab_switch(tenant, code, cid):
    t = load_tenant_by_slug(tenant)
    if not t:
        return ("", 404)
    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=cid, tenant_id=t.id, jd_code=code).first()
        if not c:
            return ("", 404)
        c.left_tab_count = (c.left_tab_count or 0) + 1
        db.commit()
        return ("", 204)
    finally:
        db.close()

# ─── Download & Delete résumé (tenant scoped) ────────────────────
@app.route("/resume/<cid>")
@app.route("/<tenant>/resume/<cid>")
@login_required
def download_resume(cid, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug: return redirect(url_for("download_resume", tenant=slug, cid=cid))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        c = db.get(Candidate,cid)
    finally:
        db.close()
    if not c or c.tenant_id != t.id: abort(404)

    fn = os.path.basename(c.resume_url)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fn.lower().endswith(".docx") else "application/pdf"
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        return redirect(presign(c.resume_url))
    return send_file(c.resume_url, as_attachment=True, download_name=fn, mimetype=mime)

@app.route("/delete/<cid>")
@app.route("/<tenant>/delete/<cid>")
@login_required
def delete_candidate(cid, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug: return redirect(url_for("delete_candidate", tenant=slug, cid=cid))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        c = db.get(Candidate,cid)
        code = ""
        if c and c.tenant_id == t.id:
            code = c.jd_code
            try:
                if S3_ENABLED and c.resume_url.startswith("s3://"):
                    delete_s3(c.resume_url)
                elif os.path.exists(c.resume_url):
                    os.remove(c.resume_url)
            except Exception:
                pass
            db.delete(c); db.commit(); flash("Deleted app")
        return redirect(url_for("view_candidates", tenant=t.slug, code=code or ""))
    finally:
        db.close()

# ─── Candidate Detail (admin) ────────────────────────────────────
@app.route("/recruiter/<cid>")
@app.route("/<tenant>/recruiter/<cid>")
@login_required
def detail(cid, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug: return redirect(url_for("detail", tenant=slug, cid=cid))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        c  = db.get(Candidate, cid)
        jd = db.query(JobDescription).filter_by(code=c.jd_code, tenant_id=t.id).first() if c else None
        if not c or c.tenant_id != t.id:
            flash("Not found"); return redirect(url_for("recruiter", tenant=t.slug))
        qa = list(zip(c.questions, c.answers, c.answer_scores))
        return render_template("candidate_detail.html",
                               title=f"Candidate – {c.name}", c=c, jd=jd, qa=qa, tenant_slug=t.slug)
    finally:
        db.close()

# ─── Entrypoint ──────────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT",5000)))
