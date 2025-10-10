# app.py
import os, json, uuid, logging, tempfile, mimetypes, re, io, csv, html
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
import math
import glob
from io import StringIO
from flask import current_app, send_from_directory, abort 
from flask import (
    Flask, request, redirect, url_for,
    render_template, flash, send_file, abort, make_response, session, g, jsonify, Response
)
from markupsafe import Markup, escape
try:
    from markdown import markdown as md_to_html
except ImportError:  # pragma: no cover - optional dependency
    md_to_html = None
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)

import PyPDF2, docx, bleach
import markdown as md
from bleach.css_sanitizer import CSSSanitizer
from openai import OpenAI
from sqlalchemy import or_, text, inspect, func, literal_column
from sqlalchemy.exc import SQLAlchemyError
from dateutil import parser as dtparse

from db import SessionLocal, Base, DATABASE_URL
from models import (
    Tenant, User, JobDescription, Candidate,
    engine as models_engine
)
from s3util import upload_pdf, presign, S3_ENABLED, delete_s3
# app.py



# ─── Config ───────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
# Jinja filter: thousand separators for integers
@app.template_filter("intcomma")
def intcomma(value):
    try:
        iv = int(value or 0)
    except (TypeError, ValueError):
        return value
    return f"{iv:,}"
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change-me")

from analytics_service import bp as analytics_bp
app.register_blueprint(analytics_bp)

logger = logging.getLogger(__name__)
_markdown_fallback_warned = False

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
    from models import Base
    
    # Create all tables if they don't exist
    Base.metadata.create_all(bind=models_engine)
    
    insp = inspect(models_engine)
    tables = insp.get_table_names()
    if "job_description" not in tables:
        Base.metadata.create_all(models_engine)
        tables = insp.get_table_names()

    # Existing JD upgrade block
    cols = {c["name"] for c in insp.get_columns("job_description")}
    adds = []
    if "status" not in cols:          adds.append("ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
    if "department" not in cols:      adds.append("ADD COLUMN department TEXT")
    if "team" not in cols:            adds.append("ADD COLUMN team TEXT")
    if "location" not in cols:        adds.append("ADD COLUMN location TEXT")
    if "employment_type" not in cols: adds.append("ADD COLUMN employment_type TEXT")
    if "salary_range" not in cols:    adds.append("ADD COLUMN salary_range TEXT")
    if "updated_at" not in cols:      adds.append("ADD COLUMN updated_at TIMESTAMPTZ")
    if "start_date" not in cols:      adds.append("ADD COLUMN start_date TIMESTAMPTZ")
    if "end_date" not in cols:        adds.append("ADD COLUMN end_date TIMESTAMPTZ")
    # NEW: feature/ET-12-FE(Jen)
    if "start_time" not in cols:      adds.append("ADD COLUMN start_time TIME")
    if "end_time" not in cols:        adds.append("ADD COLUMN end_time TIME")
    if "work_arrangement" not in cols: adds.append("ADD COLUMN work_arrangement TEXT")
    if "markdown" not in cols:   adds.append("ADD COLUMN markdown TEXT")
    # NEW: per-JD toggles
    if "id_surveys_enabled" not in cols: adds.append("ADD COLUMN id_surveys_enabled BOOLEAN DEFAULT TRUE")
    if "question_count" not in cols:     adds.append("ADD COLUMN question_count INTEGER DEFAULT 4")
    if adds:
    # Original PostgreSQL-optimized code
    # ddl = "ALTER TABLE job_description " + ", ".join(adds) + ";"
    # with models_engine.begin() as conn:
    #     conn.execute(text(ddl))

    # NEW: Cross-database compatibility added with ET-12-FE (Jen)
    # Problem: SQLite syntax doesn't support multiple ADD COLUMN in single statement
    # Solution: Environment-specific execution strategy
        with models_engine.begin() as conn:
            if DATABASE_URL.startswith("sqlite"):
                # SQLite: Individual execution (compatibility)
                for add in adds:
                    ddl = f"ALTER TABLE job_description {add};"
                    conn.execute(text(ddl))
            else:
                # PostgreSQL: Batch execution (performance optimization)
                ddl = "ALTER TABLE job_description " + ", ".join(adds) + ";"
                conn.execute(text(ddl))

    # NEW: candidate anti-cheat counter
    ccols = {c["name"] for c in insp.get_columns("candidate")}
    cadds = []
    if "left_tab_count" not in ccols:
        cadds.append("ADD COLUMN left_tab_count INTEGER DEFAULT 0")
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


def _latest_match(base_dir, patterns):
    for pat in patterns:
        matches = sorted(glob.glob(os.path.join(base_dir, pat)))
        if matches:
            return os.path.basename(matches[-1])
    return None

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
    if not t and current_user.is_authenticated and getattr(current_user, "tenant_id", None):
        db = SessionLocal()
        try:
            t = db.get(Tenant, current_user.tenant_id)
        finally:
            db.close()

    slug = t.slug if t else None
    display = t.display_name if t else "Altera"
    return {
        "tenant": t,
        "tenant_slug": slug,
        "brand_name": display,
    }

# ---------- Pagination helper (additive) ----------
@app.context_processor
def inject_pagination_helpers():
    from flask import request, url_for

    def _collect_params(exclude=None):
        exclude = set(exclude or [])
        params = dict(request.view_args or {})
        for key in request.args.keys():
            if key in exclude:
                continue
            values = request.args.getlist(key)
            if not values:
                continue
            params[key] = values if len(values) > 1 else values[0]
        return params

    def query_url(**updates):
        """Build a link to the current endpoint, preserving route args & query params with overrides."""
        params = _collect_params()
        for key, value in updates.items():
            if value is None:
                params.pop(key, None)
            else:
                params[key] = value
        return url_for(request.endpoint, **params)

    def page_url(target_page: int):
        """Build a link to the current endpoint, preserving route args & query params, with the given page."""
        try:
            p = int(target_page)
        except Exception:
            p = 1
        if p < 1:
            p = 1
        params = _collect_params(exclude={"page"})
        params["page"] = p
        return url_for(request.endpoint, **params)

    return {"page_url": page_url, "query_url": query_url}
# ---------- /Pagination helper ----------
# --- time formatting helper (mm:ss) ---
@app.context_processor
def inject_time_format():
    def fmt_mmss(ms):
        try:
            s = int(ms) // 1000
            m, s = divmod(s, 60)
            return f"{m}:{s:02d}"
        except Exception:
            return ""
    return {"fmt_mmss": fmt_mmss}
# --- /time formatting helper ---


@app.context_processor
def inject_public_links():
    # Helper builders so templates don’t need to know endpoint names
    from flask import current_app, request, url_for

    def _has(ep: str) -> bool:
        return ep in current_app.view_functions

    # Try to detect tenant slug from the current route
    tenant_slug = None
    try:
        if request and request.view_args:
            tenant_slug = request.view_args.get("tenant")
    except Exception:
        pass

    def link_privacy():
        if tenant_slug and _has("privacy_t"):
            return url_for("privacy_t", tenant=tenant_slug)
        return url_for("privacy") if _has("privacy") else "#"

    def link_terms():
        if tenant_slug and _has("terms_t"):
            return url_for("terms_t", tenant=tenant_slug)
        return url_for("terms") if _has("terms") else "#"

    def link_support():
        # Use the same page as “Forgot your password?”
        if tenant_slug and _has("forgot_tenant"):
            return url_for("forgot_tenant", tenant=tenant_slug)
        if _has("forgot"):
            return url_for("forgot")
        # Fallback
        return url_for("login") if _has("login") else "#"

    return dict(
        link_privacy=link_privacy,
        link_terms=link_terms,
        link_support=link_support,
    )



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

# 2025-10-01: added (Jen)
def _parse_time(time_str):
    """Parse time string to time object"""
    if not time_str or not time_str.strip():
        return None
    try:
        from datetime import time
        return time.fromisoformat(time_str.strip())
    except (ValueError, TypeError):
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

# NEW: update tenant logo
@app.post("/super/tenants/<int:tid>/logo")
@super_required
def super_tenant_update_logo(tid):
    logo_url = (request.form.get("logo_url") or "").strip() or None

    db = SessionLocal()
    try:
        t = db.get(Tenant, tid)
        if not t:
            flash("Tenant not found")
            return redirect(url_for("super_tenants"))

        t.logo_url = logo_url
        db.commit()
        flash(f"Logo updated for tenant '{t.slug}'.")
        return redirect(url_for("super_tenants") + f"#t-{tid}")
    finally:
        db.close()

# NEW: remove tenant logo
@app.post("/super/tenants/<int:tid>/logo/remove")
@super_required
def super_tenant_remove_logo(tid):
    db = SessionLocal()
    try:
        t = db.get(Tenant, tid)
        if not t:
            flash("Tenant not found")
            return redirect(url_for("super_tenants"))

        t.logo_url = None
        db.commit()
        flash(f"Logo removed for tenant '{t.slug}'.")
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
    "p","br","div","span","ul","ol","li","strong","b","em","i","u",
    "h1","h2","h3","h4","h5","h6",
    "a","blockquote","code","pre","hr",
    "table","thead","tbody","tr","th","td"
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
    "code": ["class"],
    "pre":  ["class"],
}
CSS_ALLOWED = CSSSanitizer(allowed_css_properties=["font-family","font-weight","text-decoration"])
MARKDOWN_EXTENSIONS = ["extra", "sane_lists"]

def render_markdown(md_text: str) -> str:
    """Convert recruiter-authored markdown into HTML before sanitization."""
    text = (md_text or "").replace("\r\n", "\n").replace("\r", "\n")
    if md_to_html:
        return md_to_html(text, extensions=MARKDOWN_EXTENSIONS)

    # Fallback: behave similar to the legacy plaintext handling so the
    # application keeps working even if python-Markdown is missing.
    global _markdown_fallback_warned
    if not _markdown_fallback_warned:
        logger.warning("python-Markdown package not installed; falling back to plain-text rendering for JDs.")
        _markdown_fallback_warned = True

    escaped = html.escape(text)
    parts = [
        "<p>{}</p>".format(segment.replace("\n", "<br>"))
        for segment in escaped.split("\n\n")
        if segment.strip()
    ]
    return "".join(parts) or "<p></p>"

def html_to_markdown_guess(html_value: str) -> str:
    """Best-effort fallback so legacy HTML loads into the markdown editor sensibly."""
    if not html_value:
        return ""

    text = html_value
    replacements = [
        (r"(?i)<br\s*/?>", "\n"),
        (r"(?i)</li>", "\n"),
        (r"(?i)<li[^>]*>", "- "),
        (r"(?i)</p>", "\n\n"),
        (r"(?i)<p[^>]*>", ""),
        (r"(?i)</h[1-6]>", "\n\n"),
        (r"(?i)<h1[^>]*>", "# "),
        (r"(?i)<h2[^>]*>", "## "),
        (r"(?i)<h3[^>]*>", "### "),
        (r"(?i)<h4[^>]*>", "#### "),
        (r"(?i)<h5[^>]*>", "##### "),
        (r"(?i)<h6[^>]*>", "###### "),
        (r"(?i)</?(ul|ol)[^>]*>", "\n"),
        (r"(?i)</?strong>", "**"),
        (r"(?i)</?b>", "**"),
        (r"(?i)</?em>", "*"),
        (r"(?i)</?i>", "*"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    stripped = bleach.clean(text, tags=[], strip=True)
    return html.unescape(stripped).strip()
def sanitize_jd(html_value: str) -> str:
    """Linkify + sanitize job description HTML while preserving Markdown output."""
    raw = (html_value or "")
    if "<" not in raw and ">" not in raw:
        # Normalize newlines
        raw = raw.replace("\r\n", "\n")
        # Turn paragraphs and line breaks into HTML
        raw = "<p>" + raw.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"

    linked = bleach.linkify(raw)
    return bleach.clean(
        linked,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        css_sanitizer=CSS_ALLOWED,
        strip=True,
    )

@app.template_filter("markdown_to_html")
def markdown_to_html_filter(text: str) -> str:
    if not text:
        return ""
    conv = md.Markdown(extensions=["extra","codehilite","toc"])
    html_out = conv.convert(text)
    # Sanitize the generated HTML as defense-in-depth
    return bleach.clean(
        bleach.linkify(html_out),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        css_sanitizer=CSS_ALLOWED,
        strip=True,
    )


@app.template_filter("jd_plaintext")
def jd_plaintext_filter(value: str) -> str:
    if not value:
        return ""

    # Normalize common block/line-break tags back to newline characters first
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)

    # Strip remaining tags, collapse spacing, and unescape entities
    text = Markup(text).striptags()
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


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
        jd = existing or JobDescription(code="", title="", html="", markdown="", status="draft", tenant_id=t.id) # NEW: markdown
        has_candidates = False
        if existing:
            has_candidates = db.query(func.count(Candidate.id)).filter(Candidate.jd_code == existing.code, Candidate.tenant_id == t.id).scalar() > 0
        else:
            has_candidates = False

        if request.method=="POST":
            posted_code     = request.form["jd_code"].strip()
            raw_markdown    = (request.form.get("jd_text","") or "").strip()
            html_rendered   = render_markdown(raw_markdown)
            html_sanitized  = sanitize_jd(html_rendered)
            title           = request.form.get("jd_title","").strip()
            status          = request.form.get("jd_status","draft")
            department      = (request.form.get("jd_department","") or "").strip() or None
            team            = (request.form.get("jd_team","") or "").strip() or None
            location        = (request.form.get("jd_location","") or "").strip() or None
            employment_type = (request.form.get("jd_employment_type","") or "").strip() or None
            salary_range    = (request.form.get("jd_salary_range","") or "").strip() or None
            start_date      = _parse_dt(request.form.get("jd_start",""))
            end_date        = _parse_dt(request.form.get("jd_end",""))
            # NEW: feature/ET-12-FE(Jen) - Fix form data persistence issue
            # Problem: start_time, end_time, work_arrangement fields were not being saved
            # Solution: Add proper form data extraction and parsing
            start_time      = _parse_time(request.form.get("start_time", ""))
            end_time        = _parse_time(request.form.get("end_time", ""))
            work_arrangement = (request.form.get("work_arrangement","") or "").strip() or None
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
                existing.markdown        = raw_markdown
                existing.html            = html_sanitized
                existing.markdown        = raw_markdown
                existing.status          = status
                existing.department      = department
                existing.team            = team
                existing.location        = location
                existing.employment_type = employment_type
                existing.salary_range    = salary_range
                existing.start_date      = start_date
                existing.end_date        = end_date
                existing.start_time      = start_time  # NEW: Fix missing field update with ET-12-FE(Jen)
                existing.end_time        = end_time    # NEW: Fix missing field update with ET-12-FE(Jen)
                existing.work_arrangement = work_arrangement  # NEW: Fix missing field update with ET-12-FE(Jen)
                existing.updated_at      = datetime.utcnow()
                # NEW
                existing.id_surveys_enabled = id_surveys_enabled
                existing.question_count     = question_count

                db.add(existing); db.commit()
                flash("JD saved", "recruiter")
                return redirect(url_for("recruiter", tenant=t.slug))

            else:
                if not posted_code:
                    flash("Job code is required", "recruiter"); return redirect(request.url)
                conflict = db.query(JobDescription).filter_by(code=posted_code, tenant_id=t.id).first()
                if conflict:
                    flash(f"Code {posted_code} is already in use for this tenant.")
                    return redirect(url_for("edit_jd", tenant=t.slug, code=conflict.code))

                jd.code            = posted_code
                jd.title           = title
                jd.markdown        = raw_markdown
                jd.html            = html_sanitized
                jd.markdown   = raw_markdown
                jd.status          = status
                jd.department      = department
                jd.team            = team
                jd.location        = location
                jd.employment_type = employment_type
                jd.salary_range    = salary_range
                jd.start_date      = start_date
                jd.end_date        = end_date
                jd.start_time      = start_time # NEW: update with ET-12-FE(Jen)
                jd.end_time        = end_time # NEW: update with ET-12-FE(Jen)
                jd.work_arrangement = work_arrangement # NEW: update with ET-12-FE(Jen)
                jd.updated_at      = datetime.utcnow()
                jd.tenant_id       = t.id
                # NEW
                jd.id_surveys_enabled = id_surveys_enabled
                jd.question_count     = question_count

                db.add(jd); db.commit()
                flash("JD saved", "recruiter")
                return redirect(url_for("recruiter", tenant=t.slug))
        # Build Application Link (robust: tries known endpoints, then falls back to /<tenant>/apply/<code>)
        apply_url = ""
        if jd and getattr(jd, "code", None):
            from flask import current_app
            for ep in ("public_apply", "apply_job", "apply", "job_apply"):
                if ep in current_app.view_functions:
                    try:
                        apply_url = url_for(ep, tenant=t.slug, code=jd.code, _external=True)
                        break
                    except Exception:
                        pass
            if not apply_url:
                apply_url = f"{request.url_root.rstrip('/')}/{t.slug}/apply/{jd.code}"

        # Applicant count (reuse the same db session)
        applicant_count = 0
        if jd and getattr(jd, "code", None):
            applicant_count = db.query(func.count(Candidate.id))\
                .filter(Candidate.tenant_id == t.id, Candidate.jd_code == jd.code)\
                .scalar() or 0

        prefill_markdown = jd.markdown or html_to_markdown_guess(jd.html)

        return render_template(
            "edit_jd.html",
            title="Edit Job",
            jd=jd,
            has_candidates=has_candidates,
            tenant=t,
            apply_url=apply_url,
            applicant_count=applicant_count,
            prefill_markdown=prefill_markdown,
        )
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
            flash("Job not found", "recruiter"); return redirect(url_for("recruiter", tenant=t.slug))

        cnt = db.query(func.count(Candidate.id)).filter(Candidate.jd_code == jd.code, Candidate.tenant_id == t.id).scalar()
        if cnt > 0:
            flash("You can't delete this job because candidates already exist for it.", "recruiter")
            return redirect(url_for("recruiter", tenant=t.slug))

        db.delete(jd); db.commit(); flash(f"Deleted {code}", "recruiter")
        return redirect(url_for("recruiter", tenant=t.slug))
    finally:
        db.close()

@app.route("/recruiter", strict_slashes=False)
@app.route("/<tenant>/recruiter", strict_slashes=False)
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
        raw_departments = [d for d in request.args.getlist("department") if d]
        departments = []
        include_blank_department = False
        for dep in raw_departments:
            val = dep.strip()
            if not val:
                continue
            if val == "__BLANK__":
                include_blank_department = True
            else:
                departments.append(val)
        start_from = (request.args.get("start_from") or "").strip()
        start_to   = (request.args.get("start_to") or "").strip()
        end_from   = (request.args.get("end_from") or "").strip()
        end_to     = (request.args.get("end_to") or "").strip()
        sort      = (request.args.get("sort") or "created").lower()
        direction = (request.args.get("dir")  or "desc").lower()
        page      = max(int(request.args.get("page", 1)), 1)
        per_page  = min(max(int(request.args.get("per_page", 25)), 5), 100)

        # Base query
        q = db.query(JobDescription).filter_by(tenant_id=t.id)

        # Search filter (title / code / department)  ⬅️ additive
        if q_str:
            like = f"%{q_str}%"
            q = q.filter(or_(
                JobDescription.title.ilike(like),
                JobDescription.code.ilike(like),
                JobDescription.department.ilike(like),
            ))

        # Status filter (only if provided)
        if status in ("open", "pending", "draft", "closed", "published"):
            q = q.filter(JobDescription.status.ilike(status))

        # Department filter (supports multiple values)
        if departments or include_blank_department:
            conds = []
            if departments:
                conds.append(JobDescription.department.in_(departments))
            if include_blank_department:
                conds.append(or_(JobDescription.department == "", JobDescription.department.is_(None)))
            if conds:
                q = q.filter(or_(*conds))

        def _parse_date(value):
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                return None

        start_from_dt = _parse_date(start_from)
        start_to_dt   = _parse_date(start_to)
        end_from_dt   = _parse_date(end_from)
        end_to_dt     = _parse_date(end_to)

        if start_from_dt:
            q = q.filter(JobDescription.start_date >= start_from_dt)
        if start_to_dt:
            q = q.filter(JobDescription.start_date <= start_to_dt)
        if end_from_dt:
            q = q.filter(JobDescription.end_date >= end_from_dt)
        if end_to_dt:
            q = q.filter(JobDescription.end_date <= end_to_dt)

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

        # Filter options source lists
        dept_counts = (
            db.query(JobDescription.department, func.count(JobDescription.id))
              .filter_by(tenant_id=t.id)
              .group_by(JobDescription.department)
              .order_by(func.lower(JobDescription.department))
              .all()
        )
        department_options = []
        for dept, count in dept_counts:
            label = dept or "Unassigned"
            department_options.append({
                "value": "__BLANK__" if not dept else dept,
                "label": label,
                "count": count,
            })

        # === initials peeks for the "View Candidates" column (unchanged) ===
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

        active_filter_count = 0
        if status:
            active_filter_count += 1
        active_filter_count += len(departments)
        if include_blank_department:
            active_filter_count += 1
        if start_from:
            active_filter_count += 1
        if start_to:
            active_filter_count += 1
        if end_from:
            active_filter_count += 1
        if end_to:
            active_filter_count += 1

        return render_template(
            "recruiter.html",
            tenant=t,
            brand_name=brand_name,
            q=q_str, status=status, sort=sort, dir=direction,
            page=page, pages=pages, per_page=per_page,
            items=items, total=total,
            status_counts=status_counts,
            cand_peeks=cand_peeks, cand_more=cand_more,
            departments_query_values=raw_departments,
            department_options=department_options,
            start_from=start_from,
            start_to=start_to,
            end_from=end_from,
            end_to=end_to,
            active_filter_count=active_filter_count,
        )
    finally:
        db.close()



# ---- Candidates Overview (all candidates across tenant) ----
# ---- Candidates Overview (all candidates across tenant) ----
# ---- Candidates Overview (all candidates across tenant) ----
@app.route("/recruiter/candidates", strict_slashes=False)
@app.route("/<tenant>/recruiter/candidates", strict_slashes=False)
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
    
    # Filter parameters with ET-12(Jen)
    job_title_filter = request.args.get("job_title", "").strip()
    department_filter = request.args.get("department", "").strip()
    claim_validity_min = request.args.get("claim_validity_min")
    claim_validity_max = request.args.get("claim_validity_max")
    relevancy_min = request.args.get("relevancy_min")
    relevancy_max = request.args.get("relevancy_max")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    def _parse_date(value):
        if not value:
            return None
        try:
            return dtparse.parse(value).date()
        except (ValueError, TypeError):
            return None

    date_from_parsed = _parse_date(date_from)
    date_to_parsed = _parse_date(date_to)

    db = SessionLocal()
    try:
        overall_total = (
            db.query(func.count(Candidate.id))
              .filter(Candidate.tenant_id == t.id)
              .scalar()
        ) or 0

        job_descriptions_all = (
            db.query(JobDescription)
              .filter(JobDescription.tenant_id == t.id)
              .all()
        )
        jd_lookup = {jd.code: jd for jd in job_descriptions_all if jd.code}
        job_titles_all = sorted({jd.title for jd in job_descriptions_all if jd.title})
        departments_all = sorted({jd.department for jd in job_descriptions_all if jd.department})

        qry = db.query(Candidate).filter_by(tenant_id=t.id)

        # Free-text search across available columns (defensive)
        if q:
            like = f"%{q}%"
            conds = []
            if hasattr(Candidate, "name"):
                conds.append(Candidate.name.ilike(like))
            if hasattr(Candidate, "job_title"):
                conds.append(Candidate.job_title.ilike(like))
            if hasattr(Candidate, "department"):
                conds.append(Candidate.department.ilike(like))
            if hasattr(Candidate, "jd_code"):
                conds.append(Candidate.jd_code.ilike(like))
            if hasattr(Candidate, "first_name"):
                conds.append(Candidate.first_name.ilike(like))
            if hasattr(Candidate, "last_name"):
                conds.append(Candidate.last_name.ilike(like))
                if hasattr(Candidate, "first_name"):
                    conds.append(func.concat(Candidate.first_name, " ", Candidate.last_name).ilike(like))
            if conds:
                qry = qry.filter(or_(*conds))
        
        # Apply filters - need to join with JobDescription for job_title and department with ET-12(Jen)
        job_title_filters = request.args.getlist('job_title')
        department_filters = request.args.getlist('department')

        def _to_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        claim_min_val = _to_float(claim_validity_min)
        claim_max_val = _to_float(claim_validity_max)
        relevancy_min_val = _to_float(relevancy_min)
        relevancy_max_val = _to_float(relevancy_max)

        active_filter_count = len(job_title_filters) + len(department_filters)
        if (claim_min_val is not None and claim_min_val > 0.0) or (claim_max_val is not None and claim_max_val < 5.0):
            active_filter_count += 1
        if (relevancy_min_val is not None and relevancy_min_val > 0.0) or (relevancy_max_val is not None and relevancy_max_val < 5.0):
            active_filter_count += 1
        if date_from_parsed:
            active_filter_count += 1
        if date_to_parsed:
            active_filter_count += 1

        has_active_filters = active_filter_count > 0

        if job_title_filters or department_filters:
            qry = qry.join(JobDescription, Candidate.jd_code == JobDescription.code)
            if job_title_filters:
                qry = qry.filter(JobDescription.title.in_(job_title_filters))
            if department_filters:
                qry = qry.filter(JobDescription.department.in_(department_filters))
        
        # Date filtering (inclusive range) on created_at to minimise result set
        if date_from_parsed:
            start_dt = datetime.combine(date_from_parsed, datetime.min.time())
            qry = qry.filter(Candidate.created_at >= start_dt)
        if date_to_parsed:
            next_day = date_to_parsed + timedelta(days=1)
            end_dt = datetime.combine(next_day, datetime.min.time())
            qry = qry.filter(Candidate.created_at < end_dt)

        rows = list(qry.all())

        # Precompute fields per row (unchanged except we record _rel_missing/_score_missing)
        # Also add job_title and department from JobDescription
        jd_cache = {}
        for c in rows:
            # Claim Validity (0–5)
            scores = getattr(c, "answer_scores", None) or []
            try:
                c.score = (sum(scores) / len(scores)) if scores else None
            except Exception:
                c.score = None
            c._score_missing = (c.score is None)  # <-- NEW: mark missing score

            # Relevancy normalize to 0–5 and remember if missing
            raw_r = getattr(c, "relevancy", None)
            if raw_r is None:
                raw_r = getattr(c, "fit_score", None)  # ET-12: Use fit_score as fallback
            if raw_r is None:
                raw_r = (getattr(c, "resume_json", None) or {}).get("fit_score")

            _missing = (raw_r is None) or (isinstance(raw_r, str) and raw_r.strip() == "")
            c._rel_missing = bool(_missing)  # mark missing

            try:
                val = 0.0 if _missing else float(raw_r)
            except Exception:
                val = 0.0

            # If a percent slipped in (>5), map back to 0–5; else assume 0–5 already
            c.relevancy = (val / 20.0) if (not _missing and val > 5.0) else (0.0 if _missing else val)

            # Applied date: created_at fallback
            c.applied_at = getattr(c, "applied_at", None) or getattr(c, "created_at", None) or getattr(c, "date_applied", None)
            
            # Add job_title and department from JobDescription
            if c.jd_code:
                if c.jd_code not in jd_cache:
                    jd_cache[c.jd_code] = jd_lookup.get(c.jd_code)
                jd = jd_cache.get(c.jd_code)
                if jd:
                    c.job_title = jd.title
                    c.department = jd.department
                else:
                    c.job_title = None
                    c.department = None
            else:
                c.job_title = None
                c.department = None

        # Apply date filtering again using applied_at to catch any records missed by SQL (parsing fallbacks)
        if date_from_parsed or date_to_parsed:
            filtered_rows = []
            for c in rows:
                applied_at = getattr(c, "applied_at", None) or getattr(c, "created_at", None)
                if not applied_at:
                    continue
                if isinstance(applied_at, datetime):
                    applied_dt = applied_at
                else:
                    try:
                        applied_dt = dtparse.parse(str(applied_at))
                    except Exception:
                        continue
                applied_date = applied_dt.date()
                if date_from_parsed and applied_date < date_from_parsed:
                    continue
                if date_to_parsed and applied_date > date_to_parsed:
                    continue
                filtered_rows.append(c)
            rows = filtered_rows

        # Apply score filters after computing scores with ET-12(Jen)
        if claim_min_val is not None or claim_max_val is not None:
            filtered_rows = []
            for c in rows:
                score_raw = getattr(c, 'score', None)
                score = float(score_raw) if score_raw is not None else 0.0
                if claim_min_val is not None and score < claim_min_val:
                    continue
                if claim_max_val is not None and score > claim_max_val:
                    continue
                filtered_rows.append(c)
            rows = filtered_rows

        if relevancy_min_val is not None or relevancy_max_val is not None:
            filtered_rows = []
            for c in rows:
                relevancy_raw = getattr(c, 'relevancy', None)
                relevancy = float(relevancy_raw) if relevancy_raw is not None else 0.0
                if relevancy_min_val is not None and relevancy < relevancy_min_val:
                    continue
                if relevancy_max_val is not None and relevancy > relevancy_max_val:
                    continue
                filtered_rows.append(c)
            rows = filtered_rows

        reverse = (dir_ == "desc")

        def _name_key(x):
            full = (getattr(x, "name", "") or "").strip()
            if not full:
                first = getattr(x, "first_name", "") or ""
                last  = getattr(x, "last_name", "") or ""
                full = f"{first} {last}".strip()
            return full.lower()

        key_map = {
            "name":      _name_key,
            "job":       lambda x: (getattr(x, "job_title", "") or ""),
            "dept":      lambda x: (getattr(x, "department", "") or ""),
            "score":     lambda x: (x._score_missing, x.score or 0),   # keep entry; overridden below when sort=='score'
            "relevancy": lambda x: (x._rel_missing, x.relevancy or 0), # keep entry; overridden below when sort=='relevancy'
            "applied":   lambda x: (x.applied_at or datetime.min),
        }

        # --- Blanks-last sorts for 'relevancy' and 'score' (additive) ---
        if sort == "relevancy":
            desc = (dir_ == "desc")
            def _rel_key(x):
                missing = getattr(x, "_rel_missing", False) or (x.relevancy is None)
                try:
                    val = float(x.relevancy or 0.0)
                except Exception:
                    val = 0.0
                return (missing, -val) if desc else (missing, val)
            rows.sort(key=_rel_key)
        elif sort == "score":
            desc = (dir_ == "desc")
            def _score_key(x):
                missing = getattr(x, "_score_missing", False) or (x.score is None)
                try:
                    val = float(x.score or 0.0)
                except Exception:
                    val = 0.0
                return (missing, -val) if desc else (missing, val)
            rows.sort(key=_score_key)
        else:
            rows.sort(key=key_map.get(sort, key_map["applied"]), reverse=reverse)
        # --- /blanks-last ---

        total = len(rows)
        pages = max(1, math.ceil(total / per_page))
        start = (page - 1) * per_page
        end = start + per_page
        items = rows[start:end]

        brand_name = getattr(t, "display_name", None) or getattr(t, "name", None) or t.slug

        # Get unique job titles and departments for filter dropdowns
        # Need to join with JobDescription to get job titles and departments
        job_titles = job_titles_all
        departments = departments_all
        
        return render_template(
            "candidates.html",
            tenant=t,
            brand_name=brand_name,
            tenant_slug=t.slug,
            jd=None,
            items=items,  # Keep as items for template compatibility
            total=total,
            page=page,
            pages=pages,
            q=q, sort=sort, dir=dir_,
            job_titles=job_titles,
            departments=departments,
            SCORE_GREEN=3.8, SCORE_YELLOW=3.3,   # claim validity thresholds (0–5)
            REL_GREEN=4.0, REL_YELLOW=3.0,       # relevancy thresholds (0–5)
            has_candidate_detail=True,
            has_active_filters=has_active_filters,
            active_filter_count=active_filter_count,
            overall_total_count=overall_total,
            showing_filtered=bool(has_active_filters or q),
        )
    finally:
        db.close()


@app.route("/analytics", strict_slashes=False)
@app.route("/<tenant>/analytics", strict_slashes=False)
@login_required
def analytics_dashboard(tenant=None):
    """Redirect to Next.js analytics dashboard"""
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("analytics_dashboard", tenant=slug))
        return redirect(url_for("login"))
    
    # Redirect to Next.js analytics route
    return redirect(f"/{t.slug}/recruiter/analytics")


# ---- Next.js Analytics Dashboard Routes ----
@app.route("/<tenant>/recruiter/analytics", strict_slashes=False)
@app.route("/<tenant>/recruiter/analytics/", strict_slashes=False)
@login_required
def analytics_overview_nextjs(tenant=None):
    """Serve Vite static files for analytics overview page"""
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("analytics_overview_nextjs", tenant=slug))
        return redirect(url_for("login"))
    
    return send_from_directory('analytics_ui/dashboard/dist', 'index.html')

@app.route("/<tenant>/recruiter/analytics/<jobCode>", strict_slashes=False)
@app.route("/<tenant>/recruiter/analytics/<jobCode>/", strict_slashes=False)
@login_required
def analytics_detail_nextjs(tenant=None, jobCode=None):
    """Serve Vite static files for analytics detail page (client-side routing)"""
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("analytics_detail_nextjs", tenant=slug, jobCode=jobCode))
        return redirect(url_for("login"))
    
    return send_from_directory('analytics_ui/dashboard/dist', 'index.html')

@app.route("/assets/<path:path>")
def vite_static(path):
    """Serve Vite static assets (assets/*, etc.)"""
    return send_from_directory('analytics_ui/dashboard/dist/assets', path)

@app.route("/favicon.ico")
@app.route("/favicon-32x32.png")
@app.route("/file.svg")
@app.route("/globe.svg")
@app.route("/next.svg")
@app.route("/vercel.svg")
@app.route("/window.svg")
def nextjs_public_assets():
    """Serve Next.js public assets"""
    filename = request.path.lstrip('/')
    return send_from_directory('analytics_ui/dashboard/dist', filename)


@app.route("/api/tenants/<tenant>/metadata", methods=["GET"], strict_slashes=False)
@login_required
def tenant_metadata(tenant):
    t = load_tenant_by_slug(tenant)
    if not t:
        abort(404, "tenant not found")

    return jsonify({
        "slug": t.slug,
        "display_name": getattr(t, "display_name", None) or t.slug,
        "logo_url": getattr(t, "logo_url", None),
    })


@app.route("/api/session/me", methods=["GET"], strict_slashes=False)
@login_required
def session_identity():
    user = current_user
    if not user:
        abort(401, "user not authenticated")

    username = getattr(user, "username", None) or "JD"
    initials = (username or "JD")[:2].upper()

    tenant_slug = None
    tenant_display = None
    if getattr(user, "tenant_id", None):
        tenant = getattr(user, "tenant", None)
        if tenant is None:
            db = SessionLocal()
            try:
                tenant = db.get(Tenant, user.tenant_id)
            finally:
                db.close()
        if tenant:
            tenant_slug = getattr(tenant, "slug", None)
            tenant_display = getattr(tenant, "display_name", None) or tenant_slug

    return jsonify({
        "username": username,
        "initials": initials,
        "is_super": bool(getattr(user, "is_super", False)),
        "tenant_slug": tenant_slug,
        "tenant_display_name": tenant_display,
    })


# ---- Export CSV for candidates ----
@app.route("/recruiter/candidates/export", strict_slashes=False)
@app.route("/<tenant>/recruiter/candidates/export", strict_slashes=False)
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
# ---------- JD-scoped candidates list (keeps endpoint name: view_candidates) ----------
@app.route("/recruiter/jd/<code>", strict_slashes=False)
@app.route("/<tenant>/recruiter/jd/<code>", strict_slashes=False)
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
        overall_total = (
            db.query(func.count(Candidate.id))
              .filter(Candidate.tenant_id == t.id, Candidate.jd_code == code)
              .scalar()
        ) or 0

        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()

        qry = db.query(Candidate).filter_by(tenant_id=t.id, jd_code=code)

        # Free-text search across available columns (defensive)
        if q:
            like = f"%{q}%"
            conds = []
            if hasattr(Candidate, "name"):
                conds.append(Candidate.name.ilike(like))
            if hasattr(Candidate, "job_title"):
                conds.append(Candidate.job_title.ilike(like))
            if hasattr(Candidate, "department"):
                conds.append(Candidate.department.ilike(like))
            if hasattr(Candidate, "jd_code"):
                conds.append(Candidate.jd_code.ilike(like))
            if hasattr(Candidate, "first_name"):
                conds.append(Candidate.first_name.ilike(like))
            if hasattr(Candidate, "last_name"):
                conds.append(Candidate.last_name.ilike(like))
                if hasattr(Candidate, "first_name"):
                    conds.append(func.concat(Candidate.first_name, " ", Candidate.last_name).ilike(like))
            if conds:
                qry = qry.filter(or_(*conds))

        rows = list(qry.all())
        for c in rows:
            # Claim Validity (0–5)
            scores = getattr(c, "answer_scores", None) or []
            try:
                c.score = (sum(scores)/len(scores)) if scores else None
            except Exception:
                c.score = None
            c._score_missing = (c.score is None)  # <-- NEW: mark missing score

            # Relevancy normalize to 0–5 (NO percent) and remember if missing
            raw_r = getattr(c, "relevancy", None)
            if raw_r is None:
                raw_r = getattr(c, "fit_score", None)  # ET-12: Use fit_score as fallback
            if raw_r is None:
                raw_r = (getattr(c, "resume_json", None) or {}).get("fit_score")

            _missing = (raw_r is None) or (isinstance(raw_r, str) and raw_r.strip() == "")
            c._rel_missing = bool(_missing)

            try:
                val = 0.0 if _missing else float(raw_r)
            except Exception:
                val = 0.0

            c.relevancy = (val / 20.0) if (not _missing and val > 5.0) else (0.0 if _missing else val)

            # Applied date
            c.applied_at = getattr(c, "applied_at", None) or getattr(c, "created_at", None)

        reverse = (dir_ == "desc")

        def _name_key(x):
            full = (getattr(x, "name", "") or "").strip()
            if not full:
                first = getattr(x, "first_name", "") or ""
                last  = getattr(x, "last_name", "") or ""
                full = f"{first} {last}".strip()
            return full.lower()

        key_map = {
            "name":      _name_key,
            "job":       lambda x: getattr(x, "job_title", None) or (x.resume_json or {}).get("job_title", "") or "",
            "dept":      lambda x: (x.department or ""),
            "score":     lambda x: (x._score_missing, x.score or 0),    # keep entry; overridden below when sort=='score'
            "relevancy": lambda x: (x._rel_missing, x.relevancy or 0),  # keep entry; overridden below when sort=='relevancy'
            "applied":   lambda x: (x.applied_at or datetime.min)
        }

        # --- Blanks-last sorts for 'relevancy' and 'score' (additive) ---
        if sort == "relevancy":
            desc = (dir_ == "desc")
            def _rel_key(x):
                missing = getattr(x, "_rel_missing", False) or (x.relevancy is None)
                try:
                    val = float(x.relevancy or 0.0)
                except Exception:
                    val = 0.0
                return (missing, -val) if desc else (missing, val)
            rows.sort(key=_rel_key)
        elif sort == "score":
            desc = (dir_ == "desc")
            def _score_key(x):
                missing = getattr(x, "_score_missing", False) or (x.score is None)
                try:
                    val = float(x.score or 0.0)
                except Exception:
                    val = 0.0
                return (missing, -val) if desc else (missing, val)
            rows.sort(key=_score_key)
        else:
            rows.sort(key=key_map.get(sort, key_map["applied"]), reverse=reverse)
        # --- /blanks-last ---

        total = len(rows)
        pages = max(1, math.ceil(total / per_page))
        start = (page - 1) * per_page
        end = start + per_page
        items = rows[start:end]
        brand_name = getattr(t, "display_name", None) or getattr(t, "name", None) or t.slug

        return render_template(
            "candidates.html",
            tenant=t,
            brand_name=brand_name,
            tenant_slug=t.slug,
            jd=jd,
            items=items,
            total=total,
            page=page,
            pages=pages,
            q=q, sort=sort, dir=dir_,
            SCORE_GREEN=3.8, SCORE_YELLOW=3.3,  # claim validity thresholds (0–5)
            REL_GREEN=4.0, REL_YELLOW=3.0,      # relevancy thresholds (0–5)
            has_candidate_detail=True,
            has_active_filters=False,
            overall_total_count=overall_total,
            showing_filtered=bool(q),
        )
    finally:
        db.close()




# ---------- Candidate Detail ----------
# ---------- Candidate Detail ----------
@app.route("/recruiter/candidate/<id>", strict_slashes=False)
@app.route("/<tenant>/recruiter/candidate/<id>", strict_slashes=False)
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
            
        # Add job_title and department to candidate object
        if jd:
            c.job_title = jd.title
            c.department = jd.department
        else:
            c.job_title = None
            c.department = None

        # Compute claim validity (average of answer_scores if present)
        scores = list(getattr(c, "answer_scores", None) or [])
        claim_validity = (sum(scores) / len(scores)) if scores else None

        # Build zipped Q&A: list of {q, a, s}
        qs  = list(getattr(c, "questions", None) or [])
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

        # Thresholds (0–5 scales)
        SCORE_GREEN  = 3.8
        SCORE_YELLOW = 3.3
        REL_GREEN    = 4.0
        REL_YELLOW   = 3.0

        # Resume preview URL - only allow inline for PDFs; provide download_url for others
        download_url = None
        is_pdf = False
        resume_url = None
        if c.resume_url:
            path_lower = (c.resume_url or "").lower()
            is_pdf = path_lower.endswith(".pdf")
            download_url = url_for("download_resume", tenant=t.slug, cid=c.id)
            if is_pdf:
                resume_url = url_for("download_resume", tenant=t.slug, cid=c.id, inline=1, _external=False)
            print(f"🔍 DEBUG: c.resume_url = {c.resume_url}")
            print(f"🔍 DEBUG: resume_url = {resume_url}")
            print(f"🔍 DEBUG: is_pdf = {is_pdf}")
        else:
            resume_url = None
            print(f"🔍 DEBUG: c.resume_url is None or empty")

        # Relevancy normalized to 0–5
        raw_r = getattr(c, "relevancy", None)
        if raw_r is None:
            raw_r = getattr(c, "fit_score", None)
        if raw_r is None:
            raw_r = (getattr(c, "resume_json", None) or {}).get("fit_score")
        if raw_r is None:
            relevancy = 0.0
        else:
            relevancy = (float(raw_r) / 20.0) if float(raw_r) > 5 else float(raw_r)

        # Tab/focus switches
        focus_changes = getattr(c, "left_tab_count", 0) or 0

        self_id = (c.resume_json or {}).get("_self_id", {})

        return render_template(
            "candidate_detail.html",
            tenant=t,
            tenant_slug=t.slug,
            jd=jd,
            c=c,
            relevancy=relevancy,
            resume_url=resume_url,
            is_pdf=is_pdf,
            download_url=download_url,
            claim_validity=claim_validity,
            qa=qa,
            focus_changes=focus_changes,
            self_id=self_id,   # <-- NEW
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
    db = SessionLocal()
    try:
        qry = db.query(Candidate).filter_by(tenant_id=tenant_obj.id)
        
        # Free-text search
        if q:
            like = f"%{q}%"
            conds = []
            if hasattr(Candidate, "name"):
                conds.append(Candidate.name.ilike(like))
            if hasattr(Candidate, "jd_code"):
                conds.append(Candidate.jd_code.ilike(like))
            if hasattr(Candidate, "first_name"):
                conds.append(Candidate.first_name.ilike(like))
            if hasattr(Candidate, "last_name"):
                conds.append(Candidate.last_name.ilike(like))
                if hasattr(Candidate, "first_name"):
                    conds.append(func.concat(Candidate.first_name, " ", Candidate.last_name).ilike(like))
            if conds:
                qry = qry.filter(or_(*conds))
        
        # Apply filters - need to join with JobDescription for job_title and department
        job_title_filters = request.args.getlist('job_title')
        department_filters = request.args.getlist('department')
        
        if job_title_filters or department_filters:
            qry = qry.join(JobDescription, Candidate.jd_code == JobDescription.code)
            if job_title_filters:
                qry = qry.filter(JobDescription.title.in_(job_title_filters))
            if department_filters:
                qry = qry.filter(JobDescription.department.in_(department_filters))
        
        rows = list(qry.all())
        total = len(rows)
        
        # Add job_title and department from JobDescription
        jd_cache = {}
        for c in rows:
            if c.jd_code:
                if c.jd_code not in jd_cache:
                    jd = db.query(JobDescription).filter(JobDescription.code == c.jd_code).first()
                    jd_cache[c.jd_code] = jd
                else:
                    jd = jd_cache[c.jd_code]
                
                if jd:
                    c.job_title = jd.title
                    c.department = jd.department
                else:
                    c.job_title = None
                    c.department = None
            else:
                c.job_title = None
                c.department = None
        
        # Apply score filters after computing scores
        claim_validity_min = request.args.get('claim_validity_min')
        relevancy_min = request.args.get('relevancy_min')
        
        if claim_validity_min:
            filtered_rows = []
            min_val = float(claim_validity_min)
            for c in rows:
                score = getattr(c, 'score', None) or 0
                if score >= min_val:
                    filtered_rows.append(c)
            rows = filtered_rows

        if relevancy_min:
            filtered_rows = []
            min_val = float(relevancy_min)
            for c in rows:
                relevancy = getattr(c, 'relevancy', None) or 0
                if relevancy >= min_val:
                    filtered_rows.append(c)
            rows = filtered_rows
        
        # Pagination
        start = (page - 1) * per_page
        end = start + per_page
        items = rows[start:end]
        
    finally:
        db.close()

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
        items=items,
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
        # Accept either a single "name" or split "first_name"/"last_name"
        first = (request.form.get("first_name") or request.form.get("firstname") or "").strip()
        last  = (request.form.get("last_name")  or request.form.get("lastname")  or "").strip()
        name  = (request.form.get("name") or f"{first} {last}".strip()).strip()

        email = (request.form.get("email") or "").strip()

        # Accept either "resume_file" or "resume"
        f = request.files.get("resume_file") or request.files.get("resume")

        if not name or not (f and f.filename):
            flash("Name & file required", "applicant")
            return redirect(request.url)


        ext = os.path.splitext(f.filename)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            f.save(tmp.name)
            path = tmp.name

        try:
            mime_guess = mimetypes.guess_type(f.filename)[0] or f.mimetype
            text = file_to_text(path, mime_guess)
        except ValueError:
            flash("PDF or DOCX only", "applicant")
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

    # NEW: Debug raw JD fields for visibility - added with ET-12-FE Jen
    app.logger.info(
        f"[ET-12] Apply JD meta code={jd.code} "
        f"start_date={getattr(jd,'start_date',None)} start_time={getattr(jd,'start_time',None)} "
        f"end_date={getattr(jd,'end_date',None)} end_time={getattr(jd,'end_time',None)} "
        f"location={getattr(jd,'location',None)} work_arrangement={getattr(jd,'work_arrangement',None)} "
        f"employment_type={getattr(jd,'employment_type',None)}"
    )

    # NEW: Format Posted/End date-time labels for Apply header - added with ET-12-FE Jen
    def _fmt_date(d):
        try:
            return d.strftime("%B %-d, %Y") if d else None
        except Exception:
            return d.strftime("%B %d, %Y") if d else None

    def _fmt_time(t):
        try:
            return t.strftime("%-I:%M %p") if t else None
        except Exception:
            return t.strftime("%I:%M %p") if t else None

    def _join_dt(d, t):
        ds = _fmt_date(d)
        ts = _fmt_time(t)
        if ds and ts:
            return f"{ds} {ts}"
        return ds or ts

    posted_label = _join_dt(getattr(jd, "start_date", None), getattr(jd, "start_time", None))
    end_label    = _join_dt(getattr(jd, "end_date", None), getattr(jd, "end_time", None))

    app.logger.info(f"[ET-12] Apply labels posted={posted_label} end={end_label} for jd={jd.code}")

    return render_template(
        "apply.html",
        title=f"Apply – {jd.code}",
        jd=jd,
        tenant_slug=t.slug,
        tenant=t,
        posted_label=posted_label,  # NEW: posted label for header - added with ET-12-FE Jen
        end_label=end_label,        # NEW: end label for header - added with ET-12-FE Jen
    )  # 2025-10-01 added: Pass tenant object to template for logo display

# ─── Camera gate ─────────────────────────────────────────────────
# Camera gate (intro/instructions + camera permission)
# ── Camera / Interview setup ───────────────────────────────────────────────────
@app.route("/<tenant>/apply/<code>/<cid>/camera", methods=["GET"])
def camera_gate(tenant, code, cid):
    t = load_tenant_by_slug(tenant)
    if not t:
        abort(404)

    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=cid, tenant_id=t.id, jd_code=code).first()
    finally:
        db.close()

    if not c:
        abort(404)

    # First name (Candidate has a single 'name' field in your DB)
    raw_name = (c.name or "").strip()
    first_name = raw_name.split()[0] if raw_name else "there"

    # Build the correct "next" URL by trying your known endpoints
    from flask import current_app
    from werkzeug.routing import BuildError
    vfs = current_app.view_functions

    next_url = None
    # 1) Paged question route requires idx
    if "question_paged" in vfs:
        try:
            next_url = url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=0)
        except BuildError:
            # Some variants also take a 'page' param, try a sensible fallback
            try:
                next_url = url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=0, page=1)
            except BuildError:
                pass
    # 2) Non-paged route (if present)
    if not next_url and "questions" in vfs:
        try:
            next_url = url_for("questions", tenant=t.slug, code=code, cid=cid)
        except BuildError:
            pass
    # 3) Older start handler
    if not next_url and "start_quiz" in vfs:
        try:
            next_url = url_for("start_quiz", tenant=t.slug, code=code, cid=cid)
        except BuildError:
            pass
    # Final guaranteed fallback to paged with idx
    if not next_url:
        next_url = url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=0)

    return render_template(
        "camera_gate.html",
        title="Interview Setup",
        c=c,
        tenant=t,
        tenant_slug=t.slug,
        first_name=first_name,
        next_url=next_url,
    )



@app.route("/<tenant>/apply/<code>/<cid>/q/<int:idx>", methods=["GET", "POST"])
def question_paged(tenant, code, cid, idx):
    t = load_tenant_by_slug(tenant)
    if not t:
        abort(404)

    db = SessionLocal()
    try:
        c  = db.get(Candidate, cid)
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
    finally:
        db.close()

    if not c or c.jd_code != code or c.tenant_id != t.id:
        flash("Application not found", "applicant")
        return redirect(url_for("apply", tenant=t.slug, code=code))

    n = len(c.questions or [])
    if n == 0:
        flash("No questions generated", "applicant")
        return redirect(url_for("apply", tenant=t.slug, code=code))

    idx = max(0, min(idx, n - 1))

    if request.method == "POST":
        a = (request.form.get("answer") or "").strip()

        # open a session to save answer + timing in one commit
        db = SessionLocal()
        try:
            c2 = db.get(Candidate, cid)
            if c2:
                # --- save answer (existing behavior) ---
                answers = list(c2.answers or [""] * n)
                answers[idx] = a
                c2.answers = answers

                # --- per-question timing (additive) ---
                elapsed_ms = int(request.form.get("elapsed_ms", "0") or 0)
                # prefer hidden field; fall back to current idx
                try:
                    q_index = int(request.form.get("q_index", idx) or idx)
                except Exception:
                    q_index = idx
                
                # ET-7: Debug log - received time
                app.logger.info(f"ET-7: ⏱️  Received time for Q{q_index}: elapsed_ms={elapsed_ms}ms ({elapsed_ms/1000:.1f}s)")
                
                if elapsed_ms > 0:
                    rj = dict(c2.resume_json or {})
                    qt = dict(rj.get("_q_times") or {})   # {"0": ms, "1": ms, ...}
                    k = str(q_index)
                    previous_time = int(qt.get(k, 0) or 0)
                    new_time = previous_time + elapsed_ms
                    qt[k] = new_time
                    rj["_q_times"] = qt
                    c2.resume_json = rj
                    
                    # ET-7: Debug log - saved time
                    app.logger.info(f"ET-7: 💾 Saved Q{k}: previous={previous_time}ms + new={elapsed_ms}ms = total={new_time}ms ({new_time/1000:.1f}s)")
                    app.logger.info(f"ET-7: 📊 All times: {qt}")
                else:
                    app.logger.warning(f"ET-7: ⚠️  No time recorded for Q{q_index} (elapsed_ms={elapsed_ms})")
                # --- /per-question timing ---


                # --- ET-7: Track paste events per question ---
                paste_detected = int(request.form.get("paste_detected", "0") or 0)
                if paste_detected:
                    rj = dict(c2.resume_json or {})
                    paste_flags = dict(rj.get("_paste_flags") or {})   # {"0": 1, "1": 0, ...}
                    k = str(q_index)
                    paste_flags[k] = 1
                    rj["_paste_flags"] = paste_flags
                    
                    # ET-7: Store paste ranges (positions of pasted text)
                    paste_ranges_str = request.form.get("paste_ranges", "[]")
                    try:
                        import json
                        paste_ranges = json.loads(paste_ranges_str)
                        if paste_ranges:
                            all_paste_ranges = dict(rj.get("_paste_ranges") or {})
                            all_paste_ranges[k] = paste_ranges
                            rj["_paste_ranges"] = all_paste_ranges
                    except Exception as e:
                        app.logger.warning(f"ET-7: Failed to parse paste_ranges: {e}")
                    
                    c2.resume_json = rj
                # --- /ET-7: Track paste events ---

                # --- ET-12: per-question immediate scoring (restore legacy behavior) ---
                try:
                    qs  = list(c2.questions or [])
                    ans = list(answers)
                    rjs = dict(getattr(c2, "resume_json", None) or {})
                    if qs and any(((a or "").strip() != "") for a in ans):
                        c2.answer_scores = score_answers(rjs, qs, ans)
                except Exception as e:
                    app.logger.warning(f"[ET-12] Immediate scoring failed for candidate {c2.id}: {e}")
                # --- /per-question immediate scoring ---

                db.merge(c2)
                db.commit()
        finally:
            db.close()

        action = request.form.get("action", "next")
        if action == "prev" and idx > 0:
            return redirect(url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=idx - 1))
        if action == "next" and idx < n - 1:
            return redirect(url_for("question_paged", tenant=t.slug, code=code, cid=cid, idx=idx + 1))

        # last question -> branch by JD toggle
        if jd and getattr(jd, "id_surveys_enabled", True):
            return redirect(url_for("self_id", tenant=t.slug, code=code, cid=cid))
        else:
            return redirect(url_for("finish_application", tenant=t.slug, code=code, cid=cid))

    # GET
    current_q      = c.questions[idx]
    current_a      = (c.answers or [""] * n)[idx] if c.answers else ""
    progress       = f"Question {idx + 1} of {n}"
    # progress bar should show 0% on Q1 -> use idx, not idx+1
    progress_pct   = int(idx * 100 / n)

    return render_template(
        "question_paged.html",
        title="Questions",
        name=c.name,
        code=code,
        cid=cid,
        q=current_q,
        a=current_a,
        idx=idx,
        n=n,
        total=n,            # backward-compat for older template variants
        progress=progress,
        progress_pct=progress_pct,
    )



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
            flash("Application not found", "applicant")
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
@app.route("/<tenant>/apply/<code>/<cid>/finish", methods=["GET"])
def finish_application(tenant, code, cid):
    t = load_tenant_by_slug(tenant)
    if not t: abort(404)

    # ET-12: Ensure answers are scored before showing the thank-you page
    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=cid, tenant_id=t.id, jd_code=code).first()
        if not c:
            db.close()
            abort(404)

        qs  = list(getattr(c, "questions", None) or [])
        ans = list(getattr(c, "answers", None) or [])
        cur = list(getattr(c, "answer_scores", None) or [])

        has_any_answer = any(((a or "").strip() != "") for a in ans)
        needs_scoring  = (len(cur) != len(qs)) or any(x is None for x in cur) or (len(cur) == 0)

        if qs and has_any_answer and needs_scoring:
            try:
                rjs = dict(getattr(c, "resume_json", None) or {})
                # Use existing scoring with heuristic + LLM guard-rails
                new_scores = score_answers(rjs, qs, ans)
                c.answer_scores = new_scores
                db.merge(c)
                db.commit()
            except Exception as e:
                # Fail-safe: keep empty scores; analytics will treat as No Score (0)
                app.logger.warning(f"[ET-12] Scoring failed for candidate {c.id}: {e}")
    finally:
        db.close()

    if not c:
        abort(404)

    # Back URL: send applicants to the JD landing (or wherever you prefer)
    back_url = url_for("apply", tenant=t.slug, code=code)

    # First/Full name if you want it shown in the header
    name = (c.name or "").strip()

    return render_template(
        "submit_thanks.html",
        title="Application Complete",
        tenant=t,
        tenant_slug=t.slug,
        name=name,
        back_url=back_url,
        # Progress UI (top-right)
        progress_label="Complete",
        progress_pct=100,
    )


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
# ─── Download & Delete résumé (tenant scoped) ────────────────────
@app.route("/resume/<cid>")
@app.route("/<tenant>/resume/<cid>")
@login_required
def download_resume(cid, tenant=None):
    t = load_tenant_by_slug(tenant) if tenant else current_tenant()
    if not t:
        slug = session.get("tenant_slug")
        if slug:
            return redirect(url_for("download_resume", tenant=slug, cid=cid))
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        c = db.get(Candidate, cid)
    finally:
        db.close()
    if not c or c.tenant_id != t.id:
        abort(404)

    if not c.resume_url:
        abort(404)

    fn = os.path.basename(c.resume_url)
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
    mime = (
        "application/pdf" if ext == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx"
        else "application/octet-stream"
    )

    # S3: redirect to a presigned URL with explicit Content-Disposition
    if S3_ENABLED and c.resume_url.startswith("s3://"):
        if inline and ext == "pdf":
            return redirect(presign(
                c.resume_url,
                content_disposition="inline",
                content_type="application/pdf",
            ))
        # Fallback to attachment for non-PDF or explicit download
        cd = f"attachment; filename=\"{fn}\""
        return redirect(presign(c.resume_url, content_disposition=cd))

    # NEW: allow inline previews when explicitly requested
    inline = request.args.get("inline") == "1"
    print(f"🔍 DEBUG: download_resume called")
    print(f"🔍 DEBUG: c.resume_url = {c.resume_url}")
    print(f"🔍 DEBUG: inline = {inline}")
    exists = os.path.exists(c.resume_url) if c.resume_url else False
    print(f"🔍 DEBUG: file exists = {exists}")
    print(f"🔍 DEBUG: mime = {mime}")

    # Gracefully handle missing file: if inline preview requested, return
    # a tiny same-origin HTML with a recognizable marker so the iframe
    # script can detect and hide the preview area without showing
    # a Flask error page to users.
    if not exists:
        if inline:
            html = (
                "<!doctype html><html><head>"
                "<meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<meta name='resume-missing' content='1'>"
                "<title>Resume Missing</title>"
                "</head><body data-resume-missing='1' style='margin:0'></body></html>"
            )
            return Response(html, status=404, mimetype="text/html")
        return abort(404)

    # For local files: allow inline only for PDFs; others force attachment
    allow_inline = inline and ext == "pdf"
    return send_file(
        c.resume_url,
        as_attachment=not allow_inline,
        download_name=fn,
        mimetype=mime
    )


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
            db.delete(c); db.commit(); flash("Deleted app", "recruiter")
        return redirect(url_for("view_candidates", tenant=t.slug, code=code or ""))
    finally:
        db.close()

# ─── Candidate Detail (admin) ────────────────────────────────────
@app.route("/recruiter/<cid>", strict_slashes=False)
@app.route("/<tenant>/recruiter/<cid>", strict_slashes=False)
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
            flash("Not found", "recruiter"); return redirect(url_for("recruiter", tenant=t.slug))

        qa = list(zip(c.questions, c.answers, c.answer_scores))

        # NEW: provide a browser-loadable resume_url for the template preview
        download_url = None
        is_pdf = False
        resume_url = None
        if c and c.resume_url:
            path_lower = (c.resume_url or "").lower()
            is_pdf = path_lower.endswith(".pdf")
            download_url = url_for("download_resume", tenant=t.slug, cid=c.id)
            # Only provide inline preview URL for PDFs
            if is_pdf:
                resume_url = url_for("download_resume", tenant=t.slug, cid=c.id, inline=1)
        else:
            resume_url = None

        return render_template(
            "candidate_detail.html",
            title=f"Candidate – {c.name}",
            c=c,
            jd=jd,
            qa=qa,
            tenant_slug=t.slug,
            resume_url=resume_url,   # <-- additive only
            is_pdf=is_pdf,
            download_url=download_url,
        )
    finally:
        db.close()


@app.route("/privacy")
@app.route("/<tenant>/privacy")
def privacy(tenant=None):
    base = os.path.join(app.root_path, "static", "legal")
    fn = _latest_match(base, ["*Privacy*.pdf", "*Privacy*.docx", "*Privacy*.*"])
    if not fn:
        return make_response("Privacy policy coming soon.", 200)
    mt = ("application/pdf"
          if fn.lower().endswith(".pdf")
          else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return send_from_directory(
        directory=base,
        path=fn,
        mimetype=mt,
        as_attachment=True,
        download_name=fn,
    )

@app.route("/terms")
@app.route("/<tenant>/terms")
def terms(tenant=None):
    base = os.path.join(app.root_path, "static", "legal")
    fn = _latest_match(base, ["*Terms*.pdf", "*Terms*.docx", "*Terms*.*"])
    if not fn:
        return make_response("Terms of Service coming soon.", 200)
    mt = ("application/pdf"
          if fn.lower().endswith(".pdf")
          else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return send_from_directory(
        directory=base,
        path=fn,
        mimetype=mt,
        as_attachment=True,
        download_name=fn,
    )
# ─── Entrypoint ──────────────────────────────────────────────────
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT",5000)))
