import { describe, it, expect } from 'vitest';
import { formatJobResponse } from '../jobFormatter.js';

// Demotion/backfill contract: the Python worker filters solutionIdeas to VISIBLE
// ideas only (candidate_status not in demoted/absorbed) before POSTing to the
// backend. The backend stores/serves whatever it receives — it does NOT re-filter.
// These tests lock that jobFormatter counts/serves stored solutionIdeas verbatim,
// so "N ideas" downstream always means "N visible ideas" by construction of the
// worker payload, not by any backend-side filtering logic.

function makeJob(overrides: Record<string, any> = {}) {
  return {
    id: 'job-1',
    niche: 'test niche',
    status: 'AWAITING_SELECTION',
    currentStage: null,
    currentStageName: null,
    stagesCompleted: 0,
    totalStages: 16,
    progressPercent: 0,
    errorMessage: null,
    startedAt: null,
    completedAt: null,
    stopReason: null,
    stopReasonDetails: null,
    errorCode: null,
    errorDetails: null,
    generateLandingPage: false,
    landingPageStatus: null,
    jobMode: null,
    entryMode: null,
    selectedSolution: null,
    selectedSolutions: [],
    awaitingSelectionAt: null,
    ideasShownAt: null,
    selectionRationale: null,
    solutionIdeas: null,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    progress: [],
    assets: [],
    ...overrides,
  } as any;
}

describe('formatJobResponse solutionIdeasCount', () => {
  it('counts off the stored solutionIdeas length (worker already filtered to visible-only)', () => {
    const job = makeJob({
      solutionIdeas: [
        { solution_name: 'Sol1', candidate_status: 'active' },
        { solution_name: 'Sol2', candidate_status: 'active' },
        { solution_name: 'Sol3', candidate_status: 'active' },
      ],
    });

    const result = formatJobResponse(job);

    expect(result.solutionIdeasCount).toBe(3);
  });

  it('is null when solutionIdeas is null', () => {
    const job = makeJob({ solutionIdeas: null });

    const result = formatJobResponse(job);

    expect(result.solutionIdeasCount).toBeNull();
  });

  it('is 0 for an empty stored array', () => {
    const job = makeJob({ solutionIdeas: [] });

    const result = formatJobResponse(job);

    expect(result.solutionIdeasCount).toBe(0);
  });

  it('exposes immutable selected idea refs without rebuilding them from the current pool', () => {
    const selectedSolutionRefs = [{
      ideaId: 'idea-alpha',
      ideaRevision: 2,
      snapshotSha256: 'a'.repeat(64),
    }];
    const result = formatJobResponse(makeJob({
      selectedSolutionRefs,
      deepResearchRecommendedIdeaId: 'idea-alpha',
      deepResearchRecommendedIdeaRevision: 2,
      solutionIdeas: [{ idea_id: 'idea-alpha', idea_revision: 3, solution_name: 'Alpha v3' }],
    }));

    expect(result.selectedSolutionRefs).toEqual(selectedSolutionRefs);
    expect(result.deepResearchRecommendedIdeaId).toBe('idea-alpha');
    expect(result.deepResearchRecommendedIdeaRevision).toBe(2);
  });
});

describe('formatJobResponse refund truth', () => {
  it('reports a refund only when spendable credits were actually restored', () => {
    const refunded = formatJobResponse(makeJob({
      creditTransactions: [{ id: 'refund-1', amount: 5 }],
    }));
    const notRefunded = formatJobResponse(makeJob({
      creditTransactions: [{ id: 'refund-expired-monthly', amount: 0 }],
    }));

    expect(refunded.creditRefunded).toBe(true);
    expect(notRefunded.creditRefunded).toBe(false);
  });

  it('returns false when refund data is loaded but empty', () => {
    const result = formatJobResponse(makeJob({
      creditTransactions: [],
    }), { includeAssetFlags: true });

    expect(result.creditRefunded).toBe(false);
  });

  it('does not attribute an older auxiliary-operation refund to the latest failed dispatch', () => {
    const result = formatJobResponse(makeJob({
      status: 'FAILED',
      creditTransactions: [{ id: 'older-seed-refund', amount: 2 }],
      dispatches: [{
        id: 'latest-deep-research',
        kind: 'DEEP_RESEARCH',
        state: 'FAILED',
        refundedAmount: null,
        refundTransaction: null,
      }],
    }));

    expect(result.creditRefunded).toBe(false);
  });

  it('reports the latest exact dispatch refund', () => {
    const result = formatJobResponse(makeJob({
      creditTransactions: [],
      dispatches: [{
        id: 'failed-deep-research',
        kind: 'DEEP_RESEARCH',
        state: 'REFUNDED',
        refundedAmount: 100,
        refundTransaction: { amount: 100 },
      }],
    }));

    expect(result.creditRefunded).toBe(true);
    expect(result.creditRefundedAmount).toBe(100);
  });

  it('exposes the exact active dispatch kind without inventing a refund', () => {
    const result = formatJobResponse(makeJob({
      activeDispatchId: 'seed-dispatch',
      creditTransactions: [],
      dispatches: [{
        id: 'seed-dispatch',
        kind: 'SEED_IDEA',
        state: 'AUTHORIZED',
        refundedAmount: null,
        refundTransaction: null,
      }],
    }));

    expect(result.creditRefunded).toBe(false);
    expect(result.creditRefundedAmount).toBe(0);
    expect(result.activeDispatchKind).toBe('SEED_IDEA');
    expect(result.activeOperation).toEqual({
      id: 'seed-dispatch',
      kind: 'SEED_IDEA',
      state: 'AUTHORIZED',
    });
  });

  it('does not expose a terminal dispatch as the job owner', () => {
    const result = formatJobResponse(makeJob({
      activeDispatchId: 'seed-dispatch',
      dispatches: [{
        id: 'seed-dispatch',
        kind: 'SEED_IDEA',
        state: 'COMPLETED',
        refundedAmount: null,
        refundTransaction: null,
      }],
    }));

    expect(result.activeDispatchKind).toBeNull();
    expect(result.activeOperation).toBeNull();
  });

  it('keeps a paid-pool recovery visible as the active operation', () => {
    const result = formatJobResponse(makeJob({
      activeDispatchId: 'seed-dispatch',
      dispatches: [{
        id: 'seed-dispatch',
        kind: 'SEED_IDEA',
        state: 'RECOVERING',
        refundedAmount: null,
        refundTransaction: null,
      }],
    }));

    expect(result.activeDispatchKind).toBe('SEED_IDEA');
    expect(result.activeOperation).toEqual({
      id: 'seed-dispatch',
      kind: 'SEED_IDEA',
      state: 'RECOVERING',
    });
  });

  it('does not invent false when the caller did not load refund data', () => {
    const result = formatJobResponse(makeJob());

    expect(result).not.toHaveProperty('creditRefunded');
    expect(result).not.toHaveProperty('creditRefundedAmount');
  });
});

describe('formatJobResponse includeSolutionIdeas', () => {
  it('serves the stored visible ideas with stable identities', () => {
    const solutions = [
      { solution_name: 'Sol1', candidate_status: 'active' },
      {
        solution_name: 'Sol2',
        candidate_status: 'active',
        merged_from: ['OldSol'],
        idea_id: 'idea_existing',
        idea_revision: 2,
      },
    ];
    const job = makeJob({ solutionIdeas: solutions });

    const result = formatJobResponse(job, { includeSolutionIdeas: true });

    expect(result.solutionIdeas).toEqual([
      {
        ...solutions[0],
        idea_id: expect.stringMatching(/^idea_[a-f0-9]{32}$/),
        idea_revision: 1,
      },
      solutions[1],
    ]);
  });

  it('is null when solutionIdeas is not stored', () => {
    const job = makeJob({ solutionIdeas: null });

    const result = formatJobResponse(job, { includeSolutionIdeas: true });

    expect(result.solutionIdeas).toBeNull();
  });

  it('stops advertising additional batches at the backend limit', () => {
    const available = formatJobResponse(
      makeJob({
        solutionIdeas: [],
        regenerationCount: 12,
        ideaBatchCompletedCount: 9,
      }),
      { includeSolutionIdeas: true },
    );
    const exhausted = formatJobResponse(
      makeJob({
        solutionIdeas: [],
        regenerationCount: 10,
        ideaBatchCompletedCount: 10,
      }),
      { includeSolutionIdeas: true },
    );

    // Failed/cancelled attempts advance regenerationCount for ledger identity,
    // but only successful completed batches consume the product cap.
    expect(available.canRegenerate).toBe(true);
    expect(available.ideaBatchCompletedCount).toBe(9);
    expect(available.maxIdeaBatches).toBe(10);
    expect(exhausted.canRegenerate).toBe(false);
    expect(exhausted.ideaBatchCompletedCount).toBe(10);
    expect(exhausted.maxIdeaBatches).toBe(10);
  });
});

// Phase B — plans/eager-meandering-feather.md: guided-mode (chatMode) G1/G2 stage gates.
describe('formatJobResponse guided-mode fields', () => {
  it('defaults chatMode to false and gate fields to null when absent', () => {
    const job = makeJob({});

    const result = formatJobResponse(job);

    expect(result.chatMode).toBe(false);
    expect(result.gateStage).toBeNull();
    expect(result.gateArtifact).toBeNull();
    expect(result.gateReachedAt).toBeNull();
  });

  it('serves chatMode/gateStage/gateArtifact/gateReachedAt when the job is AWAITING_GATE', () => {
    const gateReachedAt = new Date('2026-07-11T12:00:00Z');
    const gateArtifact = { type: 'niche_validation', niche_description: 'x' };
    const job = makeJob({
      status: 'AWAITING_GATE',
      chatMode: true,
      gateStage: 1,
      gateArtifact,
      gateReachedAt,
    });

    const result = formatJobResponse(job);

    expect(result.chatMode).toBe(true);
    expect(result.gateStage).toBe(1);
    expect(result.gateArtifact).toEqual(gateArtifact);
    expect(result.gateReachedAt).toBe(gateReachedAt.toISOString());
  });

  it('gateStage stays null at AWAITING_SELECTION (the G3 sentinel lives only in ChatMessage)', () => {
    const job = makeJob({ status: 'AWAITING_SELECTION', chatMode: true, gateStage: null });

    const result = formatJobResponse(job);

    expect(result.gateStage).toBeNull();
  });

  it('defaults gateApplyCount to 0 and serves the persisted count (apply-cap surfacing)', () => {
    const fresh = formatJobResponse(makeJob({}));
    expect(fresh.gateApplyCount).toBe(0);

    const applied = formatJobResponse(makeJob({ status: 'AWAITING_GATE', gateStage: 1, gateApplyCount: 3 }));
    expect(applied.gateApplyCount).toBe(3);
  });
});
