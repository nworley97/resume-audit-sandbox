# Three Bug Fixes Design

Date: 2026-03-08

## Bug 1: Camera UI Missing from `camera_gate.html`

**Root cause:** Tailwind migration dropped the "Allow Camera Access" card.

**Fix:** Restore camera access card between "Before You Begin" and "Agreement" sections:
- "Allow Camera Access" heading with explanation text
- Visual mock of browser camera permission prompt (3 buttons styled in Tailwind)
- Note that declining may void application
- Restore `getUserMedia()` JS on Start button click
- Update acknowledgement checkbox text to mention camera access

**Files:** `templates/camera_gate.html`

## Bug 2: Dashboard Image Duplication in `dashboard_look.html`

**Root cause:** Both `<img>` tags point to same `dashboard-overview.png` (pre-composited screenshot containing both views).

**Fix:** Crop `dashboard-overview.png` (4144x1916) into two files:
- `dashboard-matrix.png` — Cross Validation Matrix (left/upper portion)
- `dashboard-detail.png` — Software Development Associate card (bottom-right portion)

Update template to use distinct images.

**Files:** `templates/landing/sections/dashboard_look.html`, `static/img/landing/dashboard-matrix.png`, `static/img/landing/dashboard-detail.png`

## Bug 3: Analytics "Invalid Route" in iframe

**Root cause:** Iframe loads SPA at `/<tenant>/recruiter/analytics-spa` but `App.tsx` only matches path segment `analytics`, not `analytics-spa`.

**Fix (Option A):** Add `?raw=1` query param to existing routes:
- `analytics_overview_nextjs`: when `raw=1` → serve SPA HTML directly; otherwise → render embed with iframe src `?raw=1`
- `analytics_detail_nextjs`: same pattern
- SPA sees `location.pathname` = `/<tenant>/recruiter/analytics` → route matches
- No SPA rebuild needed

**Files:** `app.py`, `templates/analytics_embed.html`
