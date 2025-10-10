import { formatNumber } from "@/lib/utils";
"use client";

import { ResponsiveFunnel } from "@nivo/funnel";

// ET-12: Nivo FunnelChart implementation for completion funnel
interface FunnelStage {
  stage: string;
  count: number;
  percentage: number;
}

interface CompletionFunnelProps {
  data: FunnelStage[];
  completionRate: number;
  onOverallConversion?: (rate: number) => void;
}

export function CompletionFunnelChart({ data, completionRate, onOverallConversion }: CompletionFunnelProps) {
  // Add null/undefined checks and fallback data
  if (!data || !Array.isArray(data) || data.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">Verification Funnel</h3>
            <p className="text-sm text-muted-foreground">Track candidate progress across the verification journey</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-800">0.0%</div>
            <div className="text-xs text-muted-foreground">Overall Conversion</div>
          </div>
        </div>
        <div className="h-48 flex flex-col items-center justify-center text-muted-foreground space-y-2">
          <div className="text-center">
            <div className="text-lg font-medium text-foreground mb-1">Waiting for candidates</div>
            <div className="text-sm">Verification progress will appear here<br />once candidates start the process</div>
          </div>
        </div>
      </div>
    );
  }

  // Transform data for Nivo FunnelChart
  const chartData = data.map((stage) => ({
    id: stage.stage,
    value: stage.count,
    label: stage.stage,
  }));

  // Calculate conversion rate summary
  const totalApplicants = data[0]?.count || 0;
  const finalCompleters = data[data.length - 1]?.count || 0;
  const overallConversionRate = totalApplicants > 0 ? ((finalCompleters / totalApplicants) * 100) : 0;  // ET-12: Keep decimals

  if (typeof onOverallConversion === "function") {
    onOverallConversion(overallConversionRate);
  }

  return (
    <div className="space-y-4">
      {/* ET-12: Compact header with conversion rate */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Verification Funnel</h3>
          <p className="text-sm text-muted-foreground">Track candidate progress across the verification journey</p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-800">{overallConversionRate.toFixed(1)}%</div>
          <div className="text-xs text-muted-foreground">Overall Conversion</div>
        </div>
      </div>

      {/* ET-12: Horizontal funnel chart */}
      <div className="h-48">
        <ResponsiveFunnel
          data={chartData}
          margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
          valueFormat=">-.0f"
          colors={{ scheme: "blues" }}
          borderWidth={1}
          borderColor={{ from: "color", modifiers: [["darker", 0.3]] }}
          labelColor={{ from: "color", modifiers: [["darker", 1]] }}
          beforeSeparatorLength={100}
          beforeSeparatorOffset={20}
          afterSeparatorLength={100}
          afterSeparatorOffset={20}
          currentPartSizeExtension={10}
          currentBorderWidth={40}
          motionConfig="wobbly"
          direction="horizontal"
          theme={{
            text: {
              fontSize: 12,
              fill: "var(--foreground)",
            },
            tooltip: {
              container: {
                background: "var(--card)",
                color: "var(--card-foreground)",
                fontSize: 12,
                borderRadius: 6,
                boxShadow: "0 3px 9px rgba(0, 0, 0, 0.5)",
                border: "1px solid var(--border)",
              },
            },
          }}
          tooltip={({ part }) => (
            <div className="rounded-md border border-border bg-card px-3 py-2 text-sm text-card-foreground shadow-md">
              <div className="font-medium">{part.data.label}</div>
              <div className="text-muted-foreground">
                {formatNumber(part.data.value as number)} candidates ({data[0]?.count ? Math.round((part.data.value / data[0].count) * 100) : 0}%)
              </div>
            </div>
          )}
        />
      </div>

      {/* ET-12: Compact stage details below chart */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        {data.map((stage, index) => {
          const previousCount = index > 0 ? data[index - 1]?.count || 0 : stage.count || 0;
          const passRate = previousCount > 0 ? Math.round(((stage.count || 0) / previousCount) * 100) : 100;
          
          return (
            <div key={stage.stage} className="text-center">
              <div className="font-medium text-foreground">{stage.stage}</div>
              <div className="text-primary font-semibold">{formatNumber(stage.count || 0)}</div>
              <div>{passRate}% pass</div>
            </div>
          );
        })}
      </div>

    </div>
  );
}
