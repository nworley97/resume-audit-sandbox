import { describe, expect, it } from "vitest";
import { useAnalyticsStore } from "@/stores/analytics-store";
import { env } from "@/lib/env";

describe("analytics store", () => {
  it("should initialise with default tenant when configured", () => {
    const state = useAnalyticsStore.getState();
    if (env.defaultTenant) {
      expect(state.tenant).toBe(env.defaultTenant);
    } else {
      expect(state.tenant).toBeUndefined();
    }
  });

  it("should update tenant and selected job", () => {
    useAnalyticsStore.setState({ tenant: "test-tenant", selectedJobCode: undefined });
    useAnalyticsStore.getState().setSelectedJob("JD-100");

    const updated = useAnalyticsStore.getState();
    expect(updated.tenant).toBe("test-tenant");
    expect(updated.selectedJobCode).toBe("JD-100");
  });
});
