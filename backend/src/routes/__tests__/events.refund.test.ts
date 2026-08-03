import express from 'express';
import request from 'supertest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getJob: vi.fn(),
  getQueueStats: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
}));

let progressListener: ((data: Record<string, unknown>) => void) | null = null;

vi.mock('../../services/jobService.js', () => ({
  getJob: (...args: any[]) => mocks.getJob(...args),
}));

vi.mock('../../services/progressBroadcastService.js', () => ({
  subscribeToJobProgress: (...args: any[]) => mocks.subscribe(...args),
}));

vi.mock('../../services/queueService.js', () => ({
  getQueueStats: (...args: any[]) => mocks.getQueueStats(...args),
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
  progressListener = null;
  mocks.subscribe.mockImplementation((_jobId, listener) => {
    progressListener = listener;
    return mocks.unsubscribe;
  });
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

function parseSseData(body: string): Record<string, any>[] {
  return body
    .split('\n')
    .filter(line => line.startsWith('data: '))
    .map(line => JSON.parse(line.slice('data: '.length)));
}

describe('GET /api/jobs/:jobId/events terminal snapshot refund truth', () => {
  it('emits one terminal SSE event and closes after reconnect when a refund exists', async () => {
    mocks.getJob.mockResolvedValue(terminalJob(5));

    const response = await request(app)
      .get('/api/jobs/00000000-0000-0000-0000-000000000001/events');

    expect(response.status).toBe(200);
    expect(response.headers['content-type']).toMatch(/^text\/event-stream/);
    const events = parseSseData(response.text);
    expect(events).toHaveLength(1);
    expect(events[0].status).toBe('CANCELLED');
    expect(events[0].creditRefunded).toBe(true);
    expect(mocks.subscribe).toHaveBeenCalledOnce();
    expect(mocks.unsubscribe).toHaveBeenCalledOnce();
  });

  it('emits creditRefunded=false when a refund restored zero expired allowance credits', async () => {
    mocks.getJob.mockResolvedValue(terminalJob(0));

    const response = await request(app)
      .get('/api/jobs/00000000-0000-0000-0000-000000000001/events');

    expect(response.status).toBe(200);
    const events = parseSseData(response.text);
    expect(events).toHaveLength(1);
    expect(events[0].creditRefunded).toBe(false);
    expect(mocks.unsubscribe).toHaveBeenCalledOnce();
  });

  it('subscribes before the authoritative snapshot so a terminal transition is not lost', async () => {
    const queued = {
      ...terminalJob(null),
      status: 'QUEUED',
      errorMessage: null,
    };
    const completed = {
      ...terminalJob(null),
      status: 'COMPLETED',
      errorMessage: null,
      completedAt: new Date('2026-07-30T00:05:00Z'),
    };
    mocks.getJob
      .mockResolvedValueOnce(queued)
      .mockResolvedValueOnce(queued)
      .mockResolvedValueOnce(completed);
    mocks.getQueueStats.mockImplementationOnce(async () => {
      expect(progressListener).not.toBeNull();
      progressListener!({ stage: 16, name: 'Complete', status: 'completed' });
      return { position: 1, totalQueued: 1, aheadCount: 0 };
    });

    const response = await request(app)
      .get('/api/jobs/00000000-0000-0000-0000-000000000001/events')
      .timeout({ deadline: 2000 });

    const events = parseSseData(response.text);
    expect(events.at(-1)?.status).toBe('COMPLETED');
    expect(mocks.subscribe).toHaveBeenCalledOnce();
    expect(mocks.unsubscribe).toHaveBeenCalledOnce();
  });
});
