import express from 'express';
import request from 'supertest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetJob = vi.fn();

vi.mock('../../services/jobService.js', () => ({
  getJob: (...args: any[]) => mockGetJob(...args),
}));

vi.mock('../../services/progressBroadcastService.js', () => ({
  subscribeToJobProgress: vi.fn(() => vi.fn()),
}));

vi.mock('../../services/queueService.js', () => ({
  getQueueStats: vi.fn(),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: 'user-1' };
    next();
  },
  verifyOwnership: () => true,
}));

let app: express.Express;

beforeEach(async () => {
  vi.clearAllMocks();
  app = express();
  const { eventsRouter } = await import('../events.js');
  app.use('/api/jobs', eventsRouter);
});

function terminalJob(refundAmount: number | null) {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    userId: 'user-1',
    niche: 'test',
    status: 'CANCELLED',
    currentStage: 5,
    currentStageName: 'Solution Pipeline',
    stagesCompleted: 5,
    totalStages: 16,
    progressPercent: 31,
    errorMessage: 'Cancelled by user',
    startedAt: new Date('2026-07-30T00:00:00Z'),
    completedAt: null,
    stopReason: null,
    stopReasonDetails: null,
    errorCode: null,
    errorDetails: null,
    generateLandingPage: false,
    landingPageStatus: null,
    jobMode: 'interactive',
    entryMode: null,
    selectedSolution: null,
    selectedSolutions: [],
    selectedSolutionIds: [],
    awaitingSelectionAt: null,
    ideasShownAt: null,
    solutionIdeas: [],
    chatMode: false,
    gateStage: null,
    gateArtifact: null,
    gateReachedAt: null,
    gateApplyCount: 0,
    createdAt: new Date('2026-07-30T00:00:00Z'),
    progress: [],
    assets: [],
    creditTransactions: refundAmount == null
      ? []
      : [{ id: 'refund-1', amount: refundAmount }],
  };
}

describe('GET /api/jobs/:jobId/events terminal snapshot refund truth', () => {
  it('returns creditRefunded=true after reconnect/reload when a refund exists', async () => {
    mockGetJob.mockResolvedValue(terminalJob(5));

    const response = await request(app)
      .get('/api/jobs/00000000-0000-0000-0000-000000000001/events');

    expect(response.status).toBe(200);
    expect(response.body.status).toBe('CANCELLED');
    expect(response.body.creditRefunded).toBe(true);
  });

  it('returns creditRefunded=false when a refund restored zero expired allowance credits', async () => {
    mockGetJob.mockResolvedValue(terminalJob(0));

    const response = await request(app)
      .get('/api/jobs/00000000-0000-0000-0000-000000000001/events');

    expect(response.status).toBe(200);
    expect(response.body.creditRefunded).toBe(false);
  });
});
