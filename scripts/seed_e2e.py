"""Seed the isolated Playwright database with deterministic recruiter data."""
from pathlib import Path

from pypdf import PdfWriter

from db import SessionLocal
from models import Candidate, Department, JobDescription, Tenant, User
from subscription_models import TenantSubscription


TENANT_SLUG = "playwright"
USER_EMAIL = "playwright@example.com"
USER_PASSWORD = "PlaywrightPass123!"


def _resume_path() -> str:
    target = Path(__file__).resolve().parents[1] / "instance" / "playwright-resume.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with target.open("wb") as handle:
        writer.write(handle)
    return str(target)


def main() -> None:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter_by(slug=TENANT_SLUG).first()
        if tenant is None:
            tenant = Tenant(slug=TENANT_SLUG, display_name="Playwright Audit")
            db.add(tenant)
            db.flush()

        user = db.query(User).filter_by(username=USER_EMAIL).first()
        if user is None:
            user = User(username=USER_EMAIL, tenant_id=tenant.id, role="admin")
            db.add(user)
        user.tenant_id = tenant.id
        user.role = "admin"
        user.full_name = "Playwright Recruiter"
        user.set_pw(USER_PASSWORD)

        department = db.query(Department).filter_by(tenant_id=tenant.id, name="Engineering").first()
        if department is None:
            db.add(Department(tenant_id=tenant.id, name="Engineering", color="#085CFF"))

        job = db.query(JobDescription).filter_by(tenant_id=tenant.id, code="PW-1").first()
        if job is None:
            job = JobDescription(code="PW-1", tenant_id=tenant.id)
            db.add(job)
        job.title = "Senior Test Engineer"
        job.department = "Engineering"
        job.html = "<p>Build reliable product tests.</p>"
        job.markdown = "Build reliable product tests."
        job.status = "open"

        candidate = db.query(Candidate).filter_by(id="playwright-candidate").first()
        if candidate is None:
            candidate = Candidate(id="playwright-candidate")
            db.add(candidate)
        candidate.name = "Ada Playwright"
        candidate.email = "ada.playwright@example.com"
        candidate.phone = "555-0100"
        candidate.resume_url = _resume_path()
        candidate.resume_json = {
            "name": "Ada Playwright",
            "summary": "Test engineer focused on reliable systems.",
            "skills": ["Python", "Playwright", "Accessibility"],
            "education": [{"institution": "Example University", "degree": "BS Computer Science"}],
            "experience": [{"title": "Test Engineer", "company": "Example Labs"}],
        }
        candidate.fit_score = 90
        candidate.realism = True
        candidate.questions = ["How do you diagnose a flaky test?"]
        candidate.answers = ["I reproduce, isolate shared state, and add deterministic instrumentation."]
        candidate.answer_scores = [4.5]
        candidate.jd_code = "PW-1"
        candidate.tenant_id = tenant.id
        candidate.status = "finalist"

        subscription = db.query(TenantSubscription).filter_by(tenant_id=tenant.id).first()
        if subscription is None:
            subscription = TenantSubscription(tenant_id=tenant.id)
            db.add(subscription)
        subscription.plan_tier = "ultra"
        subscription.billing_cycle = "monthly"
        subscription.status = "grandfathered"

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
