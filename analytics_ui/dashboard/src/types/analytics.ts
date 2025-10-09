import { z } from "zod";

export const analyticsJobSummarySchema = z.object({
  jd_code: z.string(),
  jd_title: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  department: z.string().nullable().optional(),
  team: z.string().nullable().optional(),
  posted: z.string().nullable().optional(),
  applicants: z.number(),
  diamonds_found: z.number(),
});

export type AnalyticsJobSummary = z.infer<typeof analyticsJobSummarySchema>;

const statisticsSchema = z.object({
  mean: z.number().nullable(),
  median: z.number().nullable(),
  std_dev: z.number().nullable(),
});

const completionFunnelSchema = z.array(
  z.object({
    stage: z.string(),
    count: z.number(),
    percentage: z.number(),
  })
);

const diamondSchema = z.object({
  id: z.string(),
  name: z.string(),
  initials: z.string(),
  claim_validity_score: z.number(),
  relevancy_score: z.number(),
  combined_score: z.number(),
});

const relevancyAxisSchema = z.object({
  index: z.number(),
  label: z.string(),
  value: z.number().nullable(),
  is_no_score: z.boolean(),
});

const claimAxisSchema = z.object({
  index: z.number(),
  label: z.string(),
  bucket: z.number(),
  is_no_score: z.boolean(),
});

const heatmapCellSchema = z.object({
  relevancy: z.number(),
  claim: z.number(),
  candidates: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      initials: z.string(),
      claim_validity_score: z.number(),
      relevancy_score: z.number(),
    })
  ),
});

export const analyticsJobDetailSchema = z.object({
  jd: z.object({
    code: z.string(),
    title: z.string().nullable().optional(),
    status: z.string().nullable().optional(),
    department: z.string().nullable().optional(),
    team: z.string().nullable().optional(),
    posted: z.string().nullable().optional(),
  }),
  totals: z.object({
    applied: z.number(),
    diamonds_found: z.number(),
    completion_pct: z.number(),
    completed: z.number(),
  }),
  heatmap: z.object({
    matrix: z.array(z.array(z.number())),
    axes: z.object({
      relevancy: z.array(relevancyAxisSchema),
      claim_validity: z.array(claimAxisSchema),
    }),
    cells: z.array(heatmapCellSchema),
  }),
  distributions: z.object({
    claim_validity: z.array(z.number()),
    relevancy: z.array(z.number()),
  }),
  summary: z.object({
    total_candidates: z.number(),
    diamonds_found: z.number(),
    completion_rate: z.number(),
    last_updated: z.string(),
  }),
  diamonds: z.array(diamondSchema),
  completion_funnel: completionFunnelSchema,
  roi: z.object({
    variables: z.object({
      total_applicants: z.number(),
      diamonds_count: z.number(),
      manual_time_per_applicant: z.number(),
      assisted_time_per_applicant: z.number(),
      hourly_rate: z.number(),
    }),
    calculated: z.object({
      time_saved_hours: z.number(),
      cost_saved: z.number(),
      speed_improvement: z.number().nullable(),
      efficiency_percentage: z.number(),
    }),
  }),
  statistics: z.object({
    claim_validity: statisticsSchema,
    relevancy: statisticsSchema,
  }),
});

export type AnalyticsJobDetail = z.infer<typeof analyticsJobDetailSchema>;

export const analyticsSummaryResponseSchema = z.array(analyticsJobSummarySchema);
