"""Opt-in, synthetic-only live extraction evaluation; requires OPENAI_API_KEY.

Run once for each model and compare JSON summaries. This makes billable API
requests; it never reads customer resumes or changes application records.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

CASES = [
    ("multiple_roles", """Taylor Example
Experience
Senior Engineer, Example Labs, 2023-Present. Led a migration for an internal API.
Engineer, Example Labs, 2021-2023. Built integration tests.
Intern, Sample Systems, June-August 2020. Documented a test harness.
Education: BS Computer Science, Example University, 2021.
Skills: Python, SQL.
""", 3, ["Example Labs", "Sample Systems"]),
    ("contract_and_undated", """Morgan Sample
Work Experience
Consultant (contract), Fictional Studio, 2022-2024. Built a customer dashboard.
Volunteer Developer, Example Charity. Maintained a scheduling tool. Dates not provided.
Projects: Offline Notes, an open-source notes app.
Skills: Swift, JavaScript. No certifications listed.
""", 2, ["Fictional Studio", "Example Charity"]),
    ("no_experience", """Alex Test
Education: Example College, Mathematics, 2026.
Skills: Excel and Python.
Projects: Class project comparing simulated weather data.
No employment history or internships.
""", 0, []),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-6-luna"))
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        parser.exit(2, "OPENAI_API_KEY is required; no live evaluation was run.\n")
    os.environ["OPENAI_MODEL"] = args.model
    os.environ["TEST_MODE"] = "false"
    # Never connect this evaluation to production records.
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import resume_json
    results = []
    for name, text, count, companies in CASES:
        started = time.monotonic()
        try:
            parsed = resume_json(text)
            experience = parsed.get("experience", [])
            serialized = json.dumps(experience).lower()
            passed = isinstance(experience, list) and len(experience) == count and all(
                company.lower() in serialized for company in companies)
            results.append({"case": name, "passed": passed,
                            "seconds": round(time.monotonic() - started, 2), "extraction": parsed})
        except Exception as exc:
            results.append({"case": name, "passed": False, "error_type": type(exc).__name__})
    print(json.dumps({"model": args.model, "results": results}, indent=2))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
