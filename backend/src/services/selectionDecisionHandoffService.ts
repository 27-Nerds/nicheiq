import {
  SelectionDecisionHandoffAction,
  SelectionFinalDecisionDisposition,
  type Prisma,
} from '@prisma/client';
import {
  FrozenSelectionExperimentBriefSchema,
  type FrozenSelectionExperimentBrief,
} from './selectionExperimentBriefService.js';
import {
  FrozenSelectionPreMortemSchema,
  type FrozenSelectionPreMortem,
} from '../types/selectionPreMortem.js';
import { canonicalizeJson, canonicalJsonSha256 } from '../utils/canonicalFingerprint.js';
import {
  challengeConsensusLabel,
  challengeQuestionLabel,
  evidenceSignalLabel,
  experimentMethodLabel,
  handoffActionLabel,
  hostedRunStateLabel,
} from '../utils/selectionVocabulary.js';

type JsonRecord = Record<string, unknown>;

export interface FinalDecisionHandoffSource {
  id: string;
  jobId: string;
  disposition: SelectionFinalDecisionDisposition;
  selectedIdeaId: string | null;
  selectedIdeaRevision: number | null;
  testExperimentId: string | null;
  testExperimentSnapshot: unknown;
  preMortemSnapshot: unknown;
  recommendationRelation: string;
  rationale: string;
  acceptedRisks: string;
  changeCriterion: string;
  overrideReason: string | null;
  requestFingerprint: string;
  sourceFingerprint: string;
  recommendationSnapshot: unknown;
  selectedIdeaSnapshot: unknown;
  alternativesSnapshot: unknown;
  evidenceSnapshot: unknown;
  reportSha256: string;
  decidedByUserId: string;
  createdAt: Date;
}

export interface DecisionHandoffTarget {
  ideaId: string;
  ideaRevision: number;
  title: string | null;
  problem: string | null;
  audience: string | null;
  valueProposition: string | null;
  proposedScope: string[];
  technicalApproach: string | null;
  estimatedBuildTime: string | null;
}

interface SelectionDecisionHandoffArtifactBase {
  jobId: string;
  finalDecisionId: string;
  action: SelectionDecisionHandoffAction;
  target: DecisionHandoffTarget | null;
  decision: {
    disposition: SelectionFinalDecisionDisposition;
    recommendationRelation: string;
    rationale: string;
    acceptedRisks: string;
    changeCriterion: string;
    overrideReason: string | null;
    decidedAt: string;
  };
  evidence: {
    sourceFingerprint: string;
    reportSha256: string;
    recommendationSnapshot: unknown;
    selectedIdeaSnapshot: unknown;
    alternativesSnapshot: unknown;
    evidenceSnapshot: unknown;
  };
  executionPolicy: {
    providerDispatchAllowed: boolean;
    allowedOperation: 'CREATE_IMPLEMENTATION_ISSUE' | 'CREATE_VALIDATION_ISSUE' | null;
    resumeRequiresNewOwnerDecision: boolean;
    terminal: boolean;
  };
}

export interface SelectionDecisionHandoffArtifact extends SelectionDecisionHandoffArtifactBase {
  testBrief: FrozenSelectionExperimentBrief | null;
  preMortem: FrozenSelectionPreMortem | null;
}

export interface MaterializedDecisionHandoff {
  action: SelectionDecisionHandoffAction;
  ideaId: string | null;
  ideaRevision: number | null;
  inputFingerprint: string;
  artifact: SelectionDecisionHandoffArtifact;
}

function record(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : null;
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.flatMap(item => {
        const itemText = text(item);
        return itemText ? [itemText] : [];
      })
    : [];
}

function actionFor(
  disposition: SelectionFinalDecisionDisposition,
): SelectionDecisionHandoffAction {
  const actions: Record<SelectionFinalDecisionDisposition, SelectionDecisionHandoffAction> = {
    PROCEED: SelectionDecisionHandoffAction.BUILD,
    TEST_FIRST: SelectionDecisionHandoffAction.VALIDATE_MORE,
    PARK: SelectionDecisionHandoffAction.PARK,
    STOP: SelectionDecisionHandoffAction.STOP,
  };
  return actions[disposition];
}

function targetFrom(source: FinalDecisionHandoffSource): DecisionHandoffTarget | null {
  const targetBearing = source.disposition === SelectionFinalDecisionDisposition.PROCEED
    || source.disposition === SelectionFinalDecisionDisposition.TEST_FIRST;
  const snapshot = record(source.selectedIdeaSnapshot);

  if (!targetBearing) {
    if (source.selectedIdeaId !== null || source.selectedIdeaRevision !== null || snapshot !== null) {
      throw new Error('HANDOFF_NULL_TARGET_REQUIRED');
    }
    return null;
  }

  if (!source.selectedIdeaId || !source.selectedIdeaRevision || !snapshot) {
    throw new Error('HANDOFF_TARGET_MISMATCH');
  }
  if (
    snapshot.idea_id !== source.selectedIdeaId
    || snapshot.idea_revision !== source.selectedIdeaRevision
  ) {
    throw new Error('HANDOFF_TARGET_MISMATCH');
  }

  const reportEvidence = record(snapshot.reportEvidence);
  const details = record(reportEvidence?.details);
  const targetPersonas = stringList(details?.target_personas ?? snapshot.target_personas);

  return {
    ideaId: source.selectedIdeaId,
    ideaRevision: source.selectedIdeaRevision,
    title: text(snapshot.solution_name) ?? text(snapshot.name) ?? text(snapshot.headline),
    problem: text(snapshot.source_pain) ?? text(details?.source_pain),
    audience: text(snapshot.source_segment)
      ?? text(details?.source_segment)
      ?? (targetPersonas.length ? targetPersonas.join(', ') : null),
    valueProposition: text(snapshot.value_proposition) ?? text(details?.value_proposition),
    proposedScope: stringList(snapshot.core_features ?? details?.core_features),
    technicalApproach: text(snapshot.technical_approach) ?? text(details?.technical_approach),
    estimatedBuildTime: text(snapshot.build_time)
      ?? text(snapshot.estimated_development_time)
      ?? text(details?.build_time)
      ?? text(details?.estimated_development_time),
  };
}

function testBriefFrom(
  source: FinalDecisionHandoffSource,
  target: DecisionHandoffTarget | null,
): FrozenSelectionExperimentBrief | null {
  if (source.disposition !== SelectionFinalDecisionDisposition.TEST_FIRST) {
    if (source.testExperimentId !== null || source.testExperimentSnapshot !== null) {
      throw new Error('HANDOFF_NULL_TEST_BRIEF_REQUIRED');
    }
    return null;
  }
  if (!source.testExperimentId || !target) throw new Error('HANDOFF_TEST_BRIEF_REQUIRED');
  const parsed = FrozenSelectionExperimentBriefSchema.safeParse(source.testExperimentSnapshot);
  if (!parsed.success) throw new Error('HANDOFF_TEST_BRIEF_REQUIRED');
  const brief = parsed.data;
  if (
    brief.experimentId !== source.testExperimentId
    || brief.jobId !== source.jobId
    || brief.idea.ideaId !== target.ideaId
    || brief.idea.ideaRevision !== target.ideaRevision
  ) {
    throw new Error('HANDOFF_TEST_BRIEF_MISMATCH');
  }
  return brief;
}

function preMortemFrom(
  source: FinalDecisionHandoffSource,
  target: DecisionHandoffTarget | null,
): FrozenSelectionPreMortem | null {
  const targetBearing = source.disposition === SelectionFinalDecisionDisposition.PROCEED
    || source.disposition === SelectionFinalDecisionDisposition.TEST_FIRST;
  if (!targetBearing) {
    if (source.preMortemSnapshot !== null) throw new Error('HANDOFF_NULL_PRE_MORTEM_REQUIRED');
    return null;
  }
  if (!target) throw new Error('HANDOFF_PRE_MORTEM_REQUIRED');
  const parsed = FrozenSelectionPreMortemSchema.safeParse(source.preMortemSnapshot);
  if (!parsed.success) throw new Error('HANDOFF_PRE_MORTEM_REQUIRED');
  if (
    parsed.data.target.ideaId !== target.ideaId
    || parsed.data.target.ideaRevision !== target.ideaRevision
  ) {
    throw new Error('HANDOFF_PRE_MORTEM_MISMATCH');
  }
  return parsed.data;
}

function fingerprintInput(source: FinalDecisionHandoffSource): JsonRecord {
  return {
    version: 1,
    id: source.id,
    jobId: source.jobId,
    disposition: source.disposition,
    selectedIdeaId: source.selectedIdeaId,
    selectedIdeaRevision: source.selectedIdeaRevision,
    testExperimentId: source.testExperimentId,
    testExperimentSnapshot: source.testExperimentSnapshot,
    preMortemSnapshot: source.preMortemSnapshot,
    recommendationRelation: source.recommendationRelation,
    rationale: source.rationale,
    acceptedRisks: source.acceptedRisks,
    changeCriterion: source.changeCriterion,
    overrideReason: source.overrideReason,
    requestFingerprint: source.requestFingerprint,
    sourceFingerprint: source.sourceFingerprint,
    recommendationSnapshot: source.recommendationSnapshot,
    selectedIdeaSnapshot: source.selectedIdeaSnapshot,
    alternativesSnapshot: source.alternativesSnapshot,
    evidenceSnapshot: source.evidenceSnapshot,
    reportSha256: source.reportSha256,
    decidedByUserId: source.decidedByUserId,
    createdAt: source.createdAt.toISOString(),
  };
}

export function materializeDecisionHandoff(
  source: FinalDecisionHandoffSource,
): MaterializedDecisionHandoff {
  const action = actionFor(source.disposition);
  const target = targetFrom(source);
  const testBrief = testBriefFrom(source, target);
  const preMortem = preMortemFrom(source, target);
  const canDispatch = action === SelectionDecisionHandoffAction.BUILD
    || action === SelectionDecisionHandoffAction.VALIDATE_MORE;
  const baseArtifact: SelectionDecisionHandoffArtifactBase = {
    jobId: source.jobId,
    finalDecisionId: source.id,
    action,
    target,
    decision: {
      disposition: source.disposition,
      recommendationRelation: source.recommendationRelation,
      rationale: source.rationale,
      acceptedRisks: source.acceptedRisks,
      changeCriterion: source.changeCriterion,
      overrideReason: source.overrideReason,
      decidedAt: source.createdAt.toISOString(),
    },
    evidence: {
      sourceFingerprint: source.sourceFingerprint,
      reportSha256: source.reportSha256,
      recommendationSnapshot: source.recommendationSnapshot,
      selectedIdeaSnapshot: source.selectedIdeaSnapshot,
      alternativesSnapshot: source.alternativesSnapshot,
      evidenceSnapshot: source.evidenceSnapshot,
    },
    executionPolicy: {
      providerDispatchAllowed: canDispatch,
      allowedOperation: action === SelectionDecisionHandoffAction.BUILD
        ? 'CREATE_IMPLEMENTATION_ISSUE'
        : action === SelectionDecisionHandoffAction.VALIDATE_MORE
          ? 'CREATE_VALIDATION_ISSUE'
          : null,
      resumeRequiresNewOwnerDecision: !canDispatch,
      terminal: action === SelectionDecisionHandoffAction.STOP,
    },
  };
  const artifact: SelectionDecisionHandoffArtifact = {
    ...baseArtifact,
    testBrief,
    preMortem,
  };

  return {
    action,
    ideaId: target?.ideaId ?? null,
    ideaRevision: target?.ideaRevision ?? null,
    inputFingerprint: canonicalJsonSha256(fingerprintInput(source)),
    artifact,
  };
}

function markdownTitle(action: SelectionDecisionHandoffAction): string {
  return {
    BUILD: 'Implementation brief',
    VALIDATE_MORE: 'Test handoff',
    PARK: 'Parking note',
    STOP: 'Stop record',
  }[action];
}

function markdownField(label: string, value: string | null): string[] {
  return value ? [`**${label}:** ${value}`, ''] : [];
}

function testBriefMarkdown(brief: FrozenSelectionExperimentBrief): string[] {
  return [
    '## Locked test brief',
    '',
    `**Assumption:** ${brief.assumption.statement}`,
    '',
    `**Why it changes the decision:** ${brief.assumption.whyCritical}`,
    '',
    `**Method and signal:** ${experimentMethodLabel(brief.testDesign.method)} · ${evidenceSignalLabel(brief.testDesign.evidenceSignal)}`,
    '',
    `**Audience and channel:** ${brief.testDesign.audience} · ${brief.testDesign.channel}`,
    '',
    `**Stimulus:** ${brief.testDesign.stimulus}`,
    '',
    `**Primary metric:** ${brief.testDesign.primaryMetric}`,
    '',
    `**Sample target:** ${brief.testDesign.sampleTarget ?? 'Not specified'}`,
    '',
    `**Stopping rule:** ${brief.testDesign.measurementWindow}`,
    '',
    `**Pass rule:** ${brief.testDesign.passThreshold}`,
    '',
    `**Fail rule:** ${brief.testDesign.failThreshold}`,
    '',
    `**If pass:** ${brief.decisionRules.pass}`,
    '',
    `**If fail:** ${brief.decisionRules.fail}`,
    '',
    `**If ambiguous:** ${brief.decisionRules.ambiguous}`,
    '',
    `**If invalid:** ${brief.decisionRules.invalid}`,
    '',
    `**Run state at decision:** ${hostedRunStateLabel(brief.runStatusAtDecision) || 'Ready to run'}`,
    '',
    `**Test brief fingerprint:** \`${brief.briefFingerprint}\``,
    '',
  ];
}

function preMortemMarkdown(preMortem: FrozenSelectionPreMortem): string[] {
  const lines = [
    '## Pre-mortem',
    '',
    'Assume this path failed. These are the warning signals and responses recorded before commitment.',
    '',
  ];
  preMortem.entries.forEach((entry, index) => {
    lines.push(
      `### ${String(index + 1).padStart(2, '0')} · ${entry.failureMode}`,
      '',
      `**Earliest warning:** ${entry.earlyWarningSignal}`,
      '',
      `**If it appears:** ${entry.mitigation}`,
      '',
    );
    if (entry.origin) {
      lines.push(
        `**Evidence anchor:** ${entry.origin.lens} · ${challengeQuestionLabel(entry.origin.questionId)} · ${challengeConsensusLabel(entry.origin.consensus)}`,
        '',
      );
    }
  });
  return lines;
}

export function renderDecisionHandoffMarkdown(
  artifact: SelectionDecisionHandoffArtifact,
  inputFingerprint: string,
): string {
  const lines = [
    `# ${markdownTitle(artifact.action)}`,
    '',
    ...markdownField('Action', handoffActionLabel(artifact.action)),
  ];
  if (artifact.target) {
    lines.push(
      ...markdownField('Idea', artifact.target.title),
      `**Exact revision:** ${artifact.target.ideaId} · r${artifact.target.ideaRevision}`,
      '',
      ...markdownField('Problem', artifact.target.problem),
      ...markdownField('Audience', artifact.target.audience),
      ...markdownField('Value proposition', artifact.target.valueProposition),
      ...markdownField('Technical approach', artifact.target.technicalApproach),
      ...markdownField('Build estimate', artifact.target.estimatedBuildTime),
    );
    if (artifact.target.proposedScope.length) {
      lines.push('## Recorded scope', '', ...artifact.target.proposedScope.map(item => `- ${item}`), '');
    }
  }
  if (artifact.testBrief) {
    lines.push(...testBriefMarkdown(artifact.testBrief));
  }
  if (artifact.preMortem) {
    lines.push(...preMortemMarkdown(artifact.preMortem));
  }
  lines.push(
    '## Owner decision',
    '',
    `**Why now:** ${artifact.decision.rationale}`,
    '',
  );
  if (artifact.decision.acceptedRisks) {
    lines.push(`**Accepted or open risks:** ${artifact.decision.acceptedRisks}`, '');
  }
  if (artifact.decision.overrideReason) {
    lines.push(`**Recommendation override:** ${artifact.decision.overrideReason}`, '');
  }
  lines.push(
    `**Change or stop if:** ${artifact.decision.changeCriterion}`,
    '',
    `**Recorded:** ${artifact.decision.decidedAt}`,
    '',
    '---',
    '',
    'This artifact records the owner’s chosen next move. It does not label the idea validated.',
    '',
    `Decision fingerprint: \`${inputFingerprint}\``,
    '',
  );
  return lines.join('\n');
}

export function serializeDecisionHandoffJson(
  artifact: SelectionDecisionHandoffArtifact,
  inputFingerprint: string,
): string {
  return `${JSON.stringify(canonicalizeJson({ inputFingerprint, artifact }), null, 2)}\n`;
}

export function artifactAsPrismaJson(
  artifact: SelectionDecisionHandoffArtifact,
): Prisma.InputJsonValue {
  return artifact as unknown as Prisma.InputJsonValue;
}
