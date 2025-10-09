export const env = {
  analyticsBaseUrl:
    process.env.NEXT_PUBLIC_ANALYTICS_API_BASE?.replace(/\/$/, "") ||
    "http://127.0.0.1:5055",
  defaultTenant: process.env.NEXT_PUBLIC_ANALYTICS_TENANT || undefined,
};
