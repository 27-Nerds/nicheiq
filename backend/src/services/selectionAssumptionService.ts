import {
  Prisma,
  SelectionChallengeLens,
  SelectionExperimentEvidenceSource,
  SelectionExperimentOutcome,
} from '@prisma/client';
import { SelectionChallengeArtifactSchema } from '../types/selectionChallenge.js';
import type {
  SelectionAssumptionDirection,
  SelectionAssumptionEvidenceClass,
} from '../types/selectionAssumption.js';

export const APP_ASSUMPTION_LENS = {
  [SelectionChallengeLens.DEMAND]: 'demand',
  [SelectionChallengeLens.COMPETITION]: 'competition',
  [SelectionChallengeLens.DISTRIBUTION]: 'distribution',
  [SelectionChallengeLens.DEPENDENCIES]: 'dependencies',
} as const;

export const PRISMA_ASSUMPTION_LENS = {
  demand: SelectionChallengeLens.DEMAND,
  competition: SelectionChallengeLens.COMPETITION,
  distribution: SelectionChallengeLens.DISTRIBUTION,
  dependencies: SelectionChallengeLens.DEPENDENCIES,
} as const;

export const selectionAssumptionInclude = Prisma.validator<Prisma.SelectionAssumptionInclude>()({
  originChallenge: { select: { artifact: true } },
  experiments: {
    select: {
      id: true,
      status: true,
      conclusion: {
        select: {
          outcome: true,
          evidenceSource: true,
          snapshot: true,
        },
      },
    },
    orderBy: { createdAt: 'asc' },
  },
});

export type SelectionAssumptionWithEvidence = Prisma.SelectionAssumptionGetPayload<{
  include: typeof selectionAssumptionInclude;
}>;

type ConclusionSignal = {
  outcome: SelectionExperimentOutcome;
  evidenceSource: SelectionExperimentEvidenceSource;
  snapshot: Prisma.JsonValue;
};

export type SelectionAssumptionEvidenceRead = {
  direction: SelectionAssumptionDirection;
  evidenceClass: SelectionAssumptionEvidenceClass;
};

const EVIDENCE_RANK: Record<SelectionAssumptionEvidenceClass, number> = {
  NONE: 0,
  INFERENCE: 1,
  PROXY: 2,
  OBSERVED: 3,
};

function strongestEvidenceClass(
  current: SelectionAssumptionEvidenceClass,
  next: SelectionAssumptionEvidenceClass,
): SelectionAssumptionEvidenceClass {
  return EVIDENCE_RANK[next] > EVIDENCE_RANK[current] ? next : current;
}

function outcomeDirection(outcome: SelectionExperimentOutcome): SelectionAssumptionDirection {
  switch (outcome) {
    case SelectionExperimentOutcome.PASS: return 'SUPPORTING';
    case SelectionExperimentOutcome.FAIL: return 'CONTRADICTING';
    case SelectionExperimentOutcome.AMBIGUOUS: return 'MIXED';
    case SelectionExperimentOutcome.INVALID: return 'UNKNOWN';
  }
}

function conclusionEvidenceClass(conclusion: ConclusionSignal): SelectionAssumptionEvidenceClass {
  const snapshot = conclusion.snapshot;
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) return 'INFERENCE';
  const evidence = 'evidence' in snapshot && snapshot.evidence && typeof snapshot.evidence === 'object'
    && !Array.isArray(snapshot.evidence) ? snapshot.evidence : null;
  const quality = evidence && 'quality' in evidence && evidence.quality && typeof evidence.quality === 'object'
    && !Array.isArray(evidence.quality) ? evidence.quality : null;
  const qualityStatus = quality && 'status' in quality ? quality.status : null;

  if (conclusion.evidenceSource === SelectionExperimentEvidenceSource.HOSTED_RUN) {
    return qualityStatus === 'INVALID' ? 'NONE' : 'OBSERVED';
  }

  const source = evidence && 'source' in evidence && evidence.source && typeof evidence.source === 'object'
    && !Array.isArray(evidence.source) ? evidence.source : null;
  const references = source && 'references' in source && Array.isArray(source.references)
    ? source.references : [];
  const sample = evidence && 'sample' in evidence && evidence.sample && typeof evidence.sample === 'object'
    && !Array.isArray(evidence.sample) ? evidence.sample : null;
  const observed = sample && 'observed' in sample ? sample.observed : null;
  return references.length > 0 || (typeof observed === 'number' && observed > 0) ? 'PROXY' : 'INFERENCE';
}

export function deriveSelectionAssumptionEvidence(
  assumption: SelectionAssumptionWithEvidence,
  additionalConclusion?: ConclusionSignal,
): SelectionAssumptionEvidenceRead {
  const directions: SelectionAssumptionDirection[] = [];
  let evidenceClass: SelectionAssumptionEvidenceClass = 'NONE';

  const artifactResult = SelectionChallengeArtifactSchema.safeParse(assumption.originChallenge?.artifact);
  if (artifactResult.success && assumption.originQuestionId) {
    const question = artifactResult.data.questions.find(item => item.questionId === assumption.originQuestionId);
    if (question) {
      directions.push(
        question.consensus === 'supported' ? 'SUPPORTING'
          : question.consensus === 'contradicted' ? 'CONTRADICTING'
            : question.consensus === 'mixed' || question.consensus === 'disputed' ? 'MIXED'
              : 'UNKNOWN',
      );
      for (const candidate of [question.skeptic.evidenceClass, question.auditor.evidenceClass]) {
        evidenceClass = strongestEvidenceClass(evidenceClass, candidate.toUpperCase() as SelectionAssumptionEvidenceClass);
      }
    }
  }

  const conclusions = assumption.experiments
    .map(experiment => experiment.conclusion)
    .filter((value): value is NonNullable<typeof value> => Boolean(value));
  if (additionalConclusion) conclusions.push(additionalConclusion);
  for (const conclusion of conclusions) {
    directions.push(outcomeDirection(conclusion.outcome));
    evidenceClass = strongestEvidenceClass(evidenceClass, conclusionEvidenceClass(conclusion));
  }

  const hasSupporting = directions.includes('SUPPORTING');
  const hasContradicting = directions.includes('CONTRADICTING');
  const hasMixed = directions.includes('MIXED');
  const direction: SelectionAssumptionDirection = hasMixed || (hasSupporting && hasContradicting)
    ? 'MIXED'
    : hasSupporting ? 'SUPPORTING'
      : hasContradicting ? 'CONTRADICTING'
        : 'UNKNOWN';
  return { direction, evidenceClass };
}

export function serializeSelectionAssumption(
  assumption: SelectionAssumptionWithEvidence,
  stale: boolean,
) {
  const {
    originChallenge: _originChallenge,
    statementFingerprint: _statementFingerprint,
    experiments,
    lens,
    ...stored
  } = assumption;
  return {
    ...stored,
    lens: APP_ASSUMPTION_LENS[lens],
    stale,
    ...deriveSelectionAssumptionEvidence(assumption),
    experiments: experiments.map(experiment => ({
      id: experiment.id,
      status: experiment.status,
      outcome: experiment.conclusion?.outcome ?? null,
    })),
  };
}
