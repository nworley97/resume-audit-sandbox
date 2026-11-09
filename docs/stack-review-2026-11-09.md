# Site, app, billing, and AI review — November 9, 2026

## Release assessment

The reported Settings pricing mismatch and missing Add User workflow are fixed in this change. The review also found billing and operational issues that remain open. Passing the local tests is not a production sign-off: live Stripe transactions, live AI model access/quality, production storage configuration, and an Xcode build were not available in this Windows workspace.

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
- AI configuration now supports `OPENAI_MODEL` (default `gpt-6-astra`) and `OPENAI_REASONING_EFFORT` (default `low`). Reasoning requests omit unsupported sampling parameters, cap completion output at 8,192 tokens, and reject refused, empty, or truncated replies. Explicit timeouts are not extended by hidden SDK retries. An API outage during initial application screening produces a retry message.
- New applications record the model identifier in resume metadata; existing candidate data is not rescored. Missing AI credentials no longer fabricate candidate data or scores outside explicit `TEST_MODE`. Compatible dependency updates clear the root audit and analytics production-dependency audit findings.

## Open findings, ordered by priority

| Priority | Finding and evidence | Impact and next action |
|---|---|---|
| P1 | Paid provisioning can grant access before confirmed payment. `stripe_webhooks.py:handle_customer_created` calls `_maybe_create_account_from_pending_signup`; that function defaults status to `active`, tolerates an empty/failed subscription lookup, and trusts the pending form's tier. | Customer creation is not payment confirmation. Provision from a verified paid checkout/subscription, derive tier/cycle from Stripe price IDs, and fail closed on lookup failure. Add paid/unpaid, delayed-payment, wrong-price, and replay tests before the next billing release. |
| P1 | Extra-seat processing is not idempotent. `_maybe_add_extra_seat` increments seats and inserts `PaymentHistory` on every matching delivery; there is no processed-checkout check or unique event constraint. | Repeated webhook deliveries can grant duplicate seats, including sequential retries. Use a unique processed-event/checkout key and a locked subscription update in one transaction; reconcile later add-on quantity/cancellation events. |
| P1 | Payment services silently choose mock mode when credentials are absent or the Stripe import fails (`stripe_service.py:USE_REAL_STRIPE`, `PaymentService.is_mock_mode`). | This is a production configuration hazard, not evidence that production currently uses mock payments. Require an explicit test-only flag and refuse paid mutations if production payment setup is incomplete. |
| P1 | AI quality is not yet validated for the new model. `score_answers` truncates the entire resume JSON to 1,500 characters; `realism_check` turns a yes/no answer into an authenticity flag. | Later experience can be excluded from grading; model plausibility is not verified truth. Build a consented/de-identified evaluation set, preserve evidence per score, test prompt injection and demographic irrelevance, and retain human review. A model swap alone does not repair these semantics. |
| P1 | Scoring is synchronous in the upload request (`app.py:apply` invokes extraction, relevance, realism, and questions sequentially; `Procfile` has a 180-second worker timeout). | Four bounded AI calls can still exceed a worker timeout and occupy all workers under load. Measure model p95 latency, then use a durable job queue with pending/failed states and retries before scaling. |
| P1 | Analytics development dependencies retain 14 advisory entries: 2 critical (Vitest/Tinypool chain) and 12 moderate after compatible fixes. | Production-only audit is clean, but development/CI tooling is not. Upgrade Vitest, its UI/coverage packages, and related tooling together, run the test suite, and keep development servers isolated. Do not assume audit severity proves a deployed exploit. |
| P2 | Resume storage returns the temporary local path when neither S3 nor `PERSIST_DIR` is configured (`s3util.py:upload_pdf`). | Redeploys can lose originals while candidate records remain, causing preview/download failures. Verify durable storage on both Render services and test an upload across a redeploy; a frontend fix cannot recover deleted files. |
| P2 | Rate limiting is an in-memory dictionary (`authz.py:rate_limit`) with two Gunicorn workers. | Limits are per process and reset on restart; distributed enforcement is absent. Move counters to Redis or an equivalent shared store, with trusted proxy/IP handling and bounded cleanup. |
| P2 | Duplicate pricing remains in signup markup/JavaScript (`templates/billing/signup.html`). Extra seats are added to the effective free tier even for an inactive subscription (`TenantSubscription.get_total_seats`). | Future catalog changes can reintroduce drift; canceled add-ons may retain seat capacity. Convert signup to the catalog and define inactive-seat policy before changing entitlements for existing customers. |
| P2 | Email notification preferences are stored but there is no delivery scheduler consuming them. Settings discloses this; mobile previews use fictional behavior. | Saving a toggle does not send daily/weekly emails. Implement delivery workers and unsubscribe/recipient tests, or continue to label unavailable delivery explicitly. |
| P2 | Native runtime assurance is missing here. The source validator checks Swift syntax and Xcode file inclusion, not type checking or iOS behavior. | Run `codemagic.yaml` on macOS, test session expiry/team creation/password changes/preview downloads on a simulator, and retain screenshots/build logs. Browser mobile tests cannot replace this. |
| P2 | Python runtime dependencies use broad lower bounds and no deployment lock; the audited resolution differs from locally installed versions. | A fresh deploy can select a new major SDK without matching local tests. Pin a supported Python version and generate/test a reproducible dependency lock. |

These are code-review findings unless a local reproduction or test is specified. No production customer records, accounts, charges, emails, or provider settings were changed during the review.

## Model upgrade validation and rollout

Current official documentation resolves the flagship upgrade target to GPT-6 Astra and documents Chat Completions compatibility for text-only calls, `reasoning_effort`, and removal of sampling parameters during reasoning. The existing endpoint and JSON-object output contract are preserved. [Official migration guidance](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#migration-quickstart).

This is a quality-oriented target, not an established cost or latency improvement. The model catalog currently lists Astra at $10/input million tokens and $50/output million tokens. Lower-cost family options should be evaluated against the same acceptance set if Astra's cost or latency is unsuitable. Account access and live behavior were not verified. [Official model catalog](https://developers.openai.com/api/docs/models).

Use `scripts/evaluate_ai_upgrade.py --model gpt-6-astra` in a credentialed development environment. It sends only three fictional resumes, checks separate roles/companies and absence of invented employment, and prints extraction plus elapsed time. It makes billable API calls; it does not read customer documents or mutate application records. Run the same cases against the previous model for comparison. This smoke evaluation is necessary but not a statistically meaningful hiring-score evaluation.

Before production activation: verify the model is enabled for the account; ensure `TEST_MODE` is absent/false; compare extraction completeness, score calibration, refusals, p95 latency, and cost; exercise API outages; retain an explicit `OPENAI_MODEL` override for rollback. Keep existing stored candidate data/scores unchanged. The application has no live API key in this workspace, so transport tests use mocks and no claim of improved model accuracy is made.

## Verification record

- 61 Python tests pass, including pricing propagation from the catalog, real hashed-password member creation, tenant/role/CSRF guards, duplicate emails, seat limits through both APIs, last-admin protection, password session lifecycle, AI transport errors, and migrations.
- Seven Node data/notification tests pass; two analytics store tests pass. Analytics lint, type checking, and production build pass.
- Root dependency audit: zero findings after compatible updates. Analytics `--omit=dev` audit: zero. Full analytics audit: the development-tool findings above remain. `pip-audit -r requirements.txt`: no known findings in the resolved dependency set; this does not audit the deployed environment.
- All 35 browser tests pass after the Safari focus fix, covering pricing and adding users, original PDF preview, AI resume rendering, recruiter/analytics routes, all mobile-preview states, focus, and mobile score aggregation in desktop Chromium/Firefox/WebKit and mobile Chrome/Safari.
- Swift parser/source-inclusion validation passes for the modified sources; all 44 Swift sources are included in the Xcode project. Xcode compilation and on-device tests remain unrun.

## Recommended next release sequence

1. Review and test the Settings/team corrections on Dev, including a paid account with an available seat and one at capacity. Retain Dev.
2. Repair paid provisioning and webhook idempotency; validate Stripe in test mode with signed event replays. Confirm production storage and payment configuration without exposing secrets.
3. Run the credentialed AI evaluation and latency/cost check before promoting the new model to main.
4. Upgrade development tooling, add CI gates for both branches, and require the macOS build. Promote only the validated release and check its deployed commit, public prices, authenticated settings, and original-file delivery.
