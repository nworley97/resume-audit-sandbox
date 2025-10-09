import { createRoot } from "react-dom/client";
import { App } from "./App";
import type { AnalyticsConfig } from "./types";

function hydrateConfig(el: HTMLElement): AnalyticsConfig {
  const raw = el.dataset.config;
  if (!raw) {
    throw new Error("Missing analytics configuration on root element");
  }

  try {
    const parsed = JSON.parse(raw) as AnalyticsConfig;
    if (!parsed.tenantSlug) {
      throw new Error("tenantSlug missing in config");
    }
    return parsed;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown parsing error";
    throw new Error(`Failed to parse analytics config: ${message}`);
  }
}

const rootElement = document.getElementById("analytics-root");

if (rootElement) {
  try {
    const config = hydrateConfig(rootElement as HTMLElement);
    const root = createRoot(rootElement);
    root.render(<App config={config} />);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    rootElement.innerHTML = `
      <div class="rounded-xl border border-rose-200 bg-rose-50 p-6 type-body text-rose-700">
        ${message}
      </div>
    `;
  }
} else {
  console.warn("Analytics root element not found. Skipping mount.");
}
