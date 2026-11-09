"""Pricing, tenant membership, and AI transport regression contracts."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TEST_MODE"] = "true"
os.environ["OPENAI_API_KEY"] = ""
os.environ["SESSION_COOKIE_SECURE"] = "false"

import app as module
from db import Base, SessionLocal, engine
from models import Tenant, User
from subscription_models import TenantSubscription
from plans_config import get_all_plans_for_display


class PricingTeamTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(engine)
        db = SessionLocal()
        tenant = Tenant(slug="team-test", display_name="Team test")
        other = Tenant(slug="other-team", display_name="Other team")
        db.add_all([tenant, other]); db.flush()
        self.tenant_id = tenant.id
        user = User(username="admin@example.com", tenant_id=tenant.id, role="admin")
        user.set_pw("Password-test-123")
        db.add(user)
        db.add(TenantSubscription(tenant_id=tenant.id, plan_tier="pro", status="active", extra_seats=0))
        db.commit()
        self.user_id = user.id
        self.client = module.app.test_client()
        with module.app.app_context():
            login_id = user.get_id()
        with self.client.session_transaction() as session:
            session["_user_id"] = login_id
            session["_fresh"] = True
            session["tenant_slug"] = tenant.slug
        db.close()
        token = self.client.get("/api/settings").json["csrf_token"]
        self.headers = {"X-CSRF-Token": token}

    def tearDown(self):
        SessionLocal.remove()
        Base.metadata.drop_all(engine)
        engine.dispose()

    def add_member(self, email="new@example.com", path="/api/settings/team-test/team", **data):
        return self.client.post(path, json={"name": "New Person", "email": email, "role": "viewer", **data}, headers=self.headers)

    def test_public_settings_mobile_share_all_four_plans(self):
        public = self.client.get("/pricing").get_data(as_text=True)
        settings = self.client.get("/team-test/settings").get_data(as_text=True)
        mobile = self.client.get("/api/mobile/team-test/billing").json
        for plan in get_all_plans_for_display():
            for html in (public, settings):
                self.assertIn(f'data-plan-tier="{plan["tier"]}"', html)
                self.assertIn(f'${plan["monthly_price"]}', html)
            self.assertIn(plan, mobile["plans"])
        self.assertNotIn("$149", settings)
        self.assertNotIn("Unlimited jobs", settings)

    def test_pricing_tracks_catalog_changes(self):
        from plans_config import PLAN_PRICING, PLAN_LIMITS
        with patch.dict(PLAN_PRICING["pro"], monthly_price=137), patch.dict(PLAN_LIMITS["pro"], active_jobs=11):
            for path in ("/pricing", "/team-test/settings", "/billing/signup"):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn("$137", html)
                self.assertIn("11 active jobs", html)

    def test_create_user_returns_working_password_without_email_claim(self):
        response = self.add_member(email="NEW@EXAMPLE.COM")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        db = SessionLocal()
        user = db.get(User, response.json["id"])
        self.assertEqual(user.username, "new@example.com")
        self.assertEqual(user.tenant_id, self.tenant_id)
        self.assertTrue(user.check_pw(response.json["temp_password"]))
        self.assertNotEqual(user.pw_hash, response.json["temp_password"])
        db.close()
        html = self.client.get("/team-test/settings").get_data(as_text=True)
        self.assertIn("New Person", html)
        self.assertNotIn(response.json["temp_password"], html)

    def test_requires_csrf(self):
        self.assertEqual(self.client.post("/api/settings/team-test/team", json={}).status_code, 403)

    def test_rejects_cross_tenant(self):
        self.assertEqual(self.add_member(path="/api/settings/other-team/team").status_code, 403)

    def test_viewer_cannot_add_users_or_view_team_controls(self):
        db = SessionLocal(); db.get(User, self.user_id).role = "viewer"; db.commit(); db.close()
        self.assertEqual(self.add_member().status_code, 403)
        self.assertNotIn('id="team-form"', self.client.get("/team-test/settings").get_data(as_text=True))
        self.assertEqual(self.add_member(path="/api/mobile/team-test/team/invite").status_code, 403)

    def test_rejects_duplicate_email_case_insensitively(self):
        self.assertEqual(self.add_member(email="ADMIN@EXAMPLE.COM").status_code, 409)

    def test_enforces_seats_for_web_and_mobile(self):
        self.assertEqual(self.add_member().status_code, 201)
        self.assertEqual(self.add_member(email="second@example.com", path="/api/mobile/team-test/team/invite").status_code, 201)
        for path in ("/api/settings/team-test/team", "/api/mobile/team-test/team/invite"):
            response = self.add_member(email="overflow@example.com", path=path)
            self.assertEqual(response.status_code, 409)
            self.assertIn("Seat limit", str(response.json))

    def test_rejects_malformed_input(self):
        for path in ("/api/settings/team-test/team", "/api/mobile/team-test/team/invite"):
            for data in (["invalid"], {"name": "Name", "email": "a@", "role": "viewer"}, {"name": "Name", "email": "a@b.com", "role": "super"}):
                self.assertEqual(self.client.post(path, json=data, headers=self.headers).status_code, 400)

    def test_last_admin_cannot_be_demoted(self):
        response = self.client.patch(f"/api/mobile/team-test/team/{self.user_id}", json={"role": "viewer"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("admin", response.json["description"])

    def test_mobile_password_change_refreshes_current_session(self):
        other_client = module.app.test_client()
        with self.client.session_transaction() as state:
            old_identity = state["_user_id"]
        with other_client.session_transaction() as state:
            state["_user_id"] = old_identity
            state["_fresh"] = True
        response = self.client.post("/api/mobile/auth/change-password", json={
            "current_password": "Password-test-123", "new_password": "New-password-456"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/mobile/auth/me").status_code, 200)
        self.assertNotEqual(other_client.get("/api/mobile/auth/me").status_code, 200)


class AITransportTests(unittest.TestCase):
    def test_questions_include_job_and_grading_keeps_late_experience(self):
        with patch.object(module, "chat", return_value='{"questions": []}') as chat:
            module.generate_questions({"skills": ["Python"]}, "Needs database optimization")
            self.assertIn("Needs database optimization", chat.call_args.args[1])
        resume = {"summary": "x" * 1600, "experience": [{"company": "Earlier role", "title": "Database engineer"}]}
        with patch.object(module, "chat", return_value='{"score": 4}') as chat:
            module.score_answers(resume, ["Describe your experience"], ["I maintained the database and improved its query performance significantly."])
            self.assertIn("Earlier role", chat.call_args.args[1])

    def reply(self, content='{"score": 4}', finish="stop", refusal=None):
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content, refusal=refusal))])

    def test_reasoning_model_uses_supported_parameters_and_json(self):
        client = Mock()
        client.chat.completions.create.return_value = self.reply()
        with patch.object(module, "client", client), patch.object(module, "MODEL", "gpt-6-luna"):
            self.assertEqual(module.chat("Return JSON", "sample", structured=True), '{"score": 4}')
        params = client.chat.completions.create.call_args.kwargs
        self.assertEqual(params["model"], "gpt-6-luna")
        self.assertNotIn("temperature", params)
        self.assertNotIn("top_p", params)
        self.assertEqual(params["reasoning_effort"], "low")
        self.assertEqual(params["response_format"], {"type": "json_object"})
        self.assertEqual(params["max_completion_tokens"], 8192)

    def test_legacy_override_retains_compatible_parameters(self):
        client = Mock(); client.chat.completions.create.return_value = self.reply()
        with patch.object(module, "client", client), patch.object(module, "MODEL", "gpt-4o"):
            module.chat("Return JSON", "sample", structured=True)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["temperature"], 0)
        self.assertNotIn("reasoning_effort", client.chat.completions.create.call_args.kwargs)

    def test_missing_key_never_fabricates_production_scores(self):
        with patch.object(module, "client", None), patch.dict(os.environ, {"TEST_MODE": "false"}):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                module.chat("Score resume", "sample", structured=True)

    def test_incomplete_refused_and_empty_output_are_errors(self):
        for response in (self.reply(finish="length"), self.reply(refusal="Cannot comply"), self.reply(content="")):
            client = Mock(); client.chat.completions.create.return_value = response
            with patch.object(module, "client", client):
                with self.assertRaises(RuntimeError):
                    module.chat("Return JSON", "sample", structured=True)
