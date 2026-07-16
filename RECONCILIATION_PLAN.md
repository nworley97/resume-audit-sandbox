# Resume‑Audit — Branch Reconciliation Plan

_Prepared 2026‑07‑06. Status: reviewed; decisions confirmed. Nothing in production or git has been changed by this document._

> **This is the strategy overview.** The full step‑by‑step, execution‑ready plan (every task, command, verification, and rollback) lives in **`docs/superpowers/plans/2026-07-06-branch-reconciliation.md`**.

---

## 0. Executive summary

Your two environments have drifted into an unmaintainable state:

- **`main` runs production** (`blackboxstrategies.alterasf.com`); **`Dev` runs the sandbox** (`resume-audit-sandbox.onrender.com`).
- **`main` and `Dev` have completely disjoint git histories** — two separate "Initial commit" roots, **no common ancestor**. You cannot merge, rebase, or promote `Dev → main` through normal git.
- **Both services share ONE database** (`blackbox_prod_db`). The "sandbox" reads and writes **live production data**. It is not isolated.
- The current **login 500 on the sandbox** is a symptom: `Dev`'s code selects `candidate.archived`, a column that doesn't exist in the (main‑shaped) shared DB.
- Contrary to first impression, **`main` is the feature *superset***: it has **15 endpoints `Dev` dropped** and 88 files `Dev` lacks (incl. the entire iOS app). `Dev`'s value is **UI polish on ~15 shared files**, not new features.

**Recommended path:** keep **`main` as the trunk**, port `Dev`'s polish onto it, adopt a real migration tool, unify the histories, and recreate `Dev` as a branch off the new `main` so promotion works again.

---

## 1. Branch inventory

Two lineages that share no history:

| Branch | Lineage | Role | vs `main` (behind/ahead) | Last commit | Disposition |
|---|---|---|---|---|---|
| **`main`** | A — production | live prod | — | 2026‑06‑30 | **Trunk (keep)** |
| `auto-emails` | A | email feature | 3 / **0** | 2026‑06‑30 | Merged into main (PR #7) → **delete** |
| `fix/three-bugs-camera-dashboard-analytics` | A | bugfix WIP | 38 / **1** | 2026‑03‑15 | 1 unmerged commit → cherry‑pick or **delete** |
| **`Dev`** | B — sandbox | live sandbox | 194 / **259** | 2026‑06‑10 | **Source of polish to port, then rebase off main** |
| `claude/quirky-carson` | B | old Dev snapshot | 194 / 251 | 2026‑02‑25 | Ancestor of `Dev` (contained) → **delete** |

Roots: `main` = `b78cdf4`, `Dev` = `c8393e8` — both "Initial commit", same timestamp, **no merge base**. The parallel `main` line was almost certainly created by a history rewrite / re‑init.

---

## 2. The three structural problems

### 2.1 Disjoint histories
`git merge-base origin/main origin/Dev` → **no common ancestor**. Normal promotion is impossible; git treats the two as unrelated repositories. This must be fixed or every future "push sandbox to prod" is a manual copy.

### 2.2 Shared production database (highest risk)
The Render account has exactly **one** Postgres: `blackbox_prod_db` (`dpg-d1umj23…`, pro_4gb). Both prod and sandbox point at it.
- Every sandbox action mutates real data: **301 tenants, 4,491 candidates**.
- The DB is also shared with **another app (BeeCovered)** — `bc_*` tables plus duplicate `candidates` / `tenants` / `users` plural tables.
- Schema is **main‑shaped**: `candidate.status` present; `candidate.archived` absent; `department` table + `job_description.question_difficulty` present.

Per your direction we are **keeping the unified DB** (no separate sandbox DB). Consequence: **schema changes must stay additive** (never drop a column prod code uses) so both `main` and in‑progress code work against it simultaneously.

### 2.3 No migrations
There is no Alembic. Schema is patched at boot by a hand‑rolled `ensure_schema()` in `app.py` that `create_all()`s (missing tables only) and `ALTER … ADD COLUMN`s a hardcoded list. When a model gains a column that isn't added to that list, long‑lived DBs silently lack it → 500. **This is the root cause pattern and should be replaced with Alembic.**

---

## 3. Feature reality: `main` ⊃ `Dev`

| Check | `main` | `Dev` |
|---|---|---|
| HTTP endpoints | **87** | 72 |
| `app.py` | 3,521 lines | 3,190 (−507 net) |
| Endpoints the other lacks | **15** | **0** |
| Non‑asset files the other lacks | 88 | 1 |

**15 endpoints in `main` but not `Dev`** (all backed by live prod data):
- Departments CRUD — `/departments/create|edit|delete` (+ tenant‑scoped)
- Candidate email — `/recruiter/candidate/<id>/send-email` (`resend`)
- Candidate status workflow — `/recruiter/candidate/<id>/set-status`
- Close role — `/recruiter/job/<code>/close`
- `/settings`, `/contact`

**0 endpoints in `Dev` but not `main`.** `Dev` added no new surface; it trimmed the app and polished existing screens.

---

## 4. Reconciliation surface (what actually has to be merged)

Excluding `node_modules` / build output:

**A. `main`‑only — preserved for FREE by choosing main as trunk (no work):**
`ios/` (entire Swift app), `ios_api.py`, `docs/`, `templates/contact.html`, `templates/settings.html`, `DEPLOYMENT_CHECKLIST.md`, `job-description-sample.md`, figma + landing assets. (~88 files)

**B. `Dev`‑only — trivial:**
`WEBSITE_FIXES_TRACKER.md` (doc) + compiled `analytics_ui/dashboard/dist/*` artifacts (regenerated by build; ignore).

**C. Bidirectional — the REAL work (~15 files).** These are the files where `Dev` made changes worth keeping and that must be merged onto `main`:

| File | Δ (main↔Dev) | Nature | Proposed resolution |
|---|---|---|---|
| `templates/candidate_detail.html` | 943 | Dev UI rewrite | **Take Dev's UI**, re‑wire to main's status/email/department features |
| `templates/recruiter.html` | 650 | Dev UI rewrite | **Take Dev's UI**, keep main's status/close/dept controls |
| `app.py` | 615 | Dev trimmed 15 routes, added logic | **Keep main base (all routes)**, port Dev's logic (AI Q/A sourcing, markdown, candidate‑detail handlers) |
| `templates/billing/notifications.html` | 452 | Dev‑heavy additions | Likely **take Dev** |
| `templates/landing/sections/faq.html` | 358 | Dev polish | Take Dev |
| `models.py` | ~30 | Schema union | **Union**: keep main's Department/status/question_difficulty; decide archived (see §5) |
| `templates/partials/header.html` | 302 | main‑heavy | Take main, graft Dev tweaks |
| `templates/pricing_page.html` | 103 | Dev polish | Take Dev |
| `templates/edit_jd.html` | 108 | Dev tweaks | Merge |
| `templates/candidates.html` | 101 | Dev tweaks | Merge |
| `analytics_ui/.../analytics-overview.tsx` (+4 tsx) | ~300 | Dev tweaks | Merge, then rebuild dist |
| `templates/camera_gate.html` | 66 | Dev tweaks | Merge |
| `static/js/landing.js`, `static/css/output.css` | 149 | Dev polish + generated CSS | Merge JS; regenerate CSS via Tailwind build |
| `billing_routes.py` | ~20 | Dev removed seat‑limit notif | **Keep main** (don't regress) |
| `stripe_webhooks.py` | 126 | main‑heavy | Keep main, graft Dev if any |

Each row needs an eyes‑on decision; per your "delete nothing" rule the default is **keep main's feature, adopt Dev's presentation.**

---

## 5. Schema & data strategy (unified DB, additive‑only)

- Target schema = **superset** of both models. Nothing is dropped.
- `candidate.status` (main, live data) **stays**. `candidate.archived`/`archived_at` (Dev) are **added** (already the 500 fix).
- **Decision needed:** keep both stage mechanisms, or migrate `Dev`'s archive‑boolean into `main`'s richer `status` (`active`/`finalist`/`archived`)? Recommended: **standardize on `status`**, treat `archived=true` as `status='archived'` during a one‑time backfill, and keep `archived` as a computed convenience if the new UI needs it.
- **Adopt Alembic**: baseline a migration from the current prod schema, then express every future change as a migration. Retire `ensure_schema()`.

---

## 6. History unification (make `Dev → main` work again)

After the unified tree is built and verified:

1. Tag safety points: `git tag prod-pre-reconcile origin/main` and `git tag dev-pre-reconcile origin/Dev`.
2. Build the reconciled tree on a branch off **`main`** (call it `reconcile`), porting §4‑C.
3. Tie the histories together so future merges have a base:
   `git checkout main && git merge -s ours --allow-unrelated-histories origin/Dev` (records Dev as an ancestor without changing files), **then** merge `reconcile` normally. This gives `main` a shared ancestor with `Dev` going forward.
4. Recreate the sandbox branch: `git branch -f Dev main` (Dev now descends from main). Future flow: branch off `Dev` → preview on sandbox → PR into `main` → prod.
5. Delete `auto-emails` and `claude/quirky-carson`; cherry‑pick or drop `fix/three-bugs`.

---

## 7. Staged execution (each stage independently reviewable)

- **Stage 0 — Unblock sandbox (in progress):** the sandbox had **two** bugs: (a) missing `candidate.archived`/`archived_at` columns → login 500; (b) `app.py` hard‑imports `python-dotenv` but it was never in `requirements.txt` → **every deploy since 2026‑06‑10 crashed on boot** (`ModuleNotFoundError: dotenv`), freezing the sandbox on the June‑8 build. Both fixed on `Dev` (`c59f686` adds the columns via `ensure_schema()`; `84edda5` adds the dependency). Once the deploy boots, `ensure_schema()` adds the columns. NOTE: `main` guards the dotenv import in try/except, so production is unaffected — this is Dev‑only requirements drift.
- **Stage 1 — Freeze & branch:** tag safety points; create `reconcile` off `main`.
- **Stage 2 — Port UI (§4‑C):** bring Dev's polished templates/JS/TSX onto `main`, re‑wired to main's features. Verify each screen on the sandbox (real data).
- **Stage 3 — Schema/Alembic (§5):** baseline Alembic; `status`/`archived` decision + backfill.
- **Stage 4 — Verify:** exercise the full app on the sandbox against the shared DB; confirm prod features intact + Dev polish present.
- **Stage 5 — Unify histories & promote (§6):** merge to `main`, deploy prod, rebase `Dev`.
- **Stage 6 — Cleanup:** delete dead branches; document the new promotion flow.

---

## 8. Decisions (confirmed 2026‑07‑06)

1. **Trunk direction** — ✅ **`main` is the trunk.** Dev's work is ported on top via branches; `Dev` recreated off `main`.
2. **Candidate stage model** — ✅ standardize on `status`; fold Dev's `archived` boolean in via one‑time backfill.
3. **Ship Stage 0** — ✅ shipped to `Dev` (commits `c59f686` + `84edda5`); deploying.
4. **Alembic** — ✅ adopt during Stage 3.
5. **`fix/three-bugs`** — ✅ delete (its `target=_top` change already exists in `main`).

---

## 9. Immediate 500 fix (reference)

Root cause: `Dev`'s `Candidate` model declares `archived`/`archived_at`; `ensure_schema()` only patched `left_tab_count`; no migrations → shared DB lacks the columns → `/recruiter` 500s post‑login.

```sql
ALTER TABLE candidate ADD COLUMN IF NOT EXISTS archived boolean NOT NULL DEFAULT false;
ALTER TABLE candidate ADD COLUMN IF NOT EXISTS archived_at timestamp;
```
Equivalent code fix committed as `c59f686` (branch `fix/sandbox-candidate-archived`).
