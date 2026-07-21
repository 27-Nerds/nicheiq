import { z } from 'zod';
import {
  EvidenceSignalSchema,
  ExperimentMethodSchema,
} from './selectionExperiment.js';
import { SynthesisOperationSchema } from './ideaSynthesis.js';

export const SelectionConceptPurposeSchema = z.enum([
  'diverge',
  'resolve_tradeoff',
  'reshape',
]);
export type SelectionConceptPurpose = z.infer<typeof SelectionConceptPurposeSchema>;

export const SelectionConceptParentRequestSchema = z.object({
  ideaId: z.string().trim().min(1).max(128),
  ideaRevision: z.number().int().positive().max(1_000_000),
}).strict();

export const SelectionConceptSetRequestSchema = z.object({
  purpose: SelectionConceptPurposeSchema,
  parents: z.array(SelectionConceptParentRequestSchema).min(1).max(2),
  targetTradeoff: z.string().trim().min(3).max(500).optional(),
}).strict().superRefine((value, ctx) => {
  const refs = value.parents.map((parent) => `${parent.ideaId}:${parent.ideaRevision}`);
  if (new Set(refs).size !== refs.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['parents'],
      message: 'Concept parents must be distinct exact revisions',
    });
  }
  if (value.purpose === 'resolve_tradeoff' && value.parents.length !== 2) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['parents'],
      message: 'Resolving a trade-off requires exactly two parents',
    });
  }
});

export const SelectionConceptParentSchema = SelectionConceptParentRequestSchema.extend({
  solutionName: z.string().trim().min(1).max(300),
  candidateSnapshotSha256: z.string().regex(/^[a-f0-9]{64}$/),
  pain: z.string().trim().min(1).max(500).nullable(),
  audience: z.string().trim().min(1).max(500).nullable(),
}).strict();

export const SelectionConceptAxisSchema = z.enum([
  'buyer',
  'job',
  'mechanism',
  'channel',
  'scope',
  'business_model',
]);

export const SelectionConceptRiskTypeSchema = z.enum([
  'demand',
  'distribution',
  'competition',
  'feasibility',
  'founder_fit',
]);

export const SelectionConceptChangedAxisSchema = z.object({
  axis: SelectionConceptAxisSchema,
  from: z.string().trim().min(1).max(500),
  to: z.string().trim().min(1).max(500),
  reason: z.string().trim().min(3).max(600),
}).strict();

export const SelectionConceptAssumptionSchema = z.object({
  assumptionId: z.string().regex(/^A[a-f0-9]{10}$/),
  type: SelectionConceptRiskTypeSchema,
  statement: z.string().trim().min(3).max(500),
  whyDecisionChanging: z.string().trim().min(3).max(600),
  consequenceIfFalse: z.string().trim().min(3).max(600),
}).strict();

export const SelectionConceptTestSchema = z.object({
  assumptionId: z.string().regex(/^A[a-f0-9]{10}$/),
  hypothesis: z.string().trim().min(3).max(700),
  method: ExperimentMethodSchema,
  evidenceSignal: EvidenceSignalSchema,
  audience: z.string().trim().min(3).max(500),
  artifact: z.string().trim().min(3).max(700),
  primaryMetric: z.string().trim().min(3).max(500),
  passThreshold: z.string().trim().min(3).max(500),
  failThreshold: z.string().trim().min(3).max(500),
  measurementWindow: z.string().trim().min(3).max(300),
}).strict();

export const SelectionConceptOptionSchema = z.object({
  optionId: z.string().regex(/^O[a-f0-9]{11}$/),
  operation: SynthesisOperationSchema,
  title: z.string().trim().min(3).max(160),
  brief: z.string().trim().min(20).max(2_000),
  changeSummary: z.string().trim().min(10).max(700),
  rationale: z.string().trim().min(10).max(700),
  parentContributions: z.array(SelectionConceptParentSchema.extend({
    contribution: z.string().trim().min(3).max(300),
  }).strict()).min(1).max(2),
  changedAxes: z.array(SelectionConceptChangedAxisSchema).min(1).max(4),
  retainedEvidence: z.array(z.string().trim().min(3).max(400)).min(1).max(6),
  evidenceToRecheck: z.array(z.string().trim().min(3).max(400)).min(1).max(8),
  assumptions: z.array(SelectionConceptAssumptionSchema).min(1).max(3),
  disqualifiers: z.array(z.string().trim().min(3).max(400)).min(1).max(5),
  suggestedTest: SelectionConceptTestSchema,
}).strict().superRefine((value, ctx) => {
  const requiredParents = value.operation === 'combine' ? 2 : 1;
  if (value.parentContributions.length !== requiredParents) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['parentContributions'],
      message: `${value.operation} requires exactly ${requiredParents} parent${requiredParents === 1 ? '' : 's'}`,
    });
  }
  if (!value.assumptions.some((assumption) => assumption.assumptionId === value.suggestedTest.assumptionId)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['suggestedTest', 'assumptionId'],
      message: 'The suggested test must target one option assumption',
    });
  }
});

export const SelectionConceptContextSchema = z.object({
  reportSha256: z.string().regex(/^[a-f0-9]{64}$/),
  founderFitFingerprint: z.string().regex(/^[a-f0-9]{64}$/).nullable(),
  challengeFingerprints: z.array(z.string().regex(/^[a-f0-9]{64}$/)).max(24),
  conclusionFingerprints: z.array(z.string().regex(/^[a-f0-9]{64}$/)).max(12),
}).strict();

export const SelectionConceptSetArtifactSchema = z.object({
  inputFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  purpose: SelectionConceptPurposeSchema,
  targetTradeoff: z.string().trim().min(3).max(500).nullable(),
  parents: z.array(SelectionConceptParentSchema).min(1).max(2),
  context: SelectionConceptContextSchema,
  options: z.array(SelectionConceptOptionSchema).length(3),
  model: z.string().trim().min(1).max(255),
  promptId: z.string().trim().min(1).max(100),
  createdAt: z.string().datetime(),
}).strict().superRefine((value, ctx) => {
  const optionIds = value.options.map((option) => option.optionId);
  if (new Set(optionIds).size !== optionIds.length) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['options'], message: 'Option identities must be unique' });
  }
  if (value.parents.length === 1) {
    const operations = new Set(value.options.map((option) => option.operation));
    for (const required of ['narrow', 'reposition', 'adjacent'] as const) {
      if (!operations.has(required)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['options'],
          message: 'A one-parent set must include narrow, reposition, and adjacent directions',
        });
        break;
      }
    }
  } else if (!value.options.some((option) => option.operation === 'combine')) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['options'],
      message: 'A two-parent set must include one combined direction',
    });
  }
});

export const PrepareSelectionConceptOptionSchema = z.object({
  expectedInputFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
}).strict();

export type SelectionConceptSetRequest = z.infer<typeof SelectionConceptSetRequestSchema>;
export type SelectionConceptParent = z.infer<typeof SelectionConceptParentSchema>;
export type SelectionConceptOption = z.infer<typeof SelectionConceptOptionSchema>;
export type SelectionConceptSetArtifact = z.infer<typeof SelectionConceptSetArtifactSchema>;
