import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  getDiscovery: vi.fn(),
  loadCurrentSelectionContext: vi.fn(),
  buildState: vi.fn(),
  hasDecisionToolsAccess: vi.fn().mockResolvedValue(true),
}));

// This route is deliberately NOT blocked by the grant — it resolves it and passes it
// through, so the projection collapses instead of the request failing.
vi.mock('../../services/featureAccess.js', () => ({
  hasDecisionToolsAccess: (...a: unknown[]) => mocks.hasDecisionToolsAccess(...a),
}));

vi.mock('../../services/db.js', () => ({
  prisma: { job: { findFirst: mocks.jobFindFirst } },
}));
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: 'owner-1' };
    next();
  },
}));
vi.mock('../../services/assetService.js', () => ({
  getDiscoveryDataForJob: mocks.getDiscovery,
}));
vi.mock('../../services/currentSelectionContext.js', () => ({
  loadCurrentSelectionContext: mocks.loadCurrentSelectionContext,
}));
vi.mock('../../services/selectionDecisionStateService.js', () => ({
  buildSelectionDecisionState: mocks.buildState,
}));

import { selectionDecisionStateRouter } from '../selectionDecisionState.js';

const jobId = '11111111-1111-4111-8111-111111111111';
const app = express();
app.use('/api/jobs', selectionDecisionStateRouter);

function job() {
  return {
    id: jobId,
    status: 'AWAITING_SELECTION',
    selectionDraft: null,
    selectionDraftVersion: 0,
    selectionDecisionProfile: null,
    selectionFounderFit: null,
    selectionChallenges: [],
    selectionOwnerEvidence: [],
    selectionAssumptions: [],
    selectionExperiments: [],
  };
}

describe('selection decision state owner API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getDiscovery.mockResolvedValue(null);
    mocks.loadCurrentSelectionContext.mockResolvedValue({
      canonical: { candidates: [] },
      runArtifacts: { verification: 'untrusted', reason: 'preview_unavailable' },
    });
    mocks.buildState.mockReturnValue({ schemaVersion: 1, jobId });
  });

  it('loads the projection through an owner-scoped query', async () => {
    mocks.jobFindFirst.mockResolvedValue(job());

    const response = await request(app).get(`/api/jobs/${jobId}/selection-decision-state`);

    expect(response.status).toBe(200);
    expect(response.headers['cache-control']).toBe('private, no-store');
    expect(response.body).toEqual({ schemaVersion: 1, jobId });
    expect(mocks.jobFindFirst).toHaveBeenCalledWith(expect.objectContaining({
      where: { id: jobId, userId: 'owner-1' },
    }));
    expect(mocks.jobFindFirst.mock.calls[0][0].select).not.toHaveProperty('solutionIdeas');
    expect(mocks.buildState).toHaveBeenCalledWith(expect.objectContaining({
      jobId,
      solutionIdeas: [],
      previewReport: null,
      discoveryData: null,
    }));
  });

  it('uses only context-verified preview evidence and canonical candidates', async () => {
    const candidate = { idea_id: 'idea-1', idea_revision: 1, solution_name: 'Current idea' };
    const previewReport = { idea_portfolio_summary: 'Version-bound evidence' };
    mocks.jobFindFirst.mockResolvedValue(job());
    mocks.loadCurrentSelectionContext.mockResolvedValue({
      canonical: { candidates: [candidate] },
      runArtifacts: { verification: 'verified', previewReport },
    });

    const response = await request(app).get(`/api/jobs/${jobId}/selection-decision-state`);

    expect(response.status).toBe(200);
    expect(mocks.buildState).toHaveBeenCalledWith(expect.objectContaining({
      solutionIdeas: [candidate],
      previewReport,
    }));
  });

  it('does not reveal another owner\'s job', async () => {
    mocks.jobFindFirst.mockResolvedValue(null);

    const response = await request(app).get(`/api/jobs/${jobId}/selection-decision-state`);

    expect(response.status).toBe(404);
    expect(mocks.buildState).not.toHaveBeenCalled();
    expect(mocks.loadCurrentSelectionContext).not.toHaveBeenCalled();
  });
});
