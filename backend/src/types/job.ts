import { z } from 'zod';

// Valid project types — must match Python pipeline (src/nicheiq/main.py valid_types)
export const VALID_PROJECT_TYPES = [
  'saas',
  'directory',
  'aggregator',
  'comparison-tool',
  'marketplace',
] as const;

// API request schemas
// Note: email and userId come from authenticated session, not request body
export const CreateJobSchema = z.object({
  niche: z.string()
    .min(10, 'Niche description must be at least 10 characters')
    .max(500, 'Niche description must be at most 500 characters')
    .regex(
      /^[\p{L}\p{N}\p{Zs}\p{Pd}\p{Po}\p{Ps}\p{Pe}\r\n\t]+$/u,
      'Niche description contains invalid characters. Use letters, numbers, spaces, and common punctuation only.'
    ),
  allowedProjectTypes: z.array(z.enum(VALID_PROJECT_TYPES)).min(1).max(5).optional(),
  entryMode: z.enum(['idea', 'audience', 'discovery']).optional(),
});

export type CreateJobInput = z.infer<typeof CreateJobSchema>;

// Progress update from Python worker
export const ProgressUpdateSchema = z.object({
  stage: z.number(),
  name: z.string(),
  status: z.enum(['running', 'completed', 'skipped', 'failed']),
  error: z.string().optional(),
});

export type ProgressUpdate = z.infer<typeof ProgressUpdateSchema>;

// Completion event from Python worker
export const CompletionEventSchema = z.object({
  status: z.enum(['completed', 'failed']),
  report_path: z.string().optional(),
  landing_path: z.string().optional(),
  error: z.string().optional(),
});

export type CompletionEvent = z.infer<typeof CompletionEventSchema>;

// Stage definitions for the NicheIQ pipeline
// Must match worker/progress.py STAGE_NAMES and research_flow.py stage methods
export const PIPELINE_STAGES = [
  { number: 1, name: 'Niche Validation', phase: 1 },
  { number: 2, name: 'Search & Discovery', phase: 1 },
  { number: 3, name: 'Pain Point Analysis', phase: 1 },
  { number: 4, name: 'Audience Mapping', phase: 1 },
  { number: 5, name: 'Solution Pipeline', phase: 1 },
  { number: 5.5, name: 'Competitive Analysis', phase: 2 },
  { number: 6, name: 'SEO & Keyword Strategy', phase: 2 },
  { number: 7, name: 'Pricing Validation', phase: 2 },
  { number: 8, name: 'Traffic Monetization', phase: 2 },
  { number: 9, name: 'Market Sizing', phase: 2 },
  { number: 10, name: 'Solution Refinement', phase: 2 },
  { number: 11, name: 'Trend Analysis', phase: 2 },
  { number: 12, name: 'SEO Score Refinement', phase: 2 },
  { number: 13, name: 'Data Source Research', phase: 2 },
  { number: 14, name: 'Report Generation', phase: 2 },
  { number: 15, name: 'Landing Page Generation', phase: 2 },
] as const;

export const TOTAL_STAGES = 16;

/** Highest stage number in Phase 1 (Discovery). Derived from PIPELINE_STAGES. */
export const DISCOVERY_PHASE_MAX_STAGE = Math.max(
  ...PIPELINE_STAGES.filter(s => s.phase === 1).map(s => s.number)
); // = 5

// Interactive job flow schemas
export const SelectSolutionSchema = z.object({
  solutionNames: z.array(z.string().trim().min(1).max(255)).min(1).max(3),
  rationale: z.string().max(2000).optional(),
});

export type SelectSolutionInput = z.infer<typeof SelectSolutionSchema>;

export const RegenerateIdeasSchema = z.object({});

export type RegenerateIdeasInput = z.infer<typeof RegenerateIdeasSchema>;

// Worker → backend schemas for interactive flow
export const IdeasReadySchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  solutions: z.array(z.record(z.any())),
  checkpoint_path: z.string().min(1).max(500),
  total_to_validate: z.number().int().min(0).default(0),
  skip_validation: z.boolean().optional(),
});

export type IdeasReadyInput = z.infer<typeof IdeasReadySchema>;

export const RegenerationCompleteSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  solutions: z.array(z.record(z.any())),
});

export type RegenerationCompleteInput = z.infer<typeof RegenerationCompleteSchema>;

export const RegenerationFailedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  error_message: z.string().max(2000),
});

export type RegenerationFailedInput = z.infer<typeof RegenerationFailedSchema>;

// API response types
export interface JobResponse {
  id: string;
  niche: string;
  status: string;
  currentStage: number;
  currentStageName: string | null;
  stagesCompleted: number;
  totalStages: number;
  progressPercent: number;
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
  // Quality gate stop metadata
  stopReason: string | null;
  stopReasonDetails: string | null;
  // User-friendly error information
  errorCode: string | null;
  errorDetails: Record<string, unknown> | null;
  // Landing page lifecycle
  generateLandingPage: boolean;
  landingPageStatus: string | null;
  // Interactive job flow
  jobMode: string | null;
  selectedSolution: string | null;
  selectedSolutions: string[] | null;
  awaitingSelectionAt: string | null;
  ideasShownAt: string | null;
  // Optional fields (endpoint-dependent)
  createdAt?: string;
  progress?: StageProgress[];
  assets?: Asset[];
  hasReport?: boolean;
  hasLandingPage?: boolean;
  creditRefunded?: boolean;
  queuePosition?: number | null;
  aheadCount?: number;
  totalQueued?: number;
  solutionIdeas?: Record<string, unknown>[] | null;
  canRegenerate?: boolean;
  selectionRationale?: string | null;
}

export interface StageProgress {
  stageNumber: number;
  stageName: string;
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  durationSeconds: number | null;
}

export interface Asset {
  type: string;
  url: string;
}
