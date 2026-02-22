import type {
  SubmitRequest,
  ExecuteRequest,
  ApiResponse,
  JobResponse,
  JobListResponse,
  JobFilesResponse,
  AuditResponse,
} from "@/types/api";

const API_BASE = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: "Request failed" }));
    throw new Error(error.error || error.detail?.[0]?.msg || `HTTP ${res.status}`);
  }
  
  return res.json();
}

export const api = {
  health: () =>
    request<ApiResponse>(`${API_BASE}/health`),

  prepare: (data: SubmitRequest) =>
    request<ApiResponse>(`${API_BASE}/prepare`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  submit: (data: SubmitRequest) =>
    request<ApiResponse>(`${API_BASE}/submit`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  executeJob: (jobId: string, data: ExecuteRequest = {}) =>
    request<ApiResponse>(`${API_BASE}/jobs/${jobId}/execute`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listJobs: () =>
    request<JobListResponse>(`${API_BASE}/jobs`),

  getJob: (jobId: string) =>
    request<JobResponse>(`${API_BASE}/jobs/${jobId}`),

  getJobFiles: (jobId: string, stage?: string) => {
    const params = stage ? `?stage=${encodeURIComponent(stage)}` : "";
    return request<JobFilesResponse>(`${API_BASE}/jobs/${jobId}/files${params}`);
  },

  listAudit: (jobExternalId?: string) => {
    const params = jobExternalId
      ? `?job_external_id=${encodeURIComponent(jobExternalId)}`
      : "";
    return request<AuditResponse>(`${API_BASE}/audit${params}`);
  },

  getJobAudit: (jobId: string, jobExternalId?: string) => {
    const params = jobExternalId
      ? `?job_external_id=${encodeURIComponent(jobExternalId)}`
      : "";
    return request<AuditResponse>(`${API_BASE}/audit/${jobId}${params}`);
  },
};
