import { env } from "@/lib/env";
import {
  analyticsJobDetailSchema,
  analyticsSummaryResponseSchema,
  type AnalyticsJobDetail,
  type AnalyticsJobSummary,
} from "@/types/analytics";

function buildUrl(path: string, tenant: string) {
  const base = (env.analyticsBaseUrl || "").trim();
  const hasCustomBase = base.length > 0;
  const fallbackOrigin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
  const baseForUrl = hasCustomBase ? (base.endsWith("/") ? base : `${base}/`) : `${fallbackOrigin}/`;
  const pathForUrl = hasCustomBase ? path.replace(/^\/+/, "") : path.startsWith("/") ? path : `/${path}`;

  const url = new URL(pathForUrl, baseForUrl);
  if (tenant) {
    url.searchParams.set("tenant", tenant);
  }
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
