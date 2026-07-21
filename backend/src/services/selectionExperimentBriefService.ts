import {
  ExperimentAssumptionType,
  ExperimentEvidenceSignal,
  ExperimentMethod,
  SelectionExperimentRunStatus,
  type SelectionExperiment,
} from '@prisma/client';
import { z } from 'zod';
import { SelectionExperimentOriginSnapshotSchema } from '../types/selectionExperiment.js';

export const SelectionExperimentBriefArtifactSchema = z.object({
  version: z.literal(1),
  experimentId: z.string().uuid(),
  jobId: z.string().uuid(),
  lockedAt: z.string().datetime().nullable(),
  idea: z.object({
    ideaId: z.string().min(1).max(100),
    ideaRevision: z.number().int().positive(),
    snapshot: z.record(z.unknown()),
  }).strict(),
  origin: SelectionExperimentOriginSnapshotSchema.nullable(),
  assumption: z.object({
    type: z.nativeEnum(ExperimentAssumptionType),
    statement: z.string(),
    whyCritical: z.string(),
    currentEvidence: z.string(),
  }).strict(),
  testDesign: z.object({
    method: z.nativeEnum(ExperimentMethod),
    evidenceSignal: z.nativeEnum(ExperimentEvidenceSignal),
    stimulus: z.string(),
    audience: z.string(),
    channel: z.string(),
    primaryMetric: z.string(),
    passThreshold: z.string(),
    failThreshold: z.string(),
    measurementWindow: z.string(),
    sampleTarget: z.number().int().positive().nullable(),
    costEstimate: z.string(),
  }).strict(),
  decisionRules: z.object({
    pass: z.string(),
    fail: z.string(),
    ambiguous: z.string(),
    invalid: z.string(),
  }).strict(),
}).strict();

export const FrozenSelectionExperimentBriefSchema = SelectionExperimentBriefArtifactSchema.extend({
  briefFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  runStatusAtDecision: z.nativeEnum(SelectionExperimentRunStatus).nullable(),
}).strict();

export function materializeSelectionExperimentBrief(experiment: SelectionExperiment) {
  const origin = experiment.originSnapshot
    ? SelectionExperimentOriginSnapshotSchema.parse(experiment.originSnapshot)
    : null;
  return SelectionExperimentBriefArtifactSchema.parse({
    version: 1 as const,
    experimentId: experiment.id,
    jobId: experiment.jobId,
    lockedAt: experiment.lockedAt?.toISOString() ?? null,
    idea: {
      ideaId: experiment.ideaId,
      ideaRevision: experiment.ideaRevision,
      snapshot: experiment.ideaSnapshot,
    },
    origin,
    assumption: {
      type: experiment.assumptionType,
      statement: experiment.assumption,
      whyCritical: experiment.whyCritical,
      currentEvidence: experiment.currentEvidence,
    },
    testDesign: {
      method: experiment.method,
      evidenceSignal: experiment.evidenceSignal,
      stimulus: experiment.stimulus,
      audience: experiment.audience,
      channel: experiment.channel,
      primaryMetric: experiment.primaryMetric,
      passThreshold: experiment.passThreshold,
      failThreshold: experiment.failThreshold,
      measurementWindow: experiment.measurementWindow,
      sampleTarget: experiment.sampleTarget,
      costEstimate: experiment.costEstimate,
    },
    decisionRules: {
      pass: experiment.passAction,
      fail: experiment.failAction,
      ambiguous: experiment.flatAction,
      invalid: experiment.invalidAction,
    },
  });
}

export type SelectionExperimentBriefArtifact = z.infer<typeof SelectionExperimentBriefArtifactSchema>;
export type FrozenSelectionExperimentBrief = z.infer<typeof FrozenSelectionExperimentBriefSchema>;

export function renderSelectionExperimentBriefMarkdown(
  brief: SelectionExperimentBriefArtifact,
): string {
  const idea = brief.idea.snapshot as Record<string, unknown>;
  const title = String(idea.headline || idea.solution_name || brief.idea.ideaId);
  const origin = brief.origin
    ? [
      '## Evidence-check origin',
      '',
      `- Challenge: ${brief.origin.challengeId}`,
      `- Question: ${brief.origin.questionId}`,
      `- Lens: ${brief.origin.lens}`,
      `- Consensus at draft time: ${brief.origin.consensus}`,
      `- Evidence packet: ${brief.origin.challengeInputFingerprint}`,
      `- Cited sources: ${brief.origin.citedSources.map(source => source.title).join('; ') || 'None'}`,
      '',
    ]
    : [];
  return [
    `# Test brief: ${title}`,
    '',
    `- Experiment: ${brief.experimentId}`,
    `- Candidate: ${brief.idea.ideaId} · revision ${brief.idea.ideaRevision}`,
    `- Locked: ${brief.lockedAt ?? 'Not recorded'}`,
    '',
    ...origin,
    '## Assumption',
    '',
    brief.assumption.statement,
    '',
    `**Why it changes the decision:** ${brief.assumption.whyCritical}`,
    '',
    `**Current evidence:** ${brief.assumption.currentEvidence || 'No evidence recorded.'}`,
    '',
    '## Test design',
    '',
    `- Method: ${brief.testDesign.method}`,
    `- Signal: ${brief.testDesign.evidenceSignal}`,
    `- Audience: ${brief.testDesign.audience}`,
    `- Channel: ${brief.testDesign.channel}`,
    `- Stimulus: ${brief.testDesign.stimulus}`,
    `- Primary metric: ${brief.testDesign.primaryMetric}`,
    `- Sample target: ${brief.testDesign.sampleTarget ?? 'Not specified'}`,
    `- Stopping rule: ${brief.testDesign.measurementWindow}`,
    `- Cost estimate: ${brief.testDesign.costEstimate || 'Not specified'}`,
    '',
    '## Precommitted thresholds',
    '',
    `- Pass: ${brief.testDesign.passThreshold}`,
    `- Fail: ${brief.testDesign.failThreshold}`,
    '',
    '## Precommitted actions',
    '',
    `- If pass: ${brief.decisionRules.pass}`,
    `- If fail: ${brief.decisionRules.fail}`,
    `- If ambiguous: ${brief.decisionRules.ambiguous}`,
    `- If invalid: ${brief.decisionRules.invalid}`,
    '',
    '> This brief records a precommitted test of one assumption. It does not validate the idea or alter its research score.',
    '',
  ].join('\n');
}
