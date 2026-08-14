import type {
  JobStatus,
  ProcessJobRequest,
  TemplateSummary,
  UploadPagesResponse,
  ValidationResult,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? `Request failed with status ${response.status}.`;
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export function listTemplates(): Promise<TemplateSummary[]> {
  return request<TemplateSummary[]>("/api/templates");
}

export function templatePdfUrl(templateId: string): string {
  return `${API_BASE_URL}/api/templates/${encodeURIComponent(templateId)}/pdf`;
}

export function createJob(templateId: string): Promise<JobStatus> {
  return request<JobStatus>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: templateId }),
  });
}

export function uploadPages(jobId: string, files: File[]): Promise<UploadPagesResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return request<UploadPagesResponse>(`/api/jobs/${encodeURIComponent(jobId)}/pages`, {
    method: "POST",
    body: formData,
  });
}

export function processJob(jobId: string, metadata: ProcessJobRequest): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(metadata),
  });
}

export function getJobStatus(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}/status`);
}

export function getValidation(jobId: string): Promise<ValidationResult[]> {
  return request<ValidationResult[]>(`/api/jobs/${encodeURIComponent(jobId)}/validation`);
}

export function downloadUrl(jobId: string, format: "ttf" | "otf" | "zip"): string {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/download?format=${format}`;
}

export function previewUrl(jobId: string, format: "png" | "pdf"): string {
  return `${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/preview?format=${format}`;
}
