"use client";

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ResponsiveBar } from "@nivo/bar";
import type { LucideIcon } from "lucide-react";
import { Activity, CheckCircle2, Clock3, Sparkles } from "lucide-react";
import { getAnalyticsDetail } from "@/lib/api";
import { useAnalyticsStore } from "@/stores/analytics-store";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import type { AnalyticsJobDetail } from "@/types/analytics";
import { env } from "@/lib/env";
import { LocalNavBar } from "@/components/layout/local-nav-bar";
// ET-12: Import Tremor components
import { CompletionFunnelChart } from "@/components/analytics/tremor-funnel";
import { RetentionHeatmap } from "@/components/analytics/retention-heatmap";

function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value);
}

function formatScore(value: number | null | undefined, digits = 1) {
  return Number.isFinite(value) ? (value as number).toFixed(digits) : "0.0";
}


function KPIGrid({ detail }: { detail: AnalyticsJobDetail }) {
  const { totals, roi } = detail;
  const timeSaved = roi.calculated.time_saved_hours;  // ET-12: Keep 1 decimal place

  const cards: Array<{
    title: string;
    value: string | number;
    caption: string;
    icon: LucideIcon;
  }> = [
    {
      title: "Total Applications",
      value: formatNumber(totals.applied),
      caption: "across this posting",
      icon: Activity,
    },
    {
      title: "Diamonds Found",
      value: totals.diamonds_found,
      caption: "high-potential talent",
      icon: Sparkles,
    },
    {
      title: "Completion Rate",
      value: `${detail.summary.completion_rate.toFixed(1)}%`,  // ET-12: 1 decimal place
      caption: "completed verification",
      icon: CheckCircle2,
    },
    {
      title: "Time Efficiency",
      value: timeSaved < 1 ? `${Math.round(timeSaved * 60)}m` : `${timeSaved.toFixed(1)}h`,  // ET-12: 1 decimal place
      caption: "saved vs manual",
      icon: Clock3,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card, index) => (
        <motion.div
          key={card.title}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.05 }}
          className="rounded-lg border border-border/60 bg-card/95 p-4"
        >
          {/* ET-12: 1st row (top): icon | title */}
          <div className="flex items-center gap-2 mb-3">
            <span className="rounded-lg bg-primary/10 p-2 text-primary">
              {(() => {
                const Icon = card.icon;
                return <Icon className="size-4" />;
              })()}
            </span>
            <div className="text-xs text-muted-foreground">{card.title}</div>
          </div>
          {/* ET-12: 2nd row (bottom): corresponding values */}
          <div className="text-2xl font-semibold text-foreground">{card.value}</div>
        </motion.div>
      ))}
    </div>
  );
}

function DiamondsCarousel({ detail, tenant }: { detail: AnalyticsJobDetail; tenant: string }) {
  const diamonds = detail.diamonds;

  if (!diamonds.length) {
    return (
      <div className="space-y-4">
        <div className="mb-2">
          <h3 className="text-lg font-semibold text-foreground">Diamonds in the Rough</h3>
          <p className="text-sm text-muted-foreground">
            Top high-potential candidates automatically identified based on Cross Matrix Validation
          </p>
        </div>
        <div className="rounded-lg border-dashed border-border/70 bg-muted/40 p-6 text-center">
          <Sparkles className="mx-auto size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground mt-2">
            No diamonds surfaced yet. Calibrate verification to uncover high-signal candidates.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="mb-2">
        <h3 className="text-lg font-semibold text-foreground">Diamonds in the Rough</h3>
        <p className="text-sm text-muted-foreground">
          Top {diamonds.length} high-potential candidates automatically identified based on Cross Matrix Validation
        </p>
      </div>

      <div className="overflow-x-auto overflow-y-hidden -mx-6 px-6 py-2">
        <div className="flex gap-4">
          {diamonds.map((diamond, idx) => (
            <motion.a
              key={diamond.id}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.05 }}
              href={`/${tenant}/recruiter/candidate/${diamond.id}`}
              className="group min-w-[280px] cursor-pointer overflow-hidden rounded-2xl border border-border/40 bg-card/95 p-5 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-brand/20 hover:shadow-lg hover:shadow-brand/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <img
                    src="/favicon-32x32.png"
                    alt="Diamond"
                    width={16}
                    height={16}
                    className="size-4"
                  />
                  <Badge variant="outline" className="text-xs font-medium text-gray-700 border-gray-300">
                    #{idx + 1}
                  </Badge>
                </div>
                <div className="h-8 w-8" />
              </div>

              <p className="mb-4 text-base font-semibold text-slate-900">{diamond.name}</p>
              <div className="mb-4 space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Claim Validity</span>
                  <span className="font-medium">{formatScore(diamond.claim_validity_score)}/5</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Relevancy</span>
                  <span className="font-medium">{formatScore(diamond.relevancy_score)}/5</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Combined</span>
                  <span className="font-semibold text-gray-700">{formatScore(diamond.combined_score)}/5</span>
                </div>
              </div>
            </motion.a>
          ))}
        </div>
      </div>
    </div>
  );
}

// 
function DistributionCharts({ detail }: { detail: AnalyticsJobDetail }) {
  // ET-12: Both distributions use 7 bins: [No Score, ≥0, ≥1, ≥2, ≥3, ≥4, 5]
  const claimLabels = ["No Score", "≥0", "≥1", "≥2", "≥3", "≥4", "5"];
  const claimData = detail.distributions.claim_validity.map((value, index) => ({
    bucket: claimLabels[index] ?? String(index),
    candidates: value,
  }));

  const relevancyLabels = ["No Score", "≥0", "≥1", "≥2", "≥3", "≥4", "5"];
  const relevancyData = detail.distributions.relevancy.map((value, index) => ({
    bucket: relevancyLabels[index] ?? String(index),
    candidates: value,
  }));

  // ET-12: Get candidate data from heatmap cells for hover tooltips
  const getCandidatesForBucket = (bucket: string, isClaim: boolean) => {
    if (!detail.heatmap?.cells) return [];

    const target = (() => {
      if (bucket === "No Score") return 0;
      const numericPortion = bucket.replace(/[^\d.]/g, "");
      const parsed = Number(numericPortion);
      return Number.isNaN(parsed) ? null : parsed;
    })();
    if (target == null) return [];

    return detail.heatmap.cells
      .filter(cell => {
        const value = isClaim ? cell.claim : cell.relevancy;
        if (target === 0) {
          return value === 0;
        }
        return Math.abs(value - target) < 0.001;
      })
      .flatMap(cell => cell.candidates || [])
      .filter(candidate => candidate.claim_validity_score > 0 && candidate.relevancy_score > 0);
  };

  const charts = [
    {
      title: "Claim Validity Distribution",
      data: claimData,
      color: "#7dd3fc", // sky-300
      stats: detail.statistics.claim_validity,
    },
    {
      title: "Job Fit Distribution",
      data: relevancyData,
      color: "#8b5cf6", // violet-500
      stats: detail.statistics.relevancy,
    },
  ];

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-foreground">Score Distributions</h3>
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {charts.map((chart) => (
          <div key={chart.title} className="rounded-lg border border-border/60 bg-card/95 p-4">
            <div className="mb-3">
              <h4 className="font-medium text-foreground">{chart.title}</h4>
              <p className="text-xs text-muted-foreground">
                Mean {chart.stats.mean ?? "—"} • Median {chart.stats.median ?? "—"} • σ {chart.stats.std_dev ?? "—"}
              </p>
              <p className="text-xs text-muted-foreground/70 italic mt-0.5">
                Statistics calculated from scored candidates only
              </p>
            </div>
            <div className="h-48">
              <ResponsiveBar
                data={chart.data}
                keys={["candidates"]}
                indexBy="bucket"
                margin={{ top: 10, right: 20, bottom: 40, left: 20 }}
                padding={0.4}
                colors={[chart.color]}
                enableGridY={false}
                valueScale={{ type: "linear", min: 0 }}
                label={(bar) => `${Math.round(bar.value as number)}`}
                labelSkipHeight={12}
                labelTextColor="var(--foreground)"
                valueFormat={(value) => `${Math.round(value as number)}`}
                axisLeft={null}
                axisBottom={{
                  tickSize: 0,
                  tickPadding: 8,
                  tickRotation: 0,
                }}
                enableLabel={true}
                isInteractive={false}
                theme={{
                  text: {
                    fontSize: 12,
                    fill: "var(--muted-foreground)",
                  },
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// 
function RoiSummary({ detail }: { detail: AnalyticsJobDetail }) {
  const { roi } = detail;
  return (
    <div className="space-y-4">
      {/* ET-12: ROI header with total saved highlight aligned right, matching Funnel typography */}
      <div className="text-left lg:text-right">
        <h3 className="text-lg font-semibold text-foreground">ROI Impact</h3>
        <div className="mt-2">
          <div className="text-2xl font-bold text-gray-800">${formatNumber(Math.round(roi.calculated.cost_saved))}</div>
          <div className="text-xs text-muted-foreground">Total Saved</div>
        </div>
      </div>

      {/* ET-12: Accordion layout for ROI metrics */}
      <Accordion type="multiple" defaultValue={["time-saved", "screening-speed", "efficiency"]} className="w-full">
        {/* 1. Time Saved - Highest priority */}
        <AccordionItem value="time-saved" className="border border-gray-200 rounded-lg mb-2">
          <AccordionTrigger className="px-4 py-3 hover:no-underline">
            <div className="flex w-full flex-col gap-2 text-left sm:flex-row sm:items-center sm:justify-between sm:text-right">
              <span className="text-sm font-medium text-foreground">Time Saved</span>
              <span className="text-lg font-bold text-gray-800">{roi.calculated.time_saved_hours.toFixed(1)}h</span>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-3">
            <div className="text-xs text-muted-foreground">
              Time saved compared to manual screening process
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* 2. Speed Improvement - Second priority */}
        {roi.calculated.speed_improvement && (
          <AccordionItem value="screening-speed" className="border border-gray-200 rounded-lg mb-2">
            <AccordionTrigger className="px-4 py-3 hover:no-underline">
              <div className="flex w-full flex-col gap-2 text-left sm:flex-row sm:items-center sm:justify-between sm:text-right">
                <span className="text-sm font-medium text-foreground">Screening Speed</span>
                <span className="text-lg font-bold text-gray-800">{roi.calculated.speed_improvement}×</span>
              </div>
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-3">
              <div className="text-xs text-muted-foreground">
                Speed improvement over traditional screening methods
              </div>
            </AccordionContent>
          </AccordionItem>
        )}

        {/* 3. Efficiency - Third priority */}
        <AccordionItem value="efficiency" className="border border-gray-200 rounded-lg mb-2">
          <AccordionTrigger className="px-4 py-3 hover:no-underline">
            <div className="flex w-full flex-col gap-2 text-left sm:flex-row sm:items-center sm:justify-between sm:text-right">
              <span className="text-sm font-medium text-foreground">Human Review Load</span>
              <span className="text-lg font-bold text-gray-800">{roi.calculated.efficiency_percentage}%</span>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-3">
            <div className="text-xs text-muted-foreground">
              {roi.variables.diamonds_count}/{roi.variables.total_applicants} candidates reviewed
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

export function AnalyticsDetail({
  tenant,
  jobCode,
}: {
  tenant: string;
  jobCode: string;
}) {
  const navigate = useNavigate();
  const { setSelectedJob, setTenant: persistTenant } = useAnalyticsStore();

  useEffect(() => {
    persistTenant(tenant);
    setSelectedJob(jobCode);
    return () => setSelectedJob(undefined);
  }, [jobCode, persistTenant, setSelectedJob, tenant]);

  const { data, isLoading, isError, refetch, error } = useQuery({
    queryKey: ["analytics-detail", tenant, jobCode],
    queryFn: () => getAnalyticsDetail(jobCode, tenant),
    enabled: Boolean(jobCode && tenant),
    retry: (failureCount, err) => {
      if (err instanceof Error && err.message.includes("404")) {
        return false;
      }
      return failureCount < 2;
    },
  });

  const title = data?.jd?.title || jobCode;

  return (
    <div className="space-y-0">
      {/* ET-12: Sticky Local Navigation Bar */}
      <LocalNavBar
        title={title}
        subtitle={`${data?.summary.total_candidates || 0} total applicants`}
        showBackButton={true}
        onBackClick={() => {
          setSelectedJob(undefined);
          navigate(`/${tenant}/recruiter/analytics`);
        }}
        showRefreshButton={false}
        showDateRange={false}
        showFilters={false}
      />
      
      <section className="bg-white p-6">

      {isError ? (
        <Card className="rounded-3xl border-destructive/60 bg-destructive/10 p-6">
          <CardHeader className="p-0">
            <CardTitle className="text-base text-destructive">
              Unable to load analytics detail
            </CardTitle>
          </CardHeader>
          <CardContent className="mt-2 space-y-3 p-0 text-sm text-destructive/80">
            <p>
              {error instanceof Error && error.message.includes("404")
                ? "No analytics found for this job code in the selected tenant."
                : `Check that analytics_service.py is running and reachable at ${env.analyticsBaseUrl}.`}
            </p>
            <Button variant="outline" size="sm" onClick={() => refetch()} className="hover:bg-[#F2F1EE] cursor-pointer">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {isLoading ? (
        <div className="space-y-6">
          <Skeleton className="h-32 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : null}

      {!data || isLoading ? null : (
        <div className="space-y-0">
          {/* 1. Summary 4 cards 4 columns (PC: 4*1) (responsive: 2*2 -> 1*4) */}
          <div className="border-b border-gray-200 pb-6">
            <KPIGrid detail={data} />
          </div>
          
          {/* 2. Diamonds: 1 full row (responsive: max 2 items then Show More button) */}
          <div className="border-b border-gray-200 py-6">
            <DiamondsCarousel detail={data} tenant={tenant} />
          </div>
          
          {/* 3. Cross Validation Matrix: 1 full row */}
          <div className="border-b border-gray-200 py-6">
            <RetentionHeatmap detail={data} tenant={tenant} />
          </div>
          
          {/* 4. Score Distribution: 2 rows used (2 charts side by side) */}
          <div className="border-b border-gray-200 py-6">
            <DistributionCharts detail={data} />
          </div>
          
          {/* 5. Verification Funnel + ROI Impact: same row on PC, separated on Phone */}
          <div className="border-b border-gray-200 py-6">
            <div className="grid gap-8 grid-cols-1 lg:grid-cols-3">
              {/* Funnel Chart - 2/3 width on PC, full width on phone */}
              <div className="lg:col-span-2">
                <CompletionFunnelChart 
                  data={data.completion_funnel || []} 
                  completionRate={data.summary?.completion_rate || 0} 
                />
              </div>
              
              {/* Vertical separator line */}
              <div className="hidden lg:block lg:col-span-1">
                <div className="h-full border-l border-gray-200 pl-8">
                  <RoiSummary detail={data} />
                </div>
              </div>
            </div>
          </div>
          
          {/* ROI Summary - Phone only, below Funnel */}
          <div className="lg:hidden py-6">
            <RoiSummary detail={data} />
          </div>
        </div>
      )}
      </section>
    </div>
  );
}
