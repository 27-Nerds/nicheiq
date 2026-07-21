import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

const mocks = vi.hoisted(() => ({
  jobFindFirst: vi.fn(),
  getPreview: vi.fn(),
  getDiscovery: vi.fn(),
  buildState: vi.fn(),
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
  getPreviewReportForJob: mocks.getPreview,
  getDiscoveryDataForJob: mocks.getDiscovery,
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
    solutionIdeas: [],
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
    mocks.getPreview.mockResolvedValue(null);
    mocks.getDiscovery.mockResolvedValue(null);
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
    expect(mocks.buildState).toHaveBeenCalledWith(expect.objectContaining({
      jobId,
      previewReport: null,
      discoveryData: null,
    }));
  });

  it('does not reveal another owner\'s job', async () => {
    mocks.jobFindFirst.mockResolvedValue(null);

    const response = await request(app).get(`/api/jobs/${jobId}/selection-decision-state`);

    expect(response.status).toBe(404);
    expect(mocks.buildState).not.toHaveBeenCalled();
    expect(mocks.getPreview).not.toHaveBeenCalled();
  });
});
