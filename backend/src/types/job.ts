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
      /^[\p{L}\p{N}\p{Zs}\p{Pd}\p{Po}\p{Ps}\p{Pe}]+$/u,
      'Niche description contains invalid characters. Use letters, numbers, spaces, and common punctuation only.'
    ),
  allowedProjectTypes: z.array(z.enum(VALID_PROJECT_TYPES)).min(1).max(5).optional(),
  generateLandingPage: z.boolean().optional().default(true),
});

export type CreateJobInput = z.infer<typeof CreateJobSchema>;

// Progress update from Python worker
export const ProgressUpdateSchema = z.object({
  stage: z.number(),
  name: z.string(),
  status: z.enum(['running', 'completed', 'failed']),
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
  { number: 1, name: 'Niche Validation' },
  { number: 5, name: 'Search & Discovery' },
  { number: 6, name: 'Pain Point Analysis' },
  { number: 6.5, name: 'Audience Mapping' },
  { number: 7, name: 'Solution Pipeline' },
  { number: 8, name: 'Pricing Validation' },
  { number: 8.5, name: 'Keyword Validation' },
  { number: 8.55, name: 'Traffic Monetization' },
  { number: 8.6, name: 'Market Sizing' },
  { number: 8.7, name: 'Solution Refinement' },
  { number: 9, name: 'SEO Strategy' },
  { number: 9.5, name: 'Trend Analysis' },
  { number: 9.6, name: 'SEO Score Refinement' },
  { number: 9.7, name: 'Data Source Research' },
  { number: 10, name: 'Report Generation' },
  { number: 11, name: 'Landing Page Generation' },
] as const;

export const TOTAL_STAGES = PIPELINE_STAGES.length;

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
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  progress: StageProgress[];
  assets: Asset[];
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
