# iOS design alignment

Reference: [Figma design](https://www.figma.com/design/IhwBTlbcWYbBcKR9a8E4xc/Untitled?node-id=0-1).

The native implementation is accompanied by an interactive browser recreation at
`/mobile-demo/preview-798d342bc7cf47bb72d54e8ac0a46f93202e75050dd84abd`. That preview has now been updated separately;
it does not execute SwiftUI. The main web application and Flask API are unchanged.
See `../docs/mobile-preview.md` for preview coverage and verification.

## Coverage

All 43 reference screens were reviewed. Existing screens and shared components
were adapted rather than adding duplicate routes for each design state.
Typography, spacing, colors, and radii were interpreted from the visible Figma
frames; exact design-token values were not exported.

| Reference frames | Native implementation |
| --- | --- |
| 01–05: sign-in, validation, Google sign-in, reset and cancellation | `Views/Auth/SignInView.swift`, `ResetPasswordView.swift`, existing authentication service |
| 06: jobs | `Views/Jobs/JobPostingsView.swift`, `JobRowView.swift`, shared theme and stat cards |
| 07, 15: candidates in light and dark mode | `Views/Candidates/CandidatesView.swift`, `CandidateRowView.swift` |
| 08, 16: analytics in light and dark mode | `Views/Analytics/AnalyticsView.swift` |
| 09, 14: account in light and dark mode | `Views/Main/MainTabView.swift` |
| 10: job details | `Views/Jobs/JobDetailView.swift` |
| 11: create/edit job | `Views/Jobs/EditJobView.swift` |
| 12: add department | `AddDepartmentSheet` in `JobPostingsView.swift` |
| 17: notification preview | `Components/AppTopBar.swift` |
| 18: account settings | `Views/Settings/SettingsView.swift` |
| 19: billing | `Views/Settings/BillingView.swift` |
| 20: privacy | `Views/Settings/PrivacyPolicyView.swift` |
| 21: help | `Views/Settings/HelpSupportView.swift` |
| 22: candidates for a role | Filtered `CandidatesView` |
| 13, 23: job analytics and cross validation matrix | `Views/Analytics/JobAnalyticsView.swift` |
| 24: job actions | `JobActionsSheet` in `JobRowView.swift` |
| 25: department filter | `DepartmentFilterSheet` in `CandidatesView.swift` |
| 26: sort | `SelectionListSheet` in `EditJobView.swift` |
| 27: department selection | `DepartmentSelectSheet` in `EditJobView.swift` |
| 28: check email | `Views/Auth/CheckEmailView.swift` |
| 29: change password | `ChangePasswordView` in `SettingsView.swift` |
| 30: close role | `Views/Jobs/CloseRoleSheet.swift` |
| 31: edit department | `EditDepartmentSheet` in `JobPostingsView.swift` |
| 32: upgrade/highest plan | `UpgradeSheet` in `BillingView.swift` |
| 33: copied-link toast | `ToastView` in `JobPostingsView.swift`, account/job actions |
| 34–35: drafts and closed-role empty state | `JobPostingsView.swift` |
| 36: candidate profile | `Views/Candidates/CandidateProfileView.swift` |
| 37: all notifications | `Views/Notifications/NotificationsView.swift` |
| 38: candidate quick preview | `Views/Candidates/CandidateQuickPreviewSheet.swift` |
| 39–40: add finalists and private note | `AddFinalistsSheet`, `NoteEditorSheet` in `JobAnalyticsView.swift` |
| 41–42: date and time | `DateSheet`, `TimeSheet` in `EditJobView.swift` |
| 43: loading/error state | Jobs inline error and retry; existing screen loading/error handling |

## Behavior retained

- Counts, names, scores and plan details come from the API, not the Figma fixtures.
- Google consent UI remains controlled by iOS/the authentication provider.
- Billing actions continue to respect actual plan eligibility and grandfathered status.
- Hiring mutations and administrative settings retain their permission checks.
- Department/team management remains accessible through account settings.
- Date/time cancellation discards the draft selection. Password reset can return
  directly to sign-in. Candidate status feedback follows the API result.
- Sheets with potentially long lists scroll and support a larger detent.

## Native comparison and next-build checklist — September 30, 2026

The user selected **Mobile revisions** as the current design target. This supersedes
the original page for subsequent visual work. Reference page:
https://www.figma.com/design/IhwBTlbcWYbBcKR9a8E4xc/AlteraSF-Mobile?node-id=33-2

This pass compared the running native app, not the HTML browser recreation. The
user navigated the native simulator because automation could view its screen but
could not reliably send taps to the embedded player. No hiring, billing, profile,
or notification-read mutations were performed for this review. Appearance was
temporarily changed by the user to inspect dark mode.

### Evidence and limits

- **Visually compared in the native app:** Jobs/Open; Candidates overview;
  Analytics overview; role Analytics/Diamonds; Score Distribution and the visible
  portion of the matrix; Account/light and dark; Account Settings; Billing;
  notification preview sheet.
- **Design/source comparison only:** Job Detail and Add Job; candidate quick
  preview/profile; Help, Privacy. These are not native
  interaction passes.
- Figma frames inspected are 393 × 852. The current preview is an iPhone 17 Pro.
  This is a visual/structural review, not a same-viewport pixel-difference test.
- Live applicant counts, names, account details and billing usage legitimately
  differ from Figma fixtures. Do not hardcode design sample data into production.
- Smoothness, transition duration/easing, keyboard behavior, destructive actions,
  and all 43 states have **not** passed native regression testing. Cloud streaming
  latency must be distinguished from actual device/app performance.

### First: functional fixes discovered while reviewing the menus

- [ ] **F1 — Candidate pagination and counts.** `CandidatesViewModel.load` only
  requests the default first page; the API defaults to 50 rows. The view uses the
  fetched group size as its badge and the fetched array size in role headings.
  Implement pagination and authoritative role totals, keeping department filters
  and search consistent across pages. Pass: a role with more than 50 candidates
  exposes every result and shows the correct total before and after filtering.
- [ ] **F2 — Accurate score labels.** `DiamondLeaderboard` shows
  `claimValidityScore` as its main number and `relevancyScore` under a “Claim” label.
  Correct the label/value relationship and compare against the same candidate's
  profile and Q&A. The reference repeats this misleading secondary label; visual
  fidelity must not preserve inaccurate score semantics.
- [ ] **F3 — Job scheduling persistence.** Add Job exposes start/end date and time,
  but `EditJobView.save` omits them, and editing initializes them to today/+30 days.
  Complete the model/mobile API round trip and validate ordering/time zones.
  Pass: save, close, reopen and relaunch preserve the selected schedule. This may
  require a mobile API change; it is not merely a SwiftUI layout adjustment.
- [ ] **F4 — Unavailable email notifications.** User approved disabling the six
  switches for this iteration because the corresponding delivery system does not
  exist. Keep them off, disabled, and explained as unavailable. Delivery and
  server preference implementation are deferred. Pass: the native screen never
  implies that these email subscriptions are active or saved.
- [ ] **F5 — Failure feedback.** Candidate detail loading catches and hides errors;
  a missing preloaded candidate can remain on “Loading…” after a failure. Note
  Editor dismisses immediately while its asynchronous save is pending. Add retry
  and visible errors; retain an unsaved note until a successful save. Validate in
  a test environment without editing live candidate records.
- [ ] **F6 — Share behavior.** Analytics' share-icon action currently copies a
  hardcoded `jobs.alterasf.com` URL, unlike the tenant-aware application links used
  elsewhere. Verify the intended destination, use the correct link and provide
  the intended share sheet or explicit copied feedback.

### Second: shared native appearance

- [ ] **V1 — Bottom navigation and navigation controls.** Replace/adapt the iOS 26
  floating pill bar to match Figma's flat full-width bottom bar, outline icons,
  selected colors, labels and account avatar initials. Native screenshots show a
  plain circular account icon. Detail back/share buttons also inherit round
  system chrome absent from the reference. Check content insets so controls do
  not cover the last row or chart cells.
- [ ] **V2 — Measured design tokens.** Inspect actual Figma text/layer properties
  for font sizes, weights, line height, colors, radii and spacing; replace the
  previous estimated values. Several native supporting labels/cards are visibly
  more compact than the reference. Validate at the reference viewport first,
  then at smaller/larger sizes and increased text sizes.
- [ ] **V3 — Shared controls and dark mode.** Match button heights, outline icons,
  segmented controls, badges, dividers, sheet corners and background dimming.
  Dark Account changes to black canvas/charcoal cards correctly, but its spacing,
  icon colors and navigation still differ. Dark Candidates and Analytics need
  their own native comparison.

### Third: menu-by-menu visual work

| Menu | To do for the next visual pass | Pass condition |
| --- | --- | --- |
| Jobs | Align header-to-stat spacing, stat-card proportions, Create/Add Dept controls, segmented tabs, department headers and role-row spacing with frame 06. | Matching fixture/viewport aligns without truncation or bottom-bar overlap. |
| Jobs detail/forms | Check description visibility, information-card hierarchy, form label case, input heights and fixed action footer. Verify Draft/Closed/Error, job actions, department sheets, date and time sheets. | Each applicable state matches frames 10–12, 24, 27, 30–31, 34–35, 41–43 and retains correct persistence/cancel behavior. |
| Candidates | Increase card/text spacing to measured values, match score chips/avatar geometry and compact “Fit: High to low” filter copy. Preserve correct live results/counts. | Frame 07 at equal viewport/data, plus dark frame 15, agrees visually. |
| Candidate detail | Verify role list, filter/sort sheets, quick preview → profile transition, résumé/Q&A, score consistency and bottom actions. | Frames 22, 25–26, 36, 38 match; close/back and failure states work. |
| Analytics overview | Restore white title-header background in light mode; remove extra top spacing; use reference outline icons and larger status badges; align role cards and metrics. | Frame 08, then dark frame 16, agrees at the same viewport/data. |
| Analytics detail | Match header, stat/leaderboard typography and row spacing. Distribution currently defaults to Claim Validity with a segmented picker and gradient bars; frame 23 shows a fit-score subtitle and solid bars without that picker. Resolve this presentation while retaining access to needed metrics. | Frames 13 and 23 agree, matrix labels/cells remain readable and fully reachable, and displayed metrics are correctly labeled. |
| Analytics shortlist | Verify empty/populated finalists, Add Finalists, private Note, and save/cancel/error feedback. | Frames 39–40 match and no successful-save feedback appears before server success. |
| Account | Match profile-card/menu spacing, icon colors and row height; fix tab avatar. Verify name fallback from actual profile data rather than substituting the fixture's name. | Frames 09 and 14 agree for light/dark mode. |
| Account Settings | Compact section/row spacing to the reference; align section-label style, sheet header and Done control. Preserve authorized Departments/Team access while reconciling their placement with the design. | Frame 18 matches and intended account actions remain accessible. |
| Billing | For the applicable grandfathered state, separate Members and Seats/Unlimited as in frame 19 instead of Status plus a combined used/limit value. Align plan/usage-card spacing, feature outline icons and navigation. | Frame 19 matches with true billing values; other plan states remain correct. No real subscription changes during visual QA. |
| Help / Privacy / Password | Match FAQ rows, privacy shield outline, header/button placement and password/reset states. | Frames 20–21, 29 and relevant auth frames pass native checks and links open correctly. |
| Notifications | Native preview opens lower than frame 17, uses rounder system sheet/header styling and smaller row text. Match height, typography and controls; check full list and dismiss transition. | Frames 17 and 37 match; opening for inspection does not silently mark everything read. |
| Authentication | Compare current revised sign-in, validation, reset/check-email and cancellation screens. Keep provider-controlled Google UI distinct from app-owned screens. | Frames 01–05 and 28 pass on the native build, including keyboard/validation states. |

### Fourth: rebuild and prove the changes

- [ ] Build a deterministic native visual-test path with fictional fixtures for
  all 43 reference states; do not rely on live production records for repeatable
  screenshots or mutation tests. Preserve normal authentication in release builds.
- [ ] Capture matched 393 × 852 reference screenshots and native screenshots, then
  produce overlays/differences per screen. Record any deliberate exceptions.
- [ ] Exercise every sheet's opening/closing, navigation push/back, tab switching,
  keyboard, scrolling, filter changes, toast and cancellation. Record/reference
  animation timing and easing before calling motion “exact”; respect Reduce Motion.
- [ ] Profile cold/warm tab loads and scrolling on an actual device/TestFlight.
  Candidates currently waits for jobs/departments before fetching its candidate
  list; measure this sequence and repeated loads instead of blaming stream lag.
- [ ] Test small/large screens, larger text, light/dark appearance, empty/loading/
  offline/error states, long names and permission-based actions.
- [ ] Rebuild in Codemagic, repeat this menu audit, then validate a signed device
  build/TestFlight installation. Publication remains gated on functional fixes
  and the remaining visual/interaction checks, not compilation alone.

No implementation changes or new cloud build were made during this comparison.

## First implementation iteration — September 30, 2026

The following changes are implemented, pending a new Xcode build and native
screen comparison. Audit checkboxes remain open until their pass conditions are
verified; this is not a claim of exact visual or motion parity.

| Area | Implemented | Still to verify |
| --- | --- | --- |
| F1 Candidates | Server totals per role across all pages; stable pagination; department and role-title search; explicit Load more; stale-response protection; concurrent initial jobs/candidates loading and visible role-load failures. | Native filter/search/page transitions, long lists, and offline retries. Grouped overview shows up to three loaded candidates per role; View opens the paginated role list. |
| F2/F6 Analytics | Diamond secondary score correctly labeled Fit; tenant-aware system ShareLink; fit-only solid score-distribution bars. | Score/card presentation and share sheet destination in the rebuilt app. |
| F3 Scheduling | Explicit-offset UTC mobile API round trip; native schedule initialization/persistence; invalid ranges rejected; salary retained when editing. Unscheduled existing roles stay unscheduled unless a date/time is explicitly accepted. | Native date/time Cancel/Done, relaunch, and local timezone display. Legacy timezone-less records are interpreted as UTC; the old web form stores no timezone information. |
| F4/F5 Settings and errors | Six unavailable email toggles disabled with explanatory copy; detail load error/retry; note save awaited, unsaved text retained on failure. | Native failure behavior and disabled-control accessibility. |
| V1 Navigation | Flat full-width bottom bar, outline symbols, initials avatar; visited tab navigation stacks retained. | Native safe areas, pushed-screen navigation and keyboard. Detail toolbar system chrome still needs a separate pass. |
| V2 Typography | Bundled Poppins Bold page titles, Figtree Regular/Medium/SemiBold/Bold text; revised text colors and 14-point card radius. | Actual font loading, baselines, wrapping and Dynamic Type on the native build. |
| Menu styling | Candidate 96-point minimum cards, 18-point names and 15-point roles; Analytics white header/outline icons/larger status badges; grandfathered Billing Members/Seats; notification sheet height/text; Settings row sizing. | Compare every touched menu at equal data/viewport, then dark mode. These changes are not pixel-certified. |

Measured Figma properties: Candidates title Poppins Bold 32/38, #0A0A0A;
candidate name Figtree SemiBold 18; supporting role Figtree Regular 15,
#8E8E93; candidate card 361 x 96 with radius 14 in a 393 x 852 frame.
Font sources: Google Fonts `ofl/figtree` and `ofl/poppins`; OFL licenses are
bundled alongside the font files. `scripts/prepare_fonts.py` reproduces the
static Figtree weights using fontTools 4.60.1.

Local verification: all 39 Python regression tests pass against isolated SQLite,
including the new pagination/tenant-isolation/filtering and scheduling contracts.
Modified Swift sources pass the portable parser, all 44 sources remain included
in the Xcode project, and whitespace checks pass. Windows cannot run the Xcode
type checker. The screenshot script now prefers a 393 x 852 iPhone model when
available; automatic capture still covers sign-in only. Fictional authenticated
fixtures, all 43 states, exact animation timing and signed-device QA remain open.

Next gate: rebuild this iteration in Codemagic, inspect the actual native output,
then continue the checklist. The team uses pay-as-you-go build minutes; a new
build has not yet been started for this iteration.

## Verification status

Modified Swift files pass the portable tree-sitter syntax check, and all 44 Swift
sources have entries in the Xcode project's Sources build phase. Whitespace
validation passes. Two untouched HEAD files (`AppConfig.swift` and
`JobsViewModel.swift`) produce four existing parser diagnostics and are reported
separately, not counted as validated.

Run the portable check with Python, `tree-sitter==0.26.0` and
`tree-sitter-swift==0.7.3` installed:

```sh
python ios/scripts/validate_sources.py
git diff --check -- ios
```

On September 30, 2026, Codemagic successfully built commit `932c4b0` with Xcode
26.6 for the iOS simulator (arm64 and x86_64), launched the app, and produced
light/dark sign-in screenshot artifacts. This verifies native compilation and
launch, not all-screen visual parity. The first simulator boot logged a migration
failure but subsequently launched the app and completed both captures.

Build: https://codemagic.io/app/6abd48f2feb1fabba1e12f0f/build/6abd49cc083ff0a9a53acb15

**Still required:** inspect the screenshot artifacts against Figma, capture and
compare authenticated screens, test native interactions and animations, and
validate a signed device archive/TestFlight build.

## Mac verification checklist

1. Open `ios/AlteraSF.xcodeproj`, resolve packages, select an available iPhone
   simulator and build. Use the sandbox API configuration described in `README.md`.
2. Compare each reference frame at the matching viewport in light/dark appearance.
   Check small iPhones, large text, keyboard overlap, safe areas and sheet scrolling.
3. Exercise sign-in success/failure, Google cancellation, reset submission and
   return to sign-in; verify password-change success and failure.
4. Check jobs open/draft/closed states, filters, editing, department selection,
   date/time Cancel/Done, copy links and notifications navigation.
5. Check role candidate counts, sort/search, preview-to-profile navigation, résumé
   download, finalist/archive API success and failure, and analytics note saving.
6. Confirm role permissions, account appearance persistence, billing eligibility,
   support/privacy links and logout. Use sandbox records for mutations.
7. Record any screenshot differences and resolve them before TestFlight release.

The original alignment pass did not run Xcode. The later Codemagic simulator
build above succeeded; no signed archive or TestFlight upload has been performed.
