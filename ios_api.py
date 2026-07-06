"""
ios_api.py — Mobile JSON API blueprint for the AlteraSF iOS app.

All routes live under /api/mobile/…
Auth: same Flask-Login session cookies that the web app uses.
"""
from __future__ import annotations
import math
import secrets
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, abort, session
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy import func, or_

from db import SessionLocal
from models import Tenant, User, JobDescription, Candidate, Department

mobile_api = Blueprint("mobile_api", __name__, url_prefix="/api/mobile")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_tenant(slug: str):
    db = SessionLocal()
    try:
        t = db.query(Tenant).filter_by(slug=slug).first()
    finally:
        db.close()
    return t


def tenant_required(f):
    """Resolve <tenant> slug and attach it as kwarg `t`."""
    @wraps(f)
    def inner(*args, **kwargs):
        slug = kwargs.pop("tenant", None)
        if not slug:
            abort(400, "tenant slug required")
        db = SessionLocal()
        try:
            t = db.query(Tenant).filter_by(slug=slug).first()
        finally:
            db.close()
        if not t:
            abort(404, f"tenant '{slug}' not found")
        # Ensure the logged-in user belongs to this tenant
        if not current_user.is_authenticated:
            abort(401, "not authenticated")
        if not getattr(current_user, "is_super", False):
            if getattr(current_user, "tenant_id", None) != t.id:
                abort(403, "access denied")
        return f(*args, t=t, **kwargs)
    return inner


def _normalize_score(raw) -> float:
    """Normalize fit_score to 0–5 scale."""
    if raw is None:
        return 0.0
    v = float(raw)
    return round(v / 20.0, 2) if v > 5 else round(v, 2)


def _avg_answer_scores(scores: list) -> float | None:
    if not scores:
        return None
    valid = [float(s) for s in scores if s is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _is_diamond(relevancy_5: float, claim_5: float | None) -> bool:
    return relevancy_5 >= 4.0 and (claim_5 is not None and claim_5 >= 4.0)


def _is_flagged(c: Candidate) -> bool:
    return (getattr(c, "left_tab_count", 0) or 0) > 5


def _job_dict(jd: JobDescription, db, t: Tenant) -> dict:
    applicant_count = (
        db.query(func.count(Candidate.id))
        .filter_by(jd_code=jd.code, tenant_id=t.id)
        .scalar()
    ) or 0

    # Diamond = high fit + high claim
    diamond_count = 0
    cands = db.query(Candidate).filter_by(jd_code=jd.code, tenant_id=t.id).all()
    for c in cands:
        rel = _normalize_score(getattr(c, "fit_score", None))
        claim = _avg_answer_scores(getattr(c, "answer_scores", None) or [])
        if _is_diamond(rel, claim):
            diamond_count += 1

    posted = jd.created_at
    return {
        "id": jd.id,
        "code": jd.code,
        "title": jd.title or "",
        "department": jd.department or "",
        "location": jd.location or "",
        "employment_type": jd.employment_type or "",
        "work_arrangement": jd.work_arrangement or "",
        "salary_range": jd.salary_range or "",
        "status": (jd.status or "draft").lower(),
        "question_count": jd.question_count or 4,
        "start_date": jd.start_date.isoformat() if jd.start_date else None,
        "end_date": jd.end_date.isoformat() if jd.end_date else None,
        "posted_date": posted.isoformat() if posted else None,
        "applicant_count": applicant_count,
        "diamond_count": diamond_count,
        "description": "",   # markdown omitted for list view (bandwidth)
    }


def _job_detail_dict(jd: JobDescription, db, t: Tenant) -> dict:
    base = _job_dict(jd, db, t)
    base["description"] = jd.markdown or ""
    return base


def _candidate_list_dict(c: Candidate, jd: JobDescription | None) -> dict:
    rel = _normalize_score(getattr(c, "fit_score", None))
    scores = getattr(c, "answer_scores", None) or []
    claim = _avg_answer_scores(scores)
    tab_switches = getattr(c, "left_tab_count", 0) or 0
    return {
        "id": c.id,
        "name": c.name or "",
        "email": c.email or "",
        "phone": getattr(c, "phone", "") or "",
        "jd_code": c.jd_code or "",
        "job_title": jd.title if jd else "",
        "department": jd.department if jd else "",
        "relevancy_score": rel,
        "claim_validity_score": claim,
        "tab_switches": tab_switches,
        "is_diamond": _is_diamond(rel, claim),
        "is_flagged": _is_flagged(c),
        "status": c.status or "",
        "applied_date": c.created_at.isoformat() if c.created_at else None,
    }


def _candidate_detail_dict(c: Candidate, jd: JobDescription | None, t: Tenant) -> dict:
    base = _candidate_list_dict(c, jd)

    # Q&A
    qs = list(getattr(c, "questions", None) or [])
    ans = list(getattr(c, "answers", None) or [])
    scs = list(getattr(c, "answer_scores", None) or [])
    question_meta = list((c.resume_json or {}).get("_question_meta", []))

    # Normalize questions: may be strings or dicts
    def _norm_q(q):
        if isinstance(q, dict):
            return q.get("question") or q.get("text") or str(q)
        return str(q)

    qa = []
    n = max(len(qs), len(ans), len(scs))
    for i in range(n):
        meta = question_meta[i] if i < len(question_meta) and isinstance(question_meta[i], dict) else {}
        raw_ans = ans[i] if i < len(ans) else ""
        if isinstance(raw_ans, dict):
            answer_text = raw_ans.get("text") or raw_ans.get("answer") or str(raw_ans)
            has_pasted = bool(raw_ans.get("pasted"))
        else:
            answer_text = str(raw_ans)
            has_pasted = False
        qa.append({
            "question": _norm_q(qs[i]) if i < len(qs) else "",
            "answer": answer_text,
            "score": float(scs[i]) if i < len(scs) and scs[i] is not None else None,
            "has_pasted_content": has_pasted,
            "duration_seconds": meta.get("duration_seconds", 0),
        })

    # Resume JSON fields
    rj = c.resume_json or {}
    education = rj.get("education", "")
    if isinstance(education, list):
        education = "\n".join(str(e) for e in education)
    experience = rj.get("experience", "")
    if isinstance(experience, list):
        experience = "\n".join(str(e) for e in experience)
    skills = rj.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    base.update({
        "resume_url": f"api/mobile/{t.slug}/candidates/{c.id}/resume" if c.resume_url else "",
        "education": education or "",
        "experience": experience or "",
        "skills": skills if isinstance(skills, list) else [],
        "qa_responses": qa,
    })
    return base


def _analytics_for_job(jd: JobDescription, db, t: Tenant) -> dict:
    cands = db.query(Candidate).filter_by(jd_code=jd.code, tenant_id=t.id).all()
    total = len(cands)
    qcount = jd.question_count or 4

    started = sum(1 for c in cands if (getattr(c, "answers", None) or []))
    completed = sum(
        1 for c in cands
        if len(getattr(c, "answers", None) or []) >= qcount
    )
    verified = sum(1 for c in cands if getattr(c, "realism", False))
    diamonds = []
    passed = 0
    for c in cands:
        rel = _normalize_score(getattr(c, "fit_score", None))
        claim = _avg_answer_scores(getattr(c, "answer_scores", None) or [])
        if _is_diamond(rel, claim):
            diamonds.append(_candidate_list_dict(c, jd))
            passed += 1

    completion_rate = round((completed / total * 100), 1) if total else 0.0
    time_saved = round(completed * 22 / 60, 1)   # ~22 min saved per completed screen

    # Score distribution buckets 1-5
    def score_dist(values):
        buckets = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for v in values:
            if v is None:
                continue
            bucket = max(1, min(5, round(float(v))))
            buckets[bucket] += 1
        return [{"label": str(k), "count": v, "score": float(k)} for k, v in sorted(buckets.items())]

    fit_scores = [_normalize_score(getattr(c, "fit_score", None)) for c in cands]
    claim_scores = [
        _avg_answer_scores(getattr(c, "answer_scores", None) or [])
        for c in cands
    ]

    return {
        "job_id": jd.id,
        "job_code": jd.code,
        "job_title": jd.title or "",
        "department": jd.department or "",
        "status": (jd.status or "draft").lower(),
        "total_applicants": total,
        "diamonds_found": len(diamonds),
        "completion_rate": completion_rate,
        "time_saved_hours": time_saved,
        "screen_speed": min(99, round(60 + completed * 0.1, 1)) if completed else 0,
        "review_load_reduction": min(95, round(50 + len(diamonds) * 2, 1)),
        "funnel": {
            "applied": total,
            "started": started,
            "completed": completed,
            "verified": verified,
            "passed": passed,
        },
        "claim_score_distribution": score_dist([s for s in claim_scores if s is not None]),
        "fit_score_distribution": score_dist(fit_scores),
        "diamonds": diamonds[:10],
    }


# ─── Auth ─────────────────────────────────────────────────────────────────────

@mobile_api.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not username or not password:
        abort(400, "username and password required")

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).first()
        if not user or not user.check_pw(password):
            abort(401, "invalid credentials")

        login_user(user)

        tenant_slug = None
        tenant_display = None
        if user.tenant_id:
            tenant = db.get(Tenant, user.tenant_id)
            if tenant:
                tenant_slug = tenant.slug
                tenant_display = tenant.display_name or tenant.slug
                session["tenant_slug"] = tenant_slug

        display_name = user.full_name or username
        initials = "".join(w[0] for w in display_name.split()[:2]).upper() or "U"
        return jsonify({
            "ok": True,
            "user": {
                "username": username,
                "full_name": user.full_name or "",
                "company": user.company or "",
                "initials": initials,
                "is_super": bool(user.is_super),
                "tenant_slug": tenant_slug,
                "tenant_display_name": tenant_display,
            }
        })
    finally:
        db.close()


@mobile_api.route("/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    logout_user()
    return jsonify({"ok": True})


@mobile_api.route("/auth/me", methods=["GET"])
@login_required
def auth_me():
    user = current_user
    username = getattr(user, "username", "") or ""
    full_name = getattr(user, "full_name", "") or ""
    display_name = full_name or username
    initials = "".join(w[0] for w in display_name.split()[:2]).upper() or "U"
    tenant_slug = None
    tenant_display = None
    if getattr(user, "tenant_id", None):
        db = SessionLocal()
        try:
            t = db.get(Tenant, user.tenant_id)
            if t:
                tenant_slug = t.slug
                tenant_display = t.display_name or t.slug
        finally:
            db.close()
    return jsonify({
        "username": username,
        "full_name": full_name,
        "company": getattr(user, "company", "") or "",
        "initials": initials,
        "is_super": bool(getattr(user, "is_super", False)),
        "tenant_slug": tenant_slug,
        "tenant_display_name": tenant_display,
    })


# ─── Jobs ─────────────────────────────────────────────────────────────────────

@mobile_api.route("/<tenant>/jobs", methods=["GET"])
@login_required
@tenant_required
def list_jobs(t: Tenant):
    status_filter = request.args.get("status", "").lower()
    db = SessionLocal()
    try:
        q = db.query(JobDescription).filter_by(tenant_id=t.id)
        if status_filter in ("open", "draft", "closed", "pending", "published"):
            q = q.filter(JobDescription.status.ilike(status_filter))
        jobs = q.order_by(JobDescription.created_at.desc()).all()
        return jsonify([_job_dict(jd, db, t) for jd in jobs])
    finally:
        db.close()


@mobile_api.route("/<tenant>/jobs/<code>", methods=["GET"])
@login_required
@tenant_required
def get_job(t: Tenant, code: str):
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            abort(404, f"job '{code}' not found")
        return jsonify(_job_detail_dict(jd, db, t))
    finally:
        db.close()


@mobile_api.route("/<tenant>/jobs", methods=["POST"])
@login_required
@tenant_required
def create_job(t: Tenant):
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    title = (data.get("title") or "").strip()
    if not code or not title:
        abort(400, "code and title required")

    db = SessionLocal()
    try:
        if db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first():
            abort(409, f"job code '{code}' already exists")

        jd = JobDescription(
            code=code,
            title=title,
            department=data.get("department") or None,
            location=data.get("location") or None,
            employment_type=data.get("employment_type") or None,
            work_arrangement=data.get("work_arrangement") or None,
            salary_range=data.get("salary_range") or None,
            markdown=data.get("description") or "",
            html="",
            status=data.get("status") or "draft",
            question_count=int(data.get("question_count") or 4),
            tenant_id=t.id,
        )
        db.add(jd)
        db.commit()
        db.refresh(jd)
        return jsonify(_job_detail_dict(jd, db, t)), 201
    finally:
        db.close()


@mobile_api.route("/<tenant>/jobs/<code>", methods=["PUT", "PATCH"])
@login_required
@tenant_required
def update_job(t: Tenant, code: str):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            abort(404)

        for field, col in [
            ("title", "title"), ("department", "department"),
            ("location", "location"), ("employment_type", "employment_type"),
            ("work_arrangement", "work_arrangement"), ("salary_range", "salary_range"),
            ("description", "markdown"), ("status", "status"),
        ]:
            if field in data:
                setattr(jd, col, data[field])

        if "question_count" in data:
            jd.question_count = max(1, min(5, int(data["question_count"])))
        jd.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(jd)
        return jsonify(_job_detail_dict(jd, db, t))
    finally:
        db.close()


@mobile_api.route("/<tenant>/jobs/<code>", methods=["DELETE"])
@login_required
@tenant_required
def delete_job(t: Tenant, code: str):
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            abort(404)
        db.delete(jd)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@mobile_api.route("/<tenant>/jobs/<code>/close", methods=["POST"])
@login_required
@tenant_required
def close_job(t: Tenant, code: str):
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            abort(404)
        jd.status = "closed"
        jd.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"ok": True, "status": "closed"})
    finally:
        db.close()


@mobile_api.route("/<tenant>/jobs/<code>/reopen", methods=["POST"])
@login_required
@tenant_required
def reopen_job(t: Tenant, code: str):
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            abort(404)
        jd.status = "open"
        jd.updated_at = datetime.utcnow()
        db.commit()
        return jsonify({"ok": True, "status": "open"})
    finally:
        db.close()


# ─── Departments ──────────────────────────────────────────────────────────────

@mobile_api.route("/<tenant>/departments", methods=["GET"])
@login_required
@tenant_required
def list_departments(t: Tenant):
    db = SessionLocal()
    try:
        depts = db.query(Department).filter_by(tenant_id=t.id).all()
        return jsonify([
            {"id": d.id, "name": d.name, "team_lead": d.team_lead or "", "color": d.color or "#6366f1"}
            for d in depts
        ])
    finally:
        db.close()


@mobile_api.route("/<tenant>/departments", methods=["POST"])
@login_required
@tenant_required
def create_department(t: Tenant):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name required")
    db = SessionLocal()
    try:
        dept = Department(
            tenant_id=t.id,
            name=name,
            team_lead=data.get("team_lead") or None,
            color=data.get("color") or "#6366f1",
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)
        return jsonify({"id": dept.id, "name": dept.name, "team_lead": dept.team_lead or "", "color": dept.color}), 201
    except Exception:
        db.rollback()
        abort(409, "department name already exists")
    finally:
        db.close()


@mobile_api.route("/<tenant>/departments/<int:dept_id>", methods=["PUT", "PATCH"])
@login_required
@tenant_required
def update_department(t: Tenant, dept_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        dept = db.query(Department).filter_by(id=dept_id, tenant_id=t.id).first()
        if not dept:
            abort(404)
        if "name" in data:
            dept.name = data["name"]
        if "team_lead" in data:
            dept.team_lead = data["team_lead"] or None
        if "color" in data:
            dept.color = data["color"]
        db.commit()
        return jsonify({"id": dept.id, "name": dept.name, "team_lead": dept.team_lead or "", "color": dept.color})
    finally:
        db.close()


@mobile_api.route("/<tenant>/departments/<int:dept_id>", methods=["DELETE"])
@login_required
@tenant_required
def delete_department(t: Tenant, dept_id: int):
    db = SessionLocal()
    try:
        dept = db.query(Department).filter_by(id=dept_id, tenant_id=t.id).first()
        if dept:
            db.delete(dept)
            db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ─── Candidates ───────────────────────────────────────────────────────────────

@mobile_api.route("/<tenant>/candidates", methods=["GET"])
@login_required
@tenant_required
def list_candidates(t: Tenant):
    job_code = request.args.get("job_code", "").strip()
    status_filter = request.args.get("status", "").strip()   # finalist / archived / ''
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "score")         # score | newest | flagged
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(int(request.args.get("per_page", 50)), 200)

    db = SessionLocal()
    try:
        qry = db.query(Candidate).filter_by(tenant_id=t.id)

        if job_code:
            qry = qry.filter_by(jd_code=job_code)

        if status_filter in ("finalist", "archived"):
            qry = qry.filter(Candidate.status == status_filter)
        elif status_filter == "active":
            qry = qry.filter(or_(Candidate.status == None, Candidate.status == ""))

        if search:
            like = f"%{search}%"
            qry = qry.filter(or_(
                Candidate.name.ilike(like),
                Candidate.email.ilike(like),
                Candidate.jd_code.ilike(like),
            ))

        if sort == "newest":
            qry = qry.order_by(Candidate.created_at.desc())
        elif sort == "flagged":
            qry = qry.order_by(Candidate.left_tab_count.desc())
        else:
            qry = qry.order_by(Candidate.fit_score.desc())

        total = qry.count()
        cands = qry.offset((page - 1) * per_page).limit(per_page).all()

        # Build jd lookup
        codes = {c.jd_code for c in cands if c.jd_code}
        jd_map: dict[str, JobDescription] = {}
        if codes:
            jds = db.query(JobDescription).filter(
                JobDescription.code.in_(codes),
                JobDescription.tenant_id == t.id,
            ).all()
            jd_map = {j.code: j for j in jds}

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": math.ceil(total / per_page) if per_page else 1,
            "candidates": [_candidate_list_dict(c, jd_map.get(c.jd_code)) for c in cands],
        })
    finally:
        db.close()


@mobile_api.route("/<tenant>/candidates/<cid>", methods=["GET"])
@login_required
@tenant_required
def get_candidate(t: Tenant, cid: str):
    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=cid, tenant_id=t.id).first()
        if not c:
            abort(404, "candidate not found")
        jd = db.query(JobDescription).filter_by(code=c.jd_code, tenant_id=t.id).first() if c.jd_code else None
        return jsonify(_candidate_detail_dict(c, jd, t))
    finally:
        db.close()


@mobile_api.route("/<tenant>/candidates/<cid>/status", methods=["PATCH"])
@login_required
@tenant_required
def set_candidate_status(t: Tenant, cid: str):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("status") or "").strip()
    if new_status not in ("finalist", "archived", ""):
        abort(400, "status must be 'finalist', 'archived', or '' (to clear)")
    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=cid, tenant_id=t.id).first()
        if not c:
            abort(404)
        c.status = new_status or None
        db.commit()
        return jsonify({"ok": True, "status": c.status or ""})
    finally:
        db.close()


@mobile_api.route("/<tenant>/candidates/<cid>/resume", methods=["GET"])
@login_required
@tenant_required
def download_candidate_resume(t: Tenant, cid: str):
    import os
    from flask import send_file, redirect

    db = SessionLocal()
    try:
        c = db.query(Candidate).filter_by(id=cid, tenant_id=t.id).first()
        if not c or not c.resume_url:
            abort(404, "resume not found")
        storage_path = c.resume_url
    finally:
        db.close()

    from app import S3_ENABLED, presign

    fn = os.path.basename(storage_path)
    if S3_ENABLED and storage_path.startswith("s3://"):
        try:
            url = presign(storage_path, content_disposition=f'attachment; filename="{fn}"')
            return redirect(url)
        except Exception:
            abort(502, "unable to generate resume download link")

    if os.path.exists(storage_path):
        return send_file(storage_path, as_attachment=True, download_name=fn or "resume")

    abort(404, "resume file not found")


# ─── Analytics ────────────────────────────────────────────────────────────────

@mobile_api.route("/<tenant>/analytics", methods=["GET"])
@login_required
@tenant_required
def analytics_overview(t: Tenant):
    db = SessionLocal()
    try:
        jobs = (
            db.query(JobDescription)
            .filter_by(tenant_id=t.id)
            .order_by(JobDescription.created_at.desc())
            .all()
        )
        totals_applicants = (
            db.query(func.count(Candidate.id)).filter_by(tenant_id=t.id).scalar()
        ) or 0

        job_summaries = []
        total_diamonds = 0
        for jd in jobs:
            a = _analytics_for_job(jd, db, t)
            total_diamonds += a["diamonds_found"]
            job_summaries.append({
                "job_id": a["job_id"],
                "job_code": a["job_code"],
                "job_title": a["job_title"],
                "department": a["department"],
                "status": a["status"],
                "total_applicants": a["total_applicants"],
                "diamonds_found": a["diamonds_found"],
                "completion_rate": a["completion_rate"],
                "time_saved_hours": a["time_saved_hours"],
            })

        return jsonify({
            "total_applicants": totals_applicants,
            "total_diamonds": total_diamonds,
            "job_postings": job_summaries,
        })
    finally:
        db.close()


@mobile_api.route("/<tenant>/analytics/<code>", methods=["GET"])
@login_required
@tenant_required
def analytics_job(t: Tenant, code: str):
    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter_by(code=code, tenant_id=t.id).first()
        if not jd:
            abort(404)
        return jsonify(_analytics_for_job(jd, db, t))
    finally:
        db.close()


# ─── Profile & Password ───────────────────────────────────────────────────────

@mobile_api.route("/auth/profile", methods=["PATCH"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if "full_name" in data:
            user.full_name = (data.get("full_name") or "").strip() or None
        if "company" in data:
            user.company = (data.get("company") or "").strip() or None
        if "email" in data:
            new_email = (data.get("email") or "").strip().lower()
            if new_email and new_email != user.username:
                if db.query(User).filter(User.username == new_email, User.id != user.id).first():
                    abort(409, "email already in use")
                user.username = new_email
        db.commit()
        return jsonify({
            "username": user.username,
            "full_name": user.full_name or "",
            "company": user.company or "",
            "initials": (user.full_name or user.username)[:2].upper(),
        })
    finally:
        db.close()


@mobile_api.route("/auth/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""
    if len(new_pw) < 8:
        abort(400, "new password must be at least 8 characters")
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        if not user.check_pw(current_pw):
            abort(401, "current password is incorrect")
        user.set_pw(new_pw)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ─── Team ──────────────────────────────────────────────────────────────────────

def _team_member_dict(u: User) -> dict:
    display_name = u.full_name or u.username
    return {
        "id": u.id,
        "name": display_name,
        "email": u.username,
        "role": (u.role or "admin"),
        "initials": "".join(w[0] for w in display_name.split()[:2]).upper() or "U",
    }


@mobile_api.route("/<tenant>/team", methods=["GET"])
@login_required
@tenant_required
def list_team(t: Tenant):
    db = SessionLocal()
    try:
        members = db.query(User).filter_by(tenant_id=t.id).order_by(User.id.asc()).all()
        return jsonify([_team_member_dict(u) for u in members])
    finally:
        db.close()


@mobile_api.route("/<tenant>/team/invite", methods=["POST"])
@login_required
@tenant_required
def invite_team_member(t: Tenant):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "manager").strip().lower()
    if not name or not email:
        abort(400, "name and email required")
    if role not in ("admin", "manager", "viewer"):
        abort(400, "role must be admin, manager, or viewer")

    db = SessionLocal()
    try:
        from subscription_models import check_can_add_seat
        can_add, used, limit = check_can_add_seat(t.id, db)
        if not can_add:
            abort(409, f"seat limit reached ({used}/{limit}). Upgrade your plan to add more members.")

        if db.query(User).filter_by(username=email).first():
            abort(409, "a user with this email already exists")

        temp_password = secrets.token_urlsafe(9)
        user = User(username=email, full_name=name, role=role, tenant_id=t.id)
        user.set_pw(temp_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        result = _team_member_dict(user)
        result["temp_password"] = temp_password
        return jsonify(result), 201
    finally:
        db.close()


@mobile_api.route("/<tenant>/team/<int:user_id>", methods=["PATCH"])
@login_required
@tenant_required
def update_team_member(t: Tenant, user_id: int):
    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip().lower()
    if role not in ("admin", "manager", "viewer"):
        abort(400, "role must be admin, manager, or viewer")
    db = SessionLocal()
    try:
        member = db.query(User).filter_by(id=user_id, tenant_id=t.id).first()
        if not member:
            abort(404)
        member.role = role
        db.commit()
        return jsonify(_team_member_dict(member))
    finally:
        db.close()


@mobile_api.route("/<tenant>/team/<int:user_id>", methods=["DELETE"])
@login_required
@tenant_required
def remove_team_member(t: Tenant, user_id: int):
    db = SessionLocal()
    try:
        member = db.query(User).filter_by(id=user_id, tenant_id=t.id).first()
        if not member:
            abort(404)
        if member.id == current_user.id:
            abort(400, "you cannot remove yourself")
        remaining = db.query(func.count(User.id)).filter_by(tenant_id=t.id).scalar() or 0
        if remaining <= 1:
            abort(400, "cannot remove the last team member")
        db.delete(member)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ─── Notifications (derived from live job/candidate activity) ───────────────

def _derive_notifications(t: Tenant, db) -> list[dict]:
    notifs: list[dict] = []

    jobs = db.query(JobDescription).filter_by(tenant_id=t.id).all()
    jd_by_code = {jd.code: jd for jd in jobs}
    cands = (
        db.query(Candidate)
        .filter_by(tenant_id=t.id)
        .order_by(Candidate.created_at.desc())
        .limit(100)
        .all()
    )

    for c in cands:
        jd = jd_by_code.get(c.jd_code)
        job_title = jd.title if jd else "a role"
        created = c.created_at or datetime.utcnow()

        notifs.append({
            "id": f"app_{c.id}",
            "type": "new_application",
            "title": "New application",
            "subtitle": f"{c.name} applied to {job_title}",
            "created_at": created.isoformat(),
        })

        answers = getattr(c, "answers", None) or []
        qcount = jd.question_count if jd and jd.question_count else 4
        if len(answers) >= qcount:
            notifs.append({
                "id": f"assess_{c.id}",
                "type": "assessment_completed",
                "title": "Assessment completed",
                "subtitle": f"{c.name} finished the {job_title} assessment",
                "created_at": created.isoformat(),
            })

        rel = _normalize_score(getattr(c, "fit_score", None))
        claim = _avg_answer_scores(getattr(c, "answer_scores", None) or [])
        if _is_diamond(rel, claim):
            notifs.append({
                "id": f"diamond_{c.id}",
                "type": "diamond_found",
                "title": "Diamond candidate found",
                "subtitle": f"{c.name} passed verification for {job_title}",
                "created_at": created.isoformat(),
            })

    for jd in jobs:
        if (jd.status or "").lower() == "draft" and jd.updated_at:
            notifs.append({
                "id": f"draft_{jd.id}",
                "type": "draft_saved",
                "title": "Draft saved",
                "subtitle": f"{jd.title} draft was auto-saved",
                "created_at": jd.updated_at.isoformat(),
            })

    notifs.sort(key=lambda n: n["created_at"], reverse=True)
    return notifs[:50]


@mobile_api.route("/<tenant>/notifications", methods=["GET"])
@login_required
@tenant_required
def list_notifications(t: Tenant):
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        read_ids = set(user.read_notification_ids or [])
        derived = _derive_notifications(t, db)
        for n in derived:
            n["is_read"] = n["id"] in read_ids
        return jsonify(derived)
    finally:
        db.close()


@mobile_api.route("/<tenant>/notifications/read-all", methods=["POST"])
@login_required
@tenant_required
def mark_all_notifications_read(t: Tenant):
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        derived = _derive_notifications(t, db)
        ids = {n["id"] for n in derived}
        existing = set(user.read_notification_ids or [])
        user.read_notification_ids = list(existing | ids)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@mobile_api.route("/<tenant>/notifications/<notif_id>/read", methods=["PATCH"])
@login_required
@tenant_required
def mark_notification_read(t: Tenant, notif_id: str):
    db = SessionLocal()
    try:
        user = db.get(User, current_user.id)
        existing = set(user.read_notification_ids or [])
        existing.add(notif_id)
        user.read_notification_ids = list(existing)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ─── Billing ───────────────────────────────────────────────────────────────────

@mobile_api.route("/<tenant>/billing", methods=["GET"])
@login_required
@tenant_required
def get_billing(t: Tenant):
    from subscription_models import get_usage_summary, TenantSubscription, PaymentHistory
    from plans_config import get_all_plans_for_display

    db = SessionLocal()
    try:
        summary = get_usage_summary(t.id, db)
        if not summary:
            abort(404, "no billing account for this tenant")
        if summary.get("period_end") is not None:
            summary["period_end"] = summary["period_end"].isoformat()

        sub = db.query(TenantSubscription).filter_by(tenant_id=t.id).first()
        invoices = (
            db.query(PaymentHistory)
            .filter_by(tenant_id=t.id)
            .order_by(PaymentHistory.created_at.desc())
            .limit(24)
            .all()
        )

        return jsonify({
            "summary": summary,
            "payment_method": {
                "brand": sub.payment_method_brand if sub else None,
                "last4": sub.payment_method_last4 if sub else None,
                "exp_month": sub.payment_method_exp_month if sub else None,
                "exp_year": sub.payment_method_exp_year if sub else None,
            },
            "has_stripe_customer": bool(sub and sub.stripe_customer_id),
            "invoices": [
                {
                    "id": inv.id,
                    "description": inv.description or "",
                    "amount": inv.amount,
                    "status": inv.status,
                    "created_at": inv.created_at.isoformat() if inv.created_at else None,
                }
                for inv in invoices
            ],
            "plans": get_all_plans_for_display(),
        })
    finally:
        db.close()


@mobile_api.route("/<tenant>/billing/change-plan", methods=["POST"])
@login_required
@tenant_required
def billing_change_plan(t: Tenant):
    from subscription_models import TenantSubscription, PaymentHistory, get_tenant_subscription
    from plans_config import PLAN_TIERS, PLAN_PRICING, get_plan_price

    data = request.get_json(silent=True) or {}
    new_tier = (data.get("plan_tier") or "").strip().lower()
    if new_tier not in PLAN_TIERS:
        abort(400, "invalid plan_tier")

    db = SessionLocal()
    try:
        virtual = get_tenant_subscription(t.id, db)
        if virtual and virtual.status == "grandfathered":
            abort(400, "grandfathered accounts cannot change plans")

        sub = db.query(TenantSubscription).filter_by(tenant_id=t.id).first()
        if not sub:
            sub = TenantSubscription(tenant_id=t.id, plan_tier="free", billing_cycle="monthly", status="active")
            db.add(sub)
            db.flush()

        new_cycle = (data.get("billing_cycle") or sub.billing_cycle or "monthly").strip().lower()
        old_amount = get_plan_price(sub.plan_tier, sub.billing_cycle)
        new_amount = get_plan_price(new_tier, new_cycle)

        sub.plan_tier = new_tier
        sub.billing_cycle = new_cycle
        db.add(PaymentHistory(
            tenant_id=t.id,
            amount=max(new_amount - old_amount, 0),
            currency="USD",
            description=f"Plan change to {PLAN_PRICING[new_tier]['display_name']} ({new_cycle})",
            status="succeeded",
            plan_tier=new_tier,
            billing_cycle=new_cycle,
            payment_method_last4=sub.payment_method_last4,
            payment_method_brand=sub.payment_method_brand,
        ))
        db.commit()
        return jsonify({"ok": True, "plan_tier": new_tier, "billing_cycle": new_cycle})
    finally:
        db.close()


@mobile_api.route("/<tenant>/billing/cancel", methods=["POST"])
@login_required
@tenant_required
def billing_cancel(t: Tenant):
    from subscription_models import TenantSubscription, get_tenant_subscription

    db = SessionLocal()
    try:
        virtual = get_tenant_subscription(t.id, db)
        if virtual and virtual.status == "grandfathered":
            abort(400, "grandfathered accounts cannot be canceled")

        sub = db.query(TenantSubscription).filter_by(tenant_id=t.id).first()
        if not sub or sub.status == "canceled":
            abort(400, "no active subscription to cancel")

        sub.status = "canceled"
        sub.canceled_at = datetime.utcnow()
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@mobile_api.route("/<tenant>/billing/portal", methods=["GET"])
@login_required
@tenant_required
def billing_portal(t: Tenant):
    from subscription_models import TenantSubscription

    db = SessionLocal()
    try:
        sub = db.query(TenantSubscription).filter_by(tenant_id=t.id).first()
        if not sub or not sub.stripe_customer_id:
            abort(400, "no payment method on file to manage")

        from stripe_service import create_billing_portal_session
        success, error, portal_url = create_billing_portal_session(
            sub.stripe_customer_id,
            request.args.get("return_url", "https://alterasf.com"),
        )
        if not success or not portal_url:
            abort(502, error or "unable to reach billing portal")
        return jsonify({"url": portal_url})
    finally:
        db.close()
