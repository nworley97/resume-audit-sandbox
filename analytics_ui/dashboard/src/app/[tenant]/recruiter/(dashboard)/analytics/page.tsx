import { AnalyticsOverview } from "@/features/analytics/overview/analytics-overview";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ tenant: string }>;
}) {
  const { tenant } = await params;
  return <AnalyticsOverview tenant={tenant} />;
}
