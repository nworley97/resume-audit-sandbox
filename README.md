# AlteraSF resume audit

The Flask application serves the recruiter experience, public application flow, mobile API, and the built analytics dashboard. The iOS client lives in `ios/` and is released separately through Xcode and TestFlight.

## Branch workflow

Keep exactly two long-lived branches:

- `Dev` (uppercase D on the remote) is the sandbox/test branch. The local checkout may be named `dev` on Windows.
- `main` is the production branch.

Promote a tested `Dev` commit to `main` through a pull request. Preserve remote `Dev` after merging; the sandbox service watches that branch. Do not create a separate remote lowercase `dev` branch.

Sandbox and production must use separate databases, Stripe modes/webhooks, storage prefixes or buckets, and session secrets. Test data must never share the production database.

## Local setup

Prerequisites: Python 3.11+, Node.js 22.12+ or 24+, npm, and a local SQLite database or PostgreSQL URL.

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

## Website account settings

The website Settings page saves profile details and per-user preferences through `/api/settings`. Migration `0005_user_settings` adds the preference/address table; `0006_checkout_fulfillment` adds payment receipts. In Render, set **Pre-Deploy Command** to `python -m alembic upgrade head`; its dashboard Start Command overrides the repository Procfile, so the Procfile alone does not guarantee migrations run. Verify the deployed database reaches the migration head before checking the authenticated dashboard and billing. Email and password changes require the current password. Password changes invalidate other sessions and outstanding reset links.

Email choices are saved, but delivery is inactive and clearly labeled until email jobs are implemented. Site alerts use the existing tenant notification API. Optional sound and desktop notifications require browser support; desktop notifications work while the dashboard is open, with browser permission, and do not provide background push delivery. Light/Dark choices persist per account; System is not offered.

For isolated manual testing, run `python scripts/preview_settings.py` and open `http://127.0.0.1:5063`. The script prints synthetic sign-in credentials and creates a temporary local database. Run the regression suite with `python -m unittest discover -s tests -p "test_*.py"`.

Run the website notification race regression with `node --test tests/web-settings-notifications.test.cjs`.

## Pricing, team management, and AI

Settings, public pricing, and signup read `plans_config.py`, including all four tiers, limits, features, and annual totals. Admins can add users from the Team members section of Settings. Creation enforces seats and tenant permissions, and returns a generated password to share securely; it does not send an email invitation. Mobile uses the same creation service.

AI screening requires `OPENAI_API_KEY`. `OPENAI_MODEL` defaults to `gpt-6-luna`; `OPENAI_REASONING_EFFORT` defaults to `low`. This cheaper model handles extraction, questions, and scoring; there is no automatic Astra fallback. If Render already sets `OPENAI_MODEL`, change it explicitly to `gpt-6-luna` because environment overrides take precedence. An explicit model override also allows rollback. Do not set `TEST_MODE=true` in production: it enables synthetic AI results and mock payments when their real services are unavailable. Run `python scripts/evaluate_ai_upgrade.py --model gpt-6-luna` with a development API key for a small, billable evaluation using fictional resumes before production rollout. See [the November stack review](docs/stack-review-2026-11-09.md) for the remaining billing, AI validation, storage, and deployment findings.

Paid signup and account upgrades/seats open Stripe Checkout sessions using the configured product/price lookup keys. Web and mobile purchases attach to the account's saved Stripe customer. Configure `STRIPE_SECRET_KEY` and a signing secret; enable `checkout.session.completed` and `checkout.session.async_payment_succeeded` on the webhook endpoint. Fulfillment retrieves the checkout and subscription from Stripe, validates payment and product, and commits a unique receipt with access changes. Failed processing returns HTTP 500 for retry. `customer.created` never creates a paid account. Legacy already-open Payment Links still use verified checkout email for new signups; new signups bind the exact pending account details. Missing payment configuration disables paid actions outside explicit test mode.

## Mobile app

Open `ios/AlteraSF.xcodeproj` on a Mac. Debug builds default to the local API; a physical phone needs the Mac's LAN address or the HTTPS sandbox URL. Release builds target production. See [ios/README.md](ios/README.md) for signing, local-network, and TestFlight steps.

## Browser mobile demo

The Render sandbox exposes a synthetic-data mobile product walkthrough at:

`/mobile-demo/preview-798d342bc7cf47bb72d54e8ac0a46f93202e75050dd84abd`

The fallback slug is enabled only when Render reports that the deployed branch is `dev`/`Dev` (and in tests). Set `MOBILE_DEMO_SLUG` on the sandbox service to rotate the unlisted link. Production keeps the route disabled unless that environment variable is intentionally configured. The preview never reads tenant or candidate data from the database.
