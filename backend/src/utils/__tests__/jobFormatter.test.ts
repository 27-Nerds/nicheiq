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
});

describe('formatJobResponse includeSolutionIdeas', () => {
  it('serves the stored solutionIdeas array verbatim, without filtering by candidate_status', () => {
    const solutions = [
      { solution_name: 'Sol1', candidate_status: 'active' },
      { solution_name: 'Sol2', candidate_status: 'active', merged_from: ['OldSol'] },
    ];
    const job = makeJob({ solutionIdeas: solutions });

    const result = formatJobResponse(job, { includeSolutionIdeas: true });

    // Backend performs no filter of its own — it trusts the worker's payload as-is.
    expect(result.solutionIdeas).toEqual(solutions);
  });

  it('is null when solutionIdeas is not stored', () => {
    const job = makeJob({ solutionIdeas: null });

    const result = formatJobResponse(job, { includeSolutionIdeas: true });

    expect(result.solutionIdeas).toBeNull();
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
