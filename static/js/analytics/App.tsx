import { useEffect, useMemo, useState } from "react";
import { SummaryList } from "./components/SummaryList";
import { JobDetailPanel } from "./components/JobDetail";
import type { AnalyticsConfig, JobDetail, SummaryItem } from "./types";

interface AppProps {
  config: AnalyticsConfig;
}

interface FetchState<T> {
  data?: T;
  loading: boolean;
  error?: string;
}

export function App({ config }: AppProps) {
  const [summaryState, setSummaryState] = useState<FetchState<SummaryItem[]>>({ loading: true });
  const [detailState, setDetailState] = useState<FetchState<JobDetail>>({ loading: false });
  const [selectedJob, setSelectedJob] = useState<string | undefined>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function loadSummary() {
      setSummaryState({ loading: true });
      try {
        const res = await fetch(
          `${config.summaryEndpoint}?tenant=${encodeURIComponent(config.tenantSlug)}`,
          {
            credentials: "include",
            signal: controller.signal,
          },
        );

        if (!res.ok) {
          throw new Error(`Failed to load summary (${res.status})`);
        }

        const payload = (await res.json()) as SummaryItem[];
        if (!cancelled) {
          setSummaryState({ data: payload, loading: false });
          if (!payload.length) {
            setSelectedJob(undefined);
          } else if (!selectedJob) {
            setSelectedJob(payload[0].jd_code);
          } else if (payload.every((item) => item.jd_code !== selectedJob)) {
            setSelectedJob(payload[0].jd_code);
          }
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unable to load analytics";
          setSummaryState({ loading: false, error: message });
        }
      }
    }

    loadSummary();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [config.summaryEndpoint, config.tenantSlug, refreshKey]);

  useEffect(() => {
    if (!selectedJob) {
      setDetailState({ loading: false });
      return;
    }

    const controller = new AbortController();
    let cancelled = false;

    async function loadDetail() {
      setDetailState({ loading: true });
      try {
        const url = `${config.jobDetailEndpoint}/${encodeURIComponent(selectedJob)}?tenant=${encodeURIComponent(config.tenantSlug)}`;
        const res = await fetch(url, {
          credentials: "include",
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`Failed to load job analytics (${res.status})`);
        }

        const payload = (await res.json()) as JobDetail;
        if (!cancelled) {
          setDetailState({ data: payload, loading: false });
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unable to load job analytics";
          setDetailState({ loading: false, error: message });
        }
      }
    }

    loadDetail();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [config.jobDetailEndpoint, config.tenantSlug, selectedJob, detailRefreshKey]);

  const summaryData = summaryState.data ?? [];

  const currentJobTitle = useMemo(() => {
    if (!selectedJob || !summaryData.length) return "";
    const match = summaryData.find((item) => item.jd_code === selectedJob);
    return match?.jd_title || match?.jd_code || "";
  }, [selectedJob, summaryData]);

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 rounded-3xl bg-white p-6 shadow-sm ring-1 ring-gray-200 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="type-heading-md text-title">Analytics overview</h1>
          <p className="type-body-sm text-slate/80 mt-1">
            Review pipeline performance, diamonds found, and score distributions across {config.tenantName}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {currentJobTitle && (
            <span className="hidden rounded-full bg-gray-100 px-3 py-1 type-caption text-slate/70 md:inline-flex">
              Viewing: {currentJobTitle}
            </span>
          )}
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 px-4 py-2 type-body-sm text-title hover:bg-gray-50"
            onClick={() => {
              setRefreshKey((key) => key + 1);
              if (selectedJob) {
                setDetailRefreshKey((key) => key + 1);
              }
            }}
          >
            Refresh
          </button>
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-[minmax(0,320px)_1fr]">
        <aside className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="type-heading-sm text-title">Job postings</h2>
            <span className="type-caption text-slate/60">{summaryData.length}</span>
          </div>
          <SummaryList
            items={summaryData}
            selected={selectedJob}
            onSelect={setSelectedJob}
            loading={summaryState.loading}
            error={summaryState.error}
          />
        </aside>

        <section>
          <JobDetailPanel
            detail={detailState.data}
            loading={detailState.loading}
            error={detailState.error}
            tenantName={config.tenantName}
          />
        </section>
      </div>
    </div>
  );
}
