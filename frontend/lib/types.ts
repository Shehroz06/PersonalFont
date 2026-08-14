// Mirrors the backend's Pydantic response models (see
// backend/app/api/schemas.py, app/services/job_status.py,
// pipeline/validation/schema.py). Kept in one file since the frontend
// only ever reads these shapes, never re-derives them.

export interface TemplateSummary {
  template_id: string;
  template_version: string;
  page_count: number;
  character_count: number;
}

export type JobState = "created" | "uploading" | "processing" | "completed" | "failed";

export interface JobStatus {
  job_id: string;
  state: JobState;
  template_id: string;
  pages_uploaded: number;
  valid_glyph_count: number | null;
  invalid_glyph_count: number | null;
  error: string | null;
  created_at: number;
  updated_at: number;
}

export interface UploadPagesResponse {
  job_id: string;
  pages_uploaded: number;
  filenames: string[];
}

export interface ValidationResult {
  character: string;
  character_id: string;
  valid: boolean;
  confidence: number;
  warnings: string[];
}

export interface ProcessJobRequest {
  family_name: string;
  creator: string;
  version: string;
  description: string;
}
