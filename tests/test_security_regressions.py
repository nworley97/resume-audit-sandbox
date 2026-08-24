import os
import tempfile
import unittest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OPENAI_API_KEY"] = ""
os.environ["TEST_MODE"] = "true"
os.environ["SESSION_COOKIE_SECURE"] = "false"

from app import app  # noqa: E402
from analytics_service import _relevancy_score  # noqa: E402
from db import Base, SessionLocal, engine  # noqa: E402
from models import Candidate, JobDescription, Tenant, User  # noqa: E402


class SecurityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        handle, cls.resume_path = tempfile.mkstemp(suffix=".pdf")
        os.write(handle, b"%PDF-1.4\n%%EOF\n")
        os.close(handle)

        db = SessionLocal()
        alpha = Tenant(slug="security-alpha", display_name="Security Alpha")
        beta = Tenant(slug="security-beta", display_name="Security Beta")
        db.add_all([alpha, beta])
        db.flush()

        alpha_admin = User(
            username="security-admin@example.com",
            pw_hash="unused",
            tenant_id=alpha.id,
            role="admin",
        )
        alpha_viewer = User(
            username="security-viewer@example.com",
            pw_hash="unused",
            tenant_id=alpha.id,
            role="viewer",
        )
        beta_admin = User(
            username="security-beta@example.com",
            pw_hash="unused",
            tenant_id=beta.id,
            role="admin",
        )
        db.add_all([alpha_admin, alpha_viewer, beta_admin])
        db.flush()

        db.add_all([
            JobDescription(
                code="OPEN-1",
                title="Open Role",
                html="<p>Open</p>",
                status="open",
                tenant_id=alpha.id,
            ),
            JobDescription(
                code="DRAFT-1",
                title="Draft Role",
                html="<p>Draft</p>",
                status="draft",
                tenant_id=alpha.id,
            ),
            JobDescription(
                code="BETA-1",
                title="Beta Role",
                html="<p>Beta</p>",
                status="open",
                tenant_id=beta.id,
            ),
            Candidate(
                id="security-beta-candidate",
                name="Beta Candidate",
                email="candidate@example.com",
                resume_url=cls.resume_path,
                resume_json={},
                fit_score=90,
                questions=[],
                answers=[],
                answer_scores=[4.5],
                jd_code="BETA-1",
                tenant_id=beta.id,
            ),
        ])
        db.commit()
        cls.alpha_admin_id = alpha_admin.id
        cls.alpha_viewer_id = alpha_viewer.id
        db.close()

    @classmethod
    def tearDownClass(cls):
        SessionLocal.remove()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(cls.resume_path):
            os.unlink(cls.resume_path)

    @staticmethod
    def authenticated_client(user_id, tenant_slug="security-alpha"):
        client = app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["_user_id"] = str(user_id)
            flask_session["_fresh"] = True
            flask_session["tenant_slug"] = tenant_slug
        return client

    def test_analytics_requires_login(self):
        response = app.test_client().get("/analytics/summary?tenant=security-beta")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_cross_tenant_candidate_and_metadata_access_is_forbidden(self):
        client = self.authenticated_client(self.alpha_admin_id)
        self.assertEqual(
            client.get("/security-beta/recruiter/candidate/security-beta-candidate").status_code,
            403,
        )
        self.assertEqual(client.get("/api/tenants/security-beta/metadata").status_code, 403)
        self.assertEqual(
            client.post(
                "/security-beta/recruiter/candidate/security-beta-candidate/set-status",
                data={"status": "archived"},
            ).status_code,
            403,
        )

    def test_public_job_board_remains_public_when_signed_in_elsewhere(self):
        client = self.authenticated_client(self.alpha_admin_id)
        self.assertEqual(client.get("/security-beta/jobs").status_code, 200)

    def test_viewer_cannot_create_jobs_or_change_billing(self):
        client = self.authenticated_client(self.alpha_viewer_id)
        self.assertEqual(
            client.post(
                "/api/mobile/security-alpha/jobs",
                json={"code": "NOPE", "title": "Forbidden"},
            ).status_code,
            403,
        )
        self.assertEqual(client.get("/billing/account").status_code, 403)
        self.assertEqual(client.get("/api/mobile/security-alpha/team").status_code, 403)

    def test_public_billing_status_cannot_log_in_by_email(self):
        client = app.test_client()
        response = client.get(
            "/billing/api/check-account-status?email=security-admin@example.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["account_created"])
        with client.session_transaction() as flask_session:
            self.assertNotIn("_user_id", flask_session)

    def test_session_identity_does_not_lazy_load_detached_tenant(self):
        response = self.authenticated_client(self.alpha_admin_id).get("/api/session/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tenant_slug"], "security-alpha")

    def test_invalid_pagination_and_status_are_rejected(self):
        client = self.authenticated_client(self.alpha_admin_id)
        self.assertEqual(
            client.get("/api/mobile/security-alpha/candidates?page=abc").status_code,
            400,
        )
        self.assertEqual(
            client.get("/api/mobile/security-alpha/candidates?per_page=0").status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/security-alpha/recruiter/candidate/missing/set-status",
                data={"status": "invalid"},
            ).status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/api/mobile/security-alpha/jobs",
                json={"code": "BAD-COUNT", "title": "Bad", "question_count": "nope"},
            ).status_code,
            400,
        )
        self.assertEqual(
            client.post(
                "/api/mobile/security-alpha/jobs",
                json={"code": "BAD-STATUS", "title": "Bad", "status": "mystery"},
            ).status_code,
            400,
        )

    def test_draft_application_is_not_public_and_deletes_are_not_get(self):
        client = app.test_client()
        self.assertEqual(client.get("/security-alpha/apply/DRAFT-1").status_code, 404)
        self.assertEqual(client.get("/security-alpha/apply/OPEN-1").status_code, 200)
        authenticated = self.authenticated_client(self.alpha_admin_id)
        self.assertEqual(authenticated.get("/security-alpha/delete/anything").status_code, 405)
        self.assertEqual(authenticated.get("/security-alpha/delete-jd/OPEN-1").status_code, 405)

    def test_security_headers_are_present(self):
        response = app.test_client().get("/")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", response.headers["Content-Security-Policy"])

    def test_contact_form_rejects_non_text_and_oversized_input(self):
        client = app.test_client()
        self.assertEqual(client.post("/contact", json={"first_name": 123}).status_code, 400)
        payload = {
            "first_name": "A",
            "last_name": "B",
            "email": "a@example.com",
            "company_name": "Example",
            "country": "US",
            "role": "Recruiter",
            "company_size": "1-10",
            "hiring": "Yes",
            "subject": "Question",
            "message": "x" * 5001,
        }
        self.assertEqual(client.post("/contact", json=payload).status_code, 400)

    def test_legacy_relevancy_score_is_normalized_to_five_point_scale(self):
        db = SessionLocal()
        try:
            candidate = db.get(Candidate, "security-beta-candidate")
            self.assertEqual(_relevancy_score(candidate), 4.5)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
