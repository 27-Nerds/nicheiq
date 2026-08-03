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
  entryMode: z.enum(['idea', 'audience', 'discovery', 'pain_research', 'pain_remix', 'deep_idea']).optional(),
  // GTM-focus steer for idea generation/ranking emphasis (only active when angle eval is on).
  ideaFocus: z.enum(['auto', 'novelty', 'distribution']).optional(),
  // Guided research (Phase B) opt-in. The route re-checks entitlement and rejects
  // non-entitled requests rather than silently changing the confirmed product/price.
  chatMode: z.boolean().optional(),
  // The price the intake displayed for the first purchased segment. Job creation
  // compares this inside the same transaction that creates the job and charge.
  expectedCost: z.number().int().min(0).max(1000),
});

export type CreateJobInput = z.infer<typeof CreateJobSchema>;

// The dispatch a worker callback claims to be reporting for. Every guarded callback CASes on
// this against Job.activeDispatchId, so a message from a superseded attempt matches nothing and
// mutates nothing.
//
// OPTIONAL on purpose, and it must stay optional until the queue has drained: a worker deployed
// before the backend, or a message that was already queued when this shipped, carries no id.
// Absence is NOT a free pass — the route only takes its legacy path when the JOB also has no
// active dispatch. Treating a missing id as "skip the check" would quietly reinstate every race
// this exists to close.
export const DispatchIdSchema = z.string().uuid().optional();

// Progress update from Python worker
export const ProgressUpdateSchema = z.object({
  stage: z.number(),
  name: z.string(),
  status: z.enum(['running', 'completed', 'skipped', 'failed']),
  error: z.string().optional(),
  dispatch_id: DispatchIdSchema,
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
export const SelectionDecisionProfileSchema = z.object({
  preset: z.enum(['balanced', 'fast_revenue', 'solo_bootstrap', 'audience_first']),
  weeklyTime: z.enum(['under_10', '10_20', '20_40', 'full_time']),
  budget: z.enum(['under_1k', '1k_5k', '5k_20k', '20k_plus']),
  team: z.enum(['solo', 'small_team', 'funded_team']),
  revenueHorizon: z.enum(['30_days', '90_days', '6_months', 'patient']),
  distributionAdvantages: z.array(
    z.enum(['seo', 'community', 'existing_audience', 'outbound', 'paid', 'partnerships']),
  ).max(4).default([]),
  strengths: z.string().trim().max(500).default(''),
  hardConstraints: z.string().trim().max(1000).default(''),
}).strict();

export type SelectionDecisionProfile = z.infer<typeof SelectionDecisionProfileSchema>;

export const SelectionDraftItemSchema = z.object({
  ideaId: z.string().trim().min(1).max(128),
  ideaRevision: z.number().int().min(1),
}).strict();

export const SelectionDraftUpdateSchema = z.object({
  expectedVersion: z.number().int().min(0),
  items: z.array(SelectionDraftItemSchema).max(3),
}).strict().superRefine((value, ctx) => {
  const keys = new Set<string>();
  value.items.forEach((item, index) => {
    const key = `${item.ideaId}:${item.ideaRevision}`;
    if (keys.has(key)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['items', index],
        message: 'Selection draft items must be unique',
      });
    }
    keys.add(key);
  });
});

export type SelectionDraftUpdateInput = z.infer<typeof SelectionDraftUpdateSchema>;

export const ExactIdeaRefSchema = SelectionDraftItemSchema.extend({
  snapshotSha256: z.string().regex(/^[a-f0-9]{64}$/),
}).strict();

export const SelectSolutionSchema = z.object({
  clientRequestId: z.string().uuid(),
  expectedCost: z.number().int().min(0).max(1000),
  expectedDraftVersion: z.number().int().min(0),
  expectedSelectionFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  rationale: z.string().max(2000).optional(),
}).strict();

export type SelectSolutionInput = z.infer<typeof SelectSolutionSchema>;

export const RegenerateIdeasSchema = z.object({
  clientRequestId: z.string().uuid(),
  expectedCost: z.number().int().min(0).max(1000),
  idea_focus: z.enum(['auto', 'novelty', 'distribution']).default('auto'),
}).strict();

export type RegenerateIdeasInput = z.infer<typeof RegenerateIdeasSchema>;

/** Product limit for append-only idea batches on one discovery run. */
export const MAX_IDEA_BATCHES = 10;

// Worker → backend schemas for interactive flow
export const IdeasReadySchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  // Minimal shape guard (2026-07-02 infra review): the backend stores the blob and matches
  // by solution_name downstream — an idea without a name is undeliverable, and an empty
  // delivery is a worker bug. Passthrough keeps the rest of each idea open (full model
  // mirroring would be brittle churn).
  solutions: z.array(z.object({ solution_name: z.string().min(1) }).passthrough()).min(1),
  checkpoint_path: z.string().min(1).max(500),
  total_to_validate: z.number().int().min(0).default(0),
  skip_validation: z.boolean().optional(),
  discovery_data_path: z.string().max(500).optional().default(''),
  preview_report_path: z.string().optional(),
  // Phase-1 LLM cost breakdown (CostTracker.get_summary()), persisted so the admin
  // pricing view shows spend on awaiting-selection runs before Phase-2 completes.
  cost_summary: z.record(z.any()).optional(),
  // G2's Continue terminates HERE, not at /gate-reached — it runs on to stage 5. Guarding only
  // the gate callbacks would have left the entire G2 continuation unprotected.
  dispatch_id: DispatchIdSchema,
});

export type IdeasReadyInput = z.infer<typeof IdeasReadySchema>;

export const RegenerationCompleteSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  dispatch_id: z.string().uuid().optional(),
  solutions: z.array(z.record(z.any())),
  batch_ordinal: z.number().int().positive().optional(),
  generated_count: z.number().int().min(0).optional(),
  ruled_out_count: z.number().int().min(0).optional(),
  ruled_out_refs: z.array(z.object({
    finding_id: z.string().min(1).max(128),
    finding_revision: z.number().int().min(1),
    idea_id: z.string().min(1).max(128),
    idea_revision: z.number().int().min(1),
    evaluation_id: z.string().max(128).optional(),
    generation_operation_id: z.string().max(128).optional(),
  }).passthrough()).optional(),
  // Per-batch LLM cost breakdown (CostTracker.get_summary()) for this regeneration.
  // Accumulated onto the job's existing costUsd (regeneration adds spend to an
  // already-completed job, unlike report-ready which sets the initial total).
  cost_summary: z.record(z.any()).optional(),
});

export type RegenerationCompleteInput = z.infer<typeof RegenerationCompleteSchema>;

export const RegenerationFailedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  dispatch_id: z.string().uuid().optional(),
  error_message: z.string().max(2000),
});

export type RegenerationFailedInput = z.infer<typeof RegenerationFailedSchema>;

// ============================================
// User-seed pipeline (plans/eager-meandering-feather.md Phase 5): "generate an idea from your
// own idea" at selection chat. Paid, numbered (seed_idea_N), and dispatch-lifecycle-backed,
// like guided Continue and append-only additional batches.
// ============================================

// POST /:jobId/seed-idea body
const UserSeedIdeaSchema = z.object({
  kind: z.literal('user_seed').optional(),
  free_text: z.string().trim().min(1).max(2000),
  pain_ref: z.string().max(500).optional(),
  tool_ref: z.string().max(300).optional(),
  // The frontend's SeedIdeaRequest also carries an optional `rationale` (the analyst's
  // free text for why it proposed this) — not validated/stored here, silently dropped by
  // this non-strict object (unlike GateActionSchema's patches, a seed has no field
  // whitelist to enforce).
  /** Chat message that proposed this seed — REQUIRED (unlike GateActionSchema's optional
   *  sourceMessageId): a seed's card identity IS this id. Stamped onto the dispatch AND the
   *  durable `seed_submitted`/`seed_settled` receipts so the card can resolve its state
   *  across a ledger reload. */
  sourceMessageId: z.string().min(1).max(64),
  /** The price the seed card showed. REQUIRED (unlike guided Continue's optional field) — a
   *  seed's price is always confirmed up front, never inferred from a free discovery run. */
  expectedCost: z.number().int().min(0).max(1000),
});

const SynthesisSeedIdeaSchema = z.object({
  kind: z.literal('idea_synthesis'),
  sourceMessageId: z.string().min(1).max(64),
  expectedCost: z.number().int().min(0).max(1000),
});

export const SeedIdeaSchema = z.union([UserSeedIdeaSchema, SynthesisSeedIdeaSchema]);

export type SeedIdeaInput = z.infer<typeof SeedIdeaSchema>;

export const SeedIdeaCompleteSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  // Exactly one outcome idea — active OR demoted; the worker never drops a paid seed
  // (keep-with-caveat dedup instead — see `duplicate_of` on the idea dict).
  idea: z.object({ solution_name: z.string().min(1) }).passthrough(),
  outcome: z.enum(['accepted', 'demoted']),
  cost_summary: z.record(z.any()).optional(),
  dispatch_id: DispatchIdSchema,
});

export type SeedIdeaCompleteInput = z.infer<typeof SeedIdeaCompleteSchema>;

export const SeedIdeaFailedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  error_message: z.string().max(2000),
  dispatch_id: DispatchIdSchema,
});

export type SeedIdeaFailedInput = z.infer<typeof SeedIdeaFailedSchema>;

// ============================================
// Guided mode (Phase B — plans/eager-meandering-feather.md): G1 (post-Stage-1) / G2
// (post-Stage-4) stage gates. Worker → backend notification schemas + the gate-action
// patch whitelist (kept in lockstep with the Python Pydantic whitelist in
// src/nicheiq/flows/gate_patches.py — shared valid/invalid fixtures test BOTH layers, R4).
// ============================================

export const GateReachedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  gate_stage: z.union([z.literal(1), z.literal(4)]),
  // The EFFECTIVE post-resume checkpoint path (fork semantics) — never the input path a
  // continuation was given.
  checkpoint_path: z.string().min(1).max(500),
  gate_artifact: z.record(z.any()),
  cost_summary: z.record(z.any()).optional(),
  dispatch_id: DispatchIdSchema,
});

export type GateReachedInput = z.infer<typeof GateReachedSchema>;

export const GateFailedSchema = z.object({
  worker_id: z.string().min(1),
  job_id: z.string().uuid(),
  gate_stage: z.union([z.literal(1), z.literal(4)]).nullable(),
  error_message: z.string().max(2000),
  dispatch_id: DispatchIdSchema,
  // Only a SYSTEM_FAULT gives the money back. Today this endpoint conflates a rejected user
  // patch with a genuine infrastructure failure, and refunding both is an abuse path: submit a
  // deliberately invalid patch, get refunded, repeat. Defaults to SYSTEM_FAULT so an older
  // worker that cannot classify is treated the way it is treated today.
  failure_kind: z.enum(['SYSTEM_FAULT', 'USER_PATCH_REJECTED', 'STALE_CHECKPOINT'])
    .default('SYSTEM_FAULT'),
});

export type GateFailedInput = z.infer<typeof GateFailedSchema>;

// Gate patch whitelists (G1/G2 — plan §"Patch whitelists"). NO add-segment in v1;
// excluded_segments/segment_emphasis/primary_target_segment/pain_scope titles are
// cross-checked against the job's stored gateArtifact at the route layer (jobs.ts
// gate-action), not here — this schema only enforces SHAPE.
export const GateG1PatchSchema = z.object({
  niche_description: z.string().max(2000).optional(),
  market_segments: z.array(z.string().max(120)).max(12).optional(),
  industry_boundaries: z.string().max(2000).optional(),
  user_target_audience: z.string().max(500).optional(),
}).strict();

export type GateG1PatchInput = z.infer<typeof GateG1PatchSchema>;

export const GateG2PatchSchema = z.object({
  user_target_audience: z.string().max(500).optional(),
  primary_target_segment: z.string().max(255).optional(),
  excluded_segments: z.array(z.string().max(255)).optional(),
  segment_emphasis: z.record(z.enum(['high', 'low'])).optional(),
  pain_scope: z.object({
    excluded_titles: z.array(z.string().max(500)).default([]),
    pinned_titles: z.array(z.string().max(500)).default([]),
  }).strict().optional(),
}).strict();

export type GateG2PatchInput = z.infer<typeof GateG2PatchSchema>;

// POST /:jobId/gate-action body
export const GateActionSchema = z.object({
  action: z.enum(['continue', 'apply_stay']),
  gateStage: z.union([z.literal(1), z.literal(4)]),
  patch: z.record(z.any()).optional(),
  /** Chat message that proposed this patch, when it came from the analyst — stored on
   *  the durable receipt so the proposal card can render its terminal "Applied" state
   *  after a reload. Absent for the inline exclude-pain chips (no proposing message). */
  sourceMessageId: z.string().max(64).optional(),
  /** The price the Continue button showed. Continue is now a purchase, so the number the user
   *  agreed to must be the number they are charged — if an admin re-priced the segment between
   *  the gate rendering and the click, the route 409s instead of quietly charging something else. */
  expectedCost: z.number().int().min(0).max(1000).optional(),
}).superRefine((data, ctx) => {
  if (data.action === 'apply_stay' && !data.patch) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'patch is required for apply_stay' });
  }
});

export type GateActionInput = z.infer<typeof GateActionSchema>;

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
  solutionIdeasCount?: number | null;
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
