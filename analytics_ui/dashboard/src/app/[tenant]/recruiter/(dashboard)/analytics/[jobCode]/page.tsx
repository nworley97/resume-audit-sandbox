import { AnalyticsDetail } from "@/features/analytics/detail/analytics-detail";

export const dynamic = "force-dynamic";

export default async function AnalyticsDetailPage({
  params,
}: {
  params: Promise<{ tenant: string; jobCode: string }>;
}) {
  const { tenant, jobCode } = await params;
  return <AnalyticsDetail tenant={tenant} jobCode={jobCode} />;
}
