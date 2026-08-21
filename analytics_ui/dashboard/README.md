# Altera Analytics Dashboard

The recruiter analytics interface is a React 18 application built with Vite. It is bundled into `dist/` and served by the main Flask application.

## Local setup

From this directory:

```bash
npm install
npm run dev
```

Vite starts on `http://localhost:3000` and proxies `/analytics` requests to the main application on `http://localhost:8000`.

Optional settings can be placed in `.env.local`:

```bash
VITE_ANALYTICS_TENANT=acme
VITE_ANALYTICS_API_BASE=http://localhost:8000
```

Open `http://localhost:3000/{tenant}/recruiter/analytics`, replacing `{tenant}` with a real tenant slug.

## Verification

Run these checks before committing dashboard changes:

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm audit
```

The production build is written to `dist/`. The repository tracks this output because Flask serves it directly.

## Structure

```text
src/
├── main.tsx                     Vite entry point
├── App.tsx                      React Router routes
├── globals.css                  shared styling and theme variables
├── components/                  UI, layout, and chart components
├── features/analytics/          overview and job-detail screens
├── lib/                         API, environment, and utility helpers
├── stores/                      Zustand state
└── types/                       analytics response schemas
```

The dashboard uses React Router, TanStack Query, Zustand, Zod, Radix UI, Nivo, and Tailwind CSS. It does not use Next.js.

## Main routes

- `/{tenant}/recruiter/analytics` — job overview
- `/{tenant}/recruiter/analytics/{jobCode}` — job detail

The API client validates analytics responses with Zod before rendering them. Loading, empty, error, and retry states are handled in the feature screens.

## Troubleshooting

- If analytics cannot load, confirm the main Flask application is running on port 8000 and that the tenant exists.
- If styles or scripts look stale, run `npm run build` and confirm the updated files under `dist/` are included in the commit.
- If a dependency changes, run `npm audit` and all verification commands above before rebuilding `dist/`.
