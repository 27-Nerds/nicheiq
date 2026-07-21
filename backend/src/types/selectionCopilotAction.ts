import { z } from 'zod';
import { SelectionDecisionProfileSchema } from './job.js';
import { SelectionChallengeLensSchema } from './selectionChallenge.js';
import { SelectionConceptPurposeSchema } from './selectionConceptSet.js';
import { SelectionExperimentDraftSchema } from './selectionExperiment.js';
import { SelectionOwnerEvidenceFieldsSchema } from './selectionOwnerEvidence.js';

export const SelectionCandidateRefSchema = z.string().regex(/^R[1-9]\d*$/);
export const SelectionAssumptionRefSchema = z.string().regex(/^A[1-9]\d*$/);
export const SelectionExperimentRefSchema = z.string().regex(/^X[1-9]\d*$/);
export const SelectionOwnerEvidenceRefSchema = z.string().regex(/^O[1-9]\d*$/);
export const SelectionChallengeQuestionRefSchema = z.string().regex(/^Q[1-9]\d*$/);

export const SelectionCopilotOpenTargetSchema = z.enum([
  'candidate',
  'compare',
  'decision_profile',
  'risk_queue',
  'assumptions',
  'challenge',
  'founder_fit',
  'owner_evidence',
  'experiments',
]);

const OpenSelectionActionSchema = z.object({
  kind: z.literal('open'),
  target: SelectionCopilotOpenTargetSchema,
  idea_refs: z.array(SelectionCandidateRefSchema).max(2).default([]),
  lens: SelectionChallengeLensSchema.optional(),
  assumption_ref: SelectionAssumptionRefSchema.optional(),
  experiment_ref: SelectionExperimentRefSchema.optional(),
  evidence_ref: SelectionOwnerEvidenceRefSchema.optional(),
  question_ref: SelectionChallengeQuestionRefSchema.optional(),
  rationale: z.string().trim().min(3).max(500),
}).strict().superRefine((value, ctx) => {
  const requiresOneIdea = ['candidate', 'challenge', 'owner_evidence'].includes(value.target);
  if (requiresOneIdea && value.idea_refs.length !== 1) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['idea_refs'], message: `${value.target} requires one candidate reference` });
  }
  if (value.target === 'compare' && (value.idea_refs.length < 1 || value.idea_refs.length > 2)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['idea_refs'], message: 'compare requires one or two candidate references' });
  }
  if ((value.target === 'challenge' || value.target === 'owner_evidence') && !value.lens) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lens'], message: `${value.target} requires a lens` });
  }
});

const nonEmptyPartial = <T extends z.ZodRawShape>(schema: z.ZodObject<T>) => schema.refine(
  value => Object.values(value).some(item => item !== undefined),
  { message: 'At least one draft field is required' },
);

const DecisionProfilePrefillSchema = z.object({
  form: z.literal('decision_profile'),
  values: nonEmptyPartial(SelectionDecisionProfileSchema.partial()),
}).strict();

const ConceptForgePrefillSchema = z.object({
  form: z.literal('concept_forge'),
  idea_refs: z.array(SelectionCandidateRefSchema).min(1).max(2),
  values: z.object({
    purpose: SelectionConceptPurposeSchema,
    targetTradeoff: z.string().trim().min(3).max(500).optional(),
  }).strict(),
}).strict().superRefine((value, ctx) => {
  if (new Set(value.idea_refs).size !== value.idea_refs.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['idea_refs'], message: 'Concept Forge sources must be distinct' });
  }
  if (value.values.purpose === 'resolve_tradeoff' && value.idea_refs.length !== 2) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['values', 'purpose'], message: 'Resolving a trade-off requires two candidates' });
  }
});

const AssumptionValuesSchema = z.object({
  statement: z.string().trim().min(3).max(2_000).optional(),
  impactIfFalse: z.string().trim().min(3).max(2_000).optional(),
  falsificationQuestion: z.string().trim().min(3).max(2_000).optional(),
}).strict();

const AssumptionDraftFieldSchema = z.enum([
  'statement',
  'impactIfFalse',
  'falsificationQuestion',
]);

const AssumptionGroundingRefSchema = z.string().regex(/^[RAOQ][1-9]\d*$/);

const AssumptionGroundingSchema = z.object({
  statement: z.array(AssumptionGroundingRefSchema).min(1).max(8).optional(),
  impactIfFalse: z.array(AssumptionGroundingRefSchema).min(1).max(8).optional(),
  falsificationQuestion: z.array(AssumptionGroundingRefSchema).min(1).max(8).optional(),
}).strict();

const AssumptionPrefillSchema = z.object({
  form: z.literal('assumption'),
  idea_ref: SelectionCandidateRefSchema,
  assumption_ref: SelectionAssumptionRefSchema.optional(),
  question_ref: SelectionChallengeQuestionRefSchema.optional(),
  lens: SelectionChallengeLensSchema.optional(),
  values: nonEmptyPartial(AssumptionValuesSchema),
  grounding: AssumptionGroundingSchema,
}).strict().superRefine((value, ctx) => {
  if (!value.assumption_ref && !value.lens) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['lens'], message: 'A new assumption requires a lens' });
  }
  for (const field of AssumptionDraftFieldSchema.options) {
    const hasValue = value.values[field] !== undefined;
    const hasGrounding = Boolean(value.grounding[field]?.length);
    if (hasValue && !hasGrounding) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['grounding', field],
        message: `Grounding is required for ${field}`,
      });
    }
    if (!hasValue && hasGrounding) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['grounding', field],
        message: `Grounding was provided without a ${field} draft`,
      });
    }
  }
});

const OwnerEvidenceValuesSchema = SelectionOwnerEvidenceFieldsSchema.omit({
  ideaId: true,
  ideaRevision: true,
  lens: true,
}).partial();

const OwnerEvidencePrefillSchema = z.object({
  form: z.literal('owner_evidence'),
  idea_ref: SelectionCandidateRefSchema,
  lens: SelectionChallengeLensSchema,
  values: nonEmptyPartial(OwnerEvidenceValuesSchema),
}).strict();

const ExperimentValuesSchema = SelectionExperimentDraftSchema.omit({
  ideaId: true,
  ideaRevision: true,
  originChallengeId: true,
  originQuestionId: true,
  assumptionId: true,
}).partial();

const ExperimentPrefillSchema = z.object({
  form: z.literal('experiment'),
  idea_ref: SelectionCandidateRefSchema,
  experiment_ref: SelectionExperimentRefSchema.optional(),
  assumption_ref: SelectionAssumptionRefSchema.optional(),
  question_ref: SelectionChallengeQuestionRefSchema.optional(),
  values: nonEmptyPartial(ExperimentValuesSchema),
}).strict();

const PrefillSelectionActionSchema = z.object({
  kind: z.literal('prefill'),
  draft: z.union([
    DecisionProfilePrefillSchema,
    ConceptForgePrefillSchema,
    AssumptionPrefillSchema,
    OwnerEvidencePrefillSchema,
    ExperimentPrefillSchema,
  ]),
  rationale: z.string().trim().min(3).max(500),
  caveats: z.array(z.string().trim().min(3).max(300)).max(5).default([]),
}).strict();

const ShortlistReviewActionSchema = z.object({
  kind: z.literal('shortlist_review'),
  idea_refs: z.array(SelectionCandidateRefSchema).max(3),
  rationale: z.string().trim().min(3).max(1_000),
}).strict();

export const PrepareSelectionActionArgsSchema = z.union([
  OpenSelectionActionSchema,
  PrefillSelectionActionSchema,
  ShortlistReviewActionSchema,
]);

const CanonicalIdeaSchema = z.object({
  ideaId: z.string().min(1).max(128),
  ideaRevision: z.number().int().positive(),
  solutionName: z.string().min(1).max(500),
}).strict();

const CanonicalRecordSchema = z.object({
  id: z.string().uuid(),
  version: z.number().int().positive().optional(),
  status: z.string().min(1).max(40).optional(),
}).strict();

const AssumptionGroundingSourceSchema = z.object({
  ref: AssumptionGroundingRefSchema,
  kind: z.enum(['candidate', 'assumption', 'owner_evidence', 'challenge_question']),
  label: z.string().trim().min(1).max(500),
  recordId: z.string().uuid().optional(),
  challengeId: z.string().uuid().optional(),
  questionId: z.string().min(1).max(100).optional(),
}).strict();

const ResolvedAssumptionGroundingSchema = z.object({
  statement: z.array(AssumptionGroundingSourceSchema).min(1).max(8).optional(),
  impactIfFalse: z.array(AssumptionGroundingSourceSchema).min(1).max(8).optional(),
  falsificationQuestion: z.array(AssumptionGroundingSourceSchema).min(1).max(8).optional(),
}).strict();

export const SelectionCopilotActionSchema = z.object({
  kind: z.literal('selection_copilot_action'),
  action: z.enum(['open', 'prefill', 'shortlist_review']),
  target: z.string().min(1).max(80),
  ideas: z.array(CanonicalIdeaSchema).max(3).default([]),
  lens: SelectionChallengeLensSchema.optional(),
  record: CanonicalRecordSchema.optional(),
  origin: z.object({ challengeId: z.string().uuid(), questionId: z.string().min(1).max(100) }).strict().optional(),
  expectedVersion: z.number().int().nonnegative().optional(),
  values: z.record(z.unknown()).optional(),
  grounding: ResolvedAssumptionGroundingSchema.optional(),
  rationale: z.string().trim().min(3).max(1_000),
  caveats: z.array(z.string().trim().min(3).max(300)).max(5).default([]),
}).strict();

export type PrepareSelectionActionArgs = z.infer<typeof PrepareSelectionActionArgsSchema>;
export type SelectionCopilotAction = z.infer<typeof SelectionCopilotActionSchema>;
