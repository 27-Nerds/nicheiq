import { Redis } from 'ioredis';
import { CONFIG } from '../config.js';

// Redis connection options with retry logic
const redisOptions = {
  retryStrategy: (times: number) => Math.min(times * 100, 3000),
  maxRetriesPerRequest: 3,
};

// Redis client for queue operations
const redis = new Redis(CONFIG.redisUrl, redisOptions);

redis.on('error', (err: Error) => {
  console.error('Redis connection error:', err.message);
});

redis.on('connect', () => {
  console.log('Redis connected');
});

// Queue name for research jobs
const QUEUE_NAME = 'nicheiq:jobs';

/**
 * Enqueue a job for processing by Python worker
 */
export async function enqueueJob(
  jobId: string,
  niche: string,
  userId?: string,
  allowedProjectTypes?: string[],
  resume: boolean = false,
  jobMode?: string,
  entryMode?: string
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    niche,
    user_id: userId,
    allowed_project_types: allowedProjectTypes,
    resume,
    job_mode: jobMode || null,
    entry_mode: entryMode || null,
    created_at: new Date().toISOString(),
  });

  // Push to the left (LPUSH), workers pop from the right (BRPOP)
  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Enqueue a landing-page-only generation task
 */
export async function enqueueLandingPageJob(
  jobId: string,
  reportPath: string,
  pageMode: string = 'coming_soon'
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    report_path: reportPath,
    page_mode: pageMode,
    task_type: 'landing_page',
    created_at: new Date().toISOString(),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued landing page job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Enqueue Phase 2 deep investigation for selected solutions (1-3)
 */
export async function enqueuePhase2Job(
  jobId: string,
  checkpointPath: string,
  selectedSolutions: string[],
  selectionRationale?: string,
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    checkpoint_path: checkpointPath,
    selected_solutions: selectedSolutions,
    selected_solution: selectedSolutions[0],  // backward compat for in-flight workers
    selection_rationale: selectionRationale || '',
    task_type: 'research_phase2',
    created_at: new Date().toISOString(),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued phase 2 job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Enqueue idea regeneration task
 */
export async function enqueueRegenerateJob(
  jobId: string,
  checkpointPath: string,
  existingSolutionNames: string[],
  niche: string
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    checkpoint_path: checkpointPath,
    existing_solution_names: existingSolutionNames,
    niche,
    task_type: 'regenerate_ideas',
    created_at: new Date().toISOString(),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued regenerate ideas job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Enqueue catalog pain point generation task
 */
export async function enqueueCatalogPainPointsJob(
  jobId: string,
  categoryId: string,
  categoryName: string,
  categoryDescription: string,
  parentCategoryName: string,
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    category_id: categoryId,
    category_name: categoryName,
    category_description: categoryDescription,
    parent_category_name: parentCategoryName,
    task_type: 'catalog_pain_points',
    created_at: new Date().toISOString(),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued catalog pain points job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Enqueue catalog idea generation task
 */
export async function enqueueCatalogIdeasJob(
  jobId: string,
  categoryId: string,
  painPoints: Record<string, unknown>[],
  niche: string,
  parentCategoryName: string,
  existingIdeas: Array<{name: string, description: string}> = [],
  parentSourceJobId?: string,
  contentCategorization?: unknown,
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    category_id: categoryId,
    pain_points: painPoints,
    niche,
    parent_category_name: parentCategoryName,
    existing_ideas: existingIdeas,
    task_type: 'catalog_ideas',
    created_at: new Date().toISOString(),
    // Phase 5.4 — when the admin generates ideas from existing pain points,
    // the ideas should inherit the pain-points-job's sourceJobId so they FK
    // into the same CatalogResearchContext row.
    ...(parentSourceJobId && { parent_source_job_id: parentSourceJobId }),
    ...(contentCategorization != null
      ? { content_categorization: contentCategorization }
      : {}),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued catalog ideas job ${jobId} to ${QUEUE_NAME}` + (parentSourceJobId ? ` (parent=${parentSourceJobId})` : ''));
}

/**
 * Enqueue a catalog "pain research" job: seed Phase-1 discovery with one or more
 * (remix) catalog pain points, skip stages 1-4, run stage 5, land awaiting-selection.
 * Seeds travel in the payload (the worker has no DB access).
 */
export async function enqueuePainResearchJob(
  jobId: string,
  painSeeds: Record<string, unknown>[],
  niche: string,
  userId?: string,
  allowedProjectTypes?: string[],
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    pain_seeds: painSeeds,
    niche,
    user_id: userId,
    allowed_project_types: allowedProjectTypes,
    task_type: 'catalog_pain_research',
    created_at: new Date().toISOString(),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued catalog pain research job ${jobId} (${painSeeds.length} pain(s)) to ${QUEUE_NAME}`);
}

/**
 * Enqueue a catalog "deep research" job: seed a solution from a catalog idea,
 * skip stages 1-5, run Phase 2 (5.5 -> 14) in one shot. Seed travels in the payload.
 */
export async function enqueueDeepIdeaResearchJob(
  jobId: string,
  ideaSeed: Record<string, unknown>,
  niche: string,
  userId?: string,
): Promise<void> {
  const jobData = JSON.stringify({
    job_id: jobId,
    idea_seed: ideaSeed,
    niche,
    user_id: userId,
    task_type: 'catalog_deep_research',
    created_at: new Date().toISOString(),
  });

  await redis.lpush(QUEUE_NAME, jobData);
  console.log(`Enqueued catalog deep idea research job ${jobId} to ${QUEUE_NAME}`);
}

/**
 * Remove a job from the Redis queue (e.g. when cancelled while QUEUED)
 */
export async function removeJobFromQueue(jobId: string): Promise<boolean> {
  const queue = await redis.lrange(QUEUE_NAME, 0, -1);
  for (const item of queue) {
    try {
      const parsed = JSON.parse(item);
      if (parsed.job_id === jobId) {
        const removed = await redis.lrem(QUEUE_NAME, 1, item);
        return removed > 0;
      }
    } catch { continue; }
  }
  return false;
}

/**
 * Get queue length
 */
export async function getQueueLength(): Promise<number> {
  return redis.llen(QUEUE_NAME);
}

/**
 * Get all queued job IDs in order (oldest first = next to be processed)
 */
export async function getQueuedJobIds(): Promise<string[]> {
  const queue = await redis.lrange(QUEUE_NAME, 0, -1);
  // Queue is LPUSH (newest at head/left), BRPOP (oldest at tail/right)
  // So reverse to get oldest-first order (processing order)
  return queue.reverse().map(item => {
    try {
      const parsed = JSON.parse(item);
      return parsed.job_id;
    } catch {
      return null;
    }
  }).filter((id): id is string => id !== null);
}

/**
 * Get position of a specific job in the queue (1-based, null if not in queue)
 */
export async function getJobQueuePosition(jobId: string): Promise<number | null> {
  const queuedIds = await getQueuedJobIds();
  const index = queuedIds.indexOf(jobId);
  return index === -1 ? null : index + 1;
}

/**
 * Queue stats for a specific job
 */
export interface QueueStats {
  position: number | null;  // 1-based position, null if not in queue
  totalQueued: number;      // Total jobs in queue
  aheadCount: number;       // Jobs ahead of this one (position - 1)
}

/**
 * Get queue stats for a specific job
 */
export async function getQueueStats(jobId: string): Promise<QueueStats> {
  const queuedIds = await getQueuedJobIds();
  const index = queuedIds.indexOf(jobId);
  const totalQueued = queuedIds.length;

  if (index === -1) {
    return { position: null, totalQueued, aheadCount: 0 };
  }

  return {
    position: index + 1,
    totalQueued,
    aheadCount: index  // Jobs ahead of this one
  };
}

/**
 * Health check for Redis connection
 */
export async function checkRedisHealth(): Promise<boolean> {
  try {
    const result = await redis.ping();
    return result === 'PONG';
  } catch (error) {
    console.error('Redis health check failed:', error);
    return false;
  }
}

// Cleanup on shutdown
export async function closeRedis(): Promise<void> {
  await redis.quit();
}
