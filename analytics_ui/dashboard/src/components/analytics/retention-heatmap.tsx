"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { AnalyticsJobDetail } from "@/types/analytics";

interface RetentionHeatmapProps {
  detail: AnalyticsJobDetail;
}

type NormalizedRelevancyAxis = {
  index: number;
  label: string;
  value: number | null;
  isNoScore: boolean;
};

type NormalizedClaimAxis = {
  index: number;
  label: string;
  bucket: number | null;
  isNoScore: boolean;
};

function normalizeRelevancyAxis(axis: unknown, idx: number): NormalizedRelevancyAxis {
  if (typeof axis === "number") {
    const isNoScore = axis === 0;
    return {
      index: idx,
      label: isNoScore ? "No Score" : `${axis}/5`,
      value: axis,
      isNoScore,
    };
  }

  if (axis && typeof axis === "object") {
    const obj = axis as {
      index?: number;
      label?: string;
      value?: number | null;
      bucket?: number;
      is_no_score?: boolean;
    };

    const value = typeof obj.value === "number"
      ? obj.value
      : typeof obj.bucket === "number"
        ? obj.bucket
        : null;

    const label = typeof obj.label === "string"
      ? obj.label
      : value !== null
        ? `${value}/5`
        : `Range ${obj.index ?? idx}`;

    const isNoScore = Boolean(
      obj.is_no_score ?? label.toLowerCase().includes("no score") ?? value === 0
    );

    return {
      index: typeof obj.index === "number" ? obj.index : idx,
      label,
      value,
      isNoScore,
    };
  }

  return {
    index: idx,
    label: `Range ${idx}`,
    value: null,
    isNoScore: true,
  };
}

function normalizeClaimAxis(axis: unknown, idx: number): NormalizedClaimAxis {
  if (typeof axis === "number") {
    const isNoScore = axis === 0;
    return {
      index: idx,
      label: isNoScore ? "No Score" : `Claim ${axis}`,
      bucket: axis,
      isNoScore,
    };
  }

  if (axis && typeof axis === "object") {
    const obj = axis as {
      index?: number;
      label?: string;
      bucket?: number;
      value?: number;
      is_no_score?: boolean;
    };

    const bucket = typeof obj.bucket === "number"
      ? obj.bucket
      : typeof obj.value === "number"
        ? obj.value
        : null;

    const label = typeof obj.label === "string"
      ? obj.label
      : bucket !== null
        ? `Claim ${bucket}`
        : `Bucket ${obj.index ?? idx}`;

    const isNoScore = Boolean(
      obj.is_no_score ?? label.toLowerCase().includes("no score") ?? bucket === 0
    );

    return {
      index: typeof obj.index === "number" ? obj.index : idx,
      label,
      bucket,
      isNoScore,
    };
  }

  return {
    index: idx,
    label: `Bucket ${idx}`,
    bucket: null,
    isNoScore: true,
  };
}

export function RetentionHeatmap({ detail }: RetentionHeatmapProps) {
  const formatScore = (value: number | null | undefined) =>
    Number.isFinite(value) ? (value as number).toFixed(1) : "0.0";
  
  // Add safety checks
  if (!detail?.heatmap?.matrix) {
    return (
      <Card className="rounded-3xl border-border/60 bg-card/95">
        <CardHeader className="p-6">
          <CardTitle>Cross Validation Matrix</CardTitle>
          <CardDescription>No heatmap data available</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const totals = detail.totals?.applied || 1;

  const rawClaimAxes = detail.heatmap.axes?.claim_validity ?? [];
  const normalizedClaimAxes = rawClaimAxes.map(normalizeClaimAxis);
  const claimAxes = [...normalizedClaimAxes].sort((a, b) => {
    if (a.isNoScore && b.isNoScore) return 0;
    if (a.isNoScore) return 1;
    if (b.isNoScore) return -1;
    return (b.bucket ?? -Infinity) - (a.bucket ?? -Infinity);
  });

  const rawRelevancyAxes = detail.heatmap.axes?.relevancy ?? [];
  const normalizedRelevancyAxes = rawRelevancyAxes.map(normalizeRelevancyAxis);
  const relevancyAxes = [...normalizedRelevancyAxes].sort((a, b) => {
    if (a.isNoScore && b.isNoScore) return 0;
    if (a.isNoScore) return 1;
    if (b.isNoScore) return -1;
    return (b.value ?? -Infinity) - (a.value ?? -Infinity);
  });

  // Create cells map - filter only completed candidates (no "No Score" entries)
  const cellsMap = new Map<string, { count: number; candidates: { id: string; name: string; initials: string; claim_validity_score: number; relevancy_score: number; }[] }>();
  
  if (detail.heatmap?.cells) {
    detail.heatmap.cells.forEach((cell) => {
      // ET-12: Only show completed candidates (filter out No Score entries)
      const completedCandidates = cell.candidates?.filter(candidate => 
        candidate.claim_validity_score > 0 && candidate.relevancy_score > 0
      ) || [];
      
      cellsMap.set(`${cell.relevancy}-${cell.claim}`, {
        count: completedCandidates.length,
        candidates: completedCandidates.map((candidate) => ({
          ...candidate,
          claim_validity_score: Number.isFinite(candidate.claim_validity_score)
            ? Number(candidate.claim_validity_score)
            : candidate.claim_validity_score,
          relevancy_score: Number.isFinite(candidate.relevancy_score)
            ? Number(candidate.relevancy_score)
            : candidate.relevancy_score,
        })),
      });
    });
  }

  const getCellColor = (
    relAxis: NormalizedRelevancyAxis,
    claimAxis: NormalizedClaimAxis,
    count: number
  ) => {
    const ideal = "bg-sky-300 text-sky-950 hover:bg-sky-400";
    const strong = "bg-violet-300 text-violet-900 hover:bg-violet-400";
    const satisfactory = "bg-teal-300 text-teal-900 hover:bg-teal-400";
    const weak = "bg-red-300 text-red-900 hover:bg-red-400";
    const isNoScoreCell = relAxis.isNoScore || claimAxis.isNoScore;
    const relValue = relAxis.value ?? 0;
    const claimBucket = claimAxis.bucket ?? 0;

    if (isNoScoreCell) {
      return count === 0
        ? "bg-slate-50 text-slate-300 dark:bg-slate-950 dark:text-slate-700"
        : "bg-slate-200 text-slate-700 hover:bg-slate-300 dark:bg-slate-800 dark:text-slate-300";
    }

    if (count === 0) return "bg-slate-50 text-slate-300 dark:bg-slate-900 dark:text-slate-600";

    const isIdeal = claimBucket === 5 && relValue === 5;
    const isStrong =
      (relValue === 4 && claimBucket >= 4) ||
      (relValue === 5 && claimBucket === 4);
    const isSatisfactory = claimBucket >= 3 && relValue >= 3;

    if (isIdeal) return ideal;
    if (isStrong) return strong;
    if (isSatisfactory) return satisfactory;
    return weak;
  };

  return (
    <div className="space-y-4">
      {/* ET-12: Title and legend without card border */}
      <div className="border-b border-border/60 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              Cross Validation Matrix
            </h3>
            <p className="text-sm text-muted-foreground">
              Applicant quality matrix: Claim Validity vs Job Fit Score
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge className="rounded-full bg-sky-100 text-sky-800 px-3 py-1">Ideal</Badge>
            <Badge className="rounded-full bg-violet-100 text-violet-800 px-3 py-1">Strong</Badge>
            <Badge className="rounded-full bg-teal-100 text-teal-800 px-3 py-1">Satisfactory</Badge>
            <Badge className="rounded-full bg-red-100 text-red-800 px-3 py-1">Weak</Badge>
          </div>
        </div>
      </div>

      {/* ET-12: Matrix without card container, compressed height, no cell spacing */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-background px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-foreground">
                <div className="flex flex-col items-center">
                  <span>FIT</span>
                  <span>↓</span>
                  <span>CLAIM</span>
                  <span>→</span>
                </div>
              </th>
              {claimAxes.map((claim) => (
                <th key={`claim-${claim.index}`} className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {claim.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {relevancyAxes.map((rel) => (
              <tr key={`rel-${rel.index}`}>
                <td className="sticky left-0 z-10 bg-background px-4 py-1 text-left text-xs font-bold text-foreground">
                  {rel.isNoScore ? "No Score" : `Fit ${rel.label}`}
                </td>
                {claimAxes.map((claim) => {
                  const key = `${rel.index}-${claim.index}`;
                  const cellData = cellsMap.get(key);
                  const count = (cellData?.candidates?.length) ?? 0;
                  const pct = Math.round((count / totals) * 100);
                  const fitLabel = rel.isNoScore ? "Fit No Score" : `Fit ${rel.label}`;
                  const claimLabel = claim.isNoScore ? "Claim No Score" : `Claim ${claim.label}`;
                  const colorClass = getCellColor(rel, claim, count);

                  return (
                    <td key={key} className="p-0">
                      <HoverCard>
                        <HoverCardTrigger asChild>
                          <button
                            className={cn(
                              "flex h-14 w-full flex-col items-center justify-center border-0 transition-all",
                              colorClass
                            )}
                            aria-label={`${count} candidates with ${fitLabel} and Claim ${claimLabel}`}
                          >
                            <span className="text-base font-bold">{count}</span>
                            <span className="text-xs opacity-80">{pct}%</span>
                          </button>
                        </HoverCardTrigger>
                        {count > 0 && (
                          <HoverCardContent className="w-80">
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <h4 className="font-semibold text-foreground">
                                  {count} Candidates
                                </h4>
                                <Badge variant="outline" className="text-xs">
                                  {claimLabel} • {fitLabel}
                                </Badge>
                              </div>
                              <ScrollArea className="h-48">
                                <div className="space-y-2">
                                  {cellData?.candidates
                                    ?.sort((a, b) => {
                                      // Sort by Claim (desc) → Fit (desc) → Name (asc)
                                      const claimDiff = (b.claim_validity_score ?? 0) - (a.claim_validity_score ?? 0);
                                      if (claimDiff !== 0) {
                                        return claimDiff;
                                      }
                                      const relevancyDiff = (b.relevancy_score ?? 0) - (a.relevancy_score ?? 0);
                                      if (relevancyDiff !== 0) {
                                        return relevancyDiff;
                                      }
                                      return a.name.localeCompare(b.name);
                                    })
                                    .map((candidate) => (
                                      <div
                                        key={candidate.id}
                                        className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 p-2"
                                      >
                                        <div className="flex items-center gap-2">
                                          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                                            {candidate.initials}
                                          </div>
                                          <span className="text-sm font-medium text-foreground">
                                            {candidate.name}
                                          </span>
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                          {formatScore(candidate.claim_validity_score)}/5 • {formatScore(candidate.relevancy_score)}/5
                                        </div>
                                      </div>
                                    ))}
                                </div>
                              </ScrollArea>
                            </div>
                          </HoverCardContent>
                        )}
                      </HoverCard>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
