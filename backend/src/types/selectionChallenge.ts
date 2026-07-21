import { z } from 'zod';

export const SELECTION_CHALLENGE_LENSES = [
  'demand',
  'competition',
  'distribution',
  'dependencies',
] as const;

export const SelectionChallengeLensSchema = z.enum(SELECTION_CHALLENGE_LENSES);
export type SelectionChallengeLens = z.infer<typeof SelectionChallengeLensSchema>;

export const SELECTION_CHALLENGE_QUESTIONS = {
  demand: [
    'pain_is_observed',
    'urgency_is_behavioral',
    'buyer_will_pay',
  ],
  competition: [
    'substitutes_are_weak',
    'switching_barrier_is_surmountable',
    'wedge_is_defensible',
  ],
  distribution: [
    'audience_is_reachable',
    'channel_matches_observed_behavior',
    'acquisition_friction_is_plausible',
  ],
  dependencies: [
    'required_data_is_obtainable',
    'critical_integrations_are_available',
    'platform_and_compliance_risk_is_bounded',
  ],
} as const satisfies Record<SelectionChallengeLens, readonly string[]>;

export const SelectionChallengeRequestSchema = z.object({
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive().max(1_000_000),
  lens: SelectionChallengeLensSchema,
}).strict();

export const SelectionChallengePositionSchema = z.enum([
  'supports',
  'contradicts',
  'mixed',
  'insufficient',
]);

export const SelectionChallengeEvidenceClassSchema = z.enum([
  'observed',
  'proxy',
  'inference',
]);

export const SelectionChallengeAgentAssessmentSchema = z.object({
  questionId: z.string().trim().min(1).max(100),
  position: SelectionChallengePositionSchema,
  summary: z.string().trim().min(3).max(1_000),
  subjectKeys: z.array(z.string().regex(/^I\d+$/)).max(8),
  evidenceKeys: z.array(z.string().regex(/^S\d+$/)).max(10),
  evidenceClass: SelectionChallengeEvidenceClassSchema,
}).strict();

export const SelectionChallengeAgentResponseSchema = z.object({
  assessments: z.array(SelectionChallengeAgentAssessmentSchema).length(3),
}).strict();

const SelectionChallengeExperimentMetricSchema = z.object({
  key: z.string().trim().min(1).max(100),
  label: z.string().trim().min(1).max(300),
  valueType: z.string().trim().min(1).max(50),
  value: z.number().finite(),
  numerator: z.number().finite().optional(),
  denominator: z.number().finite().optional(),
  isPrimary: z.boolean(),
}).strict();

const SelectionChallengeExperimentObservationSchema = z.object({
  observedThrough: z.string().datetime().nullable(),
  observationSummary: z.string().trim().min(1).max(1_500).nullable(),
  observedMetric: z.string().trim().min(1).max(500).nullable(),
  metrics: z.array(SelectionChallengeExperimentMetricSchema).max(12),
  sample: z.object({
    observed: z.number().int().nonnegative().nullable(),
    target: z.number().int().positive().nullable(),
    unit: z.string().trim().min(1).max(100).nullable(),
  }).strict(),
  limitations: z.array(z.string().trim().min(1).max(500)).max(10),
}).strict();

export const SelectionChallengeSourceSchema = z.object({
  key: z.string().regex(/^S\d+$/),
  kind: z.enum([
    'customer_quote',
    'competitor_fact',
    'market_caveat',
    'audience_fact',
    'dependency_note',
    'owner_evidence',
    'experiment_result',
  ]),
  title: z.string().trim().min(1).max(300),
  excerpt: z.string().trim().min(1).max(1_500),
  url: z.string().url().refine(value => /^https?:\/\//i.test(value)).nullable(),
  capturedAt: z.string().datetime().nullable(),
  provenance: z.discriminatedUnion('assetType', [
    z.object({
      assetType: z.enum(['DISCOVERY_DATA', 'PREVIEW_REPORT']),
      jsonPointer: z.string().trim().min(1).max(500),
    }).strict(),
    z.object({
      assetType: z.literal('OWNER_EVIDENCE'),
      evidenceItemId: z.string().uuid(),
      position: z.enum(['SUPPORTS', 'CONTRADICTS', 'CONTEXT']),
      ownerKind: z.enum(['NOTE', 'CUSTOMER_QUOTE', 'ANALYTICS_OBSERVATION', 'LINK']),
    }).strict(),
    z.object({
      assetType: z.literal('EXPERIMENT_RESULT'),
      experimentId: z.string().uuid(),
      conclusionId: z.string().uuid(),
      originChallengeId: z.string().uuid(),
      evidenceClass: z.enum(['observed', 'proxy']),
      sourceType: z.enum(['FIRST_PARTY', 'MANUAL']),
      adapterKey: z.string().trim().min(1).max(100),
      precommitment: z.object({
        primaryMetric: z.string().trim().min(1).max(500),
        passThreshold: z.string().trim().min(1).max(500),
        failThreshold: z.string().trim().min(1).max(500),
        measurementWindow: z.string().trim().min(1).max(500),
        sampleTarget: z.number().int().positive().nullable(),
      }).strict(),
      observation: SelectionChallengeExperimentObservationSchema,
    }).strict(),
  ]),
}).strict();

export const SelectionChallengeSubjectSchema = z.object({
  key: z.string().regex(/^I\d+$/),
  field: z.string().trim().min(1).max(100),
  value: z.unknown(),
}).strict();

export const SelectionChallengeConsensusSchema = z.enum([
  'supported',
  'contradicted',
  'mixed',
  'disputed',
  'insufficient',
]);

export const SelectionChallengeOverallSchema = z.enum([
  'withstands',
  'weakened',
  'contradicted',
  'disputed',
  'insufficient_evidence',
]);

export const SelectionChallengeQuestionResultSchema = z.object({
  questionId: z.string().trim().min(1).max(100),
  consensus: SelectionChallengeConsensusSchema,
  skeptic: SelectionChallengeAgentAssessmentSchema,
  auditor: SelectionChallengeAgentAssessmentSchema,
}).strict();

export const SelectionChallengeArtifactSchema = z.object({
  version: z.literal(1),
  inputFingerprint: z.string().length(64),
  ideaId: z.string().min(1).max(100),
  ideaRevision: z.number().int().positive(),
  ideaTitle: z.string().min(1).max(500),
  lens: SelectionChallengeLensSchema,
  overall: SelectionChallengeOverallSchema,
  ideaSnapshot: z.record(z.unknown()),
  subjectSnapshot: z.array(SelectionChallengeSubjectSchema).min(1).max(24),
  evidenceSnapshot: z.array(SelectionChallengeSourceSchema).max(24),
  questions: z.array(SelectionChallengeQuestionResultSchema).length(3),
  skepticModel: z.string().min(1).max(255),
  auditorModel: z.string().min(1).max(255),
  promptVersion: z.literal(1),
  createdAt: z.string().datetime(),
}).strict();

export type SelectionChallengeArtifact = z.infer<typeof SelectionChallengeArtifactSchema>;
export type SelectionChallengeAgentAssessment = z.infer<typeof SelectionChallengeAgentAssessmentSchema>;
export type SelectionChallengeConsensus = z.infer<typeof SelectionChallengeConsensusSchema>;
export type SelectionChallengePosition = z.infer<typeof SelectionChallengePositionSchema>;
export type SelectionChallengeSource = z.infer<typeof SelectionChallengeSourceSchema>;
export type SelectionChallengeSubject = z.infer<typeof SelectionChallengeSubjectSchema>;
