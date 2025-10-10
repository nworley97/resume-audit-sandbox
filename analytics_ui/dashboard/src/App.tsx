import { useLocation } from "react-router-dom";
import { DashboardChrome } from "@/components/layout/dashboard-chrome";
import { AnalyticsOverview } from "@/features/analytics/overview/analytics-overview";
import { AnalyticsDetail } from "@/features/analytics/detail/analytics-detail";

export default function App() {
  const location = useLocation();
  
  // Parse the path to extract tenant and jobCode
  const pathParts = location.pathname.split('/').filter(Boolean);
  
  if (pathParts.length >= 3 && pathParts[0] && pathParts[1] === 'recruiter' && pathParts[2] === 'analytics') {
    const tenant = pathParts[0];
    
    if (pathParts.length === 3) {
      // /{tenant}/recruiter/analytics - overview page
      return (
        <DashboardChrome tenant={tenant}>
          <AnalyticsOverview tenant={tenant} />
        </DashboardChrome>
      );
    } else if (pathParts.length === 4) {
      // /{tenant}/recruiter/analytics/{jobCode} - detail page
      const jobCode = pathParts[3];
      return (
        <DashboardChrome tenant={tenant}>
          <AnalyticsDetail tenant={tenant} jobCode={jobCode} />
        </DashboardChrome>
      );
    }
  }
  
  // Default fallback
  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold text-foreground" style={{ fontFamily: "var(--font-heading), var(--font-sans)" }}>
        Analytics Dashboard
      </h1>
      <p>Invalid route. Please navigate to /tenant/recruiter/analytics</p>
    </div>
  );
}
