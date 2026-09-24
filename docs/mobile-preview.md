# iOS browser preview

The existing slug-gated route `/mobile-demo/preview-61d7c4a9f2e8` now serves the
Figma-aligned iOS walkthrough. `MOBILE_DEMO_SLUG` may override that slug in Render.
The existing blueprint access rules and no-store/no-index headers are unchanged.

## Files and local use

- `templates/mobile_demo.html`: device container and external preview controls.
- `static/css/mobile-preview.css`: native-style surfaces, sizing and light/dark colors.
- `static/js/mobile-preview.js`: 43 selectable design states and isolated demo interactions.
- `scripts/serve-mobile-preview.cjs`: optional local server, bound to loopback only,
  serving only these three files at port 5057.

Run `node scripts/serve-mobile-preview.cjs`, then open
`http://127.0.0.1:5057/mobile-demo/preview-61d7c4a9f2e8`.
The normal Flask app serves the same files without a build step.

The selector outside the device makes all 43 Figma states accessible. Ordinary
app navigation also connects tabs, candidate profiles, settings and sheets.
Search, filtering, sorting, finalist selection, private notes, date/time selection,
job creation, close/archive confirmations and dark mode work with session-only
sample data. Reset demo restores the initial fixtures. Authentication and billing
are simulated. No live recruiting, authentication or payment endpoints are called.

## Verification

- Browser-selected all 43 screens: rendered content, no horizontal device overflow,
  no JavaScript error/warning logs.
- Exercised candidate search, quick preview, full profile and Original résumé view.
- Exercised calendar selection, finalist addition and private-note saving.
- Reviewed rendered jobs, dark account and candidate-sheet layouts against Figma.
- Updated the existing Playwright walkthrough plus a 43-screen smoke test in
  `tests/e2e.spec.js`. The full repository Playwright suite was not run in this
  workspace because its Node packages and Flask test environment are unavailable.
- `node --check` validates the preview JS, local server and updated test file.

## Fidelity and deployment limits

This is an HTML recreation, not an Xcode simulator or generated SwiftUI build.
Reference layout, hierarchy, colors, copy and states are reproduced, but native
system dialogs, fonts and controls can differ by browser/OS. Sample résumé text,
long lists and analytics content are illustrative. Exact pixel parity across all
43 screens has not been certified; native Xcode review remains separate.

Changes must be deployed to the Render service serving the posted preview before
that URL changes. Local verification alone does not update Render.

## Prototype motion refinement

Reviewed the supplied prototype at `/proto/IhwBTlbcWYbBcKR9a8E4xc/Untitled`.
The preview now uses a lighter 10% backdrop, explicit sheet heights corresponding
to the visible reference, and centered department forms. The Google consent mock
uses a centered dialog. Sheet entrance/dismissal and page/toast transitions are
approximations: 260 ms for sheet entrance, 180 ms for dismissal/navigation, with
an ease-out curve. Exact Figma timing/easing properties were not accessible.

In-place sheet updates retain focus and scroll without recreating the animated
container. Cancel/Escape restore focus after dismissal. Visible handles support
pointer drag-to-dismiss; this gesture is a native-style fallback, not a verified
Figma gesture specification. Reduced-motion preference disables animation.
