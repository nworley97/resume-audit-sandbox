"""Mobile contract regressions; isolated SQLite data, never production."""
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OPENAI_API_KEY"] = ""
os.environ["TEST_MODE"] = "true"
os.environ["SESSION_COOKIE_SECURE"] = "false"

from app import app
from db import Base, SessionLocal, engine
from models import Candidate, JobDescription, Tenant, User


class MobileIterationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        tenant = Tenant(slug="mobile-iteration", display_name="Mobile test")
        other = Tenant(slug="mobile-other", display_name="Other")
        db.add_all([tenant, other])
        db.flush()
        user = User(username="mobile-test@example.com", pw_hash="unused", role="admin", tenant_id=tenant.id)
        db.add(user)
        db.flush()
        cls.user_id = user.id
        for owner, code, title, department in [
            (tenant, "ENGINEER", "Platform Engineer", "Engineering"),
            (tenant, "SALES", "Sales Associate", "Sales"),
            (other, "OTHER", "Platform Engineer", "Engineering"),
        ]:
            db.add(JobDescription(code=code, title=title, department=department, status="open", html="", tenant_id=owner.id))
        for index in range(57):
            db.add(Candidate(id=f"mobile-candidate-{index:03}", name=f"Person {index:03}",
                             email=f"person{index}@example.com", resume_url="", resume_json={},
                             questions=[], answers=[], answer_scores=[4.2], fit_score=90,
                             jd_code="ENGINEER" if index < 55 else "SALES", tenant_id=tenant.id))
        db.add(Candidate(id="mobile-private", name="Private person", resume_url="", resume_json={},
                         questions=[], answers=[], answer_scores=[], fit_score=99,
                         jd_code="OTHER", tenant_id=other.id))
        db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        SessionLocal.remove()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def client(self):
        client = app.test_client()
        with client.session_transaction() as state:
            with app.app_context():
                state["_user_id"] = SessionLocal().get(User, self.user_id).get_id()
            state["_fresh"] = True
            state["tenant_slug"] = "mobile-iteration"
        return client

    def test_candidate_pages_have_authoritative_group_counts_and_no_duplicates(self):
        client = self.client()
        first = client.get("/api/mobile/mobile-iteration/candidates").get_json()
        second = client.get("/api/mobile/mobile-iteration/candidates?page=2").get_json()
        self.assertEqual(first["total"], 57)
        self.assertEqual(first["job_counts"], {"ENGINEER": 55, "SALES": 2})
        ids = [c["id"] for page in (first, second) for c in page["candidates"]]
        self.assertEqual(len(ids), 57)
        self.assertEqual(len(set(ids)), 57)
        self.assertNotIn("mobile-private", ids)

    def test_department_and_role_title_search_apply_before_pagination(self):
        client = self.client()
        filtered = client.get("/api/mobile/mobile-iteration/candidates?department=Sales").get_json()
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(filtered["job_counts"], {"SALES": 2})
        searched = client.get("/api/mobile/mobile-iteration/candidates?q=Platform%20Engineer").get_json()
        self.assertEqual(searched["total"], 55)
        self.assertEqual(searched["job_counts"], {"ENGINEER": 55})

    def test_schedule_round_trip_normalizes_offset_and_keeps_partial_updates(self):
        client = self.client()
        response = client.post("/api/mobile/mobile-iteration/jobs", json={
            "code": "SCHEDULE", "title": "Scheduled role",
            "start_date": "2026-10-01T09:30:00-04:00",
            "end_date": "2026-10-31T17:00:00-04:00",
        })
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["start_date"], "2026-10-01T13:30:00Z")
        changed = client.patch("/api/mobile/mobile-iteration/jobs/SCHEDULE", json={"title": "Updated title"})
        self.assertEqual(changed.get_json()["end_date"], "2026-10-31T21:00:00Z")
        read = client.get("/api/mobile/mobile-iteration/jobs/SCHEDULE").get_json()
        self.assertEqual(read["start_date"], response.get_json()["start_date"])
        invalid = client.patch("/api/mobile/mobile-iteration/jobs/SCHEDULE", json={
            "title": "Must not be saved", "end_date": "2026-09-01T10:00:00Z"})
        self.assertEqual(invalid.status_code, 400)
        unchanged = client.get("/api/mobile/mobile-iteration/jobs/SCHEDULE").get_json()
        self.assertEqual(unchanged["title"], "Updated title")
        self.assertEqual(unchanged["end_date"], read["end_date"])
        cleared = client.patch("/api/mobile/mobile-iteration/jobs/SCHEDULE", json={"end_date": None})
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.get_json()["end_date"])

    def test_invalid_schedule_is_rejected_without_creating_a_job(self):
        client = self.client()
        for index, fields in enumerate([
            {"start_date": "not a date"},
            {"start_date": "2026-10-01T09:00:00"},
            {"start_date": "2026-10-02T09:00:00Z", "end_date": "2026-10-01T09:00:00Z"},
        ]):
            code = f"INVALID-{index}"
            result = client.post("/api/mobile/mobile-iteration/jobs", json={"code": code, "title": "Invalid", **fields})
            self.assertEqual(result.status_code, 400)
            self.assertEqual(client.get(f"/api/mobile/mobile-iteration/jobs/{code}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
