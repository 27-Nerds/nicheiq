import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  parseFounderFit: vi.fn(),
  prepareChallenge: vi.fn(),
}));

vi.mock('../founderFitService.js', () => ({
  parseCurrentFounderFitArtifact: mocks.parseFounderFit,
}));
vi.mock('../selectionChallengeService.js', () => ({
  prepareSelectionChallengeInput: mocks.prepareChallenge,
}));

import { buildSelectionDecisionState, type SelectionDecisionStateInput } from '../selectionDecisionStateService.js';
import { SELECTION_CHALLENGE_QUESTIONS, type SelectionChallengeLens } from '../../types/selectionChallenge.js';

const jobId = '11111111-1111-4111-8111-111111111111';
const fingerprint = 'c'.repeat(64);
const idea = {
  idea_id: 'idea-current',
  idea_revision: 2,
  solution_name: 'Current signal desk',
};
const profile = {
  preset: 'solo_bootstrap',
  weeklyTime: 'under_10',
  budget: 'under_1k',
  team: 'solo',
  revenueHorizon: '90_days',
  distributionAdvantages: ['seo'],
  strengths: 'Research',
  hardConstraints: '',
};

function input(overrides: Partial<SelectionDecisionStateInput> = {}): SelectionDecisionStateInput {
  return {
    jobId,
    status: 'AWAITING_SELECTION',
    solutionIdeas: [idea],
    selectionDraft: { schemaVersion: 1, items: [] },
    selectionDraftVersion: 0,
    selectionDecisionProfile: null,
    selectionFounderFit: null,
    challenges: [],
    ownerEvidence: [],
    assumptions: [],
    experiments: [],
    previewReport: null,
    discoveryData: null,
    // Granted by default here; the ungated behaviour has its own describe block.
    decisionTools: true,
    ...overrides,
  };
}

function currentDraft() {
  return {
    schemaVersion: 1,
    items: [{ ideaId: idea.idea_id, ideaRevision: idea.idea_revision }],
  };
}

function fitArtifact() {
  return {
    inputFingerprint: 'f'.repeat(64),
    results: [{
      ideaId: idea.idea_id,
      ideaRevision: idea.idea_revision,
      verdict: 'fits',
    }],
  };
}

function challenge(lens: SelectionChallengeLens, consensus: 'supported' | 'insufficient' = 'supported') {
  const assessment = (questionId: string) => ({
    questionId,
    position: consensus === 'supported' ? 'supports' as const : 'insufficient' as const,
    summary: 'The captured packet was assessed.',
    subjectKeys: ['I1'],
    evidenceKeys: [],
    evidenceClass: 'inference' as const,
  });
  const artifact = {
    version: 1 as const,
    inputFingerprint: fingerprint,
    ideaId: idea.idea_id,
    ideaRevision: idea.idea_revision,
    ideaTitle: idea.solution_name,
    lens,
    overall: consensus === 'supported' ? 'withstands' as const : 'insufficient_evidence' as const,
    ideaSnapshot: { solution_name: idea.solution_name },
    subjectSnapshot: [{ key: 'I1', field: 'solution_name', value: idea.solution_name }],
    evidenceSnapshot: [],
    questions: SELECTION_CHALLENGE_QUESTIONS[lens].map(questionId => ({
      questionId,
      consensus,
      skeptic: assessment(questionId),
      auditor: assessment(questionId),
    })),
    skepticModel: 'test-skeptic',
    auditorModel: 'test-auditor',
    promptVersion: 1 as const,
    createdAt: '2026-07-16T00:00:00.000Z',
  };
  return {
    id: `challenge-${lens}`,
    ideaId: idea.idea_id,
    ideaRevision: idea.idea_revision,
    lens: lens.toUpperCase() as Uppercase<SelectionChallengeLens>,
    inputFingerprint: fingerprint,
    artifact,
  };
}

describe('selection decision state projection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.parseFounderFit.mockReturnValue(null);
    mocks.prepareChallenge.mockReturnValue({ inputFingerprint: fingerprint });
  });

  it('applies the deterministic priority order before optional evidence work', () => {
    const noShortlist = buildSelectionDecisionState(input());
    expect(noShortlist.nextAction.kind).toBe('select_candidate');

    const noProfile = buildSelectionDecisionState(input({ selectionDraft: currentDraft() }));
    expect(noProfile.nextAction.kind).toBe('add_decision_context');

    const noFit = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
    }));
    expect(noFit.nextAction.kind).toBe('analyze_founder_fit');

    mocks.parseFounderFit.mockReturnValue(fitArtifact());
    const noChallenge = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
    }));
    expect(noChallenge.nextAction).toMatchObject({
      kind: 'stress_test_evidence',
      lens: 'demand',
      ideas: [{ ideaId: idea.idea_id, ideaRevision: 2 }],
    });

    const gapChallenge = challenge('demand', 'insufficient');
    const untrackedGap = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: [gapChallenge],
    }));
    expect(untrackedGap.nextAction).toMatchObject({
      kind: 'capture_assumption',
      lens: 'demand',
      records: [{ kind: 'challenge', id: gapChallenge.id }],
    });

    const assumption = {
      id: 'assumption-1',
      ideaId: idea.idea_id,
      ideaRevision: 2,
      lens: 'DEMAND' as const,
      statement: 'Qualified buyers will pay for the signal.',
      impact: 'HIGH',
      ownerState: 'OPEN',
      version: 3,
      originChallengeId: gapChallenge.id,
      originQuestionId: SELECTION_CHALLENGE_QUESTIONS.demand[0],
      experiments: [],
    };
    const untestedAssumption = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: [gapChallenge],
      assumptions: [assumption],
    }));
    expect(untestedAssumption.nextAction).toMatchObject({
      kind: 'capture_assumption',
      records: [{ kind: 'challenge', id: gapChallenge.id }],
    });

    const allGapAssumptions = gapChallenge.artifact.questions.map((question, index) => ({
      ...assumption,
      id: `assumption-${index}`,
      originQuestionId: question.questionId,
    }));
    const readyForTest = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: [gapChallenge],
      assumptions: allGapAssumptions,
    }));
    expect(readyForTest.nextAction).toMatchObject({
      kind: 'draft_test',
      records: [{ kind: 'assumption', id: 'assumption-0', version: 3 }],
    });
  });

  it('keeps only exact current revisions and reports stale exact-reference artifacts', () => {
    mocks.parseFounderFit.mockReturnValue(fitArtifact());
    const state = buildSelectionDecisionState(input({
      selectionDraft: {
        schemaVersion: 1,
        items: [{ ideaId: idea.idea_id, ideaRevision: 1 }],
      },
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: [{
        ...challenge('demand'),
        ideaRevision: 1,
        artifact: { ...challenge('demand').artifact, ideaRevision: 1 },
      }],
      ownerEvidence: [{
        id: 'evidence-old',
        ideaId: idea.idea_id,
        ideaRevision: 1,
        lens: 'DEMAND',
        kind: 'NOTE',
        position: 'CONTEXT',
        title: 'Old note',
        content: 'Captured for the prior revision.',
        sourceUrl: null,
        observedAt: null,
        createdAt: new Date('2026-07-16T00:00:00.000Z'),
        retractedAt: null,
      }],
      assumptions: [{
        id: 'assumption-old',
        ideaId: idea.idea_id,
        ideaRevision: 1,
        lens: 'DEMAND',
        statement: 'An assumption on an old revision.',
        impact: 'HIGH',
        ownerState: 'OPEN',
        version: 1,
        originChallengeId: null,
        originQuestionId: null,
        experiments: [{ id: 'experiment-old' }],
      }],
      experiments: [{
        id: 'experiment-old',
        ideaId: idea.idea_id,
        ideaRevision: 1,
        assumptionId: 'assumption-old',
        status: 'LOCKED',
        originChallengeId: null,
        originChallenge: null,
        run: { status: 'CLOSED' },
        conclusion: {
          id: 'conclusion-old',
          ideaId: idea.idea_id,
          ideaRevision: 1,
          outcome: 'FAIL',
          createdAt: new Date('2026-07-16T00:00:00.000Z'),
          snapshot: {},
        },
      }],
    }));

    expect(state.shortlist.items).toEqual([]);
    expect(state.challenges).toEqual([]);
    expect(state.ownerEvidence).toEqual([]);
    expect(state.assumptions).toEqual([]);
    expect(state.experiments).toEqual([]);
    expect(state.conclusions).toEqual([]);
    expect(state.staleCounts).toMatchObject({
      shortlist: 1,
      founderFit: 1,
      challenges: 1,
      ownerEvidence: 1,
      assumptions: 1,
      experiments: 1,
      conclusions: 1,
    });
    expect(state.nextAction.kind).toBe('select_candidate');
  });

  it('excludes a stale challenge from completion while counting it, preferring the next new step', () => {
    mocks.parseFounderFit.mockReturnValue(fitArtifact());
    const staleChallenge = challenge('demand');
    staleChallenge.inputFingerprint = '0'.repeat(64);
    const state = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: [staleChallenge],
    }));

    expect(state.challenges).toEqual([]);
    expect(state.staleCounts.challenges).toBe(1);
    // The stale demand slot must not be re-presented as a first-time step
    // while a never-run lens remains; the next new step wins.
    expect(state.nextAction).toMatchObject({ kind: 'stress_test_evidence', lens: 'competition' });
    expect(state.nextAction.variant).toBeUndefined();
  });

  function staleChallengeSet() {
    // All four lenses were run, then the underlying evidence changed:
    // stored fingerprints no longer match the currently prepared one.
    return (['demand', 'competition', 'distribution', 'dependencies'] as const).map(lens => {
      const row = challenge(lens);
      const oldFingerprint = '0'.repeat(64);
      return {
        ...row,
        inputFingerprint: oldFingerprint,
        artifact: { ...row.artifact, inputFingerprint: oldFingerprint },
      };
    });
  }

  it('suggests a rerun variant, not a first-time step, when a conclusion invalidates completed challenges', () => {
    mocks.parseFounderFit.mockReturnValue(fitArtifact());
    const state = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: staleChallengeSet(),
      experiments: [{
        id: 'experiment-1',
        ideaId: idea.idea_id,
        ideaRevision: idea.idea_revision,
        assumptionId: null,
        status: 'LOCKED',
        originChallengeId: null,
        originChallenge: null,
        run: { status: 'CLOSED' },
        conclusion: {
          id: 'conclusion-1',
          ideaId: idea.idea_id,
          ideaRevision: idea.idea_revision,
          outcome: 'PASS',
          createdAt: new Date('2026-07-16T00:00:00.000Z'),
          snapshot: {},
        },
      }],
    }));

    expect(state.staleCounts.challenges).toBe(4);
    expect(state.nextAction).toMatchObject({
      kind: 'stress_test_evidence',
      lens: 'demand',
      variant: 'rerun',
      reason: 'Your evidence changed. This check is worth re-running.',
    });
  });

  it('surfaces invalidated founder fit as a refresh, not a restart, after a shortlist edit', () => {
    // Fit exists but was computed for a different revision set (shortlist edit).
    mocks.parseFounderFit.mockReturnValue({
      inputFingerprint: 'f'.repeat(64),
      results: [{ ideaId: idea.idea_id, ideaRevision: 1, verdict: 'fits' }],
    });
    const allCurrentChallenges = (['demand', 'competition', 'distribution', 'dependencies'] as const)
      .map(lens => challenge(lens));
    const state = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: allCurrentChallenges,
    }));

    expect(state.founderFit).toBeNull();
    expect(state.nextAction).toMatchObject({
      kind: 'analyze_founder_fit',
      variant: 'refresh',
      reason: 'Your shortlist changed. Refresh founder fit to match.',
    });
  });

  it('prefers a new first-time step over the founder-fit refresh, and the refresh over a challenge rerun', () => {
    mocks.parseFounderFit.mockReturnValue({
      inputFingerprint: 'f'.repeat(64),
      results: [{ ideaId: idea.idea_id, ideaRevision: 1, verdict: 'fits' }],
    });

    // A never-run lens outranks the invalidated founder fit.
    const withNewStep = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
    }));
    expect(withNewStep.nextAction).toMatchObject({ kind: 'stress_test_evidence', lens: 'demand' });
    expect(withNewStep.nextAction.variant).toBeUndefined();

    // With only re-do work left, spine order applies: refresh before rerun.
    const onlyRedos = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: staleChallengeSet(),
    }));
    expect(onlyRedos.nextAction).toMatchObject({ kind: 'analyze_founder_fit', variant: 'refresh' });
  });

  it('keeps the completed happy path on start_deep_research with no variant', () => {
    mocks.parseFounderFit.mockReturnValue(fitArtifact());
    const state = buildSelectionDecisionState(input({
      selectionDraft: currentDraft(),
      selectionDecisionProfile: profile,
      selectionFounderFit: fitArtifact(),
      challenges: (['demand', 'competition', 'distribution', 'dependencies'] as const)
        .map(lens => challenge(lens)),
    }));

    expect(state.nextAction).toMatchObject({ kind: 'start_deep_research' });
    expect(state.nextAction.variant).toBeUndefined();
  });

  it('never gates Deep Research on optional profile, fit, or evidence work', () => {
    const state = buildSelectionDecisionState(input({ selectionDraft: currentDraft() }));

    expect(state.deepResearch).toEqual({
      eligible: true,
      optionalWorkRequired: false,
      blockers: [],
    });
    expect(state.nextAction).toMatchObject({
      kind: 'add_decision_context',
      required: false,
    });
  });

  describe('without the decision tools grant', () => {
    const gated = (overrides = {}) =>
      buildSelectionDecisionState(input({ decisionTools: false, ...overrides }));

    it('still asks for a shortlist when there is none', () => {
      expect(gated().nextAction.kind).toBe('select_candidate');
    });

    it('goes straight from shortlist to Deep Research, skipping the optional ladder', () => {
      const state = gated({ selectionDraft: currentDraft() });
      expect(state.nextAction.kind).toBe('start_deep_research');
      expect(state.nextAction.required).toBe(false);
      expect(state.deepResearch.eligible).toBe(true);
    });

    it('never suggests build limits or an evidence check, whatever is saved', () => {
      mocks.parseFounderFit.mockReturnValue(fitArtifact());
      const state = gated({
        selectionDraft: currentDraft(),
        selectionDecisionProfile: profile,
        selectionFounderFit: fitArtifact(),
      });
      expect(state.nextAction.kind).toBe('start_deep_research');
    });

    it('empties historical decision-tool rows so a revoked grant leaks nothing', () => {
      mocks.parseFounderFit.mockReturnValue(fitArtifact());
      const state = gated({
        selectionDraft: currentDraft(),
        selectionDecisionProfile: profile,
        selectionFounderFit: fitArtifact(),
      });
      expect(state.profile).toBeNull();
      expect(state.founderFit).toBeNull();
      expect(state.challenges).toEqual([]);
      expect(state.ownerEvidence).toEqual([]);
      expect(state.assumptions).toEqual([]);
      expect(state.experiments).toEqual([]);
      expect(state.conclusions).toEqual([]);
      expect(state.staleCounts.total).toBe(state.staleCounts.shortlist);
    });

    it('keeps the shortlist intact — it is not a decision tool', () => {
      const state = gated({ selectionDraft: currentDraft() });
      expect(state.shortlist.items).toEqual([
        expect.objectContaining({ ideaId: idea.idea_id, ideaRevision: 2 }),
      ]);
    });
  });
});
