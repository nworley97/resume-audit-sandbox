import type { SummaryItem } from "../types";

interface SummaryListProps {
  items: SummaryItem[];
  selected?: string;
  onSelect: (code: string) => void;
  loading: boolean;
  error?: string;
}

export function SummaryList({ items, selected, onSelect, loading, error }: SummaryListProps) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-center type-body text-slate">
        Loading analytics…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center type-body text-rose-700">
        {error}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-center type-body text-slate">
        No analytics data yet. Once candidates apply, metrics will appear here.
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {items.map((item) => {
        const isActive = selected === item.jd_code;
        return (
          <button
            key={item.jd_code}
            type="button"
            onClick={() => onSelect(item.jd_code)}
            className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-primary/60 ${
              isActive
                ? "border-primary/30 bg-primary/5 shadow-sm"
                : "border-gray-200 bg-white hover:bg-gray-50"
            }`}
          >
            <div>
              <div className="type-heading-sm text-title">
                {item.jd_title || item.jd_code || "Untitled role"}
              </div>
              <div className="type-body-sm text-slate/80 mt-1 flex flex-wrap gap-x-3 gap-y-1">
                {item.department && <span>{item.department}</span>}
                {item.team && <span>{item.team}</span>}
                {item.status && <span className="uppercase tracking-wide text-xs text-slate/60">{item.status}</span>}
                {item.posted && (
                  <span className="text-xs text-slate/60">
                    Posted {new Date(item.posted).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="type-body text-title">{item.applicants}</div>
              <div className="type-caption text-slate/70">Applicants</div>
              <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 type-chip text-emerald-700">
                <span className="font-semibold">{item.diamonds_found}</span>
                <span>diamonds</span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
