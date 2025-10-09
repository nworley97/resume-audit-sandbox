import type { JobDetail } from "../types";

interface JobDetailProps {
  detail?: JobDetail;
  loading: boolean;
  error?: string;
  tenantName: string;
}

const EMPTY_STATE = (
  <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center">
    <div className="type-heading-sm text-title">Select a job to view analytics</div>
    <p className="mt-2 type-body-sm text-slate/80">
      Choose a posting from the list to see applicant flow, diamonds, and score distributions.
    </p>
  </div>
);

export function JobDetailPanel({ detail, loading, error, tenantName }: JobDetailProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="h-5 w-48 animate-pulse rounded bg-gray-200" />
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, idx) => (
            <div key={idx} className="rounded-lg border border-gray-200 p-4">
              <div className="h-4 w-20 animate-pulse rounded bg-gray-200" />
              <div className="mt-3 h-6 w-16 animate-pulse rounded bg-gray-200" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 type-body text-rose-700">
        {error}
      </div>
    );
  }

  if (!detail) {
    return EMPTY_STATE;
  }

  const stats = [
    {
      label: "Applicants",
      value: detail.totals.applied,
      tone: "text-title",
    },
    {
      label: "Diamonds",
      value: detail.totals.diamonds_found,
      tone: "text-emerald-600",
    },
    {
      label: "Completion",
      value: `${detail.totals.completion_pct.toFixed(1)}%`,
      tone: "text-primary",
    },
  ];

  const claimDistribution = detail.distributions.claim_validity;
  const relevancyDistribution = detail.distributions.relevancy;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <header className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="type-heading-sm text-title">{detail.jd.title || detail.jd.code}</h2>
            <div className="type-body-sm text-slate/70">
              {detail.jd.department && <span>{detail.jd.department}</span>}
              {detail.jd.team && <span className="ml-2">· {detail.jd.team}</span>}
            </div>
            <div className="type-caption text-slate/60 mt-1">
              Updated {new Date(detail.summary.last_updated).toLocaleString()} • {tenantName}
            </div>
          </div>
          <div className="rounded-lg bg-primary/10 px-3 py-1 type-caption text-primary">
            Status: {detail.jd.status ?? "unknown"}
          </div>
        </header>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="type-caption text-slate/70">{stat.label}</div>
              <div className={`mt-2 type-heading-md ${stat.tone}`}>{stat.value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h3 className="type-heading-sm text-title">Score distribution</h3>
          <div className="mt-4 space-y-4">
            <div>
              <div className="type-body-sm text-slate/70">Claim validity</div>
              <BarList values={claimDistribution} />
            </div>
            <div>
              <div className="type-body-sm text-slate/70">Relevancy</div>
              <BarList values={relevancyDistribution} tone="emerald" />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h3 className="type-heading-sm text-title">Diamonds roster</h3>
          {detail.diamonds.length ? (
            <ul className="mt-4 space-y-3">
              {detail.diamonds.map((cand) => (
                <li key={cand.id} className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 type-caption text-primary">
                      {cand.initials}
                    </span>
                    <div>
                      <div className="type-body text-title">{cand.name || "Unnamed"}</div>
                      <div className="type-caption text-slate/70">
                        Claim {cand.claim_validity_score} • Relevancy {cand.relevancy_score}
                      </div>
                    </div>
                  </div>
                  <div className="type-body-sm text-title/80">
                    {cand.combined_score ? `${cand.combined_score}%` : ""}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 type-body-sm text-slate/70">
              No diamonds yet. Keep reviewing applicants to uncover high-signal matches.
            </p>
          )}
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h3 className="type-heading-sm text-title">Process funnel</h3>
          <ol className="mt-4 space-y-3">
            {detail.completion_funnel.map((stage) => (
              <li key={stage.stage} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2 bg-gray-50">
                <span className="type-body text-title">{stage.stage}</span>
                <span className="type-body-sm text-slate/70">
                  {stage.count} • {stage.percentage}%
                </span>
              </li>
            ))}
          </ol>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6">
          <h3 className="type-heading-sm text-title">ROI snapshot</h3>
          <div className="mt-4 space-y-3">
            <MetricRow label="Time saved" value={`${detail.roi.calculated.time_saved_hours.toFixed(2)} hrs`} />
            <MetricRow label="Cost saved" value={`$${detail.roi.calculated.cost_saved.toLocaleString()}`} />
            <MetricRow
              label="Efficiency"
              value={`${detail.roi.calculated.efficiency_percentage.toFixed(1)}%`}
            />
            {detail.roi.calculated.speed_improvement && (
              <MetricRow
                label="Speed improvement"
                value={`${detail.roi.calculated.speed_improvement.toFixed(1)}× faster`}
              />
            )}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-6">
        <h3 className="type-heading-sm text-title">Heatmap overview</h3>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left">
            <thead>
              <tr>
                <th className="type-caption text-slate/60">Relevancy ↓ / Claim →</th>
                {detail.heatmap.axes.claim_validity.map((claim) => (
                  <th key={claim} className="type-caption text-slate/60 px-2 text-center">
                    {claim}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {detail.heatmap.axes.relevancy
                .slice()
                .reverse()
                .map((rel) => (
                  <tr key={rel}>
                    <th className="type-caption text-slate/70 py-2 pr-3">{rel}</th>
                    {detail.heatmap.axes.claim_validity.map((claim) => {
                      const cell = detail.heatmap.cells.find(
                        (c) => c.relevancy === rel && c.claim === claim,
                      );
                      const total = cell ? cell.candidates.length : 0;
                      const tone = total >= 4 ? "bg-emerald-50" : total >= 2 ? "bg-amber-50" : "bg-gray-50";
                      return (
                        <td key={claim} className="px-2 py-1 text-center">
                          <span className={`inline-flex min-w-[2.5rem] justify-center rounded-full px-2 py-0.5 type-caption ${tone}`}>
                            {total}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function BarList({ values, tone = "slate" }: { values: number[]; tone?: "slate" | "emerald" }) {
  const max = Math.max(...values, 1);
  const palette = tone === "emerald" ? "bg-emerald-500" : "bg-primary";

  return (
    <ul className="mt-2 space-y-2">
      {values.map((count, idx) => (
        <li key={idx} className="flex items-center gap-3">
          <span className="type-caption text-slate/60 w-6 text-right">{idx}</span>
          <div className="h-2 flex-1 rounded-full bg-gray-100">
            <div
              className={`${palette} h-2 rounded-full transition-all`}
              style={{ width: `${Math.max((count / max) * 100, 4)}%` }}
            />
          </div>
          <span className="type-caption text-slate/80 w-10 text-right">{count}</span>
        </li>
      ))}
    </ul>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      <span className="type-body text-title/80">{label}</span>
      <span className="type-body-sm text-title">{value}</span>
    </div>
  );
}
