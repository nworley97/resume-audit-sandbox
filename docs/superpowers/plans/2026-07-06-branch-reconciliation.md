# Branch Reconciliation & Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two disjoint lineages (`main` = production, `Dev` = sandbox) into a single trunk (`main`) that unions every feature, replace the fragile boot-time `ensure_schema()` with Alembic migrations, restore a working `Dev → main` promotion path, and clean up the repository — without regressing any production feature or data.

**Architecture:** `main` is the trunk (feature superset + matches the shared production DB). A `reconcile` branch is cut from `main`; Dev's UI polish is ported **onto** it hunk-by-hunk (adopt Dev's presentation, retain main's feature controls). Alembic is baselined against the live schema. After verification on the sandbox (which shares the prod DB), `reconcile` merges to `main`, prod deploys, and `Dev` is recreated as a descendant of `main`.

**Tech Stack:** Python 3.13, Flask + Flask-Login, SQLAlchemy 2.0, Alembic (new), PostgreSQL 16 (Render, shared `blackbox_prod_db`), gunicorn, Tailwind + esbuild (analytics React), Render auto-deploy on push.

## Global Constraints

- **Delete no features and no data.** The end state is a UNION of `main` and `Dev`. If a merge would drop a `main` endpoint/model/column or a `Dev` UI improvement, that's a defect.
- **Schema changes are additive-only.** The sandbox and prod share ONE database; both old-`main` code and reconciled code must run against it simultaneously during the transition. Never `DROP` a column/table that live code reads.
- **The DB is shared with other apps.** It also holds BeeCovered `bc_*` tables and duplicate `candidates`/`tenants`/`users` plural tables. Migrations must NEVER touch tables this app doesn't own — Alembic is filtered via `include_object` to app tables only. No migration may `drop_table`/`alter` a non-app table.
- **Trunk = `main`.** Candidate stage standardizes on `status` (`active`/`finalist`/`archived`); Dev's `archived` boolean is folded into it.
- **Only Phase 6 touches production.** Phases 0–5 happen on branches and are verified on the sandbox. Pause for explicit human approval before Phase 6.
- **One deploy at a time.** Push, then watch the single auto-deploy. Never trigger a manual deploy while a push-deploy is in flight (that caused earlier deploy churn).
- **Prod DB DSN** (used only where a step explicitly says so): `postgresql://blackbox_prod_db_user:***@dpg-d1umj23uibrs738l8r7g-a.oregon-postgres.render.com/blackbox_prod_db`. Read-only for inspection; writes only in Phase 3/6 controlled steps.
- **Render:** sandbox service `srv-d2dn6aili9vc73b31r50` (branch `Dev`), prod service `srv-d1umidndiees73athn60` (branch `main`), owner `tea-d1r8t6ur433s73a0n3t0`.

---

## Phase 0 — Safety net & branch setup (no prod impact)

### Task 0.1: Tag current prod and sandbox states

**Files:** none (git refs only)

- [ ] **Step 1: Fetch latest**

Run: `git fetch origin --prune`
Expected: refs for `origin/main`, `origin/Dev` up to date.

- [ ] **Step 2: Create safety tags on both tips**

```bash
git tag prod-pre-reconcile origin/main
git tag dev-pre-reconcile   origin/Dev
git push origin prod-pre-reconcile dev-pre-reconcile
```
Expected: two tags pushed. These are the rollback anchors for Phase 6.

- [ ] **Step 3: Record the current live prod deploy id** (for Render rollback)

Run: `curl -s -H "Authorization: Bearer $RENDER_KEY" "https://api.render.com/v1/services/srv-d1umidndiees73athn60/deploys?limit=5" | grep -o '"id":"dep-[^"]*"' | head`
Expected: note the newest `live` deploy id in `docs/superpowers/plans/reconcile-rollback.md`.

### Task 0.2: Create the `reconcile` branch off `main`

**Files:** none

- [ ] **Step 1: Branch from prod trunk**

```bash
git checkout -b reconcile origin/main
```
Expected: `Switched to a new branch 'reconcile'` tracking `origin/main`.

- [ ] **Step 2: Confirm it has main's features (sanity)**

Run: `grep -c 'departments/create' app.py`
Expected: `>= 1` (Department routes present — proves we're on the superset).

- [ ] **Step 3: Push the branch (so the sandbox can later preview it)**

```bash
git push -u origin reconcile
```
Expected: `reconcile` on origin. (Does not deploy anything yet.)

---

## Phase 1 — Adopt Alembic (replaces `ensure_schema()`)

**Why:** `ensure_schema()` silently drifts (it caused the outage). Alembic makes schema changes explicit and versioned. On this shared/existing DB we **baseline** (describe current schema) and **stamp** the DB, then express future changes as migrations. The actual DB stamp is deferred to Phase 6 (it's a prod write); Phase 1 is code-only.

### Task 1.1: Install and initialize Alembic

**Files:**
- Modify: `requirements.txt`
- Create: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/`

- [ ] **Step 1: Add dependency**

Add to `requirements.txt`:
```
alembic>=1.13
```

- [ ] **Step 2: Initialize migration tree**

Run: `alembic init migrations`
Expected: creates `alembic.ini` + `migrations/`.

- [ ] **Step 3: Wire env.py to the app's metadata and env var**

Edit `migrations/env.py` — replace the config/url and target_metadata sections with:
```python
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# App metadata (all models register on Base)
from models import Base  # noqa: E402
import subscription_models  # noqa: F401,E402  (ensures those tables register)
target_metadata = Base.metadata

# Use the same DATABASE_URL the app uses
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

# CRITICAL: this DB is SHARED with other apps (BeeCovered bc_* tables, plural
# candidates/tenants/users). Only ever manage tables THIS app owns, so
# autogenerate can never propose dropping another app's tables.
APP_TABLES = set(target_metadata.tables.keys())
def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and name not in APP_TABLES:
        return False
    return True

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt alembic.ini migrations/
git commit -m "chore(alembic): initialize Alembic wired to app metadata + DATABASE_URL"
```

### Task 1.2: Author the baseline migration (current schema)

**Files:** Create `migrations/versions/0001_baseline.py`

- [ ] **Step 1: Autogenerate against a scratch empty DB** (NOT prod)

```bash
createdb reconcile_scratch 2>/dev/null || true
DATABASE_URL="postgresql://localhost/reconcile_scratch" alembic revision --autogenerate -m "baseline current schema"
```
Expected: a migration in `migrations/versions/` containing `op.create_table(...)` for every model table (candidate, tenant, user, job_description, department, subscription tables, …).

- [ ] **Step 2: Reconcile the baseline against the LIVE schema (read-only)**

Run a read-only column diff of the generated baseline vs the actual prod DB:
```bash
DATABASE_URL="<prod DSN>" python scripts/diff_schema.py   # read-only; lists model-vs-DB column diffs
```
Expected: the only differences should be additive columns already present in prod via `ensure_schema()` (e.g. `job_description.start_time/end_time/work_arrangement`, `candidate.left_tab_count/archived/archived_at`). Add any missing columns to the baseline so `stamp` will match. Record leftover drift in the migration comments.

- [ ] **Step 3: Rename to a stable revision id**

Rename the file to `0001_baseline.py` and set `revision = "0001_baseline"`, `down_revision = None`.

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/0001_baseline.py scripts/diff_schema.py
git commit -m "feat(alembic): baseline migration matching current production schema"
```

### Task 1.3: Remove `ensure_schema()`, run Alembic on boot

**Files:**
- Modify: `app.py` (delete the `ensure_schema()` def + its call, ~lines 90–155)
- Modify: `Procfile`

- [ ] **Step 1: Delete `ensure_schema()` and its invocation** in `app.py`. Keep `subscription_models.ensure_subscription_schema()` behavior folded into Alembic (its tables are in the baseline).

- [ ] **Step 2: (DEFERRED to Phase 6) migrations run at deploy, before gunicorn**

> **Sequencing correction:** the `Procfile` change below must NOT ship before the prod DB is stamped
> (Task 6.1). On an un-stamped shared DB, `alembic upgrade head` would try to CREATE existing tables and
> the deploy would fail. So through Phases 2–5 the `Procfile` stays plain gunicorn; the alembic-on-boot
> line lands in Phase 6 together with the stamp. Target `Procfile` (applied in Task 6.2):
```
web: python -m alembic upgrade head && gunicorn app:app --timeout 180 --graceful-timeout 120 --workers 2 --threads 4 -b 0.0.0.0:$PORT
```

- [ ] **Step 3: Local smoke test against scratch DB**

Run: `DATABASE_URL="postgresql://localhost/reconcile_scratch" alembic upgrade head`
Expected: `Running upgrade -> 0001_baseline` and all tables created; no errors.

- [ ] **Step 4: Commit**

```bash
git add app.py Procfile
git commit -m "refactor(schema): replace ensure_schema() with alembic upgrade on boot"
```

> Note: the prod DB is **stamped** (not upgraded) in Phase 6 so `alembic upgrade head` becomes a no-op there. Do NOT run upgrade/stamp against prod yet.

---

## Phase 2 — Port Dev's UI polish onto `main` (no prod impact)

**Method for every task in this phase:** open the *live sandbox* and the two file versions side by side. **Adopt Dev's presentation/layout, retain main's feature controls.** After each file, deploy `reconcile` to the sandbox (Phase 2 preview, see Task 2.0) and eyeball the screen. Each task = one screen area, ends in a commit.

Diff any file with: `git diff origin/main origin/Dev -- <path>`  (main = base, Dev = polish).

### Task 2.0: Point the sandbox at `reconcile` for preview

- [ ] **Step 1: Temporarily set the sandbox service to auto-deploy `reconcile`**

Via Render API (branch change), or push `reconcile` and manually deploy it to the sandbox. Expected: sandbox now serves `reconcile`. (Prod service stays on `main`.) Revert to `Dev` only matters until Phase 6, where `Dev` becomes `main`.

- [ ] **Step 2: Confirm sandbox boots on reconcile** — `GET /login` → 200; watch deploy to `live`.

### Task 2.1: Recruiter + candidate screens

**Files:** `templates/recruiter.html`, `templates/candidate_detail.html`, `templates/candidates.html`, `templates/edit_jd.html`, `templates/camera_gate.html`

- [ ] **Step 1: Merge each file** — take Dev's markup/styling; **keep** main's controls: the department filter, the status dropdown / `set-status` action, the "close role" button, and `send-email`. (These correspond to routes `set-status`, `job/<code>/close`, `send-email`, `departments/*` that exist only on `main`.)
- [ ] **Step 2: Verify on sandbox** — log in, open a role's candidate list and a candidate detail. Confirm: Dev's polished layout renders AND status/close/email/department controls are present and functional.
- [ ] **Step 3: Commit** — `git commit -am "feat(ui): port Dev recruiter/candidate polish onto main controls"`

### Task 2.2: Landing / marketing pages

**Files:** `templates/landing/sections/*.html` (faq, hero, how_it_works, navbar, footer, testimonials, pain_points, tools_tabs, video_demo, why_choose_us, ai_screening, app_platform, apply_jobs, contact_us, dashboard_look, recruiter_quote), `templates/landing.html`, `templates/base_landing.html`, `templates/pricing_page.html`, `templates/product.html`, `templates/about.html`, `static/js/landing.js`

- [ ] **Step 1: Merge each** — landing pages are presentation-only; **take Dev's versions** where they diverge (Dev has the newer landing polish). Preserve `main`-only pages `contact.html` and `settings.html` unchanged (they don't exist on Dev).
- [ ] **Step 2: Verify on sandbox** — load `/`, `/pricing`, `/product`, `/about`; confirm rendering and that `landing.js` interactions work.
- [ ] **Step 3: Commit** — `git commit -am "feat(landing): port Dev marketing/landing polish"`

### Task 2.3: Billing screens (retain main's seat-limit logic)

**Files:** `templates/billing/notifications.html`, `templates/billing/account.html`, `templates/billing/add_seats.html`

- [ ] **Step 1: Merge** — adopt Dev's `notifications.html` additions; for `account.html`/`add_seats.html` **keep main's `seat_limit_notification` block** (Dev removed it — see `billing_routes.py` diff). Do not remove seat-limit UI.
- [ ] **Step 2: Verify on sandbox** — open `/<tenant>/account` and add-seats; confirm seat-limit notice still shows when at limit.
- [ ] **Step 3: Commit** — `git commit -am "feat(billing): port Dev notifications UI, keep main seat-limit logic"`

### Task 2.4: Shared partials & app chrome

**Files:** `templates/partials/header.html`, `templates/partials/sidebar.html`, `templates/base_app.html`

- [ ] **Step 1: Merge** — take Dev's chrome polish; **keep** main's sidebar links to Departments and Settings (main-only nav).
- [ ] **Step 2: Verify on sandbox** — every authenticated page shows the full nav incl. Departments + Settings.
- [ ] **Step 3: Commit** — `git commit -am "feat(ui): port Dev app chrome, retain main nav links"`

### Task 2.5: Analytics dashboard (React) + rebuild assets

**Files:** `analytics_ui/dashboard/src/**` (5 changed tsx: retention-heatmap, tremor-funnel, dashboard-chrome, analytics-detail, analytics-overview), `templates/analytics_embed.html`, generated `static/js/analytics/analytics.bundle.js`, `static/css/output.css`

- [ ] **Step 1: Merge the tsx source** — take Dev's component changes; **ensure main's `target="_top"` fix on candidate links is retained** (it exists in main; Dev lacks it — re-add if Dev's version overwrites).
- [ ] **Step 2: Rebuild generated assets**

Run: `npm install && npm run build`
Expected: regenerates `static/css/output.css` and `static/js/analytics/analytics.bundle.js`; `⚡ Done`.

- [ ] **Step 3: Verify on sandbox** — open an analytics dashboard; confirm charts render and candidate links open top-level (not nested in iframe).
- [ ] **Step 4: Commit** — `git commit -am "feat(analytics): port Dev dashboard changes, rebuild assets, keep target=_top"`

### Task 2.6: Backend logic (`app.py`) — port Dev's non-schema improvements

**Files:** `app.py` (base = main, which has all 15 endpoints)

- [ ] **Step 1: Port Dev-only logic that isn't a feature removal** — AI Q/A sourcing, markdown job-description handling, candidate-detail handlers, anti-cheat `left_tab_count` increments. Diff with `git diff origin/main origin/Dev -- app.py` and apply only the *additive* hunks. **Do NOT** delete the Department/`set-status`/`close`/`send-email`/`settings`/`contact` routes.
- [ ] **Step 2: Verify on sandbox** — regenerate questions for a JD (AI Q/A), render a markdown JD, and confirm all main endpoints still resolve (`/departments/create`, `/settings`, `/contact` return non-404).
- [ ] **Step 3: Commit** — `git commit -am "feat(app): port Dev logic improvements onto main route set"`

---

## Phase 3 — Candidate stage: standardize on `status` (additive)

**Why:** main uses `candidate.status`; Dev used the `archived` boolean. We keep `status` as source of truth and treat `archived` as a derived/back-compat field. All changes additive.

### Task 3.1: Models & code use `status`

**Files:** `models.py`, `app.py`, `templates/recruiter.html`, `templates/candidate_detail.html`

- [ ] **Step 1: In `models.py`, keep both columns** — `status = Column(String(20), nullable=True)` (source of truth) and keep `archived`/`archived_at` as nullable for back-compat. Do not drop either (additive rule).
- [ ] **Step 2: In code, write `status`** — any place Dev set `archived=True` now sets `status='archived'` (and may also set `archived=True` for transition). Reads filter on `status`.
- [ ] **Step 3: Verify on sandbox** — archive a candidate → they appear under the "Archived" status filter; un-archive → back to active.
- [ ] **Step 4: Commit** — `git commit -am "feat(candidate): standardize stage on status, keep archived for back-compat"`

### Task 3.2: Backfill migration `status` from `archived`

**Files:** Create `migrations/versions/0002_backfill_status.py`

- [ ] **Step 1: Write the data migration**
```python
revision = "0002_backfill_status"
down_revision = "0001_baseline"
from alembic import op
def upgrade():
    op.execute("UPDATE candidate SET status='archived' WHERE archived = true AND (status IS NULL OR status='')")
def downgrade():
    pass  # non-destructive; no downgrade needed
```
- [ ] **Step 2: Dry-run on scratch DB** — seed a row with `archived=true`, run `alembic upgrade head`, assert `status='archived'`.
- [ ] **Step 3: Commit** — `git add migrations/versions/0002_backfill_status.py && git commit -m "feat(migration): backfill candidate.status from archived flag"`

> This migration runs against prod automatically in Phase 6 (via `alembic upgrade head` on boot) — after the DB is stamped at `0001_baseline`.

---

## Phase 4 — Repository hygiene cleanup (no prod impact)

### Task 4.1: Add `.gitignore` and stop tracking `node_modules` / build junk

**Files:** Create `.gitignore`; remove tracked artifacts.

- [ ] **Step 1: Write `.gitignore`**
```
node_modules/
**/node_modules/
.venv/
__pycache__/
*.pyc
.env
dev.db
analytics_ui/dashboard/dist/
*.xcuserstate
.DS_Store
```
- [ ] **Step 2: Untrack committed dependencies/artifacts (keeps files on disk)**
```bash
git rm -r --cached node_modules analytics_ui/dashboard/node_modules analytics_ui/dashboard/dist 2>/dev/null || true
git rm --cached $(git ls-files '*.xcuserstate') 2>/dev/null || true
```
Expected: thousands of paths staged for deletion from the index only.
- [ ] **Step 3: Verify build still works from a clean install**

Run: `rm -rf node_modules && npm install && npm run build`
Expected: assets rebuild successfully (proves committed `node_modules` was unnecessary).

- [ ] **Step 4: Commit** — `git commit -am "chore(repo): add .gitignore; stop tracking node_modules and build artifacts"`

### Task 4.2: Reconcile requirements & remove Dev-only cruft

**Files:** `requirements.txt`, remove `WEBSITE_FIXES_TRACKER.md` if obsolete

- [ ] **Step 1: Ensure `requirements.txt` is the union** — includes `python-dotenv>=1.0`, `resend>=2.0` (main's email dep), `alembic>=1.13`. Guard the dotenv import in `app.py` with try/except to match main's resilient pattern.
- [ ] **Step 2: Verify** — `pip install -r requirements.txt` in a fresh venv succeeds; `python -c "import app"` imports without error (with a dummy `DATABASE_URL`).
- [ ] **Step 3: Commit** — `git commit -am "chore(deps): unify requirements (dotenv, resend, alembic); guard dotenv import"`

---

## Phase 5 — Full verification on the sandbox (no prod impact)

### Task 5.1: End-to-end smoke on `reconcile` (sandbox = shared prod DB)

- [ ] **Step 1: Ensure sandbox is on latest `reconcile`** and `live`.
- [ ] **Step 2: Run the checklist** (log in as a real tenant, e.g. `alterasf`):
  - [ ] Login → recruiter dashboard loads (no 500).
  - [ ] Departments: create/edit/delete a department.
  - [ ] Candidate: view detail, set status (finalist/archived), send-email action.
  - [ ] Job: close a role; create a JD with markdown + question_difficulty.
  - [ ] Billing: `/account`, add-seats, seat-limit notice.
  - [ ] Analytics dashboard renders; candidate links open top-level.
  - [ ] Landing pages render (`/`, `/pricing`, `/product`, `/about`, `/contact`, `/settings`).
- [ ] **Step 3: Confirm zero 500s** in sandbox logs during the run:

Run: `curl -s -H "Authorization: Bearer $RENDER_KEY" ".../logs?...&statusCode=500&startTime=<run start>"`
Expected: 0.

- [ ] **Step 4: Run Playwright suite if present** — `npx playwright test` (uses `./tests`, mock OpenAI via `client is None`). Expected: pass, or triage failures before promoting.

### Task 5.2: Prod-safety review of the reconciled diff

- [ ] **Step 1: Diff `reconcile` vs `origin/main`** — `git diff --stat origin/main..reconcile`. Confirm: no route deleted, no column dropped, only additive migrations.
- [ ] **Step 2: Confirm Alembic baseline matches prod** — re-run the read-only `scripts/diff_schema.py` against prod; expected: no missing columns (so the Phase 6 `stamp` will be valid).

---

## Phase 6 — Promote to production (⚠️ the only prod-touching phase — requires explicit approval)

### Task 6.1: Stamp the production DB at the Alembic baseline

**Files:** none (one controlled prod write: creates `alembic_version`, inserts one row)

- [ ] **Step 1: Get human go-ahead.** Announce: "About to stamp prod DB and deploy reconciled code."
- [ ] **Step 2: Stamp** (does NOT run DDL; just records that prod is at baseline)
```bash
DATABASE_URL="<prod DSN>" alembic stamp 0001_baseline
```
Expected: `alembic_version` table created with `0001_baseline`. Verify read-only: `SELECT version_num FROM alembic_version;` → `0001_baseline`.

### Task 6.2: Merge `reconcile` → `main` and deploy prod

- [ ] **Step 1: Merge**
```bash
git checkout main && git pull --ff-only origin main
git merge --no-ff reconcile -m "reconcile: unify Dev polish onto main trunk; adopt Alembic"
```
- [ ] **Step 2: Push (auto-deploys prod)** — `git push origin main`. Watch the prod deploy to `live`; on boot `alembic upgrade head` runs `0002_backfill_status` (baseline is a no-op since stamped).
- [ ] **Step 3: Verify prod** — `GET https://blackboxstrategies.alterasf.com/login` → 200; spot-check recruiter + landing; 0 new 500s in prod logs.
- [ ] **Step 4: Rollback path if broken** — Render → prod service → "Rollback" to the deploy id recorded in Task 0.1 Step 3; or `git revert -m 1 <merge-sha> && git push`. DB is safe (all additive; backfill only set `status`).

### Task 6.3: Recreate `Dev` as a descendant of `main`

- [ ] **Step 1: Force `Dev` to the reconciled `main`**
```bash
git branch -f Dev origin/main
git push --force-with-lease origin Dev
```
Expected: `origin/Dev` now equals `origin/main`; histories are shared going forward.
- [ ] **Step 2: Ensure sandbox service auto-deploys `Dev`** (revert any Phase-2 branch change). Watch sandbox deploy to `live`; `GET /login` → 200.
- [ ] **Step 3: Confirm promotion works** — `git merge-base origin/main origin/Dev` now returns a real commit (no longer "no common ancestor").

---

## Phase 7 — Final cleanup

### Task 7.1: Delete dead branches

- [ ] **Step 1: Delete merged/redundant/contained branches**
```bash
git push origin --delete auto-emails                              # merged via PR #7
git push origin --delete claude/quirky-carson                     # ancestor of old Dev, contained
git push origin --delete fix/three-bugs-camera-dashboard-analytics # target=_top already in main
git push origin --delete reconcile                                # merged into main
git branch -D fix/sandbox-candidate-archived reconcile 2>/dev/null || true
```
Expected: each `- [deleted]`.

### Task 7.2: Document the new workflow

**Files:** Update `README.md` / `RECONCILIATION_PLAN.md`

- [ ] **Step 1: Write the promotion flow** — "branch off `Dev` → sandbox previews `Dev` → open PR `Dev → main` → merge deploys prod. Schema changes = a new Alembic migration; never edit the DB by hand." Commit and push to `main`.

---

## Rollback summary

| If broken at… | Recovery |
|---|---|
| Sandbox (Phases 2–5) | It shares prod DB but runs branch code; revert the offending commit on `reconcile`, redeploy. No prod impact. |
| Prod deploy (6.2) | Render rollback to recorded deploy id, or `git revert` the merge + push. |
| Prod DB | All changes additive; the only data write is `status='archived'` backfill (reversible by clearing it). `prod-pre-reconcile` tag preserves the exact pre-change code. |

## Self-review checklist (run before executing)

- **Feature coverage:** every `main`-only endpoint (Departments, set-status, close, send-email, settings, contact) has an explicit "retain" instruction in Phase 2. ✔
- **Data safety:** no `DROP`; only additive columns + one idempotent backfill. ✔
- **History fix:** Phase 6.3 makes `Dev` descend from `main`; `merge-base` check proves it. ✔
- **Cleanup:** node_modules untracked, .gitignore added, dead branches deleted, workflow documented. ✔
