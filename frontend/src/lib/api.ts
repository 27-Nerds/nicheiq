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

export type { Job, JobAsset, StageProgress as JobProgress, ErrorDetails, ErrorSeverity, SolutionPreview, SolutionValidationData, ReportSummary } from '$lib/types/job';
import type { Job, SolutionPreview, ReportSummary } from '$lib/types/job';

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

// ============================================
// Interactive Job Flow
// ============================================

export interface SelectSolutionRequest {
  solutionNames: string[];
  rationale?: string;
}

export interface SolutionsResponse {
  solutionIdeas: SolutionPreview[] | null;
  selectedSolution: string | null;
  selectedSolutions: string[] | null;
  selectionRationale: string | null;
  canRegenerate: boolean;
}

/**
 * Select a solution for deep investigation (Phase 2)
 */
export async function selectSolution(jobId: string, request: SelectSolutionRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/select-solution`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  return handleResponse<{ message: string }>(response);
}

/**
 * Regenerate solution ideas
 */
export async function regenerateIdeas(jobId: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/regenerate-ideas`, {
    method: 'POST',
  });
  return handleResponse<{ message: string }>(response);
}

/**
 * Get solution ideas for an interactive job
 */
export async function getSolutions(jobId: string): Promise<SolutionsResponse> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/solutions`);
  return handleResponse<SolutionsResponse>(response);
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
 * Check if SSE should stay open (accounts for landing page generation on completed jobs)
 */
export function shouldKeepSSEOpen(job: { status: string; landingPageStatus?: string | null }): boolean {
  if (!isTerminalStatus(job.status)) return true;
  return job.landingPageStatus === 'QUEUED' || job.landingPageStatus === 'RUNNING';
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
  let lastKnownLandingStatus: string | null | undefined;

  function connect() {
    if (isCleanedUp) return;

    // Don't connect if we know the job is in a terminal state with no landing in progress
    if (isTerminalStatus(lastKnownStatus) && lastKnownLandingStatus !== 'QUEUED' && lastKnownLandingStatus !== 'RUNNING') return;

    eventSource?.close();
    eventSource = new EventSource(`${SSE_BASE}/jobs/${jobId}/events`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Job;
        lastKnownStatus = data.status;
        lastKnownLandingStatus = data.landingPageStatus;
        reconnectAttempts = 0; // Reset on successful message
        onUpdate(data);

        // Close connection if job reached terminal state and no landing in progress
        if (!shouldKeepSSEOpen(data)) {
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

      // Don't reconnect if cleaned up or terminal with no landing in progress
      if (isCleanedUp || (isTerminalStatus(lastKnownStatus) && lastKnownLandingStatus !== 'QUEUED' && lastKnownLandingStatus !== 'RUNNING')) {
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
 * Get lightweight report summary for preview cards
 */
export async function getReportSummary(jobId: string): Promise<ReportSummary> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/report-summary`);
  return handleResponse<ReportSummary>(response);
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
// Report Sharing
// ============================================

export interface ShareInfo {
  isShared: boolean;
  shareToken?: string;
  viewCount?: number;
}

/**
 * Get share status for a job
 */
export async function getShareStatus(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share`);
  return handleResponse<ShareInfo>(response);
}

/**
 * Enable sharing for a job
 */
export async function enableSharing(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share`, {
    method: 'POST',
  });
  return handleResponse<ShareInfo>(response);
}

/**
 * Disable sharing for a job
 */
export async function disableSharing(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share`, {
    method: 'DELETE',
  });
  return handleResponse<ShareInfo>(response);
}

/**
 * Regenerate share token (invalidates old link)
 */
export async function regenerateShareToken(jobId: string): Promise<ShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/share/regenerate`, {
    method: 'POST',
  });
  return handleResponse<ShareInfo>(response);
}

// ============================================
// Discovery Sharing
// ============================================

export interface DiscoveryShareInfo {
  isShared: boolean;
  shareToken?: string;
  viewCount?: number;
  voteCount?: number;
  solutionVotes?: Record<string, number>;
}

export interface VoteSummary {
  totalVotes: number;
  solutionVotes: Record<string, number>;
  viewerVote?: { solutionName: string; comment: string | null } | null;
}

export interface DiscoveryShareData {
  shareType: 'discovery';
  niche: string;
  solutions: SolutionPreview[];
  discoveryFindings: Record<string, any>;
  voteSummary: VoteSummary;
  allowIndexing?: boolean;
}

export async function getDiscoveryShareStatus(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share`);
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function enableDiscoverySharing(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share`, {
    method: 'POST',
  });
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function disableDiscoverySharing(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share`, {
    method: 'DELETE',
  });
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function regenerateDiscoveryShareToken(jobId: string): Promise<DiscoveryShareInfo> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/discovery-share/regenerate`, {
    method: 'POST',
  });
  return handleResponse<DiscoveryShareInfo>(response);
}

export async function fetchSharedDiscovery(shareToken: string): Promise<DiscoveryShareData> {
  const response = await fetch(`${API_BASE}/shared/discovery/${shareToken}`);
  return handleResponse<DiscoveryShareData>(response);
}

export async function submitDiscoveryVote(
  shareToken: string,
  solutionName: string,
  viewerToken: string,
  comment?: string,
): Promise<VoteSummary> {
  const response = await fetch(`${API_BASE}/shared/discovery/${shareToken}/vote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ solutionName, viewerToken, comment }),
  });
  return handleResponse<VoteSummary>(response);
}

export async function getDiscoveryVotes(shareToken: string, viewerToken?: string): Promise<VoteSummary> {
  const url = viewerToken
    ? `${API_BASE}/shared/discovery/${shareToken}/votes?viewerToken=${viewerToken}`
    : `${API_BASE}/shared/discovery/${shareToken}/votes`;
  const response = await fetch(url);
  return handleResponse<VoteSummary>(response);
}

// ============================================
// Notification Preferences
// ============================================

export interface NotificationPreferences {
  emailEnabled: boolean;
  emailOnJobStart: boolean;
  emailOnJobComplete: boolean;
  emailOnJobError: boolean;
  emailOnSolutionsReady: boolean;
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
