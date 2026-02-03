export type JobStatus = 'PENDING' | 'PROCESSING' | 'PAUSED' | 'CANCELED' | 'DONE' | 'FAILED';

export interface Job {
  id: number;
  preset: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: number;
  total_files: number;
  processed_files: number;
  error_message?: string | null;
}

export interface JobFileReport {
  id: number;
  original_name: string;
  original_size: number;
  output_name: string | null;
  output_size: number | null;
  status: JobStatus;
  error_message: string;
  reduction_percent: number | null;
  final_format: string | null;
  original_url?: string | null;
  output_url?: string | null;
  crop_mode?: string | null;
  crop_x?: number | null;
  crop_y?: number | null;
  crop_w?: number | null;
  crop_h?: number | null;
  original_width?: number | null;
  original_height?: number | null;
  orientation?: string | null;
  aspect_label?: string | null;
  has_transparency?: boolean | null;
  analysis_type?: string | null;
  metadata_tags?: string[] | null;
  keep_metadata?: boolean | null;
  selected_preset_id?: string | null;
  output_format?: string | null;
  quality_webp?: number | null;
  quality_jpg?: number | null;
  quality_avif?: number | null;
  keep_transparency?: boolean | null;
  rename_pattern?: string | null;
  normalize_lowercase?: boolean | null;
  normalize_remove_accents?: boolean | null;
  normalize_replace_spaces?: string | null;
  normalize_collapse_dashes?: boolean | null;
  crop_enabled?: boolean | null;
  crop_aspect?: string | null;
  output_width?: number | null;
  output_height?: number | null;
  output_formats?: string[] | null;
  output_variants?: OutputVariant[] | null;
  generate_2x?: boolean | null;
  generate_sharpened?: boolean | null;
  width_before?: number | null;
  height_before?: number | null;
  width_after?: number | null;
  height_after?: number | null;
  cropped?: boolean | null;
  metadata_removed?: boolean | null;
}

export interface OutputVariant {
  name: string;
  size: number;
  format: string;
  scale: string;
  width?: number | null;
  height?: number | null;
}

export interface JobDetail extends Job {
  files: JobFileReport[];
}

export interface PresetItem {
  id: string;
  label: string;
  category: string;
  width: number;
  height: number;
  aspect: string;
  typeHint: string;
  recommendedFormat?: string;
  density?: string;
  source?: 'base' | 'custom';
}

export interface PresetsResponse {
  version: number;
  naming?: {
    pattern?: string;
    normalize?: Record<string, unknown>;
  };
  defaults?: Record<string, unknown>;
  presets: PresetItem[];
}

export interface AppSettings {
  concurrency: number;
  default_remove_metadata: boolean;
  default_keep_transparency: boolean;
  show_debug_details: boolean;
}

// URL base del backend; se puede ajustar con VITE_API_URL.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  // Wrapper con manejo de errores para respuestas JSON del API.
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error ?? 'Error de API');
  }
  return response.json() as Promise<T>;
}

export async function listJobs(): Promise<Job[]> {
  return request<Job[]>('/api/jobs/');
}

export async function getJob(id: number): Promise<JobDetail> {
  return request<JobDetail>(`/api/jobs/${id}/`);
}

export async function createJob(preset: string, files: File[]): Promise<JobDetail> {
  const form = new FormData();
  form.append('preset', preset);
  files.forEach((file) => form.append('files', file));

  return request<JobDetail>('/api/jobs/', {
    method: 'POST',
    body: form,
  });
}

export async function fetchPresets(): Promise<PresetsResponse> {
  return request<PresetsResponse>('/api/presets/');
}

export function buildDownloadUrl(id: number): string {
  return `${API_URL}/api/jobs/${id}/download/`;
}

export interface CropPayload {
  crop_mode: 'manual';
  crop_x: number;
  crop_y: number;
  crop_w: number;
  crop_h: number;
}

export async function patchCrop(id: number, payload: CropPayload): Promise<JobFileReport> {
  return request<JobFileReport>(`/api/job-files/${id}/crop/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function reprocessFile(id: number): Promise<JobDetail> {
  return request<JobDetail>(`/api/job-files/${id}/reprocess/`, {
    method: 'POST',
  });
}

export interface JobFileUpdatePayload {
  selected_preset_id?: string | null;
  output_format?: string | null;
  output_formats?: string[] | null;
  quality_webp?: number | null;
  quality_jpg?: number | null;
  quality_avif?: number | null;
  keep_metadata?: boolean;
  keep_transparency?: boolean;
  rename_pattern?: string | null;
  normalize_lowercase?: boolean;
  normalize_remove_accents?: boolean;
  normalize_replace_spaces?: string;
  normalize_collapse_dashes?: boolean;
  crop_enabled?: boolean;
  crop_aspect?: string;
  crop_x?: number;
  crop_y?: number;
  crop_w?: number;
  crop_h?: number;
  generate_2x?: boolean;
  generate_sharpened?: boolean;
}

export async function updateJobFile(id: number, payload: JobFileUpdatePayload): Promise<JobFileReport> {
  return request<JobFileReport>(`/api/job-files/${id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function reprocessJob(id: number): Promise<JobDetail> {
  return request<JobDetail>(`/api/jobs/${id}/reprocess/`, {
    method: 'POST',
  });
}

export async function pauseJob(id: number): Promise<Job> {
  return request<Job>(`/api/jobs/${id}/pause/`, { method: 'POST' });
}

export async function resumeJob(id: number): Promise<Job> {
  return request<Job>(`/api/jobs/${id}/resume/`, { method: 'POST' });
}

export async function cancelJob(id: number): Promise<Job> {
  return request<Job>(`/api/jobs/${id}/cancel/`, { method: 'POST' });
}

export async function deleteJob(id: number): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/api/jobs/${id}/delete/`, { method: 'DELETE' });
}

export async function getSettings(): Promise<AppSettings> {
  return request<AppSettings>('/api/settings/');
}

export async function updateSettings(payload: Partial<AppSettings>): Promise<AppSettings> {
  return request<AppSettings>('/api/settings/', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function createCustomPreset(payload: Partial<PresetItem> & { id: string }): Promise<PresetItem> {
  return request<PresetItem>('/api/presets/custom/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateCustomPreset(id: string, payload: Partial<PresetItem>): Promise<PresetItem> {
  return request<PresetItem>(`/api/presets/custom/${id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function duplicateCustomPreset(id: string): Promise<PresetItem> {
  return request<PresetItem>(`/api/presets/custom/${id}/duplicate/`, {
    method: 'POST',
  });
}

export async function deleteCustomPreset(id: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/api/presets/custom/${id}/`, {
    method: 'DELETE',
  });
}
