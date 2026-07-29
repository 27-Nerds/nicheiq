import { z } from 'zod';
import {
  FOUNDER_FIT_DIMENSIONS,
  FounderFitIdeaFieldSchema,
  FounderFitProfileFieldSchema,
} from './founderFit.js';

export const SynthesisOperationSchema = z.enum([
  'narrow',
  'reposition',
  'combine',
  'adjacent',
]);
export type SynthesisOperation = z.infer<typeof SynthesisOperationSchema>;

export const IDEA_SYNTHESIS_TEXT_LIMITS = {
  sourceContribution: 300,
  proposedTitle: 160,
  proposedBrief: 2000,
  changeSummary: 600,
  rationale: 600,
  newAssumption: 300,
} as const;

export const ProposeIdeaSynthesisArgsSchema = z.object({
  operation: SynthesisOperationSchema,
  source_refs: z.array(z.string().regex(/^R[1-9]\d*$/)).min(1).max(2),
  source_contributions: z.array(z.string().trim().min(1).max(IDEA_SYNTHESIS_TEXT_LIMITS.sourceContribution)).min(1).max(2),
  proposed_title: z.string().trim().min(1).max(IDEA_SYNTHESIS_TEXT_LIMITS.proposedTitle),
  proposed_brief: z.string().trim().min(1).max(IDEA_SYNTHESIS_TEXT_LIMITS.proposedBrief),
  change_summary: z.string().trim().min(1).max(IDEA_SYNTHESIS_TEXT_LIMITS.changeSummary),
  rationale: z.string().trim().min(1).max(IDEA_SYNTHESIS_TEXT_LIMITS.rationale),
  new_assumptions: z.array(z.string().trim().min(1).max(IDEA_SYNTHESIS_TEXT_LIMITS.newAssumption)).max(6).default([]),
}).superRefine((value, ctx) => {
  const requiredParents = value.operation === 'combine' ? 2 : 1;
  if (value.source_refs.length !== requiredParents) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['source_refs'],
      message: `${value.operation} requires exactly ${requiredParents} source candidate${requiredParents === 1 ? '' : 's'}`,
    });
  }
  if (value.source_contributions.length !== value.source_refs.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['source_contributions'],
      message: 'Each source candidate requires one contribution statement',
    });
  }
  if (new Set(value.source_refs).size !== value.source_refs.length) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['source_refs'],
      message: 'Source candidates must be distinct',
    });
  }
});
export type ProposeIdeaSynthesisArgs = z.infer<typeof ProposeIdeaSynthesisArgsSchema>;

function boundedProposalText(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…`;
}

/**
 * An owner-launched workshop action already fixes the operation and exact parent
 * revisions before the model runs. Treat those identity fields as server-owned and
 * recover bounded proposal prose from the tool payload instead of rejecting the
 * whole draft when the model redundantly echoes a wrong ref, an extra contribution,
 * or text beyond the persisted limits.
 */
export function normalizeLockedIdeaSynthesisArgs(
  value: unknown,
  operation: SynthesisOperation,
  sourceRefs: string[],
): ProposeIdeaSynthesisArgs | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const rawContributions = Array.isArray(raw.source_contributions)
    ? raw.source_contributions
    : [];
  if (rawContributions.length < sourceRefs.length) return null;

  const sourceContributions = rawContributions
    .slice(0, sourceRefs.length)
    .map((entry) => boundedProposalText(entry, IDEA_SYNTHESIS_TEXT_LIMITS.sourceContribution));
  if (sourceContributions.some((entry) => entry === null)) return null;

  const proposedTitle = boundedProposalText(raw.proposed_title, IDEA_SYNTHESIS_TEXT_LIMITS.proposedTitle);
  const proposedBrief = boundedProposalText(raw.proposed_brief, IDEA_SYNTHESIS_TEXT_LIMITS.proposedBrief);
  const changeSummary = boundedProposalText(raw.change_summary, IDEA_SYNTHESIS_TEXT_LIMITS.changeSummary);
  const rationale = boundedProposalText(raw.rationale, IDEA_SYNTHESIS_TEXT_LIMITS.rationale);
  if (!proposedTitle || !proposedBrief || !changeSummary || !rationale) return null;

  const rawAssumptions = Array.isArray(raw.new_assumptions) ? raw.new_assumptions : [];
  const newAssumptions = rawAssumptions
    .slice(0, 6)
    .map((entry) => boundedProposalText(entry, IDEA_SYNTHESIS_TEXT_LIMITS.newAssumption));
  if (newAssumptions.some((entry) => entry === null)) return null;

  const parsed = ProposeIdeaSynthesisArgsSchema.safeParse({
    operation,
    source_refs: sourceRefs,
    source_contributions: sourceContributions,
    proposed_title: proposedTitle,
    proposed_brief: proposedBrief,
    change_summary: changeSummary,
    rationale,
    new_assumptions: newAssumptions,
  });
  return parsed.success ? parsed.data : null;
}

export const IdeaSynthesisParentSchema = z.object({
  ideaId: z.string().trim().min(1).max(128),
  ideaRevision: z.number().int().min(1),
  solutionName: z.string().trim().min(1).max(300),
  contribution: z.string().trim().min(1).max(300),
});

export const ExperimentConclusionReferenceSchema = z.object({
  conclusionId: z.string().uuid(),
  experimentId: z.string().uuid(),
  outcome: z.enum(['FAIL', 'AMBIGUOUS']),
  evidenceSource: z.enum(['HOSTED_RUN', 'MANUAL']),
  snapshotSha256: z.string().regex(/^[a-f0-9]{64}$/),
  evidenceRefs: z.array(z.object({
    adapterKey: z.string().trim().min(1).max(64),
    reference: z.string().trim().min(1).max(1000),
  }).strict()).max(10),
}).strict();

export const FounderFitSynthesisReferenceSchema = z.object({
  inputFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  ideaId: z.string().trim().min(1).max(128),
  ideaRevision: z.number().int().min(1),
  verdict: z.literal('needs_reshape'),
  conflicts: z.array(z.object({
    dimension: z.enum(FOUNDER_FIT_DIMENSIONS),
    summary: z.string().trim().min(3).max(600),
    profileFields: z.array(FounderFitProfileFieldSchema).min(1).max(3),
    ideaFields: z.array(FounderFitIdeaFieldSchema).max(6),
  }).strict()).min(1).max(6),
}).strict();

const SynthesisChangedAxisSchema = z.object({
  axis: z.enum(['buyer', 'job', 'mechanism', 'channel', 'scope', 'business_model']),
  from: z.string().trim().min(1).max(500),
  to: z.string().trim().min(1).max(500),
  reason: z.string().trim().min(3).max(600),
}).strict();

const SynthesisDecisionAssumptionSchema = z.object({
  assumptionId: z.string().regex(/^A[a-f0-9]{10}$/),
  type: z.enum(['demand', 'distribution', 'competition', 'feasibility', 'founder_fit']),
  statement: z.string().trim().min(3).max(500),
  whyDecisionChanging: z.string().trim().min(3).max(600),
  consequenceIfFalse: z.string().trim().min(3).max(600),
}).strict();

const SynthesisSuggestedTestSchema = z.object({
  assumptionId: z.string().regex(/^A[a-f0-9]{10}$/),
  hypothesis: z.string().trim().min(3).max(700),
  method: z.string().trim().min(1).max(100),
  evidenceSignal: z.string().trim().min(1).max(100),
  audience: z.string().trim().min(3).max(500),
  artifact: z.string().trim().min(3).max(700),
  primaryMetric: z.string().trim().min(3).max(500),
  passThreshold: z.string().trim().min(3).max(500),
  failThreshold: z.string().trim().min(3).max(500),
  measurementWindow: z.string().trim().min(3).max(300),
}).strict();

/**
 * Exact, code-owned Concept Forge option selected for evaluation. Optional so older
 * analyst-authored synthesis proposals and ordinary free-text seeds remain valid.
 */
export const SynthesisEvaluationBriefSchema = z.object({
  version: z.literal(1),
  conceptSetId: z.string().uuid(),
  optionId: z.string().regex(/^O[a-f0-9]{11}$/),
  inputFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  changedAxes: z.array(SynthesisChangedAxisSchema).min(1).max(4),
  assumptions: z.array(SynthesisDecisionAssumptionSchema).min(1).max(3),
  retainedEvidence: z.array(z.string().trim().min(3).max(400)).min(1).max(6),
  evidenceToRecheck: z.array(z.string().trim().min(3).max(400)).min(1).max(8),
  disqualifiers: z.array(z.string().trim().min(3).max(400)).min(1).max(5),
  suggestedTest: SynthesisSuggestedTestSchema,
}).strict().superRefine((value, ctx) => {
  if (!value.assumptions.some((assumption) =>
    assumption.assumptionId === value.suggestedTest.assumptionId
  )) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['suggestedTest', 'assumptionId'],
      message: 'The suggested test must target one evaluation assumption',
    });
  }
});

export const IdeaSynthesisPatchSchema = z.object({
  kind: z.literal('idea_synthesis'),
  operation: SynthesisOperationSchema,
  proposedTitle: z.string().trim().min(1).max(160),
  proposedBrief: z.string().trim().min(1).max(2000),
  changeSummary: z.string().trim().min(1).max(600),
  rationale: z.string().trim().min(1).max(600),
  parents: z.array(IdeaSynthesisParentSchema).min(1).max(2),
  evidence: z.object({
    sourceAnchors: z.array(z.object({
      ideaId: z.string().trim().min(1).max(128),
      ideaRevision: z.number().int().min(1),
      candidateSnapshotSha256: z.string().regex(/^[a-f0-9]{64}$/),
      pain: z.string().trim().min(1).max(500).optional(),
      audience: z.string().trim().min(1).max(500).optional(),
    }).strict()).min(1).max(2),
    requiresValidation: z.array(z.string().trim().min(1).max(500)).min(1).max(10),
    experimentConclusionRefs: z.array(ExperimentConclusionReferenceSchema).max(1).optional(),
    founderFitRef: FounderFitSynthesisReferenceSchema.optional(),
  }).strict(),
  newAssumptions: z.array(z.string().trim().min(1).max(300)).max(6),
  evaluation: SynthesisEvaluationBriefSchema.optional(),
}).superRefine((value, ctx) => {
  const requiredParents = value.operation === 'combine' ? 2 : 1;
  if (value.parents.length !== requiredParents) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['parents'],
      message: `${value.operation} requires exactly ${requiredParents} parent candidate${requiredParents === 1 ? '' : 's'}`,
    });
  }
  const parentRefs = value.parents.map((parent) => `${parent.ideaId}:${parent.ideaRevision}`);
  const anchorRefs = value.evidence.sourceAnchors.map((anchor) => `${anchor.ideaId}:${anchor.ideaRevision}`);
  if (
    new Set(parentRefs).size !== parentRefs.length
    || new Set(anchorRefs).size !== anchorRefs.length
    || [...parentRefs].sort().join('|') !== [...anchorRefs].sort().join('|')
  ) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['evidence', 'sourceAnchors'],
      message: 'Source anchors must match every exact parent revision once',
    });
  }
  const fitRef = value.evidence.founderFitRef;
  if (fitRef && (
    value.parents.length !== 1
    || value.parents[0].ideaId !== fitRef.ideaId
    || value.parents[0].ideaRevision !== fitRef.ideaRevision
  )) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['evidence', 'founderFitRef'],
      message: 'Founder-fit provenance must match the exact single parent revision',
    });
  }
});
export type IdeaSynthesisPatch = z.infer<typeof IdeaSynthesisPatchSchema>;
