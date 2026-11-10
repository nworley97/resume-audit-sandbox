# Site, app, billing, and AI review — November 9, 2026

## Release assessment

The reported Settings pricing mismatch and missing Add User workflow are fixed in this change. Follow-up work repairs paid checkout verification and replay handling and selects a cheaper AI model. Remaining billing lifecycle and operational issues are listed below. Passing the local tests is not a production sign-off: live Stripe transactions, live AI model access/quality, production storage configuration, and an Xcode build were not available in this Windows workspace.

The working baseline includes remote main `1481d07`, including the later profile/notification and migration fixes. Remote Dev had remained at `c279639`; those main changes were fast-forwarded into the local development baseline before making these fixes.

## Stack and ownership

| Layer | Implementation | Review focus |
|---|---|---|
| Public site and recruiter UI | Flask/Jinja, Tailwind, vanilla JS; `app.py`, `templates/`, `static/` | Pricing, settings, resume delivery, authorization, browser behavior |
| Analytics | React 18, Vite 7, TypeScript, TanStack, Zustand, Nivo/Recharts | Build, types, lint, dependencies, embedded analytics regression |
| Mobile | SwiftUI native app; `ios_api.py` under `/api/mobile` | Team creation, role guards, session/password lifecycle, API contracts |
| Browser mobile preview | Separate fictional-data JS experience | All design states and primary navigation; this is not a native simulator |
| Persistence | SQLAlchemy, Alembic, PostgreSQL in deployment; SQLite in local tests | Migration compatibility, tenant scoping, transactional seat checks |
| Billing | Stripe links/webhooks, subscription/usage models, shared plan configuration | Catalog consistency, paid provisioning, seat purchasing and limits |
| AI | OpenAI Chat Completions; extraction, relevance, realism, interview questions, answer grading | Model parameters, missing-key behavior, output failures, quality/latency gates |
| Deployment | Render/Gunicorn; Codemagic macOS workflow for native builds | Branch drift, request timeouts, reproducibility, storage persistence |

## Completed corrections

- Settings now renders Free, Starter, Pro, and Ultra from `plans_config.py`. Public pricing uses the same catalog; mobile billing and billing pages already receive that catalog. Starter is $49/month with 3 active jobs; Pro is $129 with 10; Ultra is $239 with 20. Public annual equivalents use exact annual totals rather than rounded monthly approximations. Grandfathered accounts retain their existing access.
- Settings no longer claims every account has no card: it displays saved masked card details when available, otherwise links to billing details.
- Admins can add a teammate from Settings, choose a role, see the saved member, and receive a generated password once. No invitation email is claimed or sent. The web endpoint requires a session, CSRF token, admin role, tenant access, validated input, and available seats.
- Web and native creation share `team_service.py`. Seat checks and inserts lock the tenant row on PostgreSQL; emails are normalized and checked case-insensitively. Passwords are hashed at rest; creation responses use `Cache-Control: no-store`.
- Mobile errors now surface in the add-member sheet. Password display waits until the sheet is dismissed. The wording correctly says Add User, rather than implying email delivery.
- Mobile team role changes cannot remove the last admin. Password changes refresh the current session while invalidating old sessions/reset tokens.
- The browser preview now focuses clicked controls explicitly, fixing Safari sheet cancellation/selection focus restoration.
- AI configuration now supports `OPENAI_MODEL` (default `gpt-6-luna`) and `OPENAI_REASONING_EFFORT` (default `low`). Reasoning requests omit unsupported sampling parameters, cap completion output at 8,192 tokens, and reject refused, empty, or truncated replies. Explicit timeouts are not extended by hidden SDK retries. An API outage during initial application screening produces a retry message.
- New applications record the model identifier in resume metadata; existing candidate data is not rescored. Missing AI credentials no longer fabricate candidate data or scores outside explicit `TEST_MODE`. Compatible dependency updates clear the root audit and analytics production-dependency audit findings.

## PR review follow-up

All five posted findings have code corrections and local verification:

- Persist checkout requests before the provider call, serialize creation per account/signup, and reuse the open session and stable idempotency key after retries. Completed-but-unfulfilled sessions block another checkout. Duplicate paid base subscriptions are canceled while preserving the established subscription; the initial payment is flagged `refund_review` for manual review, not automatically refunded. Additive migration `0007_checkout_attempt` stores these requests.
- Store immutable signup snapshots per checkout, including only the password hash. Identical form resubmissions retain the hash and reuse checkout; subsequent form changes cannot invalidate payment against the earlier snapshot.
- Limit grading context to resume evidence sections, excluding self-identification and internal metadata before normalization. Legacy experience aliases and full experience text remain available. This does not assert that applicant-written free text contains no demographic information.
- Propagate subscription, payment-method, and payment-history database failures so webhooks return HTTP 500. A signed cancellation failure followed by a successful retry is tested.
- Block Cancel/swipe dismissal during native user creation, set the busy state before launching the request, and observe password completion independently of sheet dismissal. Swift source checks pass; native behavior still needs macOS validation.

Regression tests include repeated signup and account-upgrade requests, expired checkouts, an ambiguous provider response, database uniqueness, duplicate cancellation followed by database failure, and original signup credentials surviving later edits. PostgreSQL concurrency and live Stripe behavior remain external validation gates.

## Open findings, ordered by priority

| Priority | Finding and evidence | Impact and next action |
|---|---|---|
| Resolved locally | Paid provisioning previously granted access on customer creation or before verified payment. | `billing_fulfillment.py` now retrieves Checkout/subscription state, checks payment/product/customer, derives the purchased tier, and commits a receipt atomically. New signup sessions bind immutable form details; web/mobile upgrades bind the account customer. Signed delayed-payment, unpaid, wrong-product, provider-failure, and replay tests pass. Stripe test-account verification remains required. |
| Partially resolved | Extra-seat checkout deliveries previously incremented repeatedly. | A checkout primary key and locked subscription update now prevent replayed grants; rollback is tested. Existing recurring add-on quantity/cancellation reconciliation is still incomplete and must be verified/repaired before production billing promotion. Legacy seat purchases have no receipt history to backfill automatically. |
| Resolved locally | Payment services previously silently chose mock mode without credentials. | Mock payments require explicit `TEST_MODE`; production paid mutations fail closed. Portal creation also refuses a synthetic success outside tests. Confirm `TEST_MODE` is false/absent on both hosted services. |
| P1 | Live Luna quality and scoring semantics remain unvalidated. | Removed the 1,500-character resume truncation and included the missing job description in question generation. Added untrusted-input/job-evidence instructions, but prompts are not a demonstrated injection defense. `realism_check` is still a plausibility flag, not verified truth. Run a de-identified, human-reviewed calibration set, injection cases, and demographic-irrelevance checks before production promotion. |
| P1 | Scoring is synchronous in the upload request (`app.py:apply` invokes extraction, relevance, realism, and questions sequentially; `Procfile` has a 180-second worker timeout). | Four bounded AI calls can still exceed a worker timeout and occupy all workers under load. Measure model p95 latency, then use a durable job queue with pending/failed states and retries before scaling. |
| Resolved locally | Analytics development dependencies had 14 advisory entries, including 2 critical. | Upgraded Vitest/UI/coverage together to 5.1.0 and Node types to 24. A narrowly scoped minimatch 11.0.1 override clears the remaining typescript-eslint glob advisory; lint, types, tests, and build pass. Both full npm audits now report zero findings. Node 22.12+ or 24+ is required. |
| P2 | Resume storage returns the temporary local path when neither S3 nor `PERSIST_DIR` is configured (`s3util.py:upload_pdf`). | Redeploys can lose originals while candidate records remain, causing preview/download failures. Verify durable storage on both Render services and test an upload across a redeploy; a frontend fix cannot recover deleted files. |
| P2 | Rate limiting is an in-memory dictionary (`authz.py:rate_limit`) with two Gunicorn workers. | Limits are per process and reset on restart; distributed enforcement is absent. Move counters to Redis or an equivalent shared store, with trusted proxy/IP handling and bounded cleanup. |
| Resolved locally | Signup duplicated catalog prices and inactive accounts retained extra-seat capacity. | Signup cards, limits, features, and modal now read the catalog. Canceled/past-due accounts receive free-tier seat capacity; stored extra-seat counts and user accounts are preserved. |
| P2 | Email notification preferences are stored but there is no delivery scheduler consuming them. Settings discloses this; mobile previews use fictional behavior. | Saving a toggle does not send daily/weekly emails. Implement delivery workers and unsubscribe/recipient tests, or continue to label unavailable delivery explicitly. |
| P2 | Native runtime assurance is missing here. The source validator checks Swift syntax and Xcode file inclusion, not type checking or iOS behavior. | Run `codemagic.yaml` on macOS, test session expiry/team creation/password changes/preview downloads on a simulator, and retain screenshots/build logs. Browser mobile tests cannot replace this. |
| P2 | Python runtime dependencies use broad lower bounds and no deployment lock; the audited resolution differs from locally installed versions. | A fresh deploy can select a new major SDK without matching local tests. Pin a supported Python version and generate/test a reproducible dependency lock. |

These are code-review findings unless a local reproduction or test is specified. No production customer records, accounts, charges, emails, or provider settings were changed during the review.

## Model upgrade validation and rollout

The default is GPT-6 Luna at low reasoning effort, following the request to use a cheaper model for questions and related workflows. The same model handles resume extraction and scoring; there is no automatic fallback to Astra. Existing environment overrides take precedence and must be updated on Render if set. The current official model page lists Chat Completions and structured output support and standard short-context prices of $0.10/input million tokens and $0.50/output million tokens. These token prices do not establish task cost, quality, or latency. [Official Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna).

Use `scripts/evaluate_ai_upgrade.py --model gpt-6-luna` in a credentialed development environment. It sends only three fictional resumes, checks separate roles/companies and absence of invented employment, and prints extraction plus elapsed time. It makes billable API calls; it does not read customer documents or mutate application records. Compare against the previous model. This smoke evaluation is not a statistically meaningful hiring-score evaluation.

Before production activation: verify the model is enabled for the account; ensure `TEST_MODE` is absent/false; compare extraction completeness, score calibration, refusals, p95 latency, and cost; exercise API outages; retain an explicit `OPENAI_MODEL` override for rollback. Keep existing stored candidate data/scores unchanged. The application has no live API key in this workspace, so transport tests use mocks and no claim of improved model accuracy is made.

## Verification record

- 87 Python tests pass, including pricing propagation from the catalog, real hashed-password member creation, tenant/role/CSRF guards, duplicate emails, seat limits through both APIs, last-admin protection, password session lifecycle, AI transport errors, grading metadata exclusion, verified checkout/replay/rollback, immutable signup snapshots, duplicate purchase reconciliation, webhook failure retries, mobile cancellation, and migrations through `0007_checkout_attempt`.
- Seven Node data/notification tests pass; two analytics store tests pass. Analytics lint, type checking, and production build pass.
- Root dependency audit: zero findings after compatible updates. Analytics `--omit=dev` audit: zero. Full analytics audit: zero after the tooling upgrade. `pip-audit -r requirements.txt`: no known findings in the resolved dependency set; this does not audit the deployed environment.
- All 40 browser tests pass after the Safari focus fix, covering public/settings/signup pricing and adding users, original PDF preview, AI resume rendering, recruiter/analytics routes, all mobile-preview states, focus, and mobile score aggregation in desktop Chromium/Firefox/WebKit and mobile Chrome/Safari.
- Swift parser/source-inclusion validation passes for the modified sources; all 44 Swift sources are included in the Xcode project. Xcode compilation and on-device tests remain unrun.

## Recommended next release sequence

1. Review and test the Settings/team corrections on Dev, including a paid account with an available seat and one at capacity. Retain Dev.
2. Validate the repaired checkout flow in a Stripe test account, including replays, new/free-account upgrades, delayed payments, add-on cancellation, and native cancellation. Native cancellation now contacts Stripe and both web/native preserve access until the paid period ends; failures leave local state unchanged. Complete recurring add-on lifecycle reconciliation. Confirm production storage and payment configuration without exposing secrets.
3. Run the credentialed AI evaluation and latency/cost check before promoting the new model to main.
4. Development tooling is upgraded; add CI gates for both branches, and require the macOS build. Promote only the validated release and check its deployed commit, public prices, authenticated settings, and original-file delivery.
