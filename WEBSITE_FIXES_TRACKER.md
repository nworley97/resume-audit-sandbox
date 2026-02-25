# Website Fixes Tracker

**Source:** `20260222_Feedback_Website_r1.docx`
**Branch:** `claude/quirky-carson`
**Date Started:** 2026-02-25

---

## 1st Priority Fixes (IMMEDIATE)

### Fix #1: 'g' in 'Hiring' is clipped
- **File:** `templates/landing/sections/why_choose_us.html`
- **Issue:** The descender of 'g' in "Hiring" is cut off due to `overflow-clip` on parent containers
- **Fix:** Removed nested `overflow-clip` wrappers; removed `overflow-hidden` from section
- **Status:** [x] Complete

### Fix #2: Text change (de-cap and 'or' to '&')
- **File:** `templates/landing/sections/why_choose_us.html`
- **Issue:** "Detects AI-Generated or Copied Candidate Responses" needs de-capitalization and symbol change
- **Fix:** Changed to "Detects AI-generated &amp; copied candidate responses"
- **Status:** [x] Complete

### Fix #3: 'Tools built for clarity' section edit
- **File:** `templates/landing/sections/tools_tabs.html`
- **Issues & Fixes:**
  - Title bolded and capitalized: "Tools built for clarity" -> "Tools Built for Clarity"
  - Tab labels capitalized: "Discover talent" -> "Discover Talent", "Candidate progress" -> "Candidate Progress", etc.
  - Deleted repeated tab name labels in upper-left of each panel (5 instances)
  - Fixed bottom clipping: changed `md:h-[726px]` to `md:min-h-[726px]`, removed `overflow-hidden` from section
- **Status:** [x] Complete

### Fix #4: Title capitalization changes
- **Files & Changes:**
  - `templates/landing/sections/app_platform.html`: "Post jobs. Find talent fast." -> "Post Jobs. Find Talent Fast."
  - `templates/landing/sections/testimonials.html`: "Kind words from people who love AlteraSF" -> "Kind Words from People Who Love AlteraSF"
  - `templates/product.html`: Same testimonials title change
  - `templates/landing/sections/apply_jobs.html`: "How to find your dream job" -> "How to Find Your Dream Job"
- **Status:** [x] Complete

### Fix #5: About Us 'Learn More' hyperlink
- **File:** `templates/about.html`
- **Issue:** "Learn More" links to `/product`, should link to research paper
- **Fix:** Changed href to `https://arxiv.org/pdf/2511.00774` with `target="_blank" rel="noopener noreferrer"`
- **Status:** [x] Complete

### Fix #6: Customer validation job title bolding
- **Files:**
  - `templates/landing/sections/testimonials.html` - all job titles in desktop (7) + mobile (4) layouts
  - `templates/product.html` - all 5 job titles in testimonial cards
- **Issue:** Job titles needed `font-bold`
- **Status:** [x] Complete

### Fix #7: Pricing FAQ bullet addition
- **File:** `templates/landing/sections/faq.html`
- **Issue:** "Who is AlteraSF built for?" FAQ missing a bullet
- **Fix:** Added "Business owners hiring remote roles and startup founders" as last bullet
- **Status:** [x] Complete

### Fix #8: 'Try it Free' CTA button alignment
- **File:** `templates/landing/sections/hero.html`
- **Issue:** CTA button too low on homepage
- **Fix:** Raised text block from `md:top-[136px]` to `md:top-[100px]`, tightened gaps
- **Status:** [x] Complete

### Fix #9: Pricing page image -> looping video
- **File:** `templates/landing/sections/faq.html`
- **Issue:** Dashboard preview image should be a looping animation
- **Fix:** Replaced static `<img>` with `<video autoplay loop muted playsinline>` using `.mp4` asset. Falls back to Figma static image for browsers without video support.
- **Asset:** `static/img/pricing/dashboard_preview.mp4` (2.8MB)
- **Status:** [x] Complete

### Fix #10: Website responsiveness when minimized
- **Files:** 8+ templates
- **Issue:** Website layout breaks at viewports below ~1230px due to `md:absolute` with hardcoded pixel offsets
- **Fix:** Systematically replaced absolute positioning with flexbox + percentage widths (`md:w-[45%]`/`md:w-[50%]`) across all two-column sections; converted pricing cards from flex to CSS grid; converted fixed `md:w-[Xpx]` to `max-w-[Xpx]`
- **Files modified:**
  - `why_choose_us.html` - flexbox conversion
  - `app_platform.html` - flexbox conversion
  - `apply_jobs.html` - flexbox conversion + accordion body width fix
  - `contact_us.html` - flexbox conversion
  - `faq.html` - pricing cards grid + dashboard preview max-width
  - `dashboard_look.html` - fixed widths to max-widths
  - `recruiter_quote.html` - fixed width to max-width
  - `tools_tabs.html` - image container max-widths + text wrapper max-widths
  - `testimonials.html` - fixed widths to max-widths
- **Status:** [x] Complete

---

## 2nd Priority Fixes (IN PARALLEL WITH OUTREACH)

### 2nd-Fix #1: Pricing card alignment
- **File:** `templates/landing/sections/faq.html`
- **Issue:** "Get started for" text should align at top with other plan name labels
- **Fix:** Added `min-h-[72px]` to all 5 pricing card header divs
- **Status:** [x] Complete

### 2nd-Fix #2: Logo Replacement
- **Files:** All templates with navbar + footer
- **Issue:** Replace current logo with new Paul-designed logo
- **Status:** [ ] Pending - waiting for new logo asset from Paul

### 2nd-Fix #3: Seat Addition via Billing Page
- **Files:** Billing templates + backend
- **Issue:** Cannot add seats via Billing Page
- **Status:** [ ] Pending - backend change needed

---

## Quality Review Fixes (Post-implementation)

### QR-1: Unescaped `&` in FAQ heading
- **File:** `templates/landing/sections/faq.html`
- **Fix:** `Product & Value` -> `Product &amp; Value`
- **Status:** [x] Complete

### QR-2: Raw en-dash characters in product.html
- **File:** `templates/product.html`
- **Fix:** Replaced 2 raw `--` characters with `&ndash;` HTML entities (lines 85, 113)
- **Status:** [x] Complete

### QR-3: Missing mobile height on tab panel images
- **File:** `templates/landing/sections/tools_tabs.html`
- **Fix:** Added `h-[200px]` to 4 non-Overview tab image wrappers for consistent mobile rendering
- **Status:** [x] Complete

### QR-4: Fixed widths in testimonials section
- **File:** `templates/landing/sections/testimonials.html`
- **Fix:** Converted `md:w-[1020px]` to `max-w-[1020px]` on 2 container divs
- **Status:** [x] Complete

### QR-5: Fixed widths in tools tab text wrappers
- **File:** `templates/landing/sections/tools_tabs.html`
- **Fix:** Converted `md:w-[435px]` to `md:max-w-[435px]` on 4 text wrapper divs
- **Status:** [x] Complete

---

## Change Log

| Date | Fix # | Description | Files Modified |
|------|-------|-------------|----------------|
| 2026-02-25 | #1 | Removed overflow-clip causing 'g' clipping in "Hiring" | `why_choose_us.html` |
| 2026-02-25 | #2 | De-capitalized and changed 'or' to '&' in auth card text | `why_choose_us.html` |
| 2026-02-25 | #3 | Bolded title, capitalized tabs, removed inner panel titles, fixed clipping | `tools_tabs.html` |
| 2026-02-25 | #4 | Title capitalization across 4 templates | `app_platform.html`, `testimonials.html`, `product.html`, `apply_jobs.html` |
| 2026-02-25 | #5 | Learn More href to arxiv paper | `about.html` |
| 2026-02-25 | #6 | Added font-bold to all job titles (16 elements total) | `testimonials.html`, `product.html` |
| 2026-02-25 | #7 | Added FAQ bullet for business owners/startup founders | `faq.html` |
| 2026-02-25 | #8 | Raised hero CTA position, tightened gaps | `hero.html` |
| 2026-02-25 | #9 | Prepared gif markup with fallback (needs asset) | `faq.html` |
| 2026-02-25 | #10 | Responsive overhaul: absolute -> flexbox, fixed -> max widths, grid pricing | 9 files (see Fix #10 details) |
| 2026-02-25 | 2nd-#1 | Pricing card header alignment via min-h | `faq.html` |
| 2026-02-25 | QR-1 | Escaped `&` in FAQ category heading | `faq.html` |
| 2026-02-25 | QR-2 | Replaced raw en-dashes with `&ndash;` entities | `product.html` |
| 2026-02-25 | QR-3 | Added mobile height to 4 tab panel image wrappers | `tools_tabs.html` |
| 2026-02-25 | QR-4 | Converted fixed widths to max-widths in testimonials | `testimonials.html` |
| 2026-02-25 | QR-5 | Converted fixed widths to max-widths in tools tab text | `tools_tabs.html` |
