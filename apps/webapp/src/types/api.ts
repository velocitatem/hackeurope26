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
  
  export type ApiResponse = Record<string, string>;
  export type JobResponse = Record<string, unknown>;
  export type JobListResponse = Record<string, unknown>;
  export type JobFilesResponse = Record<string, unknown>;