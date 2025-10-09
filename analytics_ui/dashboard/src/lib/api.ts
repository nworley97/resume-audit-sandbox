import { env } from "@/lib/env";
import {
  analyticsJobDetailSchema,
  analyticsSummaryResponseSchema,
  type AnalyticsJobDetail,
  type AnalyticsJobSummary,
} from "@/types/analytics";

function buildUrl(path: string, tenant: string) {
  const url = new URL(`${env.analyticsBaseUrl}${path}`);
  url.searchParams.set("tenant", tenant);
  return url.toString();
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit) {
  const res = await fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request failed (${res.status}): ${body || res.statusText}`);
  }

  return (await res.json()) as T;
}

export async function getAnalyticsSummary(tenant: string) {
  const data = await fetchJson<unknown>(buildUrl("/analytics/summary", tenant));
  return analyticsSummaryResponseSchema.parse(data) as AnalyticsJobSummary[];
}

export async function getAnalyticsDetail(jdCode: string, tenant: string) {
  const data = await fetchJson<unknown>(
    buildUrl(`/analytics/job/${encodeURIComponent(jdCode)}`, tenant)
  );
  return analyticsJobDetailSchema.parse(data) as AnalyticsJobDetail;
}

export type { AnalyticsJobSummary, AnalyticsJobDetail };
