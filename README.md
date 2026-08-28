# AlteraSF resume audit

The Flask application serves the recruiter experience, public application flow, mobile API, and the built analytics dashboard. The iOS client lives in `ios/` and is released separately through Xcode and TestFlight.

## Branch workflow

Keep exactly two long-lived branches:

- `dev` is the sandbox/test branch.
- `main` is the production branch.

Create short-lived feature branches from `dev`, merge them back after review, and delete them after the merge. Promote a tested `dev` commit to `main` through a pull request. Before removing the legacy remote `Dev` branch, change the Render sandbox service to watch lowercase `dev` and confirm a successful sandbox deployment.

Sandbox and production must use separate databases, Stripe modes/webhooks, storage prefixes or buckets, and session secrets. Test data must never share the production database.

## Local setup

Prerequisites: Python 3.11+, Node.js 18+, npm, and a local SQLite database or PostgreSQL URL.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
npm ci
npm run build
python -m alembic upgrade head
```

Set at minimum:

```text
RESUME_APP_SECRET_KEY=<random development secret>
SESSION_COOKIE_SECURE=false
DATABASE_URL=sqlite:///dev.db
PUBLIC_APP_URL=http://localhost:5050
```

Then run `python app.py`. The app is available at `http://localhost:5050`. The analytics dashboard is built into and served by Flask; a second analytics server is not required.

## Verification

```bash
python -m unittest discover -s tests -p "test_*.py"
npm --prefix analytics_ui/dashboard run typecheck
npm --prefix analytics_ui/dashboard run lint
npm --prefix analytics_ui/dashboard test
npm run build
npx playwright test
```

The end-to-end suite uses its own `.playwright.sqlite` database. Never point it at a shared or production database.

## Mobile app

Open `ios/AlteraSF.xcodeproj` on a Mac. Debug builds default to the local API; a physical phone needs the Mac's LAN address or the HTTPS sandbox URL. Release builds target production. See [ios/README.md](ios/README.md) for signing, local-network, and TestFlight steps.

## Browser mobile demo

The Render sandbox exposes a synthetic-data mobile product walkthrough at:

`/mobile-demo/preview-61d7c4a9f2e8`

The fallback slug is enabled only when Render reports that the deployed branch is `dev`/`Dev` (and in tests). Set `MOBILE_DEMO_SLUG` on the sandbox service to rotate the unlisted link. Production keeps the route disabled unless that environment variable is intentionally configured. The preview never reads tenant or candidate data from the database.
