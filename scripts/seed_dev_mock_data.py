"""
Seeds demo/mock data (open, draft, and closed jobs with applicants — including
diamonds, flagged candidates, finalists, and archived candidates) for a given
user's tenant, so the mobile app has real data to test every feature against.

This is idempotent: it looks up the user's tenant, skips any job codes that
already exist, and only ever adds new rows — it never deletes or modifies
existing data.

Usage:
    DATABASE_URL=postgresql://... python scripts/seed_dev_mock_data.py [email]

If no email is given, defaults to vihaanparikh11@gmail.com.
Run this from the repo root (needs db.py / models.py importable), with
DATABASE_URL pointed at whichever database you want to seed (prod or local).
"""
import os
import sys
import secrets
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import User, Department, JobDescription, Candidate

random.seed(42)

DATABASE_URL="postgresql://blackbox_prod_db_user:...@dpg-d1umj23uibrs738l8r7g-a.oregon-postgres.render.com/blackbox_prod_db"

QUESTIONS = [
    "Tell us about a project you're most proud of and your specific contributions.",
    "Describe a time you overcame a technical challenge—what was the root cause and outcome?",
    "How do you prioritize tasks when timelines are tight and requirements change?",
]

ANSWER_BANK = [
    "I led the redesign of our onboarding flow, cutting drop-off by 30% through iterative user testing and close collaboration with engineering.",
    "We hit a race condition in production that only showed up under load. I added structured logging, reproduced it locally with a stress test, and fixed it by serializing the critical section.",
    "I start by separating must-haves from nice-to-haves, confirm scope with stakeholders early, and build a thin end-to-end version before polishing individual pieces.",
    "During a group project, our data pipeline kept silently dropping records. I traced it to a schema mismatch after an upstream change and added validation to catch it early.",
    "I shipped a small internal tool that automated a manual weekly report, saving the team a few hours every week, and iterated on it based on feedback.",
    "When two teammates disagreed on architecture, I ran a quick spike on both approaches so we could compare tradeoffs with real numbers instead of opinions.",
]

FIRST_NAMES = ["Maya", "Ethan", "Priya", "Noah", "Sofia", "Liam", "Aisha", "Mason", "Chloe", "Ravi",
               "Zoe", "Diego", "Amara", "Lucas", "Nina", "Omar", "Grace", "Kenji", "Isla", "Theo"]
LAST_NAMES = ["Chen", "Okafor", "Patel", "Silva", "Nguyen", "Brooks", "Kim", "Ramirez", "Turner", "Singh",
              "Rossi", "Haddad", "Foster", "Ibrahim", "Novak", "Reyes", "Bianchi", "Hassan", "Sato", "Walker"]


def rand_name(used):
    while True:
        n = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if n not in used:
            used.add(n)
            return n


def make_candidate(db, tenant_id, jd_code, name, days_ago, fit_score, answer_scores,
                    tab_switches=0, status=None, note=None):
    cid = secrets.token_hex(4)
    email = name.lower().replace(" ", ".") + "@example.com"
    answers = random.sample(ANSWER_BANK, k=min(3, len(ANSWER_BANK)))
    c = Candidate(
        id=cid,
        name=name,
        email=email,
        phone="415555" + str(random.randint(1000, 9999)),
        resume_url=f"/tmp/seed_{cid}.pdf",
        resume_json={
            "fit_score": fit_score * 20,
            "realism": True,
            "applicant_email": email,
            "_q_times": {"0": 12000, "1": 9800, "2": 15000},
            "_paste_flags": {"0": 0, "1": 0, "2": 0},
            "_paste_ranges": {},
            "_self_id": {},
        },
        fit_score=fit_score,
        realism=True,
        questions=QUESTIONS[:3],
        answers=answers,
        answer_scores=answer_scores,
        jd_code=jd_code,
        created_at=datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 20)),
        left_tab_count=tab_switches,
        status=status,
        recruiter_note=note,
        tenant_id=tenant_id,
    )
    db.add(c)
    return c


def make_job(db, tenant_id, code, title, department, status, employment_type="Full time",
             work_arrangement="Remote", location="Remote", salary_range="", days_ago_posted=5,
             question_count=3):
    jd = JobDescription(
        code=code, title=title, department=department, status=status,
        employment_type=employment_type, work_arrangement=work_arrangement,
        location=location, salary_range=salary_range,
        markdown=f"We're looking for a {title} to join our {department} team. "
                 f"You'll work closely with cross-functional partners to ship high-quality work "
                 f"and help us scale our hiring pipeline.",
        html="",
        question_count=question_count,
        id_surveys_enabled=True,
        tenant_id=tenant_id,
        created_at=datetime.utcnow() - timedelta(days=days_ago_posted),
    )
    db.add(jd)
    db.flush()
    return jd


def main():
    target_email = sys.argv[1] if len(sys.argv) > 1 else "vihaanparikh11@gmail.com"
    db = SessionLocal()
    used_names = set()
    try:
        user = db.query(User).filter_by(username=target_email).first()
        if not user:
            print(f"No user found with username '{target_email}'. Aborting — nothing was changed.")
            return
        if not user.tenant_id:
            print(f"User '{target_email}' has no tenant assigned. Aborting — nothing was changed.")
            return

        tenant_id = user.tenant_id
        print(f"Seeding tenant_id={tenant_id} for user '{target_email}'")

        existing_codes = {j.code for j in db.query(JobDescription).filter_by(tenant_id=tenant_id).all()}
        print("existing job codes:", existing_codes)

        dept_names = ["Engineering", "Design", "Sales & Marketing", "Business Development"]
        existing_depts = {d.name for d in db.query(Department).filter_by(tenant_id=tenant_id).all()}
        for name in dept_names:
            if name not in existing_depts:
                db.add(Department(tenant_id=tenant_id, name=name, team_lead=None, color="#2f7d5f"))
        db.flush()

        # Add a couple more candidates to an existing open job, if present, for variety.
        for maybe_existing_open in db.query(JobDescription).filter_by(tenant_id=tenant_id, status="open").all():
            existing_names = {c.name for c in db.query(Candidate).filter_by(tenant_id=tenant_id, jd_code=maybe_existing_open.code).all()}
            used_names |= existing_names
            break  # only touch the first pre-existing open job, not the ones we're about to create

        # ── Open roles with applicants ──────────────────────────────
        if "EPD-PD-01" not in existing_codes:
            j = make_job(db, tenant_id, "EPD-PD-01", "Product Designer", "Design", "open",
                         employment_type="Full time", work_arrangement="Remote", location="Remote",
                         salary_range="$90,000–$130,000", days_ago_posted=6)
            specs = [
                (0, 5, [5, 5, 5], 0, None, None),
                (1, 5, [4, 5, 5], 0, "finalist", "Excellent portfolio, moving to onsite loop."),
                (2, 4, [4, 4, 4], 0, None, None),
                (3, 3, [3, 3, 4], 0, None, None),
                (4, 2, [2, 2, 3], 9, None, None),
                (5, 4, [3, 4, 4], 0, None, None),
                (6, 1, [1, 2, 1], 0, None, None),
                (7, 3, [3, 3, 3], 0, "archived", "Not enough motion design experience."),
            ]
            for days_ago, fit, scores, tabs, status, note in specs:
                make_candidate(db, tenant_id, j.code, rand_name(used_names), days_ago, fit, scores, tabs, status, note)

        if "SM-SDR-01" not in existing_codes:
            j = make_job(db, tenant_id, "SM-SDR-01", "Sales Development Representative", "Sales & Marketing", "open",
                         employment_type="Full time", work_arrangement="Hybrid", location="San Francisco, CA",
                         salary_range="$60,000–$80,000", days_ago_posted=3)
            specs = [
                (0, 4, [4, 4, 5], 0, None, None),
                (1, 3, [3, 4, 3], 0, None, None),
                (2, 2, [2, 2, 2], 7, None, None),
                (3, 5, [5, 4, 5], 0, "finalist", "Top of the funnel, great energy on the phone screen."),
                (4, 3, [3, 3, 4], 0, None, None),
            ]
            for days_ago, fit, scores, tabs, status, note in specs:
                make_candidate(db, tenant_id, j.code, rand_name(used_names), days_ago, fit, scores, tabs, status, note)

        # ── Draft roles (no applicants yet) ─────────────────────────
        for code, title, dept in [
            ("EPD-BE-DRAFT", "Backend Engineer", "Engineering"),
            ("EPD-DS-DRAFT", "Data Scientist", "Engineering"),
            ("MKT-CM-DRAFT", "Content Marketing Manager", "Sales & Marketing"),
        ]:
            if code not in existing_codes:
                make_job(db, tenant_id, code, title, dept, "draft",
                         employment_type="Full time", work_arrangement="Remote", location="Remote",
                         days_ago_posted=random.randint(1, 10))

        # ── Closed roles ─────────────────────────────────────────────
        if "EPD-FE-01" not in existing_codes:
            j = make_job(db, tenant_id, "EPD-FE-01", "Frontend Engineer", "Engineering", "closed",
                         employment_type="Full time", work_arrangement="Remote", location="Remote",
                         salary_range="$100,000–$140,000", days_ago_posted=25)
            specs = [
                (20, 5, [5, 5, 5], 0, "finalist", "Hired — accepted offer."),
                (18, 4, [4, 4, 3], 0, "archived", None),
                (15, 3, [3, 3, 3], 0, "archived", None),
                (14, 2, [2, 3, 2], 6, "archived", None),
            ]
            for days_ago, fit, scores, tabs, status, note in specs:
                make_candidate(db, tenant_id, j.code, rand_name(used_names), days_ago, fit, scores, tabs, status, note)

        if "BD-CSM-01" not in existing_codes:
            j = make_job(db, tenant_id, "BD-CSM-01", "Customer Success Manager", "Business Development", "closed",
                         employment_type="Full time", work_arrangement="Hybrid", location="San Francisco, CA",
                         salary_range="$75,000–$95,000", days_ago_posted=40)
            specs = [
                (35, 4, [4, 5, 4], 0, "finalist", "Hired — started onboarding."),
                (33, 3, [3, 3, 3], 0, "archived", None),
                (30, 2, [2, 2, 3], 0, "archived", None),
            ]
            for days_ago, fit, scores, tabs, status, note in specs:
                make_candidate(db, tenant_id, j.code, rand_name(used_names), days_ago, fit, scores, tabs, status, note)

        db.commit()
        print("Seed complete.")

        jobs = db.query(JobDescription).filter_by(tenant_id=tenant_id).all()
        for jb in jobs:
            n = db.query(Candidate).filter_by(tenant_id=tenant_id, jd_code=jb.code).count()
            print(f"  {jb.code:16s} {jb.status:8s} {jb.title:35s} applicants={n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
