import os
import tempfile
from types import SimpleNamespace
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("OPENAI_API_KEY", "")

from app import (  # noqa: E402
    app,
    _average_scores,
    _is_pdf_resume,
    _normalize_questions,
    _normalize_resume_for_view,
    _resume_filename,
    _score_from_model_reply,
)
from db import Base, SessionLocal, engine  # noqa: E402
from ios_api import _candidate_detail_dict  # noqa: E402
from models import Candidate, Tenant, User  # noqa: E402


class ScoreParsingTests(unittest.TestCase):
    def test_parses_structured_score(self):
        self.assertEqual(_score_from_model_reply('{"score": 4}'), 4)

    def test_does_not_grab_unrelated_digit(self):
        text = "The candidate has 12 years of experience, but no score was supplied."
        self.assertEqual(_score_from_model_reply(text, default=1), 1)

    def test_average_ignores_invalid_values(self):
        self.assertEqual(_average_scores([5, None, "4", 99]), 4.5)


class ResumeCompatibilityTests(unittest.TestCase):
    def test_pdf_detection_handles_s3_urls_and_query_strings(self):
        path = "s3://resume-bucket/candidates/Jane%20Doe.PDF?version=2"
        self.assertTrue(_is_pdf_resume(path))
        self.assertEqual(_resume_filename(path), "Jane%20Doe.PDF")

    def test_legacy_question_shapes_are_normalized(self):
        questions = [
            {"question": "Current shape"},
            '{"text": "Legacy JSON shape"}',
            "Plain string",
        ]
        self.assertEqual(
            _normalize_questions(questions),
            ["Current shape", "Legacy JSON shape", "Plain string"],
        )

    def test_resume_aliases_map_to_view_schema(self):
        normalized = _normalize_resume_for_view({
            "Full Name": "Ada Lovelace",
            "Professional Summary": "Computing pioneer",
            "Work History": [{"role": "Analyst"}],
            "Technical Skills": ["Mathematics"],
        })
        self.assertEqual(normalized["name"], "Ada Lovelace")
        self.assertEqual(normalized["summary"], "Computing pioneer")
        self.assertEqual(normalized["experience"][0]["role"], "Analyst")
        self.assertEqual(normalized["skills"], ["Mathematics"])

    def test_mobile_detail_uses_ai_aliases_and_recorded_qa_metadata(self):
        candidate = SimpleNamespace(
            id="abc123",
            name="Ada",
            email="ada@example.com",
            phone="",
            jd_code="job1",
            fit_score=5,
            answer_scores=[4],
            left_tab_count=0,
            status=None,
            created_at=None,
            resume_url="s3://bucket/ada.pdf",
            questions=['{"question": "Why this role?"}'],
            answers=["Because it fits my experience."],
            resume_json={
                "Work History": [{"role": "Analyst", "company": "Babbage"}],
                "Technical Skills": ["Mathematics"],
                "_q_times": {"0": 12500},
                "_paste_flags": {"0": 1},
            },
        )
        tenant = SimpleNamespace(slug="altera")
        detail = _candidate_detail_dict(candidate, None, tenant)
        self.assertIn("Analyst", detail["experience"])
        self.assertEqual(detail["skills"], ["Mathematics"])
        self.assertEqual(detail["resume_url"], "/api/mobile/altera/candidates/abc123/resume")
        self.assertEqual(detail["qa_responses"][0]["duration_seconds"], 12.5)
        self.assertTrue(detail["qa_responses"][0]["has_pasted_content"])


class ResumeEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        handle, cls.resume_path = tempfile.mkstemp(suffix=".PDF")
        os.write(handle, b"%PDF-1.4\n%%EOF\n")
        os.close(handle)

        db = SessionLocal()
        cls.tenant = Tenant(slug="test-tenant", display_name="Test Tenant")
        db.add(cls.tenant)
        db.flush()
        cls.user = User(
            username="viewer@example.com",
            pw_hash="unused",
            tenant_id=cls.tenant.id,
            role="admin",
        )
        db.add(cls.user)
        db.flush()
        cls.candidate = Candidate(
            id="pdf-test",
            name="PDF Candidate",
            resume_url=cls.resume_path,
            resume_json={},
            fit_score=4,
            questions=[],
            answers=[],
            answer_scores=[],
            tenant_id=cls.tenant.id,
        )
        db.add(cls.candidate)
        db.commit()
        cls.user_id = cls.user.id
        db.close()

    @classmethod
    def tearDownClass(cls):
        SessionLocal.remove()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(cls.resume_path):
            os.unlink(cls.resume_path)

    def test_inline_pdf_has_pdf_content_type_and_inline_disposition(self):
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True
            session["tenant_slug"] = "test-tenant"
        response = client.get("/test-tenant/resume/pdf-test?inline=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("inline", response.headers.get("Content-Disposition", ""))
        response.close()


if __name__ == "__main__":
    unittest.main()
