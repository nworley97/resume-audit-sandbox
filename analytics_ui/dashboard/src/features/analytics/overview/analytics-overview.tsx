"use client";

import { useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getAnalyticsSummary } from "@/lib/api";
import { useAnalyticsStore } from "@/stores/analytics-store";
import type { AnalyticsJobSummary } from "@/types/analytics";
import { Sparkles } from "lucide-react";
import { LocalNavBar } from "@/components/layout/local-nav-bar";
import { formatNumber } from "@/lib/utils";

function statusBadge(status?: string | null) {
  if (!status) return <Badge variant="outline" className="text-xs">Draft</Badge>;
  const normalized = status.toLowerCase();
  if (normalized === "open") {
    // ET-12: Blue badge with 15% opacity background and 100% blue text
    return <Badge className="bg-blue-500/15 text-blue-600 hover:bg-blue-500/25 text-xs">Open</Badge>;
  }
  if (normalized === "closed") {
    // ET-12: Light gray background with dark gray text for Closed status
    return <Badge className="bg-gray-200 text-gray-700 hover:bg-gray-300 text-xs">Closed</Badge>;
  }
  return <Badge variant="outline" className="text-xs">{status}</Badge>;
}

function JobCard({
  job,
  index,
  tenant,
}: {
  job: AnalyticsJobSummary;
  index: number;
  tenant: string;
}) {
  const navigate = useNavigate();
  const { setSelectedJob } = useAnalyticsStore();

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
    >
      {/* ET-12: Job card with Figma-style design */}
      <Card className="group overflow-hidden rounded-2xl border border-border/40 bg-card/95 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-brand/20 hover:shadow-brand/10">
        <button
          type="button"
          onClick={() => {
            setSelectedJob(job.jd_code);
            navigate(`/${tenant}/recruiter/analytics/${job.jd_code}`);
          }}
          className="flex h-full w-full flex-col items-stretch text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label={`View analytics for ${job.jd_title || job.jd_code}`}
        >
          <CardHeader className="gap-0 space-y-0 p-5">
            {/* ET-12: Job Title and Status badge on same line with more spacing */}
            <div className="flex items-start justify-between gap-4 mb-1">
              <CardTitle className="text-base font-semibold text-foreground break-words flex-1">
                {job.jd_title || job.jd_code}
              </CardTitle>
              <div className="flex-shrink-0">
                {statusBadge(job.status)}
              </div>
            </div>
            
            {/* ET-12: Department */}
            {job.department && (
              <p className="text-xs text-muted-foreground break-words">
                {job.department}
              </p>
            )}
            
            {/* ET-12: Team */}
            {job.team && (
              <p className="text-xs text-muted-foreground break-words">
                {job.team}
              </p>
            )}
          </CardHeader>
          
          {/* ET-12: Separator line */}
          <div className="px-5">
            <div className="h-px bg-border/60" />
          </div>
          
          <CardContent className="flex flex-1 flex-col gap-2 p-5">
            {/* ET-12: Core metrics - text-xs for labels, text-sm for values */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Applicants</span>
                <span className="text-sm font-semibold text-foreground">{formatNumber(job.applicants)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Diamonds Found</span>
                <span className="text-sm font-semibold text-foreground">{formatNumber(job.diamonds_found)}</span>
              </div>
            </div>
          </CardContent>
        </button>
      </Card>
    </motion.article>
  );
}

function JobCardSkeleton({ index }: { index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="rounded-2xl border border-border/50 bg-muted/40 p-5"
    >
      {/* ET-12: Title and status badge on same line */}
      <div className="flex items-start justify-between gap-4 mb-1">
        <Skeleton className="h-5 w-40 rounded-lg flex-1" />
        <Skeleton className="h-5 w-14 rounded-md flex-shrink-0" />
      </div>
      
      {/* ET-12: Department and Team skeletons */}
      <Skeleton className="h-3 w-32 mb-1" />
      <Skeleton className="h-3 w-24 mb-4" />
      
      {/* ET-12: Separator */}
      <div className="h-px bg-border/60 mb-4" />
      
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-4 w-12" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-4 w-8" />
        </div>
      </div>
    </motion.div>
  );
}

export function AnalyticsOverview({ tenant }: { tenant: string }) {
  const { setTenant: persistTenant } = useAnalyticsStore();

  useEffect(() => {
    persistTenant(tenant);
  }, [persistTenant, tenant]);
  const {
    data: jobs,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["analytics-summary", tenant],
    queryFn: () => getAnalyticsSummary(tenant),
    enabled: Boolean(tenant),
  });

  const hasJobs = !!jobs && jobs.length > 0;

  if (!tenant) {
    return (
      <Card className="rounded-2xl border-border/60 bg-muted/40 p-10 text-center">
        <CardContent className="space-y-3 p-0">
          <Sparkles className="mx-auto size-10 text-primary" />
          <p className="text-lg font-semibold text-foreground">Select a tenant</p>
          <p className="text-sm text-muted-foreground">
            Provide a tenant slug in the URL, e.g. /acme/analytics, to load analytics data.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-0">
      {/* ET-12: Sticky Local Navigation Bar */}
      <LocalNavBar
        title="Analytics Dashboard"
        subtitle="Select a job posting to view detailed analytics"
        breadcrumbLabel="Analytics"
        showRefreshButton={true}
        onRefreshClick={() => window.location.reload()}
      />
      
      <section className="bg-white p-6">

      {isError ? (
        <Card className="rounded-2xl border-destructive/50 bg-destructive/5 p-6">
          <CardHeader className="p-0">
            <CardTitle className="text-base text-destructive">
              Unable to load analytics summary
            </CardTitle>
          </CardHeader>
          <CardContent className="mt-2 space-y-4 p-0 text-sm text-destructive/80">
            <p>Check that the analytics microservice is running on port 5055.</p>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: 3 }).map((_, index) => (
              <JobCardSkeleton key={`skeleton-${index}`} index={index} />
            ))
          : null}

        {!isLoading && hasJobs
          ? jobs?.map((job, index) => (
              <JobCard key={job.jd_code} job={job} index={index} tenant={tenant} />
            ))
          : null}
      </div>

      {!isLoading && !hasJobs && !isError ? (
        <Card className="rounded-2xl border-dashed border-border/70 bg-muted/40 p-10 text-center">
          <CardContent className="space-y-3 p-0">
            <Sparkles className="mx-auto size-10 text-primary" />
            <p className="text-lg font-semibold text-foreground">No analytics yet</p>
            <p className="text-sm text-muted-foreground">
              Create a job posting and invite candidates to unlock the analytics dashboard.
            </p>
          </CardContent>
        </Card>
      ) : null}
      </section>
    </div>
  );
}
