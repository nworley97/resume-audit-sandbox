# AlteraSF iOS app

The iOS client and Flask API live in the same repository, but they deploy separately:

- `app.py` and `ios_api.py` deploy as the web/API service.
- `ios/AlteraSF.xcodeproj` builds in Xcode and ships through App Store Connect/TestFlight.
- The `Dev` branch is for sandbox testing. Promote tested changes to `main` for production.

## First-time Xcode setup

1. On a Mac, open `ios/AlteraSF.xcodeproj` in Xcode and allow Swift packages to resolve.
2. Select the **AlteraSF** target, then **Signing & Capabilities**.
3. Choose your Apple Developer team. Keep automatic signing enabled.
4. Confirm that `com.alterasf.dashboard` belongs to that team. Change the bundle ID if it does not.
5. Confirm the Google iOS OAuth client uses the same bundle ID and URL scheme as `Info.plist`.

The repository intentionally does not commit an Apple `DEVELOPMENT_TEAM`; each developer or CI environment supplies its own signing identity.

## API environments

`API_BASE_URL` is a target build setting and is copied into `Info.plist` as `APIBaseURL`:

- Debug defaults to `http://localhost:5050`.
- Release defaults to `https://app.alterasf.com`.

For a physical phone, `localhost` means the phone itself. Set the Debug value to your Mac's LAN address (for example, `http://192.168.1.20:5050`) or to the HTTPS sandbox URL. Keep production HTTPS-only.

Before a mobile test, verify these API endpoints in the selected environment:

- `/api/mobile/auth/me`
- `/api/mobile/<tenant>/jobs`
- `/api/mobile/<tenant>/candidates`

An unauthenticated response from `/auth/me` is expected; a 404 means the server does not include `ios_api.py` or its blueprint registration.

## TestFlight deployment

1. Merge the tested API and iOS changes from `Dev` into `main`.
2. In Xcode, increment **Version** for a release and **Build** for every upload.
3. Select **Any iOS Device (arm64)**, then **Product → Archive**.
4. In Organizer, run validation and choose **Distribute App → App Store Connect → Upload**.
5. In App Store Connect, add the build to an internal TestFlight group first.
6. Smoke-test login, job lists, candidate details, resume download, status changes, and analytics against production before expanding the tester group.

Never put an OpenAI, AWS, database, Stripe, or Apple private key in the iOS project. The app should only call authenticated Flask endpoints; secrets remain on the server.

## Common failures

- **No signing team:** choose your Apple Developer team in Signing & Capabilities.
- **Bundle ID unavailable:** register a unique App ID and update the Google iOS OAuth client to match.
- **Phone cannot reach local API:** replace `localhost` with the Mac's LAN address and allow local network access.
- **Login succeeds on web but not iOS:** check HTTPS, cookie persistence, the mobile blueprint, and tenant membership.
- **Archive upload rejected:** increment the build number and resolve the exact validation item in Xcode Organizer.
