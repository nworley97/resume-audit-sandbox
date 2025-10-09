# analytics_service.py
import argparse
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, datetime as datetime_class
from statistics import mean, median, pstdev

from flask import Flask, request, jsonify, abort, make_response, Blueprint
from sqlalchemy import func

# Re-use your existing DB + models (no changes to app.py)
from db import SessionLocal
from models import JobDescription, Candidate, Tenant

bp = Blueprint("analytics_api", __name__)

# Axis metadata for Cross Validation Matrix. Exposed so the frontend can
# render human-readable labels while still reasoning about numeric buckets.
RELEVANCY_AXIS = [
    {"index": 0, "label": "5/5", "value": 5, "is_no_score": False},
    {"index": 1, "label": "4/5", "value": 4, "is_no_score": False},
    {"index": 2, "label": "3/5", "value": 3, "is_no_score": False},
    {"index": 3, "label": "2/5", "value": 2, "is_no_score": False},
    {"index": 4, "label": "1/5", "value": 1, "is_no_score": False},
    {"index": 5, "label": "0/5", "value": 0, "is_no_score": False},
    {"index": 6, "label": "No Score", "value": None, "is_no_score": True},
]

CLAIM_VALIDITY_AXIS = [
    {"index": 0, "label": ">4", "bucket": 5, "is_no_score": False},
    {"index": 1, "label": ">3", "bucket": 4, "is_no_score": False},
    {"index": 2, "label": ">2", "bucket": 3, "is_no_score": False},
    {"index": 3, "label": ">1", "bucket": 2, "is_no_score": False},
    {"index": 4, "label": ">0", "bucket": 1, "is_no_score": False},
    {"index": 5, "label": "No Score", "bucket": 0, "is_no_score": True},
]


@bp.before_app_request
def handle_cors_preflight():
    if request.method == "OPTIONS":
        response = make_response("", 200)
        response.headers.update(
            {
                "Access-Control-Allow-Origin": request.headers.get("Origin", "*"),
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": request.headers.get(
                    "Access-Control-Request-Headers", "Content-Type"
                ),
                "Access-Control-Allow-Credentials": "true",
            }
        )
        return response

@bp.after_app_request
def add_cors(response):
    response.headers.setdefault("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, OPTIONS")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    return response

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
    If empty/missing, return None (will be tracked as No Score = 0 in analytics).
    ET-12: Handle 0-100 scale scores by normalizing to 0-5 scale.
    """
    if not ans_scores:
        return None
    try:
        vals = [float(x) for x in ans_scores if x is not None]
        if not vals:
            return None
        avg = sum(vals) / len(vals)
        
        # ET-12: Normalize 0-100 scale to 0-5 scale (with ET-12-FE(Jen))
        if avg > 5:
            avg = avg / 20  # Convert 0-100 to 0-5
        
        b = int(round(avg))
        return max(1, min(5, b))
    except Exception as e:
        return None

def _relevancy_bucket(cand: Candidate):
    """
    Prefer explicit 'relevancy' if present; fall back to 'fit_score' if your
    older rows used that field. If neither is present, return None.
    """
    rel = getattr(cand, "relevancy", None)
    if rel is None:
        rel = getattr(cand, "fit_score", None)  # ET-12: Use fit_score as fallback
    if rel is None:
        return None
    try:
        b = int(round(float(rel)))
        return max(1, min(5, b))
    except Exception:
        return None


def _get_distribution_bin(score):
    """
    ET-12: Map continuous score (0-5) to distribution bin index (0-6)
    Bins: [No Score, >=0, >=1, >=2, >=3, >=4, =5]
    
    Args:
        score: float or None, range 0.0-5.0
    Returns:
        int, bin index 0-6
    """
    if score is None:
        return 0  # No Score
    if score >= 5.0:
        return 6  # Exactly 5
    if score >= 4.0:
        return 5  # >=4 (4.0 <= score < 5.0)
    if score >= 3.0:
        return 4  # >=3 (3.0 <= score < 4.0)
    if score >= 2.0:
        return 3  # >=2 (2.0 <= score < 3.0)
    if score >= 1.0:
        return 2  # >=1 (1.0 <= score < 2.0)
    if score >= 0.0:
        return 1  # >=0 (0.0 <= score < 1.0)
    return 0  # No Score


def _get_claim_range_for_matrix(score):
    """
    ET-12: Map continuous score to matrix range index for Cross Validation Matrix
    Ranges: [>4, 3-4, 2-3, 1-2, 0-1, No score] → [0, 1, 2, 3, 4, 5]
    """
    if score is None:
        return 5  # No score
    if score > 4:
        return 0  # >4
    if score > 3:
        return 1  # >3 up to 4
    if score > 2:
        return 2  # >2 up to 3
    if score > 1:
        return 3  # >1 up to 2
    if score > 0:
        return 4  # >0 up to 1
    return 5  # No score

def _get_fit_range_for_matrix(score):
    """
    ET-12: Map continuous score to matrix range index for Cross Validation Matrix
    Ranges: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No score] → [0, 1, 2, 3, 4, 5, 6]
    """
    if score is None:
        return 6  # No score
    if score >= 5:
        return 0  # 5/5
    if score >= 4:
        return 1  # 4/5
    if score >= 3:
        return 2  # 3/5
    if score >= 2:
        return 3  # 2/5
    if score >= 1:
        return 4  # 1/5
    if score >= 0:
        return 5  # 0/5
    return 6  # No score

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


def _calculate_question_progress(cand: Candidate):
    """Calculate completion status for each question"""
    qs = cand.questions or []
    ans = cand.answers or []
    
    progress = {
        "total_questions": len(qs),
        "completed_questions": 0,
        "question_stages": []
    }
    
    for i, question in enumerate(qs):
        is_answered = (
            i < len(ans) and 
            ans[i] is not None and 
            str(ans[i]).strip() != ""
        )
        progress["question_stages"].append({
            "question_index": i + 1,
            "is_completed": is_answered
        })
        if is_answered:
            progress["completed_questions"] += 1
    
    return progress


def _build_detailed_funnel(cands):
    """Create detailed question-based funnel"""
    total = len(cands)
    
    if total == 0:
        return []
    
    # Applied (Resume Upload) - 100%
    applied_count = total
    
    # Calculate completion count for each question
    question_completion = {}
    max_questions = 0
    
    for c in cands:
        progress = _calculate_question_progress(c)
        max_questions = max(max_questions, progress["total_questions"])
        
        for stage in progress["question_stages"]:
            q_num = stage["question_index"]
            if q_num not in question_completion:
                question_completion[q_num] = 0
            if stage["is_completed"]:
                question_completion[q_num] += 1
    
    # Create funnel
    funnel = [
        {
            "stage": "Applied (Resume Upload)",
            "count": applied_count,
            "percentage": 100.0,
        }
    ]
    
    # Add each question stage
    for q_num in range(1, max_questions + 1):
        completed = question_completion.get(q_num, 0)
        percentage = round((completed / total * 100.0) if total > 0 else 0.0, 1)
        
        funnel.append({
            "stage": f"Question {q_num} Completed",
            "count": completed,
            "percentage": percentage,
        })
    
    return funnel


def _initials(name: str) -> str:
    parts = (name or "").split()
    if not parts:
        return "--"
    if len(parts) == 1:
        return (parts[0][:2]).upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _calc_stats(values):
    if not values:
        return {"mean": None, "median": None, "std_dev": None}
    if len(values) == 1:
        return {
            "mean": round(values[0], 2),
            "median": round(values[0], 2),
            "std_dev": 0.0,
        }
    return {
        "mean": round(mean(values), 2),
        "median": round(median(values), 2),
        "std_dev": round(pstdev(values), 2),
    }

@bp.get("/analytics/summary")
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

                if claim_b is not None and rel_b is not None and claim_b >= 4 and rel_b >= 5:
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

@bp.get("/analytics/job/<jd_code>")
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

        # ET-12: heatmap counts for Cross Validation Matrix
        # 7x6 matrix: rows=[5/5,4/5,3/5,2/5,1/5,0/5,No Score], cols=[>4,3-4,2-3,1-2,0-1,No Score]
        heatmap = [[0 for _ in range(6)] for _ in range(7)]
        # ET-12: distributions: 7 bins [No Score, >=0, >=1, >=2, >=3, >=4, =5]
        dist_claim = [0, 0, 0, 0, 0, 0, 0]
        dist_rel   = [0, 0, 0, 0, 0, 0, 0]

        claim_values = []  # ET-12: For statistics - store actual average scores, not buckets
        relevancy_values = []  # ET-12: For statistics - store actual scores, not buckets
        diamonds_roster = []

        cell_members = defaultdict(list)

        for c in cands:
            if _is_completed(c):
                completed += 1

            # ET-12: Calculate actual average scores for statistics (before bucketing)
            # Claim validity actual average (0-5 scale)
            claim_avg = None
            ans_scores = getattr(c, "answer_scores", None)
            if ans_scores:
                try:
                    vals = [float(x) for x in ans_scores if x is not None]
                    if vals:
                        claim_avg = sum(vals) / len(vals)
                except Exception:
                    pass
            
            # Relevancy actual score (1-5 scale)
            rel_score = None
            rel_raw = getattr(c, "relevancy", None)
            if rel_raw is None:
                rel_raw = getattr(c, "fit_score", None)
            if rel_raw is not None:
                try:
                    rel_score = float(rel_raw)
                except Exception:
                    pass

            # ET-12: Calculate buckets for heatmap and distributions (1..5 or None)
            claim_b = _claim_validity_bucket(ans_scores)
            # Relevancy bucket (1..5 or None)
            rel_b = _relevancy_bucket(c)
            if rel_b is None:
                fit = getattr(c, "fit_score", None)  # ET-12: Use fit_score as fallback
                try:
                    if fit is not None:
                        cand = int(round(float(fit)))
                        if 1 <= cand <= 5:
                            rel_b = cand
                except Exception:
                    rel_b = None

            # ET-12: Calculate normalized score values for display/sorting
            claim_numeric = None
            if claim_avg is not None:
                claim_numeric = float(claim_avg)
            elif claim_b is not None:
                try:
                    claim_numeric = float(claim_b)
                except Exception:
                    claim_numeric = None

            relevancy_numeric = None
            if rel_score is not None:
                relevancy_numeric = float(rel_score)
            elif rel_b is not None:
                try:
                    relevancy_numeric = float(rel_b)
                except Exception:
                    relevancy_numeric = None

            claim_display = round(claim_numeric, 2) if claim_numeric is not None else 0.0
            relevancy_display = round(relevancy_numeric, 2) if relevancy_numeric is not None else 0.0
            combined_numeric = (
                (claim_numeric if claim_numeric is not None else 0.0) * 0.55
                + (relevancy_numeric if relevancy_numeric is not None else 0.0) * 0.45
            )
            combined_display = round(combined_numeric, 2)

            # ET-12: Calculate distribution bins (0-6) using actual scores
            # Bins: [No Score, >=0, >=1, >=2, >=3, >=4, =5]
            claim_dist_idx = _get_distribution_bin(claim_avg)
            rel_dist_idx = _get_distribution_bin(rel_score)

            # Update distributions (7 bins for charts)
            dist_claim[claim_dist_idx] += 1
            dist_rel[rel_dist_idx] += 1

            # ET-12: Track actual average values for statistics (NOT buckets)
            # This ensures Mean/Median/StdDev are calculated from real scores, not rounded buckets
            if claim_avg is not None:
                claim_values.append(claim_avg)
            if rel_score is not None:
                relevancy_values.append(rel_score)

            # ET-12: Update heatmap using original scores (7x6 matrix)
            # Rows: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No Score]
            # Cols: [>4, 3-4, 2-3, 1-2, 0-1, No Score]
            claim_matrix_idx = _get_claim_range_for_matrix(claim_avg)
            rel_matrix_idx = _get_fit_range_for_matrix(rel_score)
            heatmap[rel_matrix_idx][claim_matrix_idx] += 1

            # Diamonds logic (only for valid scores >= 4)
            if claim_b is not None and rel_b is not None:
                if claim_b >= 4 and rel_b >= 5:
                    diamonds += 1
                    diamonds_roster.append({
                        "id": c.id,
                        "name": c.name,
                        "initials": _initials(c.name),
                        "claim_validity_score": claim_display,
                        "relevancy_score": relevancy_display,
                        "combined_score": combined_display,
                        "_sort": {
                            "combined": combined_numeric,
                            "claim": claim_numeric if claim_numeric is not None else 0.0,
                            "relevancy": relevancy_numeric if relevancy_numeric is not None else 0.0,
                        },
                    })
            # ET-12: Cell members for heatmap using matrix range indices
            cell_members[(rel_matrix_idx, claim_matrix_idx)].append({
                "id": c.id,
                "name": c.name,
                "initials": _initials(c.name),
                "claim_validity_score": claim_display,
                "relevancy_score": relevancy_display,
                "combined_score": combined_display,
            })

            # resume_screened variable is no longer used (replaced with new funnel logic)

        completion_pct = (completed / total * 100.0) if total > 0 else 0.0

        diamonds_roster.sort(
            key=lambda x: (
                x.get("_sort", {}).get("combined", x["combined_score"]),
                x.get("_sort", {}).get("claim", x["claim_validity_score"]),
                x.get("_sort", {}).get("relevancy", x["relevancy_score"]),
            ),
            reverse=True,
        )

        for entry in diamonds_roster:
            entry.pop("_sort", None)

        # Create new detailed funnel (question completion status)
        funnel = _build_detailed_funnel(cands)

        manual_minutes = 10
        assisted_minutes = 5
        hourly_rate = 50
        time_saved_minutes = max((total * manual_minutes) - (diamonds * assisted_minutes), 0)
        time_saved_hours = time_saved_minutes / 60.0
        cost_saved = time_saved_hours * hourly_rate
        speed_improvement = (
            ((total * manual_minutes) / (diamonds * assisted_minutes))
            if diamonds and assisted_minutes
            else None
        )

        roi_payload = {
            "variables": {
                "total_applicants": total,
                "diamonds_count": diamonds,
                "manual_time_per_applicant": manual_minutes,
                "assisted_time_per_applicant": assisted_minutes,
                "hourly_rate": hourly_rate,
            },
            "calculated": {
                "time_saved_hours": round(time_saved_hours, 2),
                "cost_saved": round(cost_saved, 2),
                "speed_improvement": round(speed_improvement, 1) if speed_improvement else None,
                "efficiency_percentage": round((diamonds / total * 100.0) if total else 0.0, 1),
            },
        }

        # ET-12: Calculate statistics from actual average scores (not buckets)
        # This provides accurate Mean/Median/StdDev for distribution charts
        # Note: "No Score" candidates are excluded from statistics calculations
        claim_stats = _calc_stats(claim_values)
        relevancy_stats = _calc_stats(relevancy_values)

        # ET-12: Get the most recent candidate application time for last_updated
        # This shows when the last applicant was added, not when the API was called
        last_application_time = None
        if cands:
            # Get the most recent candidate by creation time
            most_recent_candidate = max(cands, key=lambda c: getattr(c, 'created_at', datetime_class.min))
            if hasattr(most_recent_candidate, 'created_at') and most_recent_candidate.created_at:
                last_application_time = most_recent_candidate.created_at.isoformat()
            else:
                # Fallback to current time if no created_at field
                last_application_time = datetime.utcnow().isoformat()
        else:
            # No candidates yet, use current time
            last_application_time = datetime.utcnow().isoformat()

        # ET-12: Heatmap 6×6 matrix with 0..5 (0=No Score, descending claim order)
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
                # ET-12: 7x6 matrix for Cross Validation Matrix
                # Rows: [5/5, 4/5, 3/5, 2/5, 1/5, 0/5, No Score]
                # Cols: [>4, 3-4, 2-3, 1-2, 0-1, No Score]
                "matrix": heatmap,
                "axes": {
                    "relevancy": RELEVANCY_AXIS,
                    "claim_validity": CLAIM_VALIDITY_AXIS,
                },
                "cells": [
                    {
                        "relevancy": r,
                        "claim": c,
                        "candidates": cell_members.get((r, c), []),
                    }
                    for r in range(7)  # 7 rows for Fit Score ranges
                    for c in range(6)   # 6 cols for Claim Validity ranges
                ],
            },
            "distributions": {
                # index 0 = No Score, 1..5 = scores 1..5
                "claim_validity": dist_claim,
                "relevancy": dist_rel,
            },
            "summary": {
                "total_candidates": total,
                "diamonds_found": diamonds,
                "completion_rate": round(completion_pct, 1),
                "last_updated": last_application_time,
            },
            "diamonds": diamonds_roster[:5],
            "completion_funnel": funnel,
            "roi": roi_payload,
            "statistics": {
                "claim_validity": claim_stats,
                "relevancy": relevancy_stats,
            },
        }
        return jsonify(payload)
    finally:
        db.close()


