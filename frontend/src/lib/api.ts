/**
 * API client for NicheIQ backend
 */

export const API_BASE = '/api';
// Use direct backend URL for SSE (Vite proxy doesn't handle streaming well)
export const SSE_BASE = import.meta.env.DEV ? 'http://localhost:3001/api' : '/api';

export interface CreateJobRequest {
  email: string;
  niche: string;
  allowedProjectTypes?: string[];
}

export interface CreateJobResponse {
  id: string;
  status: string;
  statusUrl: string;
  message: string;
}

export interface JobProgress {
  stageNumber: number;
  stageName: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'SKIPPED' | 'FAILED';
  startedAt: string | null;
  completedAt: string | null;
  durationSeconds: number | null;
}

export interface JobAsset {
  type: 'REPORT_JSON' | 'LANDING_PAGE';
  url: string;
}

export interface Job {
  id: string;
  email: string;
  niche: string;
  status: 'PENDING' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  currentStage: number;
  currentStageName: string | null;
  stagesCompleted: number;
  totalStages: number;
  progressPercent: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  progress: JobProgress[];
  assets: JobAsset[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  const data = await response.json();

  if (!response.ok) {
    throw new ApiError(
      data.error || 'An error occurred',
      response.status,
      data.details
    );
  }

  return data as T;
}

/**
 * Create a new research job
 */
export async function createJob(request: CreateJobRequest): Promise<CreateJobResponse> {
  const response = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  return handleResponse<CreateJobResponse>(response);
}

/**
 * Get job status and progress
 */
export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`);
  return handleResponse<Job>(response);
}

/**
 * Cancel a job
 */
export async function cancelJob(jobId: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`, {
    method: 'DELETE',
  });

  return handleResponse<{ message: string }>(response);
}

/**
 * Subscribe to job progress updates via SSE
 */
export function subscribeToProgress(
  jobId: string,
  onUpdate: (job: Partial<Job>) => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(`${SSE_BASE}/jobs/${jobId}/events`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onUpdate(data);
    } catch (e) {
      console.error('Failed to parse SSE data:', e);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    onError?.(new Error('SSE connection closed'));
  };

  // Return cleanup function
  return () => eventSource.close();
}

/**
 * Get download URL for report
 */
export function getReportUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/report`;
}

/**
 * Get URL for landing page
 */
export function getLandingPageUrl(jobId: string, download = false): string {
  const base = `${API_BASE}/jobs/${jobId}/landing`;
  return download ? `${base}?download=true` : base;
}
