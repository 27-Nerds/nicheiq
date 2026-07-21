import { z } from 'zod';
import { SelectionExperimentDraftSchema } from './selectionExperiment.js';

export const FOUNDER_FIT_DIMENSIONS = [
  'time',
  'budget',
  'team',
  'revenue_horizon',
  'distribution',
  'strengths',
  'hard_constraints',
] as const;

export const FounderFitRequestSchema = z.object({
  ideas: z.array(z.object({
    ideaId: z.string().trim().min(1).max(100),
    ideaRevision: z.number().int().positive().max(1_000_000),
  }).strict()).min(1).max(3),
}).strict().superRefine((value, ctx) => {
  const refs = value.ideas.map((idea) => `${idea.ideaId}:${idea.ideaRevision}`);
  if (new Set(refs).size !== refs.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Idea revisions must be unique' });
  }
});

export const FounderFitProfileFieldSchema = z.enum([
  'preset',
  'weeklyTime',
  'budget',
  'team',
  'revenueHorizon',
  'distributionAdvantages',
  'strengths',
  'hardConstraints',
]);

export const FounderFitIdeaFieldSchema = z.enum([
  'description',
  'value_proposition',
  'source_pain',
  'source_segment',
  'target_personas',
  'core_features',
  'project_type',
  'estimated_development_time',
  'dev_time_rationale',
  'technical_feasibility_score',
  'solo_dev_feasibility',
  'seo_scalability_score',
  'programmatic_seo_opportunity',
  'pricing_strategy',
  'critic_concern',
  'data_acquisition_notes',
  'tags.build_complexity',
  'tags.data_access',
  'tags.growth_channels',
]);

export const PROFILE_FIELD_FOR_DIMENSION = {
  time: 'weeklyTime',
  budget: 'budget',
  team: 'team',
  revenue_horizon: 'revenueHorizon',
  distribution: 'distributionAdvantages',
  strengths: 'strengths',
  hard_constraints: 'hardConstraints',
} as const;

export const FounderFitDimensionSchema = z.object({
  dimension: z.enum(FOUNDER_FIT_DIMENSIONS),
  status: z.enum(['aligned', 'conflict', 'unknown', 'irrelevant']),
  summary: z.string().trim().min(3).max(600),
  profileFields: z.array(FounderFitProfileFieldSchema).min(1).max(3),
  ideaFields: z.array(FounderFitIdeaFieldSchema).max(6),
}).strict().superRefine((value, ctx) => {
  const required = PROFILE_FIELD_FOR_DIMENSION[value.dimension];
  if (!value.profileFields.includes(required)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: `${value.dimension} must cite profile.${required}`,
      path: ['profileFields'],
    });
  }
});

const SuggestedExperimentSchema = SelectionExperimentDraftSchema.omit({
  ideaId: true,
  ideaRevision: true,
});

const FounderFitRawResultBaseSchema = z.object({
  ideaRef: z.string().regex(/^R[1-3]$/),
  verdict: z.enum(['fits', 'needs_reshape', 'blocked', 'insufficient_evidence']),
  summary: z.string().trim().min(3).max(1_000),
  strongestAdvantage: z.string().trim().min(3).max(800),
  blockingConflict: z.string().trim().max(800).nullable(),
  decisionChangingUnknown: z.string().trim().min(3).max(800),
  sensitivity: z.string().trim().min(3).max(800),
  dimensions: z.array(FounderFitDimensionSchema).length(FOUNDER_FIT_DIMENSIONS.length),
  suggestedExperiment: SuggestedExperimentSchema,
}).strict();

export const FounderFitRawResultSchema = FounderFitRawResultBaseSchema.superRefine((value, ctx) => {
  const dimensions = value.dimensions.map((item) => item.dimension);
  if (new Set(dimensions).size !== FOUNDER_FIT_DIMENSIONS.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Each fit dimension is required exactly once' });
  }
});

export const FounderFitRawResponseSchema = z.object({
  results: z.array(FounderFitRawResultSchema).min(1).max(3),
}).strict().superRefine((value, ctx) => {
  const refs = value.results.map((result) => result.ideaRef);
  if (new Set(refs).size !== refs.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Idea references must be unique' });
  }
});

export const FounderFitArtifactSchema = z.object({
  version: z.literal(1),
  inputFingerprint: z.string().length(64),
  profileSnapshot: z.record(z.unknown()),
  ideaSnapshots: z.array(z.record(z.unknown())).min(1).max(3),
  model: z.string().min(1).max(255),
  createdAt: z.string().datetime(),
  results: z.array(FounderFitRawResultBaseSchema.omit({ ideaRef: true }).extend({
    ideaId: z.string().min(1).max(100),
    ideaRevision: z.number().int().positive(),
    ideaTitle: z.string().min(1).max(500),
    suggestedExperiment: SelectionExperimentDraftSchema,
  }).strict()).min(1).max(3),
}).strict();

export type FounderFitRequest = z.infer<typeof FounderFitRequestSchema>;
export type FounderFitArtifact = z.infer<typeof FounderFitArtifactSchema>;
