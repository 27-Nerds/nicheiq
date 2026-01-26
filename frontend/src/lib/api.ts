/**
 * API client for NicheIQ backend
 */

export const API_BASE = '/api';
// SSE uses the same proxy - SvelteKit +server.ts handles streaming and adds auth headers
export const SSE_BASE = '/api';

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
  // Optional fields returned by some endpoints
  hasReport?: boolean;
  hasLandingPage?: boolean;
  creditRefunded?: boolean;
  queuePosition?: number | null;
  aheadCount?: number;
  totalQueued?: number;
  stopReason?: string | null;
  stopReasonDetails?: {
    qualityTier?: string;
    confidenceScore?: number;
    metrics?: {
      painPointCount?: number;
      quoteDensity?: number;
      sourceCoverage?: number;
    };
    recommendation?: string;
  } | null;
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
 * Terminal job statuses - SSE should close when job reaches these
 */
const TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'CANCELLED'];

/**
 * Check if a job status is terminal (no more updates expected)
 */
export function isTerminalStatus(status: string | undefined): boolean {
  return !!status && TERMINAL_STATUSES.includes(status.toUpperCase());
}

/**
 * SSE connection options
 */
export interface SSEOptions {
  maxReconnectAttempts?: number;
  reconnectDelayMs?: number;
  onReconnecting?: (attempt: number, maxAttempts: number) => void;
  onMaxReconnectsReached?: () => void;
}

const DEFAULT_MAX_RECONNECT_ATTEMPTS = 10;
const DEFAULT_RECONNECT_DELAY_MS = 3000;

/**
 * Subscribe to job progress updates via SSE with automatic reconnection
 *
 * @param jobId - The job ID to subscribe to
 * @param onUpdate - Callback for job updates. Return the job status to help manage connection lifecycle.
 * @param onError - Optional error callback
 * @param options - Optional configuration for reconnection behavior
 * @returns Cleanup function to close the connection
 */
export function subscribeToProgress(
  jobId: string,
  onUpdate: (job: Job) => void,
  onError?: (error: Error) => void,
  options?: SSEOptions
): () => void {
  const maxAttempts = options?.maxReconnectAttempts ?? DEFAULT_MAX_RECONNECT_ATTEMPTS;
  const delayMs = options?.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS;

  let eventSource: EventSource | null = null;
  let reconnectAttempts = 0;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let isCleanedUp = false;
  let lastKnownStatus: string | undefined;

  function connect() {
    if (isCleanedUp) return;

    // Don't connect if we know the job is in a terminal state
    if (isTerminalStatus(lastKnownStatus)) return;

    eventSource?.close();
    eventSource = new EventSource(`${SSE_BASE}/jobs/${jobId}/events`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Job;
        lastKnownStatus = data.status;
        reconnectAttempts = 0; // Reset on successful message
        onUpdate(data);

        // Close connection if job reached terminal state
        if (isTerminalStatus(data.status)) {
          eventSource?.close();
          eventSource = null;
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource?.close();
      eventSource = null;

      // Don't reconnect if cleaned up or terminal
      if (isCleanedUp || isTerminalStatus(lastKnownStatus)) {
        return;
      }

      // Attempt reconnect with backoff
      if (reconnectAttempts < maxAttempts) {
        reconnectAttempts++;
        const delay = delayMs * Math.min(reconnectAttempts, 3);
        options?.onReconnecting?.(reconnectAttempts, maxAttempts);
        reconnectTimeout = setTimeout(connect, delay);
      } else {
        options?.onMaxReconnectsReached?.();
        onError?.(new Error('Max SSE reconnection attempts reached'));
      }
    };
  }

  // Start connection
  connect();

  // Return cleanup function
  return () => {
    isCleanedUp = true;
    eventSource?.close();
    eventSource = null;
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
  };
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

// ============================================
// Notification Preferences
// ============================================

export interface NotificationPreferences {
  emailEnabled: boolean;
  emailOnJobStart: boolean;
  emailOnJobComplete: boolean;
  emailOnJobError: boolean;
}

export type NotificationPreferencesUpdate = Partial<NotificationPreferences>;

/**
 * Get user's notification preferences
 */
export async function getNotificationPreferences(userId: string): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE}/users/${userId}/notification-preferences`);
  return handleResponse<NotificationPreferences>(response);
}

/**
 * Update user's notification preferences
 */
export async function updateNotificationPreferences(
  userId: string,
  prefs: NotificationPreferencesUpdate
): Promise<NotificationPreferences> {
  const response = await fetch(`${API_BASE}/users/${userId}/notification-preferences`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  });
  return handleResponse<NotificationPreferences>(response);
}

// ============================================
// Password Management
// ============================================

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

export interface ChangePasswordResponse {
  message: string;
}

/**
 * Change user's password
 */
export async function changePassword(
  userId: string,
  request: ChangePasswordRequest
): Promise<ChangePasswordResponse> {
  const response = await fetch(`${API_BASE}/users/${userId}/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<ChangePasswordResponse>(response);
}
