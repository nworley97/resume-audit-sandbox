# ADA/WCAG 2.2 AA Accessibility Remediation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 23 accessibility issues from the AccessScan report and proactively audit remaining public pages for WCAG 2.2 AA compliance.

**Architecture:** Server-rendered Jinja2 templates with vanilla JS interactions. All fixes are HTML attribute additions and JS behavior updates — no new files needed. Phase 1 fixes the 23 reported issues across 6 existing files. Phase 2 audits and fixes the remaining public marketing pages.

**Tech Stack:** Flask/Jinja2 templates, Tailwind CSS, vanilla JavaScript

**Spec:** `docs/superpowers/specs/2026-04-09-ada-wcag-accessibility-remediation-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `templates/landing/sections/tools_tabs.html` | Modify | Add ARIA roles/attributes to tab widget (17 issues) |
| `static/js/landing.js` | Modify | Tab keyboard nav, ARIA toggling for tabs + mobile menu + video modal |
| `templates/landing/sections/navbar.html` | Modify | Fix nav landmark, add mobile menu ARIA (2 issues) |
| `templates/landing.html` | Modify | Wrap content in `<main>` landmark (1 issue) |
| `templates/landing/sections/video_demo.html` | Modify | Button semantics, SVG accessibility (2 issues) |
| `templates/landing/sections/contact_us.html` | Modify | Mailto link aria-label (1 issue) |

---

## Phase 1: Fix the 23 Reported Issues

### Task 1: Add ARIA roles and attributes to tab widget HTML

**Files:**
- Modify: `templates/landing/sections/tools_tabs.html:10-116`

**Context:** The tools-tabs section has 5 tab buttons and 5 content panels. The report flagged: missing `role="tablist"` (1), missing `role="tab"` on 5 buttons (5), missing `role="tabpanel"` on 5 panels (5), missing `aria-labelledby` on 5 panels (5), and missing keyboard focus management (1). That's 17 of 23 issues.

- [ ] **Step 1: Add `role="tablist"` and aria-label to the tab container**

In `templates/landing/sections/tools_tabs.html`, replace line 10:

```html
<div class="flex flex-wrap items-center justify-center mt-[24px] gap-1 reveal reveal-delay-1" id="tools-tabs">
```

with:

```html
<div class="flex flex-wrap items-center justify-center mt-[24px] gap-1 reveal reveal-delay-1" id="tools-tabs" role="tablist" aria-label="Product tools">
```

- [ ] **Step 2: Add `role="tab"`, `id`, `aria-selected`, `aria-controls`, and `tabindex` to each tab button**

Replace all 5 tab buttons (lines 11-25) with:

```html
      <button class="tab-pill h-[40px] md:h-[46px] rounded-tl-[12px] rounded-tr-[12px] px-3 md:px-6 font-ibm-sans text-[14px] md:text-[20px] cursor-pointer transition-all duration-200" data-tab="overview" role="tab" id="tab-overview" aria-selected="true" aria-controls="panel-overview" tabindex="0">
        Overview
      </button>
      <button class="tab-pill h-[40px] md:h-[46px] rounded-tl-[12px] rounded-tr-[12px] px-3 md:px-6 font-ibm-sans text-[14px] md:text-[20px] cursor-pointer transition-all duration-200" data-tab="discover" role="tab" id="tab-discover" aria-selected="false" aria-controls="panel-discover" tabindex="-1">
        Discover Talent
      </button>
      <button class="tab-pill h-[40px] md:h-[46px] rounded-tl-[12px] rounded-tr-[12px] px-3 md:px-6 font-ibm-sans text-[14px] md:text-[20px] cursor-pointer transition-all duration-200" data-tab="progress" role="tab" id="tab-progress" aria-selected="false" aria-controls="panel-progress" tabindex="-1">
        Candidate Progress
      </button>
      <button class="tab-pill h-[40px] md:h-[46px] rounded-tl-[12px] rounded-tr-[12px] px-3 md:px-6 font-ibm-sans text-[14px] md:text-[20px] cursor-pointer transition-all duration-200" data-tab="matrix" role="tab" id="tab-matrix" aria-selected="false" aria-controls="panel-matrix" tabindex="-1">
        Fit &amp; Validity Distributions
      </button>
      <button class="tab-pill h-[40px] md:h-[46px] rounded-tl-[12px] rounded-tr-[12px] px-3 md:px-6 font-ibm-sans text-[14px] md:text-[20px] cursor-pointer transition-all duration-200" data-tab="roi" role="tab" id="tab-roi" aria-selected="false" aria-controls="panel-roi" tabindex="-1">
        ROI Impact
      </button>
```

- [ ] **Step 3: Add `role="tabpanel"`, `id`, `aria-labelledby`, and `tabindex` to each panel**

Replace each panel's opening `<div>` tag:

Panel 1 (line 33) — replace:
```html
        <div class="tab-panel" data-panel="overview">
```
with:
```html
        <div class="tab-panel" data-panel="overview" role="tabpanel" id="panel-overview" aria-labelledby="tab-overview" tabindex="0">
```

Panel 2 (line 50) — replace:
```html
        <div class="tab-panel hidden" data-panel="discover">
```
with:
```html
        <div class="tab-panel hidden" data-panel="discover" role="tabpanel" id="panel-discover" aria-labelledby="tab-discover" tabindex="0">
```

Panel 3 (line 67) — replace:
```html
        <div class="tab-panel hidden" data-panel="progress">
```
with:
```html
        <div class="tab-panel hidden" data-panel="progress" role="tabpanel" id="panel-progress" aria-labelledby="tab-progress" tabindex="0">
```

Panel 4 (line 84) — replace:
```html
        <div class="tab-panel hidden" data-panel="matrix">
```
with:
```html
        <div class="tab-panel hidden" data-panel="matrix" role="tabpanel" id="panel-matrix" aria-labelledby="tab-matrix" tabindex="0">
```

Panel 5 (line 101) — replace:
```html
        <div class="tab-panel hidden" data-panel="roi">
```
with:
```html
        <div class="tab-panel hidden" data-panel="roi" role="tabpanel" id="panel-roi" aria-labelledby="tab-roi" tabindex="0">
```

- [ ] **Step 4: Verify the HTML changes**

Open `templates/landing/sections/tools_tabs.html` and confirm:
- The `#tools-tabs` div has `role="tablist"` and `aria-label="Product tools"`
- All 5 buttons have `role="tab"`, unique `id`, `aria-selected`, `aria-controls`, and `tabindex`
- Only the first tab has `aria-selected="true"` and `tabindex="0"`
- All 5 panels have `role="tabpanel"`, unique `id`, `aria-labelledby`, and `tabindex="0"`

---

### Task 2: Update tab switching JS with ARIA toggling and keyboard navigation

**Files:**
- Modify: `static/js/landing.js:39-70`

**Context:** The existing JS handles tab switching by toggling CSS classes. It needs to also toggle `aria-selected`, `tabindex`, and support keyboard navigation (arrow keys, Home, End) per the WAI-ARIA Tabs pattern.

- [ ] **Step 1: Replace the tab switching block**

In `static/js/landing.js`, replace the entire tab switching section (lines 39-70):

```javascript
  // ── Tab switching (Tools section) ──────────────────────────────
  const tabContainer = document.getElementById('tools-tabs');
  const panelContainer = document.getElementById('tools-panels');
  if (tabContainer && panelContainer) {
    const tabs = tabContainer.querySelectorAll('.tab-pill');
    const panels = panelContainer.querySelectorAll('.tab-panel');

    // Default: activate first tab
    if (tabs.length > 0) {
      tabs[0].classList.add('active');
    }

    tabContainer.addEventListener('click', function (e) {
      const pill = e.target.closest('.tab-pill');
      if (!pill) return;

      const target = pill.dataset.tab;

      // Update active tab
      tabs.forEach((t) => t.classList.remove('active'));
      pill.classList.add('active');

      // Show matching panel
      panels.forEach((p) => {
        if (p.dataset.panel === target) {
          p.classList.remove('hidden');
        } else {
          p.classList.add('hidden');
        }
      });
    });
  }
```

with:

```javascript
  // ── Tab switching (Tools section) ──────────────────────────────
  const tabContainer = document.getElementById('tools-tabs');
  const panelContainer = document.getElementById('tools-panels');
  if (tabContainer && panelContainer) {
    const tabs = Array.from(tabContainer.querySelectorAll('[role="tab"]'));
    const panels = panelContainer.querySelectorAll('[role="tabpanel"]');

    // Default: activate first tab
    if (tabs.length > 0) {
      tabs[0].classList.add('active');
    }

    function activateTab(tab) {
      var target = tab.dataset.tab;

      // Update ARIA and visual state on all tabs
      tabs.forEach(function (t) {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
        t.setAttribute('tabindex', '-1');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      tab.setAttribute('tabindex', '0');
      tab.focus();

      // Show matching panel, hide others
      panels.forEach(function (p) {
        if (p.dataset.panel === target) {
          p.classList.remove('hidden');
        } else {
          p.classList.add('hidden');
        }
      });
    }

    // Click handler
    tabContainer.addEventListener('click', function (e) {
      var pill = e.target.closest('[role="tab"]');
      if (!pill) return;
      activateTab(pill);
    });

    // Keyboard navigation
    tabContainer.addEventListener('keydown', function (e) {
      var currentTab = e.target.closest('[role="tab"]');
      if (!currentTab) return;

      var index = tabs.indexOf(currentTab);
      var newIndex;

      if (e.key === 'ArrowRight') {
        newIndex = (index + 1) % tabs.length;
      } else if (e.key === 'ArrowLeft') {
        newIndex = (index - 1 + tabs.length) % tabs.length;
      } else if (e.key === 'Home') {
        newIndex = 0;
      } else if (e.key === 'End') {
        newIndex = tabs.length - 1;
      } else {
        return;
      }

      e.preventDefault();
      activateTab(tabs[newIndex]);
    });
  }
```

- [ ] **Step 2: Verify tab JS changes**

Read `static/js/landing.js` and confirm:
- `activateTab()` function exists and toggles `aria-selected`, `tabindex`, `.active`, and panel visibility
- `keydown` listener handles `ArrowRight`, `ArrowLeft`, `Home`, `End`
- Arrow keys wrap around (last tab → first tab and vice versa)
- `e.preventDefault()` is called to prevent page scroll on arrow keys

- [ ] **Step 3: Commit Task 1 + Task 2**

```bash
git add templates/landing/sections/tools_tabs.html static/js/landing.js
git commit -m "fix(a11y): add ARIA roles and keyboard navigation to tab widget

Adds role=tablist/tab/tabpanel, aria-selected, aria-controls,
aria-labelledby, and keyboard navigation (arrow keys, Home, End)
to the tools-tabs section. Fixes 17 of 23 AccessScan issues.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Fix nav landmark and mobile menu accessibility

**Files:**
- Modify: `templates/landing/sections/navbar.html:2-46`

**Context:** The report flagged two issues: (1) the nav landmark contains non-navigation content (logo, login button), and (2) the mobile menu is visually hidden via `max-h-0` but still exposed to screen readers. The nav structure is actually valid — logos and login buttons are appropriate nav contents per HTML spec. The real issue is the mobile menu visibility to assistive tech.

- [ ] **Step 1: Add `aria-expanded` and `aria-controls` to the hamburger button**

In `templates/landing/sections/navbar.html`, replace line 26:

```html
    <button id="mobile-menu-btn" class="md:hidden flex flex-col gap-[5px] p-2 ml-auto" aria-label="Toggle menu">
```

with:

```html
    <button id="mobile-menu-btn" class="md:hidden flex flex-col gap-[5px] p-2 ml-auto" aria-label="Main menu" aria-expanded="false" aria-controls="mobile-menu">
```

- [ ] **Step 2: Add `aria-hidden` to the hamburger icon spans**

Replace lines 27-29:

```html
      <span class="block w-5 h-[2px] bg-gray-900 transition-all duration-300 origin-center" id="burger-top"></span>
      <span class="block w-5 h-[2px] bg-gray-900 transition-all duration-300" id="burger-mid"></span>
      <span class="block w-5 h-[2px] bg-gray-900 transition-all duration-300 origin-center" id="burger-bot"></span>
```

with:

```html
      <span class="block w-5 h-[2px] bg-gray-900 transition-all duration-300 origin-center" id="burger-top" aria-hidden="true"></span>
      <span class="block w-5 h-[2px] bg-gray-900 transition-all duration-300" id="burger-mid" aria-hidden="true"></span>
      <span class="block w-5 h-[2px] bg-gray-900 transition-all duration-300 origin-center" id="burger-bot" aria-hidden="true"></span>
```

- [ ] **Step 3: Add `aria-hidden` to the mobile menu container and wrap links in a `<nav>`**

Replace line 34:

```html
  <div id="mobile-menu" class="md:hidden overflow-hidden max-h-0 transition-all duration-300 bg-white border-t border-gray-100">
```

with:

```html
  <div id="mobile-menu" class="md:hidden overflow-hidden max-h-0 transition-all duration-300 bg-white border-t border-gray-100" aria-hidden="true">
```

- [ ] **Step 4: Add `aria-label` to distinguish the desktop and mobile nav landmarks**

Replace line 2:

```html
<nav id="landing-nav" class="sticky top-0 z-50 bg-white transition-shadow duration-300" style="height: 64px;">
```

with:

```html
<nav id="landing-nav" class="sticky top-0 z-50 bg-white transition-shadow duration-300" style="height: 64px;" aria-label="Main navigation">
```

- [ ] **Step 5: Verify navbar HTML changes**

Read `templates/landing/sections/navbar.html` and confirm:
- `<nav>` has `aria-label="Main navigation"`
- Hamburger button has `aria-label="Main menu"`, `aria-expanded="false"`, `aria-controls="mobile-menu"`
- All 3 burger spans have `aria-hidden="true"`
- `#mobile-menu` has `aria-hidden="true"`

---

### Task 4: Update mobile menu JS to toggle ARIA attributes

**Files:**
- Modify: `static/js/landing.js:122-156`

**Context:** The mobile menu toggle currently only changes `maxHeight` and burger icon transforms. It needs to also toggle `aria-expanded` on the button and `aria-hidden` on the menu.

- [ ] **Step 1: Replace the mobile menu JS block**

In `static/js/landing.js`, replace the mobile menu section (lines 122-156):

```javascript
  // ── Mobile menu ────────────────────────────────────────────────
  const menuBtn = document.getElementById('mobile-menu-btn');
  const mobileMenu = document.getElementById('mobile-menu');
  if (menuBtn && mobileMenu) {
    let isOpen = false;
    const burgerTop = document.getElementById('burger-top');
    const burgerMid = document.getElementById('burger-mid');
    const burgerBot = document.getElementById('burger-bot');

    menuBtn.addEventListener('click', function () {
      isOpen = !isOpen;
      if (isOpen) {
        mobileMenu.style.maxHeight = mobileMenu.scrollHeight + 'px';
        burgerTop.style.transform = 'rotate(45deg) translateY(5px)';
        burgerMid.style.opacity = '0';
        burgerBot.style.transform = 'rotate(-45deg) translateY(-5px)';
      } else {
        mobileMenu.style.maxHeight = '0';
        burgerTop.style.transform = '';
        burgerMid.style.opacity = '';
        burgerBot.style.transform = '';
      }
    });

    // Close menu on link click
    mobileMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        isOpen = false;
        mobileMenu.style.maxHeight = '0';
        burgerTop.style.transform = '';
        burgerMid.style.opacity = '';
        burgerBot.style.transform = '';
      });
    });
  }
```

with:

```javascript
  // ── Mobile menu ────────────────────────────────────────────────
  const menuBtn = document.getElementById('mobile-menu-btn');
  const mobileMenu = document.getElementById('mobile-menu');
  if (menuBtn && mobileMenu) {
    let isOpen = false;
    const burgerTop = document.getElementById('burger-top');
    const burgerMid = document.getElementById('burger-mid');
    const burgerBot = document.getElementById('burger-bot');

    function setMobileMenuState(open) {
      isOpen = open;
      menuBtn.setAttribute('aria-expanded', String(open));
      mobileMenu.setAttribute('aria-hidden', String(!open));
      if (open) {
        mobileMenu.style.maxHeight = mobileMenu.scrollHeight + 'px';
        burgerTop.style.transform = 'rotate(45deg) translateY(5px)';
        burgerMid.style.opacity = '0';
        burgerBot.style.transform = 'rotate(-45deg) translateY(-5px)';
      } else {
        mobileMenu.style.maxHeight = '0';
        burgerTop.style.transform = '';
        burgerMid.style.opacity = '';
        burgerBot.style.transform = '';
      }
    }

    menuBtn.addEventListener('click', function () {
      setMobileMenuState(!isOpen);
    });

    // Close menu on link click
    mobileMenu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        setMobileMenuState(false);
      });
    });
  }
```

- [ ] **Step 2: Verify mobile menu JS changes**

Read `static/js/landing.js` and confirm:
- `setMobileMenuState()` function exists
- It sets `aria-expanded` on `menuBtn` and `aria-hidden` on `mobileMenu`
- Both click handlers (button and links) call `setMobileMenuState()`

- [ ] **Step 3: Commit Task 3 + Task 4**

```bash
git add templates/landing/sections/navbar.html static/js/landing.js
git commit -m "fix(a11y): fix nav landmark and mobile menu screen reader visibility

Adds aria-label to nav, aria-expanded/aria-controls to hamburger
button, aria-hidden to decorative burger spans and collapsed mobile
menu. JS now toggles ARIA state on open/close. Fixes 2 of 23 issues.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Add main landmark to landing page

**Files:**
- Modify: `templates/landing.html:54-70`

**Context:** The page has no `<main>` element. The report flagged this as a missing landmark (WCAG 1.3.1). The navbar should sit outside `<main>` and the footer should also sit outside `<main>`.

- [ ] **Step 1: Wrap content sections in `<main>`**

In `templates/landing.html`, replace lines 54-70:

```html
{% block content %}
  {% include "landing/sections/navbar.html" %}
  {% include "landing/sections/hero.html" %}
  {% include "landing/sections/how_it_works.html" %}
  {% include "landing/sections/why_choose_us.html" %}
  {% include "landing/sections/recruiter_quote.html" %}
  {% include "landing/sections/dashboard_look.html" %}
  {% include "landing/sections/tools_tabs.html" %}
  {% include "landing/sections/ai_screening.html" %}
  {% include "landing/sections/app_platform.html" %}
  {% include "landing/sections/video_demo.html" %}
  {% include "landing/sections/testimonials.html" %}
  {% include "landing/sections/pain_points.html" %}
  {% include "landing/sections/apply_jobs.html" %}
  {% include "landing/sections/contact_us.html" %}
  {% include "landing/sections/footer.html" %}
{% endblock %}
```

with:

```html
{% block content %}
  {% include "landing/sections/navbar.html" %}
  <main id="main-content">
    {% include "landing/sections/hero.html" %}
    {% include "landing/sections/how_it_works.html" %}
    {% include "landing/sections/why_choose_us.html" %}
    {% include "landing/sections/recruiter_quote.html" %}
    {% include "landing/sections/dashboard_look.html" %}
    {% include "landing/sections/tools_tabs.html" %}
    {% include "landing/sections/ai_screening.html" %}
    {% include "landing/sections/app_platform.html" %}
    {% include "landing/sections/video_demo.html" %}
    {% include "landing/sections/testimonials.html" %}
    {% include "landing/sections/pain_points.html" %}
    {% include "landing/sections/apply_jobs.html" %}
    {% include "landing/sections/contact_us.html" %}
  </main>
  {% include "landing/sections/footer.html" %}
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/landing.html
git commit -m "fix(a11y): add main landmark to landing page

Wraps primary content sections in <main id='main-content'>,
with navbar and footer outside. Fixes 1 of 23 issues (WCAG 1.3.1).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Fix video demo play button and SVG accessibility

**Files:**
- Modify: `templates/landing/sections/video_demo.html:20-31`
- Modify: `static/js/landing.js:250-256`

**Context:** The play button is a `<div>` with `cursor-pointer` — not keyboard accessible. The SVG play icon has no alternative text, and the decorative preview video isn't hidden from assistive tech. The report flagged 2 issues here.

- [ ] **Step 1: Replace the play button `<div>` with a `<button>` and add SVG `aria-hidden`**

In `templates/landing/sections/video_demo.html`, replace lines 20-31:

```html
        <div id="demo-play-btn" class="bg-black border border-[#c1c7cd] rounded-[12px] overflow-hidden shadow-landing-card w-full h-[250px] md:h-[580px] flex items-center justify-center relative cursor-pointer group">
          <!-- Video preview (first frame) -->
          <video class="absolute inset-0 w-full h-full object-cover opacity-90 group-hover:opacity-70 transition-opacity duration-300" preload="metadata" muted>
            <source src="{{ url_for('static', filename='video/AlteraSF_Demo.mp4') }}#t=0.5" type="video/mp4">
          </video>
          <!-- Play icon overlay -->
          <div class="relative z-10 w-[56px] h-[56px] md:w-[72px] md:h-[72px] bg-white/90 rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
            <svg class="w-6 h-6 md:w-8 md:h-8 text-landing-navy ml-1" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
```

with:

```html
        <button type="button" id="demo-play-btn" class="bg-black border border-[#c1c7cd] rounded-[12px] overflow-hidden shadow-landing-card w-full h-[250px] md:h-[580px] flex items-center justify-center relative cursor-pointer group" aria-label="Play demo video">
          <!-- Video preview (first frame) -->
          <video class="absolute inset-0 w-full h-full object-cover opacity-90 group-hover:opacity-70 transition-opacity duration-300" preload="metadata" muted aria-hidden="true">
            <source src="{{ url_for('static', filename='video/AlteraSF_Demo.mp4') }}#t=0.5" type="video/mp4">
          </video>
          <!-- Play icon overlay -->
          <div class="relative z-10 w-[56px] h-[56px] md:w-[72px] md:h-[72px] bg-white/90 rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300" aria-hidden="true">
            <svg class="w-6 h-6 md:w-8 md:h-8 text-landing-navy ml-1" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </button>
```

- [ ] **Step 2: Add `role="dialog"` and `aria-label` to the video modal**

In `templates/landing/sections/video_demo.html`, replace line 38:

```html
<div id="demo-modal" class="fixed inset-0 z-[100] hidden items-center justify-center bg-black/70 backdrop-blur-sm">
```

with:

```html
<div id="demo-modal" class="fixed inset-0 z-[100] hidden items-center justify-center bg-black/70 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Demo video">
```

- [ ] **Step 3: Add `aria-label` to the modal close button**

In `templates/landing/sections/video_demo.html`, replace line 41:

```html
    <button id="demo-modal-close" class="absolute -top-12 right-0 text-white text-[32px] hover:opacity-70 transition-opacity cursor-pointer">
```

with:

```html
    <button id="demo-modal-close" class="absolute -top-12 right-0 text-white text-[32px] hover:opacity-70 transition-opacity cursor-pointer" aria-label="Close video">
```

- [ ] **Step 4: Update the demo modal JS to manage focus**

In `static/js/landing.js`, replace the demo play button click handler (inside lines 255-261):

```javascript
    demoPlayBtn.addEventListener('click', function () {
      demoModal.classList.remove('hidden');
      demoModal.classList.add('flex');
      document.body.style.overflow = 'hidden';
      if (demoVideo) demoVideo.play();
    });
```

with:

```javascript
    demoPlayBtn.addEventListener('click', function () {
      demoModal.classList.remove('hidden');
      demoModal.classList.add('flex');
      document.body.style.overflow = 'hidden';
      if (demoVideo) demoVideo.play();
      if (demoModalClose) demoModalClose.focus();
    });
```

And in the `closeDemoModal` function (lines 263-268), replace:

```javascript
    function closeDemoModal() {
      if (demoVideo) { demoVideo.pause(); }
      demoModal.classList.add('hidden');
      demoModal.classList.remove('flex');
      document.body.style.overflow = '';
    }
```

with:

```javascript
    function closeDemoModal() {
      if (demoVideo) { demoVideo.pause(); }
      demoModal.classList.add('hidden');
      demoModal.classList.remove('flex');
      document.body.style.overflow = '';
      demoPlayBtn.focus();
    }
```

- [ ] **Step 5: Commit**

```bash
git add templates/landing/sections/video_demo.html static/js/landing.js
git commit -m "fix(a11y): make video play button a real button with SVG hidden

Replaces div with button, adds aria-label, hides decorative SVG
and preview video from screen readers. Adds dialog role and focus
management to the video modal. Fixes 2 of 23 issues.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Fix mailto link accessibility

**Files:**
- Modify: `templates/landing/sections/contact_us.html:20-22`

**Context:** The mailto link shows "Contact Us" as visible text but opens an email client, which is unexpected behavior. The report flagged this as WCAG 3.2.2 (1 issue).

- [ ] **Step 1: Add `aria-label` to the mailto link**

In `templates/landing/sections/contact_us.html`, replace lines 20-22:

```html
        <a href="mailto:info@alterasf.com" class="inline-flex self-start items-center justify-center bg-landing-blue h-[56px] p-[16px] rounded-[12px] reveal reveal-delay-3 cursor-pointer">
          <span class="px-[16px] font-medium text-[20px] text-white leading-none tracking-[0.5px]" style="font-family: 'Roboto', sans-serif;">Contact Us</span>
        </a>
```

with:

```html
        <a href="mailto:info@alterasf.com" class="inline-flex self-start items-center justify-center bg-landing-blue h-[56px] p-[16px] rounded-[12px] reveal reveal-delay-3 cursor-pointer" aria-label="Contact us at info@alterasf.com (opens email)">
          <span class="px-[16px] font-medium text-[20px] text-white leading-none tracking-[0.5px]" style="font-family: 'Roboto', sans-serif;">Contact Us</span>
        </a>
```

- [ ] **Step 2: Commit**

```bash
git add templates/landing/sections/contact_us.html
git commit -m "fix(a11y): add aria-label to mailto link warning of email client

Adds descriptive aria-label indicating the link opens an email
client. Fixes 1 of 23 issues (WCAG 3.2.2).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2: Proactive Audit of Remaining Public Pages

### Task 8: Audit and fix About page

**Files:**
- Modify: `templates/about.html` (or equivalent)

- [ ] **Step 1: Read the About page template**

Read `templates/about.html` and check against the WCAG 2.2 AA audit checklist:
- Proper landmark structure (`<main>`, `<nav>`, `<header>`, `<footer>`)
- Heading hierarchy (single `<h1>`, logical nesting)
- All images have appropriate alt text
- All interactive elements keyboard accessible
- Focus indicators visible
- Color contrast meets AA ratio
- Link text is descriptive
- Skip navigation link present

- [ ] **Step 2: Apply fixes for any issues found**

Apply the same patterns from Phase 1 (landmarks, ARIA attributes, etc.) to fix any issues.

- [ ] **Step 3: Commit**

```bash
git add templates/about.html
git commit -m "fix(a11y): audit and fix About page for WCAG 2.2 AA

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Audit and fix Product page

**Files:**
- Modify: `templates/product.html` (or equivalent)

- [ ] **Step 1: Read the Product page template**

Read `templates/product.html` and check against the same WCAG 2.2 AA audit checklist from Task 8.

- [ ] **Step 2: Apply fixes for any issues found**

Apply the same patterns from Phase 1 to fix any issues.

- [ ] **Step 3: Commit**

```bash
git add templates/product.html
git commit -m "fix(a11y): audit and fix Product page for WCAG 2.2 AA

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Audit and fix FAQ page

**Files:**
- Modify: `templates/faq.html` (or equivalent)
- Possibly modify: JS handling FAQ accordion

- [ ] **Step 1: Read the FAQ page template**

Read `templates/faq.html` and check against the WCAG 2.2 AA audit checklist. Pay special attention to:
- FAQ accordion buttons — need `aria-expanded`, `aria-controls`
- FAQ answer panels — need `id` attributes, `aria-hidden` when collapsed
- FAQ icon (add/close) — needs `aria-hidden="true"`

- [ ] **Step 2: Apply fixes for any issues found**

For the FAQ accordion specifically:
- Add `aria-expanded="false"` to each `.faq-trigger` button
- Add `aria-controls` pointing to the answer `id`
- Add unique `id` to each `.faq-answer` div
- Add `aria-hidden="true"` to collapsed answers
- Add `aria-hidden="true"` to `.faq-icon` spans
- Update FAQ accordion JS to toggle `aria-expanded` and `aria-hidden`

- [ ] **Step 3: Commit**

```bash
git add templates/faq.html static/js/landing.js
git commit -m "fix(a11y): audit and fix FAQ page for WCAG 2.2 AA

Adds accordion ARIA attributes and keyboard support.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Audit and fix Contact page

**Files:**
- Modify: `templates/contact.html` (or equivalent)

- [ ] **Step 1: Read the Contact page template**

Read `templates/contact.html` and check against the WCAG 2.2 AA audit checklist. Pay special attention to:
- Form labels properly associated with inputs
- Required fields indicated with `aria-required`
- Error messages linked via `aria-describedby`
- Submit button text is descriptive
- Any mailto links have proper labels

- [ ] **Step 2: Apply fixes for any issues found**

Apply the same patterns from Phase 1 to fix any issues.

- [ ] **Step 3: Commit**

```bash
git add templates/contact.html
git commit -m "fix(a11y): audit and fix Contact page for WCAG 2.2 AA

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Add skip navigation link to base template

**Files:**
- Modify: `templates/base_landing.html:42-43`

**Context:** Skip navigation links allow keyboard users to bypass repetitive navigation and jump to main content. This benefits all public pages that extend `base_landing.html`.

- [ ] **Step 1: Add skip-to-main-content link**

In `templates/base_landing.html`, replace line 42:

```html
<body class="bg-white text-gray-900 font-ibm-sans antialiased">
```

with:

```html
<body class="bg-white text-gray-900 font-ibm-sans antialiased">
  <a href="#main-content" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[200] focus:bg-white focus:text-landing-blue focus:px-4 focus:py-2 focus:rounded-lg focus:shadow-lg focus:text-sm focus:font-medium">Skip to main content</a>
```

Note: This relies on `#main-content` existing on the page (added in Task 5 for the landing page). Other pages should also have `<main id="main-content">` — this will be ensured during each page's audit in Tasks 8-11.

- [ ] **Step 2: Commit**

```bash
git add templates/base_landing.html
git commit -m "fix(a11y): add skip navigation link to base template

Adds a visually hidden skip-to-main-content link that becomes
visible on focus. Benefits keyboard and screen reader users
across all public pages.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Verification

### After all tasks are complete:

- [ ] **Manual check:** Open the landing page in a browser, tab through all interactive elements. Verify: skip link appears on first Tab press, tabs are keyboard navigable with arrow keys, mobile menu toggles properly, video play button is focusable.
- [ ] **Screen reader spot-check:** Use NVDA or VoiceOver to navigate the landing page. Confirm tabs are announced as "tab 1 of 5", panels are announced, landmarks are reported, mobile menu state is announced.
- [ ] **Re-scan:** Run the AccessScan report again on the landing page URL to confirm 0 critical/serious findings.
- [ ] **Audit pages:** Run a quick automated check (e.g., browser devtools Lighthouse accessibility audit) on About, Product, FAQ, and Contact pages.
