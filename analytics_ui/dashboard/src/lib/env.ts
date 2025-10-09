const importMetaEnv = (typeof import.meta !== "undefined" ? import.meta.env : {}) as Record<string, any>;
const processEnv = (typeof process !== "undefined" ? process.env : {}) as Record<string, any>;

function readEnv(keys: string[]): string | undefined {
  for (const key of keys) {
    const fromImport = importMetaEnv?.[key];
    if (typeof fromImport === "string" && fromImport.length > 0) {
      return fromImport;
    }
    const fromProcess = processEnv?.[key];
    if (typeof fromProcess === "string" && fromProcess.length > 0) {
      return fromProcess;
    }
  }
  return undefined;
}

const rawBaseUrl = readEnv(["VITE_ANALYTICS_API_BASE", "NEXT_PUBLIC_ANALYTICS_API_BASE"])?.trim();
const normalizedBaseUrl = rawBaseUrl ? rawBaseUrl.replace(/\/$/, "") : "";
const defaultTenant = readEnv(["VITE_ANALYTICS_TENANT", "NEXT_PUBLIC_ANALYTICS_TENANT"]);

export const env = {
  analyticsBaseUrl: normalizedBaseUrl,
  defaultTenant: defaultTenant || undefined,
};
