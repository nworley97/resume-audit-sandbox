export interface SummaryItem {
  jd_code: string;
  jd_title: string | null;
  status: string | null;
  department: string | null;
  team: string | null;
  posted: string | null;
  applicants: number;
  diamonds_found: number;
}

export interface CandidateBadge {
  id: number;
  name: string | null;
  initials: string;
  claim_validity_score: number;
  relevancy_score: number;
  combined_score?: number;
}

export interface JobDetail {
  jd: {
    code: string;
    title: string | null;
    status: string | null;
    department: string | null;
    team: string | null;
    posted: string | null;
  };
  totals: {
    applied: number;
    diamonds_found: number;
    completion_pct: number;
    completed: number;
  };
  heatmap: {
    matrix: number[][];
    axes: {
      relevancy: number[];
      claim_validity: number[];
    };
    cells: Array<{
      relevancy: number;
      claim: number;
      candidates: CandidateBadge[];
    }>;
  };
  distributions: {
    claim_validity: number[];
    relevancy: number[];
  };
  summary: {
    total_candidates: number;
    diamonds_found: number;
    completion_rate: number;
    last_updated: string;
  };
  diamonds: CandidateBadge[];
  completion_funnel: Array<{
    stage: string;
    count: number;
    percentage: number;
  }>;
  roi: {
    variables: {
      total_applicants: number;
      diamonds_count: number;
      manual_time_per_applicant: number;
      assisted_time_per_applicant: number;
      hourly_rate: number;
    };
    calculated: {
      time_saved_hours: number;
      cost_saved: number;
      speed_improvement: number | null;
      efficiency_percentage: number;
    };
  };
  statistics: {
    claim_validity: {
      mean: number | null;
      median: number | null;
      std_dev: number | null;
    };
    relevancy: {
      mean: number | null;
      median: number | null;
      std_dev: number | null;
    };
  };
}

export interface AnalyticsConfig {
  tenantSlug: string;
  tenantName: string;
  summaryEndpoint: string;
  jobDetailEndpoint: string;
}
