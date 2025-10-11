import { env } from "@/lib/env";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AnalyticsState {
  tenant?: string;
  selectedJobCode?: string;
  setTenant: (tenant: string) => void;
  setSelectedJob: (code: string | undefined) => void;
}

export const useAnalyticsStore = create<AnalyticsState>()(
  persist(
    (set) => ({
      tenant: env.defaultTenant,
      selectedJobCode: undefined,
      setTenant: (tenant) => set({ tenant }),
      setSelectedJob: (selectedJobCode) => set({ selectedJobCode }),
    }),
    {
      name: "analytics-preferences",
      version: 1,
    }
  )
);
