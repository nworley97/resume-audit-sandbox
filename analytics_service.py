# analytics_service.py
import math
from collections import Counter, defaultdict

from flask import Flask, request, jsonify, abort
from sqlalchemy import func

# Re-use your existing DB + models (no changes to app.py)
from db import SessionLocal
from models import JobDescription, Candidate, Tenant

app = Flask(__name__)

def _tenant_or_404(db, slug: str) -> Tenant:
    if not slug:
        abort(400, "tenant is required")
    t = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not t:
        abort(404, "tenant not found")
    return t

def _claim_validity_bucket(ans_scores):
    """
    Map answer_scores -> 1..5 bucket by rounding the average.
    If empty/missing, return None (excluded from heatmap and dists).
    """
    if not ans_scores:
        return None
    try:
        vals = [float(x) for x in ans_scores if x is not None]
        if not vals:
            return None
        avg = sum(vals) / len(vals)
        b = int(round(avg))
        return max(1, min(5, b))
    except Exception:
        return None

def _relevancy_bucket(cand: Candidate):
    """
    Prefer explicit 'relevancy' if present; fall back to 'score' if your
    older rows used that field. If neither is present, return None.
    """
    rel = getattr(cand, "relevancy", None)
    if rel is None:
        rel = getattr(cand, "score", None)
    if rel is None:
        return None
    try:
        b = int(round(float(rel)))
        return max(1, min(5, b))
    except Exception:
        return None

def _is_completed(cand: Candidate) -> bool:
    """
    'Completed' == answered all questions with non-blank answers.
    This avoids schema changes and mirrors your Q&A flow.
    """
    qs = cand.questions or []
    ans = cand.answers or []
    if len(ans) < len(qs):
        return False
    # every answer must be non-blank after strip
    return all(((a or "").strip() != "") for a in ans[:len(qs)])

@app.get("/analytics/summary")
def analytics_summary():
    """
    Returns a list of jobs with applicant counts and 'diamonds found'.
    diamonds == candidates with claim>=4 AND relevancy>=4
    """
    tenant_slug = (request.args.get("tenant") or "").strip()
    db = SessionLocal()
    try:
        t = _tenant_or_404(db, tenant_slug)

        # All active JDs for tenant
        jds = (db.query(JobDescription)
                 .filter(JobDescription.tenant_id == t.id)
                 .all())

        # Group candidates by jd_code
        jd_codes = [jd.code for jd in jds if jd.code]
        if not jd_codes:
            return jsonify([])

        cands = (db.query(Candidate)
                   .filter(Candidate.tenant_id == t.id,
                           Candidate.jd_code.in_(jd_codes))
                   .all())

        by_code = defaultdict(list)
        for c in cands:
            if c.jd_code:
                by_code[c.jd_code].append(c)

        out = []
        for jd in jds:
            code = jd.code
            bucket = by_code.get(code, [])
            applicants = len(bucket)

            diamonds = 0
            for c in bucket:
                claim_b = _claim_validity_bucket(getattr(c, "answer_scores", None))
                rel_b   = _relevancy_bucket(c)
                if claim_b is not None and rel_b is not None and claim_b >= 4 and rel_b >= 4:
                    diamonds += 1

            out.append({
                "jd_code": code,
                "jd_title": jd.title,
                "status": jd.status,
                "department": jd.department,
                "team": jd.team,
                "posted": (jd.start_date.isoformat() if getattr(jd, "start_date", None) else None),
                "applicants": applicants,
                "diamonds_found": diamonds,
            })

        # sort newest first by posted if available, else title
        out.sort(key=lambda x: (x["posted"] or "", x["jd_title"] or ""), reverse=True)
        return jsonify(out)
    finally:
        db.close()

@app.get("/analytics/job/<jd_code>")
def analytics_job_detail(jd_code):
    """
    Detailed metrics for one job:
      - totals (applied, diamonds, completion %)
      - heatmap: relevancy (1..5) × claim-validity (1..5)
      - distributions for claim-validity and relevancy
    """
    tenant_slug = (request.args.get("tenant") or "").strip()
    db = SessionLocal()
    try:
        t = _tenant_or_404(db, tenant_slug)

        jd = (db.query(JobDescription)
                .filter(JobDescription.tenant_id == t.id,
                        JobDescription.code == jd_code)
                .first())
        if not jd:
            abort(404, "job not found")

        cands = (db.query(Candidate)
                   .filter(Candidate.tenant_id == t.id,
                           Candidate.jd_code == jd_code)
                   .all())

        total = len(cands)

        # Diamonds and completion
        diamonds = 0
        completed = 0

        # heatmap counts (1..5 × 1..5)
        heatmap = [[0 for _ in range(5)] for _ in range(5)]
        dist_claim = [0, 0, 0, 0, 0]
        dist_rel   = [0, 0, 0, 0, 0]

        for c in cands:
            if _is_completed(c):
                completed += 1

            claim_b = _claim_validity_bucket(getattr(c, "answer_scores", None))
            rel_b   = _relevancy_bucket(c)

            if claim_b is not None:
                dist_claim[claim_b - 1] += 1
            if rel_b is not None:
                dist_rel[rel_b - 1] += 1

            if claim_b is not None and rel_b is not None:
                heatmap[rel_b - 1][claim_b - 1] += 1
                if claim_b >= 4 and rel_b >= 4:
                    diamonds += 1

        completion_pct = (completed / total * 100.0) if total > 0 else 0.0

        payload = {
            "jd": {
                "code": jd.code,
                "title": jd.title,
                "status": jd.status,
                "department": jd.department,
                "team": jd.team,
                "posted": (jd.start_date.isoformat() if getattr(jd, "start_date", None) else None),
            },
            "totals": {
                "applied": total,
                "diamonds_found": diamonds,
                "completion_pct": round(completion_pct, 1),
                "completed": completed,
            },
            "heatmap": {
                # Rows: relevancy 1..5; Cols: claim validity 1..5
                "matrix": heatmap,
                "axes": {"relevancy": [1,2,3,4,5], "claim_validity": [1,2,3,4,5]},
            },
            "distributions": {
                "claim_validity": dist_claim,  # index 0->score 1, ..., 4->score 5
                "relevancy": dist_rel,
            }
        }
        return jsonify(payload)
    finally:
        db.close()

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5055, debug=False)
