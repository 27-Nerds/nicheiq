// Single source of truth for how a job's status maps to a lifecycle bucket,
// a human label, an accent color, and a primary CTA. Previously this logic
// was scattered across the dashboard page (statusPriority + getStatusLabel),
// JobCard, and the job page — each with a slightly different vocabulary.
//
// Colors are CSS custom-property references so they can be dropped straight
// into inline `style:color`/`style:background` bindings and stay theme-aware.

import type { Job, JobStatus } from '$lib/types/job';

/**
 * The lifecycle groups the dashboard organizes research into. AWAITING_SELECTION
 * is its OWN group ('review') — it's a positive milestone (discovery succeeded,
 * ideas are ready, next step is pick-for-deep-research), NOT an error, so it must
 * not share a bucket with hard failures ('failed').
 */
export type LifecycleBucket = 'review' | 'progress' | 'done' | 'failed' | 'archived';

interface StatusMeta {
  label: string;
  /** CSS var reference — severity ramp, accent, or muted. */
  color: string;
  /** Primary action verb for this state. */
  cta: string;
}

export const STATUS: Record<JobStatus, StatusMeta> = {
  AWAITING_SELECTION: { label: 'Ideas ready', color: 'var(--color-accent)', cta: 'Review ideas' },
  FAILED: { label: 'Failed', color: 'var(--color-error-text)', cta: 'Resume' },
  // "In progress" statuses are BLUE, not warning-orange: --color-warning-text is
  // byte-identical to --color-accent-dark, so orange progress collided with the
  // orange 'review' bucket. Blue = working; keeps the lifecycle rail legible.
  RUNNING: { label: 'Researching', color: 'var(--color-info-dark)', cta: 'View progress' },
  RUNNING_PHASE2: { label: 'Deep research', color: 'var(--color-info-dark)', cta: 'View progress' },
  REGENERATING: { label: 'Regenerating ideas', color: 'var(--color-info-dark)', cta: 'View' },
  QUEUED: { label: 'Queued', color: 'var(--color-info-dark)', cta: 'View' },
  PENDING: { label: 'Preparing', color: 'var(--color-info-dark)', cta: 'View' },
  COMPLETED: { label: 'Ready', color: 'var(--color-success-text)', cta: 'View report' },
  CANCELLED: { label: 'Cancelled', color: 'var(--color-text-muted)', cta: 'Run again' },
};

/** Fallback for any unexpected status string coming off the wire. */
const FALLBACK: StatusMeta = { label: 'Unknown', color: 'var(--color-text-muted)', cta: 'View' };

export function statusMeta(status: string): StatusMeta {
  return STATUS[status?.toUpperCase() as JobStatus] ?? FALLBACK;
}

/**
 * A quality-gate failure is a "soft" fail: the pipeline ran but stopped because
 * the niche didn't yield enough signal to justify a report. Credits are refunded
 * and there is nothing to resume — the fix is a broader niche, not a retry. These
 * belong in Archived, not in the attention bucket.
 */
export function isQualityGateFail(job: Pick<Job, 'status' | 'stopReason'>): boolean {
  return job.status?.toUpperCase() === 'FAILED' && job.stopReason === 'INSUFFICIENT_DATA';
}

/** A hard failure (infra/LLM error) IS resumable and DOES need the user. */
export function isHardFail(job: Pick<Job, 'status' | 'stopReason'>): boolean {
  return job.status?.toUpperCase() === 'FAILED' && !isQualityGateFail(job);
}

// Pulse the status dot only where something is genuinely live: actively
// computing, or waiting on the user. Not for queued/pending/terminal states.
const LIVE_STATUSES = new Set<JobStatus>([
  'AWAITING_SELECTION',
  'RUNNING',
  'RUNNING_PHASE2',
  'REGENERATING',
]);

export function isLive(status: string): boolean {
  return LIVE_STATUSES.has(status?.toUpperCase() as JobStatus);
}

const PROGRESS_STATUSES = new Set<JobStatus>([
  'PENDING',
  'QUEUED',
  'RUNNING',
  'REGENERATING',
  'RUNNING_PHASE2',
]);

/**
 * Map a job to its lifecycle bucket. The 9 raw statuses collapse to 5 groups:
 *   review   — AWAITING_SELECTION (positive: ideas ready, pick for deep research)
 *   progress — anything actively computing or queued
 *   done     — COMPLETED
 *   failed   — a hard (resumable) FAILED — an error, kept apart from 'review'
 *   archived — CANCELLED or a quality-gate (refunded, non-resumable) FAILED
 */
export function bucketOf(job: Pick<Job, 'status' | 'stopReason'>): LifecycleBucket {
  const status = job.status?.toUpperCase();
  if (status === 'AWAITING_SELECTION') return 'review';
  if (PROGRESS_STATUSES.has(status as JobStatus)) return 'progress';
  if (status === 'COMPLETED') return 'done';
  if (isHardFail(job)) return 'failed';
  return 'archived';
}

/** Verdict → severity color. GO=success, CONDITIONAL=warning, else error. */
export function verdictColor(verdict: string | null | undefined): string {
  const v = (verdict ?? '').toUpperCase();
  if (v === 'GO') return 'var(--color-success-text)';
  if (v.startsWith('CONDITIONAL')) return 'var(--color-warning-text)';
  return 'var(--color-error-text)';
}

/** 0–100 score → severity color, matching the SeverityBar cutoffs (60/45). */
export function scoreColor(value: number): string {
  return value >= 60
    ? 'var(--color-success-text)'
    : value >= 45
      ? 'var(--color-warning-text)'
      : 'var(--color-error-text)';
}

/** Normalize a 0–1 or 0–100 score to a rounded 0–100 integer. */
export function toScore100(raw: number | null | undefined): number | null {
  if (raw == null) return null;
  return raw > 1 ? Math.round(raw) : Math.round(raw * 100);
}
