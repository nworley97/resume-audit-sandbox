# 📊 Altera Analytics Dashboard

Enhanced applicant analytics dashboard for verifying deep-tech talent capabilities with data-driven insights.

## ✨ Features (ET-12)

### Two-Stage Workflow
- **Job Posting Overview**: Grid view of all job postings with key metrics
- **Individual Analytics**: Deep-dive analytics per job posting

### Key Capabilities
- 💎 **Diamonds in the Rough**: Auto-identify high-potential candidates
- 📈 **Cross Validation Matrix**: 5×5 quality heatmap (Claim Validity × Job Fit)
- 📊 **Score Distributions**: Statistical analysis with mean/median/std dev
- 🎯 **Completion Funnel**: Track candidate journey with dropoff insights
- 💰 **ROI Impact**: Time/cost savings calculation with executive summaries

---

## 🚀 Quick Start

### Prerequisites
```bash
# Install dependencies
npm install

# Ensure analytics service is running (separate terminal)
cd ../..
python analytics_service.py  # Runs on port 5055
```

### Development
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

### Environment Variables
Create `.env.local` (optional):
```bash
# Default tenant for auto-redirect
NEXT_PUBLIC_ANALYTICS_TENANT=acme

# Analytics API endpoint (default: http://127.0.0.1:5055)
NEXT_PUBLIC_ANALYTICS_API_BASE=http://localhost:5055
```

### Access Dashboard
Navigate to: `http://localhost:3000/{tenant}/recruiter/analytics`

Example: `http://localhost:3000/acme/recruiter/analytics`

---

## 🏗️ Tech Stack

### Core Framework
- **Next.js 15** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS v4** - Utility-first styling
- **Turbopack** - Fast bundler

### UI & Design
- **shadcn/ui** - Accessible component primitives
- **Radix UI** - Headless UI components
- **Framer Motion** - Animation library
- **Lucide Icons** - Icon library
- **Geist Font** - Typography

### Data & State
- **TanStack Query** - Server state management
- **Zustand** - Client state store
- **Zod** - Runtime validation
- **Nivo** - Data visualization

### Testing
- **Vitest** - Unit testing
- **Testing Library** - Component testing

---

## 📁 Project Structure

```
src/
├── app/                          # Next.js App Router
│   ├── [tenant]/                 # Tenant-scoped routes
│   │   └── recruiter/
│   │       └── (dashboard)/
│   │           ├── analytics/    # Job overview
│   │           └── [jobCode]/    # Job detail
│   ├── globals.css               # Global styles + theme vars
│   └── layout.tsx                # Root layout
├── components/
│   ├── ui/                       # shadcn/ui primitives
│   ├── layout/                   # Layout components
│   └── providers/                # Context providers
├── features/
│   └── analytics/
│       ├── overview/             # Job posting overview
│       └── detail/               # Individual analytics
├── lib/
│   ├── api.ts                    # API client
│   ├── env.ts                    # Environment config
│   └── utils.ts                  # Utility functions
├── hooks/                        # Custom React hooks
├── stores/                       # Zustand stores
└── types/                        # TypeScript types
```

---

## 🎨 Styling & Theming

### Design System
- **Color Palette**: Neutral base with blue primary
- **Border Radius**: Consistent rounded-2xl/3xl
- **Typography**: Geist Sans (headings), Geist Mono (code)
- **Spacing**: 4px grid system

### CSS Variables
All theme variables defined in `src/app/globals.css`:
```css
:root {
  --primary: oklch(0.623 0.214 259.815);
  --muted-foreground: oklch(0.552 0.016 285.938);
  --border: oklch(0.92 0.004 286.32);
  /* ... */
}
```

### Dark Mode
`.dark` class automatically supported via CSS variables.

---

## 🔌 API Integration

### Backend Service
Flask microservice at `http://127.0.0.1:5055`

### Endpoints
```
GET /analytics/summary?tenant={slug}
→ Returns array of job summaries

GET /analytics/job/{jd_code}?tenant={slug}
→ Returns detailed analytics for job
```

### Data Flow
1. **TanStack Query** fetches from API
2. **Zod schemas** validate responses
3. **TypeScript types** ensure type safety
4. **Components** render validated data

---

## 📊 Analytics Features Detail

### Job Posting Overview
- **Grid Layout**: 3-col (desktop) / 2-col (tablet) / 1-col (mobile)
- **Job Cards**: Title, status, applicants, diamonds, department, posted date
- **Interactions**: Click to navigate, hover effects, keyboard accessible

### KPI Cards
- Total Applications
- Diamonds Found
- Completion Rate
- Time Efficiency
- All with trend indicators

### Diamonds Section
- **Criteria**: Claim Validity ≥4 AND Relevancy ≥4
- **Display**: Horizontal scroll carousel
- **Sorting**: Combined score (descending)
- **Components**: Avatar, ranking badge, scores, action button

### Cross Validation Matrix
- **5×5 Grid**: Relevancy (rows) × Claim Validity (cols)
- **Cell Click**: Opens dialog with candidate list
- **Color Coding**: 
  - Blue: Ideal (Claim ≥4, Fit 5)
  - Green: Strong (3≤ Claim <4, Fit 4)
  - Orange: Satisfactory (2≤ Claim <3, Fit 3)
  - Yellow: Weak (1≤ Claim <2, Fit 1-2)

### Score Distributions
- **Charts**: Bar charts with Nivo
- **Statistics**: Mean, Median, Std Dev
- **Interactivity**: Hover tooltips

### Completion Funnel
- **4 Stages**: Applied → Screened → Started → Completed
- **Metrics**: Count and percentage per stage
- **Insights**: Alert when dropoff >42%

### ROI Summary
- **Formula**: `[(N×T) - (n×t)] × $50/hour`
- **Metrics**: Time saved, cost saved, speed improvement
- **Executive Summary**: Copy-ready snippet

---

## 🧪 Testing

### Run Tests
```bash
# Unit tests
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage
```

### Test Files
- `src/stores/__tests__/analytics-store.test.ts`

---

## 🛠️ Development Commands

```bash
# Development server
npm run dev

# Production build
npm run build

# Start production server
npm start

# Type checking
npm run type-check

# Linting
npm run lint

# Format code
npm run format
```

---

## 🔒 Error Handling

### States Covered
- ✅ Loading states (skeleton UI)
- ✅ Error states (retry buttons)
- ✅ Empty states (helpful messages)
- ✅ Network failures (graceful degradation)
- ✅ 404 handling (tenant/job not found)

### CORS
Backend CORS already configured for local development.

---

## 📈 Performance

### Optimization Techniques
- React Query caching (30s stale time)
- Lazy loading with `dynamic`
- Image optimization (Next.js built-in)
- Code splitting (route-based)
- Memoization for expensive calculations

### Metrics
- Page load: <2s
- Page transition: <1s
- Chart rendering: <500ms
- Hover interactions: <100ms

---

## ♿ Accessibility

- ✅ ARIA labels on interactive elements
- ✅ Keyboard navigation support
- ✅ Focus-visible ring states
- ✅ Color contrast compliance
- ✅ Screen reader friendly structure
- ✅ Semantic HTML

---

## 📚 Documentation

- **Implementation Guide**: `ET-12-IMPLEMENTATION.md`
- **PRD**: `/rules/feature-et12-prd.md`
- **Collaboration Rules**: `/rules/role-collaboration-rules.md`

---

## 🐛 Troubleshooting

### Dashboard shows "Unable to load analytics"
1. Verify analytics service is running: `python analytics_service.py`
2. Check service is on port 5055
3. Confirm CORS is enabled
4. Verify tenant exists in database

### Heatmap not rendering
1. Check browser console for errors
2. Verify API returns 5×5 matrix
3. Ensure axes are [1,2,3,4,5] format

### Styles look broken
1. Ensure `globals.css` has `:root` (not `::root`)
2. Check Tailwind is running
3. Verify CSS variables are defined

---

## 📝 License

Proprietary - Altera

---

## 🤝 Contributing

1. Read PRD: `/rules/feature-et12-prd.md`
2. Follow collaboration workflow in `/rules/role-collaboration-rules.md`
3. Add ticket ID (ET-12) to all comments
4. Write tests before implementation
5. Use semantic commit messages

---

**Built with ❤️ by the Altera Team**
