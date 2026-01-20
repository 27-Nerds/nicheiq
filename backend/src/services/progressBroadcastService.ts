/**
 * Progress Broadcast Service
 *
 * Internal EventEmitter for SSE broadcasting of job progress updates.
 * This replaces Redis pub/sub for progress events.
 *
 * Architecture:
 *   Worker → POST /api/workers/progress → DB update + broadcast → SSE clients
 */

import { EventEmitter } from 'events';

// Internal event emitter for progress broadcasting
const progressEmitter = new EventEmitter();

// Increase max listeners to handle many concurrent jobs
progressEmitter.setMaxListeners(100);

/**
 * Progress data structure sent to SSE clients
 */
export interface ProgressData {
  stage: number;
  name: string;
  status: 'running' | 'completed' | 'failed';
  error?: string;
  report_path?: string;
  landing_path?: string;
}

/**
 * Get the event name for a specific job
 */
function getJobEventName(jobId: string): string {
  return `progress:${jobId}`;
}

/**
 * Broadcast progress update to all SSE clients listening for this job.
 *
 * @param jobId - The job UUID
 * @param data - Progress data to broadcast
 */
export function broadcastProgress(jobId: string, data: ProgressData): void {
  const eventName = getJobEventName(jobId);
  progressEmitter.emit(eventName, data);
}

/**
 * Subscribe to progress updates for a specific job.
 *
 * @param jobId - The job UUID to subscribe to
 * @param callback - Function called with progress data on each update
 * @returns Unsubscribe function to clean up the listener
 */
export function subscribeToJobProgress(
  jobId: string,
  callback: (data: ProgressData) => void
): () => void {
  const eventName = getJobEventName(jobId);

  progressEmitter.on(eventName, callback);

  // Return unsubscribe function
  return () => {
    progressEmitter.off(eventName, callback);
  };
}

/**
 * Get the number of active listeners for a job (useful for debugging)
 */
export function getListenerCount(jobId: string): number {
  const eventName = getJobEventName(jobId);
  return progressEmitter.listenerCount(eventName);
}
