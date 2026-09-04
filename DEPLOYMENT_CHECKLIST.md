# Deployment checklist

Use this checklist separately for sandbox (`dev`) and production (`main`). Do not push or deploy until the automated checks and a human smoke test pass.

## Environment isolation

- [ ] Sandbox follows lowercase `dev`; production follows `main`.
- [ ] Sandbox and production have separate `DATABASE_URL` values.
- [ ] Stripe test keys/webhooks are used only in sandbox; live keys/webhooks only in production.
- [ ] Resume storage uses separate buckets or prefixes per environment.
- [ ] Each environment has a distinct random `RESUME_APP_SECRET_KEY`.
- [ ] Backups and restore procedures have been tested before migrations.

## Required configuration

- [ ] `RESUME_APP_SECRET_KEY` is a strong random value.
- [ ] `DATABASE_URL` points to the correct environment database.
- [ ] `PUBLIC_APP_URL` is the canonical HTTPS origin, with no trailing slash.
- [ ] `TRUSTED_HOSTS` contains only the deployed hostnames.
- [ ] `SESSION_COOKIE_SECURE=true`.
- [ ] `TRUST_PROXY_HEADERS=true` only behind the trusted single-hop hosting proxy; otherwise leave it unset.
- [ ] `OPENAI_API_KEY` is present if AI scoring is enabled.
- [ ] `RESEND_API_KEY` is present if email and password resets are enabled.
- [ ] `GOOGLE_IOS_CLIENT_ID` matches the iOS bundle identifier if Google sign-in is enabled.
- [ ] `SUPERADMIN_USER` and `SUPERADMIN_PASSWORD` are either both set securely or both omitted.
- [ ] `ANALYTICS_CORS_ORIGINS` is empty for the same-origin dashboard; otherwise it lists only explicitly trusted HTTPS origins.

If billing is enabled, also verify `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, and the environment-specific webhook secret. If S3 storage is enabled, verify its bucket, region, and credentials.

## Build and migration gate

- [ ] Python regression tests pass.
- [ ] Dashboard type checking, linting, and unit tests pass.
- [ ] `npm run build` completes and the generated dashboard assets are committed.
- [ ] Playwright passes on desktop Chrome, desktop Safari/WebKit, mobile Chrome, and mobile Safari/WebKit.
- [ ] `python -m alembic upgrade head` succeeds against a restored copy of the target database.
- [ ] Dependency security scanning has no unresolved high/critical production findings.

## Sandbox smoke test

- [ ] Admin, manager, and viewer accounts see only their permitted controls.
- [ ] A user cannot open or mutate another tenant's jobs, candidates, analytics, team, or billing data.
- [ ] A published job accepts a PDF and DOCX application; a draft or closed job does not.
- [ ] Resume preview/download, AI relevancy, Q&A scoring, finalist notes, archive, and CSV exports work.
- [ ] The 0–100 legacy relevancy score renders on the current 0–5 scale.
- [ ] Invalid status and pagination inputs return a helpful 400 response rather than a server error.
- [ ] Password-reset and billing return links use `PUBLIC_APP_URL`.
- [ ] Landing, recruiter, candidate, and analytics screens do not overflow at phone, tablet, and desktop widths.
- [ ] The iOS Debug build can log in and exercise read/write permissions against sandbox.

## Production release

1. Back up production and record the current release commit.
2. Merge the verified `dev` commit to `main` through review.
3. Watch migration, startup, error-rate, email, storage, AI, and Stripe webhook logs.
4. Repeat the read-only smoke test, then one controlled application and billing test.
5. Roll back the application commit if health checks fail; restore data only through the documented database recovery process.

The iOS binary is deployed separately. Archive a Release build in Xcode, validate it, upload to App Store Connect, and test it with an internal TestFlight group before broader distribution.
