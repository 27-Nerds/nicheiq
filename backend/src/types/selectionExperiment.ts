import { z } from 'zod';
import {
  SelectionChallengeAgentAssessmentSchema,
  SelectionChallengeSourceSchema,
} from './selectionChallenge.js';
import {
  SelectionAssumptionDirectionSchema,
  SelectionAssumptionEvidenceClassSchema,
  SelectionAssumptionOwnerStateSchema,
} from './selectionAssumption.js';

export const AssumptionTypeSchema = z.enum([
  'DESIRABILITY',
  'USABILITY',
  'FEASIBILITY',
  'VIABILITY',
  'ETHICS',
]);

export const ExperimentMethodSchema = z.enum([
  'CUSTOMER_INTERVIEWS',
  'SURVEY',
  'CTA_SMOKE_TEST',
  'BOOKED_CALL',
  'PREORDER',
  'CONCIERGE',
  'PROTOTYPE',
  'TECHNICAL_SPIKE',
  'OTHER',
]);

export const EvidenceSignalSchema = z.enum([
  'LANGUAGE',
  'STATED_PREFERENCE',
  'CTA_INTEREST',
  'SMALL_COMMITMENT',
  'PAYMENT_INTENT',
  'USAGE',
]);

export const SelectionExperimentOriginSnapshotSchema = z.object({
  version: z.literal(1),
  kind: z.literal('SELECTION_CHALLENGE_QUESTION'),
  challengeId: z.string().uuid(),
  challengeInputFingerprint: z.string().length(64),
  questionId: z.string().trim().min(1).max(100),
  lens: z.enum(['demand', 'competition', 'distribution', 'dependencies']),
  consensus: z.enum(['supported', 'contradicted', 'mixed', 'disputed', 'insufficient']),
  evidenceKeys: z.array(z.string().regex(/^S\d+$/)).max(20),
  skeptic: SelectionChallengeAgentAssessmentSchema,
  auditor: SelectionChallengeAgentAssessmentSchema,
  citedSources: z.array(SelectionChallengeSourceSchema).max(20),
}).strict();

const boundedText = (label: string, max: number) =>
  z.string().trim().min(3, `${label} is required`).max(max);

export const SelectionExperimentDraftSchema = z.object({
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive().max(1_000_000),
  originChallengeId: z.string().uuid().nullable().default(null),
  originQuestionId: z.string().trim().min(1).max(100).nullable().default(null),
  assumptionId: z.string().uuid().nullable().optional(),
  assumptionType: AssumptionTypeSchema,
  assumption: boundedText('Assumption', 1_000),
  whyCritical: boundedText('Why this matters', 1_500),
  currentEvidence: z.string().trim().max(2_000).default(''),
  method: ExperimentMethodSchema,
  evidenceSignal: EvidenceSignalSchema,
  stimulus: boundedText('Test stimulus', 1_500),
  audience: boundedText('Qualified audience', 1_000),
  channel: boundedText('Recruitment channel', 500),
  primaryMetric: boundedText('Primary metric', 500),
  passThreshold: boundedText('Pass threshold', 500),
  failThreshold: boundedText('Fail threshold', 500),
  measurementWindow: boundedText('Measurement window', 500),
  sampleTarget: z.number().int().positive().max(1_000_000).nullable().default(null),
  costEstimate: z.string().trim().max(255).default(''),
  passAction: boundedText('Pass action', 1_000),
  failAction: boundedText('Fail action', 1_000),
  flatAction: boundedText('Flat-result action', 1_000),
  invalidAction: boundedText('Invalid-result action', 1_000),
}).strict();

export type SelectionExperimentDraft = z.infer<typeof SelectionExperimentDraftSchema>;
export type SelectionExperimentOriginSnapshot = z.infer<typeof SelectionExperimentOriginSnapshotSchema>;

export const ExperimentCtaLabelSchema = z.enum([
  'IM_INTERESTED',
  'SHOW_ME_THE_CONCEPT',
  'ID_TRY_THIS',
]);

export const SelectionExperimentLaunchSchema = z.object({
  headline: boundedText('Public headline', 140),
  promise: boundedText('Public promise', 1_000),
  ctaLabel: ExperimentCtaLabelSchema,
}).strict();

export const SelectionExperimentEventInputSchema = z.object({
  eventId: z.string().uuid(),
  viewToken: z.string().min(32).max(1_000),
  type: z.enum([
    'STIMULUS_EXPOSED',
    'CTA_CLICKED',
    'FAKE_DOOR_DISCLOSED',
    'CLIENT_ERROR',
  ]),
  occurredAt: z.string().datetime({ offset: true }),
}).strict();

export const SelectionExperimentOutcomeSchema = z.enum([
  'PASS',
  'FAIL',
  'AMBIGUOUS',
  'INVALID',
]);

const ConclusionBaseSchema = z.object({
  outcome: SelectionExperimentOutcomeSchema,
  ownerRationale: boundedText('Owner rationale', 2_000),
  limitations: z.array(z.string().trim().min(3).max(500)).max(10).default([]),
});

export const SelectionExperimentConclusionInputSchema = z.discriminatedUnion('evidenceSource', [
  ConclusionBaseSchema.extend({
    evidenceSource: z.literal('HOSTED_RUN'),
  }).strict(),
  ConclusionBaseSchema.extend({
    evidenceSource: z.literal('MANUAL'),
    observationSummary: boundedText('Observed result', 3_000),
    observedAt: z.string().date(),
    sampleSize: z.number().int().positive().max(1_000_000).nullable().default(null),
    observedMetric: z.string().trim().max(500).default(''),
    sourceReferences: z.array(z.string().trim().min(1).max(1_000)).max(10).default([]),
  }).strict(),
]);

export const SelectionExperimentConclusionSnapshotSchema = z.object({
  schemaVersion: z.literal(1),
  experiment: z.object({
    experimentId: z.string(),
    jobId: z.string(),
    ideaId: z.string(),
    ideaRevision: z.number().int().positive(),
    ideaSnapshot: z.record(z.string(), z.unknown()),
    assumptionType: AssumptionTypeSchema,
    evidenceSignal: EvidenceSignalSchema,
    assumption: z.string(),
    assumptionId: z.string().nullable().optional(),
  }).passthrough(),
  precommitment: z.object({
    primaryMetric: z.string(),
    passThreshold: z.string(),
    failThreshold: z.string(),
    measurementWindow: z.string(),
    sampleTarget: z.number().int().positive().nullable(),
    passAction: z.string(),
    failAction: z.string(),
    ambiguousAction: z.string(),
    invalidAction: z.string(),
  }).passthrough(),
  evidence: z.object({
    source: z.object({
      sourceType: z.enum(['FIRST_PARTY', 'MANUAL']),
      adapterKey: z.string(),
    }).passthrough(),
    limitations: z.array(z.string()),
  }).passthrough(),
  adjudication: z.object({
    outcome: SelectionExperimentOutcomeSchema,
    basis: z.literal('OWNER_RECORDED'),
    rationale: z.string(),
    nextAction: z.string(),
  }).passthrough(),
  assumptionTransition: z.object({
    assumptionId: z.string(),
    before: z.object({
      direction: SelectionAssumptionDirectionSchema,
      evidenceClass: SelectionAssumptionEvidenceClassSchema,
      ownerState: SelectionAssumptionOwnerStateSchema,
      version: z.number().int().positive(),
    }).strict(),
    after: z.object({
      direction: SelectionAssumptionDirectionSchema,
      evidenceClass: SelectionAssumptionEvidenceClassSchema,
      ownerState: SelectionAssumptionOwnerStateSchema,
      version: z.number().int().positive(),
    }).strict(),
  }).strict().nullable().optional(),
}).passthrough();

export type SelectionExperimentLaunch = z.infer<typeof SelectionExperimentLaunchSchema>;
export type SelectionExperimentEventInput = z.infer<typeof SelectionExperimentEventInputSchema>;
export type SelectionExperimentConclusionInput = z.infer<typeof SelectionExperimentConclusionInputSchema>;
export type SelectionExperimentConclusionSnapshot = z.infer<typeof SelectionExperimentConclusionSnapshotSchema>;
