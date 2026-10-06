"""Disposable local Settings QA server. Never connects to production data.

Run with the project's Python environment. Login: settings@example.com / Demo-settings-123!
The database is unique for each run and is removed when the server exits.
"""
import os
import sys
import tempfile
from pathlib import Path


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    handle, filename = tempfile.mkstemp(prefix="altera-settings-", suffix=".db")
    os.close(handle)
    os.environ.update(DATABASE_URL="sqlite:///" + Path(filename).as_posix(),
                      TEST_MODE="true", OPENAI_API_KEY="", RESEND_API_KEY="",
                      STRIPE_SECRET_KEY="", SESSION_COOKIE_SECURE="false",
                      RESUME_APP_SECRET_KEY="local-settings-preview-only", TRUSTED_HOSTS="localhost,127.0.0.1")
    from app import app
    from db import Base, engine, SessionLocal
    from models import User, Tenant
    Base.metadata.create_all(engine)
    db = SessionLocal()
    tenant = Tenant(slug="settings-demo", display_name="Settings Demo")
    db.add(tenant)
    db.flush()
    user = User(username="settings@example.com", full_name="Demo Recruiter", tenant_id=tenant.id, role="admin")
    user.set_pw("Demo-settings-123!")
    db.add(user)
    db.commit()
    db.close()
    print("Local QA sign-in: settings@example.com / Demo-settings-123!", flush=True)
    try:
        app.run(host="127.0.0.1", port=5063, debug=False, use_reloader=False)
    finally:
        SessionLocal.remove()
        engine.dispose()
        Path(filename).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
