# ADA/WCAG 2.2 AA Accessibility Remediation

**Date:** 2026-04-09
**Target Standard:** WCAG 2.2 Level AA
**Report Source:** AccessScan report (23 issues flagged on landing page)
**Scope:** Phase 1 — fix 23 reported issues; Phase 2 — proactive audit of remaining public pages

---

## Phase 1: Fix the 23 Reported Issues

### 1.1 Tab Interface — `templates/landing/sections/tools_tabs.html` (17 issues)

The tools-tabs section has 5 tabs (Overview, Discover Talent, Candidate Progress, Fit & Validity, ROI Impact) and 5 corresponding panels. The entire tab widget is missing ARIA semantics.

**Fixes:**

1. **Add `role="tablist"` to `#tools-tabs` container** (1 issue)
   - The wrapping `<div id="tools-tabs">` must have `role="tablist"` so screen readers announce it as a group of tabs.

2. **Add `role="tab"` to each tab button** (5 issues)
   - Each `<button>` inside the tablist gets `role="tab"`.
   - Add unique `id` attributes (e.g., `tab-overview`, `tab-discover`, etc.).
   - Add `aria-selected="true"` on the active tab, `"false"` on inactive tabs.
   - Add `aria-controls` pointing to the corresponding panel's `id`.
   - Set `tabindex="0"` on active tab, `tabindex="-1"` on inactive tabs.

3. **Add `role="tabpanel"` to each panel** (5 issues)
   - Each `.tab-panel` div gets `role="tabpanel"`.
   - Add unique `id` attributes (e.g., `panel-overview`, `panel-discover`, etc.).

4. **Add `aria-labelledby` to each panel** (5 issues)
   - Each panel gets `aria-labelledby` referencing its controlling tab's `id`.

5. **Keyboard navigation** (1 issue)
   - Arrow Left/Right to move between tabs.
   - Home/End to jump to first/last tab.
   - Tab key moves focus into the active panel, not to the next tab.
   - Activation on arrow key press (automatic activation pattern).

6. **JavaScript updates required:**
   - On tab switch: toggle `aria-selected` on all tabs, update `tabindex`, show/hide panels.
   - Register `keydown` listener on tablist for arrow/Home/End navigation.

### 1.2 Navigation Landmark — `templates/landing/sections/navbar.html` (2 issues)

**Issue A: Invalid nav landmark (1 issue)**
- The `<nav id="landing-nav">` element must contain only navigation links.
- Verify the nav wraps links/buttons appropriately. If non-navigation content exists inside, move it outside or restructure.

**Issue B: Visually hidden mobile menu content exposed to screen readers (1 issue, 8 elements)**
- The mobile menu uses `max-h-0` / `overflow-hidden` to hide visually, but screen readers still see it.
- Add `aria-hidden="true"` to `#mobile-menu` when collapsed, remove it when expanded.
- Add `aria-expanded="false"` to `#mobile-menu-btn`, toggle to `"true"` on open.
- Add `aria-controls="mobile-menu"` to the hamburger button.
- JavaScript must toggle these attributes on menu open/close.

### 1.3 Main Landmark — `templates/landing.html` or `templates/base_landing.html` (1 issue)

- Wrap the primary page content in a `<main>` element.
- Best location: in `templates/landing.html`, wrap all section includes (after navbar, before footer) with `<main id="main-content">`.
- The navbar and footer sit outside `<main>` since they are not primary content.

### 1.4 SVG/Image Accessibility — `templates/landing/sections/video_demo.html` (2 issues)

**Issue A: SVG play icon missing alternative text (1 issue)**
- The SVG play triangle inside the play button overlay needs either:
  - `aria-hidden="true"` on the SVG (preferred, since the button itself conveys the action), OR
  - `role="img"` + `aria-label="Play"` on the SVG.
- The containing `<div>` should become a `<button type="button">` with `aria-label="Play demo video"`.

**Issue B: Decorative SVG not hidden (1 issue)**
- Add `aria-hidden="true"` to the decorative SVG play icon.
- Add `aria-hidden="true"` to the preview `<video>` element since it's purely decorative (the actual video is in the modal).

### 1.5 Mailto Link — `templates/landing/sections/contact_us.html` (1 issue)

- The mailto link's visible text is "Contact Us" but it opens an email client, which is unexpected behavior.
- Add `aria-label="Contact us at info@alterasf.com (opens email client)"` to the `<a>` tag.
- Alternative: add visible text like "(Email)" next to "Contact Us".

---

## Phase 2: Proactive Audit of Remaining Public Pages

After completing Phase 1, audit these pages for the same patterns and WCAG 2.2 AA compliance:

### Target Pages
- About (`/about`)
- Product (`/product`)
- FAQ (`/faq`)
- Contact (`/contact`)

### Audit Checklist per Page
- [ ] Proper landmark structure (`<main>`, `<nav>`, `<header>`, `<footer>`)
- [ ] Heading hierarchy (single `<h1>`, logical nesting)
- [ ] All images have appropriate alt text (or `aria-hidden` if decorative)
- [ ] All interactive elements are keyboard accessible
- [ ] Focus indicators visible on all focusable elements
- [ ] Color contrast meets AA ratio (4.5:1 text, 3:1 large text/UI)
- [ ] Form labels properly associated with inputs
- [ ] ARIA attributes used correctly (no redundant or incorrect roles)
- [ ] Link text is descriptive (no "click here" without context)
- [ ] Skip navigation link present
- [ ] Language attribute on `<html>` tag
- [ ] FAQ accordion has `aria-expanded`, `aria-controls`, `aria-hidden`

### Additional WCAG 2.2 Criteria
- **2.4.11 Focus Appearance:** Focus indicators must meet minimum area and contrast requirements.
- **2.4.13 Focus Not Obscured:** Focused elements must not be fully hidden by sticky headers/footers.
- **3.2.6 Consistent Help:** If help mechanisms exist, they appear in the same relative location across pages.
- **3.3.7 Redundant Entry:** Don't ask users to re-enter information already provided in the same session.

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `templates/landing/sections/tools_tabs.html` | 1 | ARIA roles, attributes for tab widget |
| `templates/landing/sections/navbar.html` | 1 | Nav landmark fix, mobile menu ARIA |
| `templates/landing.html` | 1 | Add `<main>` wrapper |
| `templates/landing/sections/video_demo.html` | 1 | Button semantics, SVG accessibility |
| `templates/landing/sections/contact_us.html` | 1 | Mailto link aria-label |
| `static/js/landing.js` (or equivalent) | 1 | Tab keyboard nav, ARIA toggling, mobile menu ARIA toggling |
| `templates/about.html` | 2 | Audit + fixes |
| `templates/product.html` | 2 | Audit + fixes |
| `templates/faq.html` | 2 | Audit + fixes (accordion ARIA) |
| `templates/contact.html` | 2 | Audit + fixes |
| `templates/base_landing.html` | 2 | Skip nav link, any shared fixes |

---

## Success Criteria

1. All 23 issues from the AccessScan report are resolved.
2. A re-scan of the landing page produces 0 critical/serious findings.
3. All public marketing pages pass WCAG 2.2 AA automated checks.
4. Tab widget is fully keyboard navigable following the WAI-ARIA Authoring Practices tab pattern.
5. Screen reader testing (manual spot-check) confirms landmarks, tabs, and navigation are announced correctly.
