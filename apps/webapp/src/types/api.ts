export interface SubmitRequest {
  repo_url: string;
  branch?: string;
  allowed_geos?: string[];
  max_price_usd_hour?: number | null;
  image?: string | null;
  timeout?: number;
  verbose?: boolean;
}

export interface ExecuteRequest {
  image?: string | null;
  namespace?: string | null;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface SchedulingDecision {
  id: number;
  job_id?: number | null;
  job_external_id: string;
  geo: string;
  provider: string;
  region: string;
  sku: string;
  start_ts?: number | null;
  end_ts?: number | null;
  avg_delta?: number | null;
  score?: number | null;
  source?: string;
  reason_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MigrationEvent {
  id: number;
  job_external_id: string;
  trigger_epoch?: number | null;
  from_region?: string | null;
  from_sku?: string | null;
  from_score?: number | null;
  to_region?: string | null;
  to_sku?: string | null;
  to_score?: number | null;
  status: string;
  message?: string | null;
  reason_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AuditResponse {
  job_external_id?: string;
  schedulingDecisions: SchedulingDecision[];
  migrationEvents: MigrationEvent[];
}

export type ApiResponse = Record<string, string>;
export type JobResponse = Record<string, unknown>;
export type JobListResponse = Record<string, unknown>;
export type JobFilesResponse = Record<string, unknown>;
