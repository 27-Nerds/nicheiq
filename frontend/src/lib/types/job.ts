/**
 * Shared Job-related types used across the application.
 * Single source of truth — do not duplicate these interfaces elsewhere.
 */

export type JobStatus = 'PENDING' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export type ErrorSeverity = 'info' | 'warning' | 'error';

export interface ErrorDetails {
  code: string;
  severity: ErrorSeverity;
  userMessage: string;
  actionableGuidance: string;
  retryDelayMinutes?: number;
  rawMessage?: string;
}

export interface StageProgress {
  stageNumber: number;
  stageName: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'SKIPPED' | 'FAILED';
  startedAt?: string | null;
  completedAt?: string | null;
  durationSeconds: number | null;
}

export interface JobAsset {
  type: 'REPORT_JSON' | 'LANDING_PAGE' | string;
  url: string;
}

export interface StopReasonDetails {
  qualityTier?: string;
  confidenceScore?: number;
  metrics?: {
    painPointCount?: number;
    quoteDensity?: number;
    sourceCoverage?: number;
  };
  recommendation?: string;
}

export interface Job {
  id: string;
  email?: string;
  niche: string;
  status: JobStatus | string;
  currentStage: number;
  currentStageName: string | null;
  stagesCompleted: number;
  totalStages: number;
  progressPercent: number;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  progress?: StageProgress[];
  assets?: JobAsset[];
  // Optional fields returned by some endpoints
  hasReport?: boolean;
  hasLandingPage?: boolean;
  creditRefunded?: boolean;
  queuePosition?: number | null;
  aheadCount?: number;
  totalQueued?: number;
  stopReason?: string | null;
  stopReasonDetails?: StopReasonDetails | null;
  // User-friendly error information
  errorCode?: string | null;
  errorDetails?: ErrorDetails | null;
  // Project type filter selected at creation
  allowedProjectTypes?: string[] | null;
  // Landing page lifecycle
  generateLandingPage?: boolean;
  landingPageStatus?: string | null;
}
