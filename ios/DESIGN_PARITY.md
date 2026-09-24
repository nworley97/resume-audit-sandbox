# iOS design alignment

Reference: [Figma design](https://www.figma.com/design/IhwBTlbcWYbBcKR9a8E4xc/Untitled?node-id=0-1).

The native implementation is accompanied by an interactive browser recreation at
`/mobile-demo/preview-61d7c4a9f2e8`. That preview has now been updated separately;
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
| 06, 13: jobs in light and dark mode | `Views/Jobs/JobPostingsView.swift`, `JobRowView.swift`, shared theme and stat cards |
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
| 23: job analytics | `Views/Analytics/JobAnalyticsView.swift` |
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

**Still required:** Swift type checking, an Xcode build, native interaction tests,
and rendered screenshot comparison. This Windows workspace has no Xcode or iOS
simulator, so this is an implementation pass, not certified visual parity.

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

No build, archive, upload or deployment was performed during this implementation.
