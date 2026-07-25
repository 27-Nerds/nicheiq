import { parseCurrentFounderFitArtifact } from './founderFitService.js';
import { prepareSelectionChallengeInput } from './selectionChallengeService.js';
import { SelectionDecisionProfileSchema } from '../types/job.js';
import {
  SELECTION_CHALLENGE_LENSES,
  SelectionChallengeArtifactSchema,
  type SelectionChallengeLens,
} from '../types/selectionChallenge.js';
import type {
  SelectionDecisionIdeaRef,
  SelectionDecisionNextAction,
  SelectionDecisionState,
} from '../types/selectionDecisionState.js';
import { ensureIdeaIdentities, ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';
import { currentSelectionDraft, parseSelectionDraft } from '../utils/selectionDraft.js';

type PrismaLens = 'DEMAND' | 'COMPETITION' | 'DISTRIBUTION' | 'DEPENDENCIES';

const APP_LENS: Record<PrismaLens, SelectionChallengeLens> = {
  DEMAND: 'demand',
  COMPETITION: 'competition',
  DISTRIBUTION: 'distribution',
  DEPENDENCIES: 'dependencies',
};

interface ChallengeRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: PrismaLens;
  inputFingerprint: string;
  artifact: unknown;
}

interface OwnerEvidenceRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: PrismaLens;
  kind: 'NOTE' | 'CUSTOMER_QUOTE' | 'ANALYTICS_OBSERVATION' | 'LINK';
  position: 'SUPPORTS' | 'CONTRADICTS' | 'CONTEXT';
  title: string;
  content: string;
  sourceUrl: string | null;
  observedAt: Date | null;
  createdAt: Date;
  retractedAt: Date | null;
}

interface AssumptionRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  lens: PrismaLens;
  statement: string;
  impact: string;
  ownerState: string;
  version: number;
  originChallengeId: string | null;
  originQuestionId: string | null;
  experiments: Array<{ id: string }>;
}

interface ExperimentRow {
  id: string;
  ideaId: string;
  ideaRevision: number;
  assumptionId: string | null;
  status: string;
  originChallengeId: string | null;
  originChallenge: {
    id: string;
    ideaId: string;
    ideaRevision: number;
    lens: PrismaLens;
  } | null;
  run: { status: string } | null;
  conclusion: {
    id: string;
    ideaId: string;
    ideaRevision: number;
    outcome: string;
    createdAt: Date;
    snapshot: unknown;
  } | null;
}

export interface SelectionDecisionStateInput {
  jobId: string;
  status: string;
  solutionIdeas: unknown;
  selectionDraft: unknown;
  selectionDraftVersion: number;
  selectionDecisionProfile: unknown;
  selectionFounderFit: unknown;
  challenges: ChallengeRow[];
  ownerEvidence: OwnerEvidenceRow[];
  assumptions: AssumptionRow[];
  experiments: ExperimentRow[];
  previewReport: unknown;
  discoveryData: unknown;
  /**
   * Whether the owner has the optional decision tools grant (User.decisionToolsAccess).
   * When false the optional ladder is skipped entirely and every decision-tool
   * projection is emptied, so the client can never surface a step the API would 403.
   * Required — a fail-closed gate must not have a permissive default.
   */
  decisionTools: boolean;
}

function ideaKey(ideaId: string, ideaRevision: number) {
  return `${ideaId}\0${ideaRevision}`;
}

function ideaRef(idea: IdeaRecord): SelectionDecisionIdeaRef {
  return {
    ideaId: String(idea.idea_id),
    ideaRevision: Number(idea.idea_revision),
    title: ideaName(idea) ?? 'Untitled candidate',
  };
}

function optionalAction(
  action: Omit<SelectionDecisionNextAction, 'required'>,
): SelectionDecisionNextAction {
  return { ...action, required: false };
}

function exactSet(left: Array<{ ideaId: string; ideaRevision: number }>, right: Array<{ ideaId: string; ideaRevision: number }>) {
  if (left.length !== right.length) return false;
  const rightKeys = new Set(right.map(item => ideaKey(item.ideaId, item.ideaRevision)));
  return left.every(item => rightKeys.has(ideaKey(item.ideaId, item.ideaRevision)));
}

export function buildSelectionDecisionState(input: SelectionDecisionStateInput): SelectionDecisionState {
  const ideas = ensureIdeaIdentities(input.jobId, input.solutionIdeas);
  const currentIdeaByKey = new Map(ideas.map(idea => [
    ideaKey(String(idea.idea_id), Number(idea.idea_revision)),
    idea,
  ]));
  const storedDraft = parseSelectionDraft(input.selectionDraft);
  const draft = currentSelectionDraft(input.selectionDraft, input.selectionDraftVersion, ideas);
  const shortlistIdeas = draft.items.flatMap(item => {
    const idea = currentIdeaByKey.get(ideaKey(item.ideaId, item.ideaRevision));
    return idea ? [idea] : [];
  });
  const shortlist = shortlistIdeas.map(ideaRef);

  const parsedProfile = SelectionDecisionProfileSchema.safeParse(input.selectionDecisionProfile);
  const profile = parsedProfile.success ? parsedProfile.data : null;
  const parsedFounderFit = parseCurrentFounderFitArtifact(
    input.selectionFounderFit,
    input.selectionDecisionProfile,
    ideas,
  );
  const founderFitMatchesShortlist = Boolean(
    parsedFounderFit
    && shortlist.length > 0
    && exactSet(parsedFounderFit.results, shortlist),
  );
  const founderFit = parsedFounderFit && founderFitMatchesShortlist
    ? {
        inputFingerprint: parsedFounderFit.inputFingerprint,
        results: parsedFounderFit.results.map(result => ({
          idea: ideaRef(currentIdeaByKey.get(ideaKey(result.ideaId, result.ideaRevision))!),
          verdict: result.verdict,
        })),
      }
    : null;

  const preparedFingerprints = new Map<string, string>();
  const currentChallenges: SelectionDecisionState['challenges'] = [];
  let staleChallenges = 0;
  for (const row of input.challenges) {
    const idea = currentIdeaByKey.get(ideaKey(row.ideaId, row.ideaRevision));
    const lens = APP_LENS[row.lens];
    const parsed = SelectionChallengeArtifactSchema.safeParse(row.artifact);
    if (!idea || !lens || !parsed.success) {
      staleChallenges += 1;
      continue;
    }
    const fingerprintKey = `${ideaKey(row.ideaId, row.ideaRevision)}\0${lens}`;
    let currentFingerprint = preparedFingerprints.get(fingerprintKey);
    if (!currentFingerprint) {
      currentFingerprint = prepareSelectionChallengeInput({
        lens,
        idea,
        previewReport: input.previewReport,
        discoveryData: input.discoveryData,
        ownerEvidence: input.ownerEvidence,
        experimentResults: input.experiments,
      }).inputFingerprint;
      preparedFingerprints.set(fingerprintKey, currentFingerprint);
    }
    const artifact = parsed.data;
    if (
      row.inputFingerprint !== currentFingerprint
      || artifact.inputFingerprint !== row.inputFingerprint
      || artifact.ideaId !== row.ideaId
      || artifact.ideaRevision !== row.ideaRevision
      || artifact.lens !== lens
    ) {
      staleChallenges += 1;
      continue;
    }
    currentChallenges.push({
      id: row.id,
      idea: ideaRef(idea),
      lens,
      overall: artifact.overall,
      gapQuestionIds: artifact.questions
        .filter(question => question.consensus !== 'supported')
        .map(question => question.questionId),
    });
  }

  const currentOwnerEvidence: SelectionDecisionState['ownerEvidence'] = [];
  let staleOwnerEvidence = 0;
  for (const row of input.ownerEvidence) {
    if (row.retractedAt) continue;
    const idea = currentIdeaByKey.get(ideaKey(row.ideaId, row.ideaRevision));
    if (!idea) {
      staleOwnerEvidence += 1;
      continue;
    }
    currentOwnerEvidence.push({
      id: row.id,
      idea: ideaRef(idea),
      lens: APP_LENS[row.lens],
      kind: row.kind,
      position: row.position,
      title: row.title,
    });
  }

  const currentAssumptions: SelectionDecisionState['assumptions'] = [];
  let staleAssumptions = 0;
  for (const row of input.assumptions) {
    const idea = currentIdeaByKey.get(ideaKey(row.ideaId, row.ideaRevision));
    if (!idea) {
      staleAssumptions += 1;
      continue;
    }
    currentAssumptions.push({
      id: row.id,
      idea: ideaRef(idea),
      lens: APP_LENS[row.lens],
      statement: row.statement,
      impact: row.impact,
      ownerState: row.ownerState,
      version: row.version,
      originChallengeId: row.originChallengeId,
      originQuestionId: row.originQuestionId,
      experimentIds: row.experiments.map(experiment => experiment.id),
    });
  }

  const currentExperiments: SelectionDecisionState['experiments'] = [];
  const currentConclusions: SelectionDecisionState['conclusions'] = [];
  let staleExperiments = 0;
  let staleConclusions = 0;
  for (const row of input.experiments) {
    const idea = currentIdeaByKey.get(ideaKey(row.ideaId, row.ideaRevision));
    const conclusionIsCurrent = Boolean(
      row.conclusion
      && currentIdeaByKey.has(ideaKey(row.conclusion.ideaId, row.conclusion.ideaRevision))
      && row.conclusion.ideaId === row.ideaId
      && row.conclusion.ideaRevision === row.ideaRevision,
    );
    if (!idea) {
      staleExperiments += 1;
      if (row.conclusion) staleConclusions += 1;
      continue;
    }
    currentExperiments.push({
      id: row.id,
      idea: ideaRef(idea),
      assumptionId: row.assumptionId,
      status: row.status,
      runStatus: row.run?.status ?? null,
      conclusionId: conclusionIsCurrent ? row.conclusion!.id : null,
    });
    if (row.conclusion && conclusionIsCurrent) {
      currentConclusions.push({
        id: row.conclusion.id,
        experimentId: row.id,
        idea: ideaRef(idea),
        outcome: row.conclusion.outcome,
      });
    } else if (row.conclusion) {
      staleConclusions += 1;
    }
  }

  const currentChallengeBySlot = new Map(currentChallenges.map(challenge => [
    `${ideaKey(challenge.idea.ideaId, challenge.idea.ideaRevision)}\0${challenge.lens}`,
    challenge,
  ]));
  // Every slot that ever had a challenge run recorded for it, current or not.
  // A slot in here but absent from currentChallengeBySlot went stale
  // (fingerprint drift after evidence changed) rather than never being run.
  const challengeEverBySlot = new Set(input.challenges.map(row =>
    `${ideaKey(row.ideaId, row.ideaRevision)}\0${APP_LENS[row.lens]}`,
  ));
  const currentExperimentById = new Map(currentExperiments.map(experiment => [experiment.id, experiment]));

  const decisionTools = input.decisionTools === true;

  let nextAction: SelectionDecisionNextAction;
  if (!decisionTools) {
    // No grant: the spine is shortlist → Deep Research. Every rung of the optional
    // ladder below opens a tool this owner cannot reach, so none of them may be
    // suggested.
    nextAction = shortlist.length === 0
      ? {
        kind: 'select_candidate',
        target: 'shortlist',
        reason: 'Choose at least one current candidate before starting Deep Research.',
        required: true,
        ideas: ideas.slice(0, 1).map(ideaRef),
        lens: null,
        records: [],
      }
      : optionalAction({
        kind: 'start_deep_research',
        target: 'deep_research',
        reason: 'The current shortlist is ready for Deep Research.',
        ideas: shortlist,
        lens: null,
        records: [],
      });
  } else if (shortlist.length === 0) {
    nextAction = {
      kind: 'select_candidate',
      target: 'shortlist',
      reason: 'Choose at least one current candidate before starting Deep Research.',
      required: true,
      ideas: ideas.slice(0, 1).map(ideaRef),
      lens: null,
      records: [],
    };
  } else if (!profile) {
    nextAction = optionalAction({
      kind: 'add_decision_context',
      target: 'profile',
      reason: 'Add your constraints to compare the current shortlist against what is practical for you.',
      ideas: shortlist,
      lens: null,
      records: [],
    });
  } else if (!founderFit && !parsedFounderFit) {
    nextAction = optionalAction({
      kind: 'analyze_founder_fit',
      target: 'founder_fit',
      reason: 'Refresh founder fit for the exact revisions in the current shortlist.',
      ideas: shortlist,
      lens: null,
      records: [],
    });
  } else {
    // Founder fit was computed but the shortlist changed underneath it. This
    // is a refresh suggestion, never a restart — and it must not outrank any
    // further-along step the owner has not done yet.
    const founderFitRefresh = founderFit
      ? null
      : optionalAction({
          kind: 'analyze_founder_fit',
          target: 'founder_fit',
          reason: 'Your shortlist changed. Refresh founder fit to match.',
          variant: 'refresh',
          ideas: shortlist,
          lens: null,
          records: [],
        });
    // A completed challenge whose fingerprint drifted (evidence changed).
    // Suggested as a rerun only when no new first-time step remains.
    let staleChallengeRerun: SelectionDecisionNextAction | null = null;

    nextAction = optionalAction({
      kind: 'start_deep_research',
      target: 'deep_research',
      reason: 'The current shortlist is ready for Deep Research; further decision work remains optional.',
      ideas: shortlist,
      lens: null,
      records: [],
    });

    actionSearch:
    for (const shortlistedIdea of shortlist) {
      const shortlistKey = ideaKey(shortlistedIdea.ideaId, shortlistedIdea.ideaRevision);
      for (const lens of SELECTION_CHALLENGE_LENSES) {
        const slotKey = `${shortlistKey}\0${lens}`;
        const challenge = currentChallengeBySlot.get(slotKey);
        if (!challenge && !challengeEverBySlot.has(slotKey)) {
          nextAction = optionalAction({
            kind: 'stress_test_evidence',
            target: 'challenges',
            reason: `Stress-test the ${lens} evidence for this exact idea revision.`,
            ideas: [shortlistedIdea],
            lens,
            records: [],
          });
          break actionSearch;
        }
        if (!challenge) {
          // The slot had a challenge that went stale. Remember the first one
          // as a rerun suggestion and keep looking for a new step.
          staleChallengeRerun ??= optionalAction({
            kind: 'stress_test_evidence',
            target: 'challenges',
            reason: 'Your evidence changed. This check is worth re-running.',
            variant: 'rerun',
            ideas: [shortlistedIdea],
            lens,
            records: [],
          });
        } else {
          const untrackedGap = challenge.gapQuestionIds.find(questionId => !currentAssumptions.some(assumption =>
            assumption.originChallengeId === challenge.id && assumption.originQuestionId === questionId
          ));
          if (untrackedGap) {
            nextAction = optionalAction({
              kind: 'capture_assumption',
              target: 'assumptions',
              reason: 'Turn the first unresolved evidence-check question into an explicit falsifiable assumption.',
              ideas: [shortlistedIdea],
              lens,
              records: [{ kind: 'challenge', id: challenge.id }],
            });
            break actionSearch;
          }
        }

        const assumption = currentAssumptions.find(candidate =>
          candidate.idea.ideaId === shortlistedIdea.ideaId
          && candidate.idea.ideaRevision === shortlistedIdea.ideaRevision
          && candidate.lens === lens
          && candidate.ownerState === 'OPEN'
          && (candidate.impact === 'DECISIVE' || candidate.impact === 'HIGH')
        );
        if (!assumption) continue;

        const experiments = assumption.experimentIds
          .map(id => currentExperimentById.get(id))
          .filter((experiment): experiment is NonNullable<typeof experiment> => Boolean(experiment));
        const experiment = experiments[0];
        if (!experiment) {
          nextAction = optionalAction({
            kind: 'draft_test',
            target: 'experiments',
            reason: 'Draft a test for the first open high-impact assumption.',
            ideas: [shortlistedIdea],
            lens,
            records: [{ kind: 'assumption', id: assumption.id, version: assumption.version }],
          });
          break actionSearch;
        }
        if (experiment.status === 'DRAFT') {
          nextAction = optionalAction({
            kind: 'review_test_brief',
            target: 'experiments',
            reason: 'Review and lock the draft before collecting evidence.',
            ideas: [shortlistedIdea],
            lens,
            records: [
              { kind: 'assumption', id: assumption.id, version: assumption.version },
              { kind: 'experiment', id: experiment.id },
            ],
          });
          break actionSearch;
        }
        if (!experiment.runStatus) {
          nextAction = optionalAction({
            kind: 'launch_test',
            target: 'experiments',
            reason: 'Launch the locked test or record its evidence manually.',
            ideas: [shortlistedIdea],
            lens,
            records: [{ kind: 'experiment', id: experiment.id }],
          });
          break actionSearch;
        }
        if (experiment.runStatus === 'ACTIVE') {
          nextAction = optionalAction({
            kind: 'monitor_test',
            target: 'experiments',
            reason: 'Review the active test before deciding whether its evidence window is complete.',
            ideas: [shortlistedIdea],
            lens,
            records: [{ kind: 'experiment', id: experiment.id }],
          });
          break actionSearch;
        }
        if (!experiment.conclusionId) {
          nextAction = optionalAction({
            kind: 'record_conclusion',
            target: 'experiments',
            reason: 'Record the outcome of the closed test against its precommitted thresholds.',
            ideas: [shortlistedIdea],
            lens,
            records: [{ kind: 'experiment', id: experiment.id }],
          });
          break actionSearch;
        }
      }
    }

    // Invalidation alone never regresses the spine below the furthest step:
    // re-do suggestions surface only once no new first-time step remains,
    // in spine order (founder-fit refresh before challenge rerun).
    if (nextAction.kind === 'start_deep_research') {
      nextAction = founderFitRefresh ?? staleChallengeRerun ?? nextAction;
    }
  }

  const staleCounts = {
    shortlist: storedDraft.length - draft.items.length,
    profile: input.selectionDecisionProfile != null && !profile ? 1 : 0,
    founderFit: input.selectionFounderFit != null && !founderFit ? 1 : 0,
    challenges: staleChallenges,
    ownerEvidence: staleOwnerEvidence,
    assumptions: staleAssumptions,
    experiments: staleExperiments,
    conclusions: staleConclusions,
    total: 0,
  };
  staleCounts.total = Object.entries(staleCounts)
    .filter(([key]) => key !== 'total')
    .reduce((sum, [, count]) => sum + count, 0);

  const blockers: SelectionDecisionState['deepResearch']['blockers'] = [];
  if (input.status !== 'AWAITING_SELECTION') blockers.push('JOB_NOT_AWAITING_SELECTION');
  if (shortlist.length === 0) blockers.push('NO_CURRENT_SHORTLIST');

  return {
    schemaVersion: 1,
    jobId: input.jobId,
    status: input.status,
    shortlist: { version: draft.version, items: shortlist },
    // Without the grant these stay empty even when historical rows exist (the grant can
    // be revoked after the owner used the tools) — the client renders progress and
    // "saved work" badges straight off these arrays.
    profile: decisionTools ? profile : null,
    founderFit: decisionTools ? founderFit : null,
    challenges: decisionTools ? currentChallenges : [],
    ownerEvidence: decisionTools ? currentOwnerEvidence : [],
    assumptions: decisionTools ? currentAssumptions : [],
    experiments: decisionTools ? currentExperiments : [],
    conclusions: decisionTools ? currentConclusions : [],
    staleCounts: decisionTools
      ? staleCounts
      : { ...staleCounts, profile: 0, founderFit: 0, challenges: 0, ownerEvidence: 0, assumptions: 0, experiments: 0, conclusions: 0, total: staleCounts.shortlist },
    deepResearch: {
      eligible: blockers.length === 0,
      optionalWorkRequired: false,
      blockers,
    },
    nextAction,
  };
}
