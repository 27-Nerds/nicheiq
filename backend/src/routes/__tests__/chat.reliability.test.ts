import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

// ============================================
// Deploy-readiness fixes (2026-07-13) covered here:
//  1. BLOCKER — POST /:jobId/chat had no top-level try/catch: an unguarded throw
//     anywhere in the handler (pre-header job/entitlement/rate-limit lookups, or the
//     POST-STREAM gate-recheck/assistantMessage.create/generateSuggestions writes)
//     left the client hanging forever — worst of all AFTER a reply had already
//     streamed. Fixed with one outer catch that always terminates the response:
//     plain JSON status pre-headers, a terminal SSE `error` event + res.end() once
//     headers are sent.
//  3. AMEND — usage accumulated before a client abort was discarded: the truncated
//     message persisted with no costUsd and job.chatCostUsd was never incremented.
//  4. AMEND — GET /chat/history's opening-message synthesis raced: two concurrent
//     zero-history requests could both persist an opening message. Fixed with the
//     same advisory-lock (pg_advisory_xact_lock(hashtext(jobId))) idiom the turn-cap
//     transaction already uses.
//
// This file is a SIBLING to chat.test.ts (not a replacement) — it exercises the
// reliability fixes above without touching that file, which another workstream owns
// for a typing fix. Mocking conventions mirror chat.test.ts.
// ============================================

const mockJobFindFirst = vi.fn();
const mockJobUpdate = vi.fn().mockResolvedValue({});
const mockChatMessageCreate = vi.fn();
const mockChatMessageUpdate = vi.fn();
const mockChatMessageDelete = vi.fn();
const mockChatMessageFindManyTop = vi.fn();

const mockExecuteRaw = vi.fn().mockResolvedValue(undefined);
const mockChatMessageCount = vi.fn();
const mockChatMessageFindManyTx = vi.fn().mockResolvedValue([]);
const mockTxChatMessageCreate = vi.fn().mockResolvedValue({});
const mockTxJobFindUnique = vi.fn(async (..._a: any[]) => {
  const j = await mockJobFindFirst();
  return j ? { status: j.status, gateStage: j.gateStage ?? null } : null;
});
let mockPostStreamJobFindUniqueError: Error | null = null;
const mockJobFindUniqueTop = vi.fn(async (...args: any[]) => {
  const j = await mockJobFindFirst();
  if (!j) return null;
  if (args[0]?.select?.selectionChallenges) {
    return {
      discoveryShare: j.discoveryShare ?? null,
      selectionChallenges: j.selectionChallenges ?? [],
      selectionExperiments: j.selectionExperiments ?? [],
    };
  }
  if (mockPostStreamJobFindUniqueError) {
    const error = mockPostStreamJobFindUniqueError;
    mockPostStreamJobFindUniqueError = null;
    throw error;
  }
  return { status: j.status, gateStage: j.gateStage ?? null };
});
const mockTransaction = vi.fn(async (cb: any) => {
  const tx = {
    $executeRaw: mockExecuteRaw,
    job: { findUnique: (...a: any[]) => mockTxJobFindUnique(...a) },
    chatMessage: {
      count: mockChatMessageCount,
      findMany: mockChatMessageFindManyTx,
      create: mockTxChatMessageCreate,
    },
  };
  return cb(tx);
});

vi.mock('../../services/db.js', () => ({
  prisma: {
    job: {
      findFirst: (...a: any[]) => mockJobFindFirst(...a),
      findUnique: (...a: any[]) => mockJobFindUniqueTop(...a),
      update: (...a: any[]) => mockJobUpdate(...a),
    },
    chatMessage: {
      create: (...a: any[]) => mockChatMessageCreate(...a),
      findMany: (...a: any[]) => mockChatMessageFindManyTop(...a),
      update: (...a: any[]) => mockChatMessageUpdate(...a),
      delete: (...a: any[]) => mockChatMessageDelete(...a),
    },
    $transaction: (cb: any) => mockTransaction(cb),
  },
}));

const mockIsEntitledUser = vi.fn().mockResolvedValue(true);
vi.mock('../../services/catalogService.js', () => ({
  isEntitledUser: (...a: any[]) => mockIsEntitledUser(...a),
}));

// The analyst gate is now hasAnalystAccess = isEntitledUser || the chatAnalystAccess
// grant. These suites drive the entitlement half, so the existing mock stands in for
// the whole gate. Decision tools default ON here so the pre-existing prompt/tool
// assertions keep describing the full-feature owner; the off case has its own tests.
const mockHasDecisionToolsAccess = vi.fn().mockResolvedValue(true);
vi.mock('../../services/featureAccess.js', () => ({
  hasAnalystAccess: (...a: any[]) => mockIsEntitledUser(...a),
  hasDecisionToolsAccess: (...a: any[]) => mockHasDecisionToolsAccess(...a),
}));

const mockCheckChatRateLimit = vi.fn().mockResolvedValue({ allowed: true, remaining: { hourly: 19, daily: 79 } });
vi.mock('../../middleware/rateLimit.js', () => ({
  checkChatRateLimit: (...a: any[]) => mockCheckChatRateLimit(...a),
}));

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, res: any, next: any) => {
    const userId = req.headers['x-user-id'];
    if (userId) {
      req.user = { id: userId };
      return next();
    }
    res.status(401).json({ error: 'Unauthorized' });
  },
  AuthenticatedRequest: {},
}));

vi.mock('../../config.js', () => ({
  CONFIG: {
    openaiApiKey: 'sk-test',
    chatModel: 'gpt-4.1-mini',
    chatRateHourly: 20,
    chatRateDaily: 80,
  },
}));

const mockChatCompleteStream = vi.fn();
const mockChatComplete = vi.fn().mockResolvedValue({
  choices: [{ message: { content: "Here's my read of the pool." } }],
  usage: { prompt_tokens: 10, completion_tokens: 5 },
});
vi.mock('../../services/openai.js', () => ({
  chatCompleteStream: (...a: any[]) => mockChatCompleteStream(...a),
  chatComplete: (...a: any[]) => mockChatComplete(...a),
}));

const mockGetPreviewReportForJob = vi.fn().mockResolvedValue(null);
const mockGetDiscoveryDataForJob = vi.fn().mockResolvedValue(null);
vi.mock('../../services/assetService.js', () => ({
  getPreviewReportForJob: (...a: any[]) => mockGetPreviewReportForJob(...a),
  getDiscoveryDataForJob: (...a: any[]) => mockGetDiscoveryDataForJob(...a),
}));

vi.mock('../../services/selectionDecisionStateLoader.js', () => ({
  loadOwnedSelectionDecisionState: vi.fn().mockResolvedValue(null),
}));

let app: Express;
const authHeaders = { 'x-user-id': 'user-123' };
const jobId = '00000000-0000-0000-0000-000000000001';

function makeJob(overrides: Record<string, any> = {}) {
  return {
    status: 'AWAITING_SELECTION',
    niche: 'test niche',
    solutionIdeas: [{ solution_name: 'Sol1', short_description: 'does a thing', market_fit_score: 0.7 }],
    ...overrides,
  };
}

beforeEach(async () => {
  vi.clearAllMocks();
  mockPostStreamJobFindUniqueError = null;
  mockJobFindFirst.mockResolvedValue(makeJob());
  mockIsEntitledUser.mockResolvedValue(true);
  mockCheckChatRateLimit.mockResolvedValue({ allowed: true, remaining: { hourly: 19, daily: 79 } });
  mockChatMessageCount.mockResolvedValue(0);
  mockChatMessageFindManyTx.mockResolvedValue([]);
  mockTxChatMessageCreate.mockResolvedValue({});
  mockChatMessageCreate.mockResolvedValue({
    id: 'asst-1',
    role: 'assistant',
    content: '',
    patchJson: null,
    toolCallsJson: null,
    createdAt: new Date('2026-07-13T00:00:00Z'),
  });
  mockChatMessageUpdate.mockResolvedValue({});
  mockChatMessageDelete.mockResolvedValue({});
  mockChatCompleteStream.mockResolvedValue([
    { choices: [{ delta: { content: 'Hello there' } }] },
    { choices: [], usage: { prompt_tokens: 10, completion_tokens: 5 } },
  ]);
  mockChatComplete.mockResolvedValue({
    choices: [{ message: { content: "Here's my read of the pool." } }],
    usage: { prompt_tokens: 10, completion_tokens: 5 },
  });
  mockGetPreviewReportForJob.mockResolvedValue(null);
  mockGetDiscoveryDataForJob.mockResolvedValue(null);

  app = express();
  app.use(express.json());
  const { chatRouter } = await import('../chat.js');
  app.use('/api/jobs', chatRouter);
});

describe('POST /api/jobs/:jobId/chat — BLOCKER: every path terminates the response', () => {
  it('returns a plain JSON 500 (not a hang) when a pre-header lookup throws', async () => {
    mockJobFindFirst.mockRejectedValue(new Error('db connection blip'));

    const response = await request(app).post(`/api/jobs/${jobId}/chat`).set(authHeaders).send({ message: 'hi' });

    expect(response.status).toBe(500);
    expect(response.body.error).toBeTruthy();
  });

  it('still delivers the streamed answer (done event) when the post-stream assistant persist throws', async () => {
    mockChatMessageCreate.mockRejectedValue(new Error('db write failed'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/chat`)
      .set(authHeaders)
      .send({ message: 'what is the market fit?' });

    expect(response.status).toBe(200);
    // The reply already streamed in full — losing the DB write must not lose the answer.
    expect(response.text).toContain('Hello there');
    expect(response.text).toContain('"type":"done"');
    // Told, not silently swallowed.
    expect(response.text).toContain('"type":"note"');
  });

  it('drops (not throws) a proposed patch when the post-stream gate freshness re-check itself fails', async () => {
    mockChatCompleteStream.mockResolvedValue([
      {
        choices: [
          { delta: { tool_calls: [{ index: 0, id: 'call_1', function: { name: 'propose_modification', arguments: '' } }] } },
        ],
      },
      {
        choices: [
          {
            delta: {
              tool_calls: [{ index: 0, function: { arguments: '{"idea_focus":"novelty","rationale":"steer"}' } }],
            },
          },
        ],
      },
      { choices: [], usage: { prompt_tokens: 10, completion_tokens: 6 } },
    ]);
    mockPostStreamJobFindUniqueError = new Error('db blip on re-check');

    const response = await request(app)
      .post(`/api/jobs/${jobId}/chat`)
      .set(authHeaders)
      .send({ message: 'give me more novel ideas' });

    expect(response.status).toBe(200);
    expect(response.text).toContain('"type":"done"');
    const createCall = mockChatMessageCreate.mock.calls[0][0];
    expect(createCall.data.patchJson).toBeUndefined();
  });

  it('ends the stream with a terminal error event (never hangs) when something after a successful persist still throws', async () => {
    // A value JSON.stringify cannot serialize (BigInt) reaching the final `done` write
    // is a stand-in for "some other truly unexpected failure after headers were already
    // sent" — the generic outer catch is the last line of defense for exactly this.
    mockChatMessageCreate.mockResolvedValue({
      id: 'asst-1',
      role: 'assistant',
      content: 'Hello there',
      patchJson: null,
      toolCallsJson: null,
      createdAt: 123n as unknown as Date,
    });

    const response = await request(app)
      .post(`/api/jobs/${jobId}/chat`)
      .set(authHeaders)
      .send({ message: 'what is the market fit?' });

    expect(response.status).toBe(200);
    expect(response.text).toContain('"type":"error"');
    expect(response.text).not.toContain('"type":"done"');
  });
});


// Generation failures are handled inside the model/tool loop, before assistant persistence.
// This is intentionally separate from the terminal-error tests above, which exercise the outer
// catch after an assistant row already exists.
describe('POST /api/jobs/:jobId/chat — generation-failure turn rollback', () => {
  it('deletes and retracts the exact user turn when generation fails', async () => {
    mockChatMessageCount.mockResolvedValue(4);
    mockTxChatMessageCreate.mockResolvedValue({ id: 'user-1' });
    mockChatCompleteStream.mockRejectedValueOnce(new Error('model down'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/chat`)
      .set(authHeaders)
      .send({ message: 'what is the market fit?' });

    expect(response.status).toBe(200);
    expect(mockChatMessageDelete).toHaveBeenCalledTimes(1);
    expect(mockChatMessageDelete).toHaveBeenCalledWith({ where: { id: 'user-1' } });
    expect(response.text).toContain('"type":"error"');
    expect(response.text).toContain('"retractMessageId":"user-1"');
    expect(response.text).toContain('"usedTurns":4');
    expect(response.text).not.toContain('"type":"done"');
    expect(mockChatMessageCreate).not.toHaveBeenCalled();
  });

  it('does not retract or refund the turn count when deleting the failed turn fails', async () => {
    mockChatMessageCount.mockResolvedValue(4);
    mockTxChatMessageCreate.mockResolvedValue({ id: 'user-1' });
    mockChatMessageDelete.mockRejectedValueOnce(new Error('delete failed'));
    mockChatCompleteStream.mockRejectedValueOnce(new Error('model down'));

    const response = await request(app)
      .post(`/api/jobs/${jobId}/chat`)
      .set(authHeaders)
      .send({ message: 'what is the market fit?' });

    expect(response.status).toBe(200);
    expect(mockChatMessageDelete).toHaveBeenCalledWith({ where: { id: 'user-1' } });
    expect(response.text).toContain('"type":"error"');
    expect(response.text).not.toContain('retractMessageId');
    expect(response.text).toContain('"usedTurns":5');
    expect(response.text).not.toContain('"type":"done"');
    expect(mockChatMessageCreate).not.toHaveBeenCalled();
  });
});

// The handler drives its abort detection off `req.on('close', ...)` (attached late,
// right before streaming starts) and `controller.abort()`. Under a real HTTP round
// trip, Node's IncomingMessage 'close' event fires once — tied to the REQUEST body
// finishing being read — and is not reliably re-emitted by a later client-side socket
// teardown, so there's no deterministic way to trigger the same code path through a
// genuine req/res pair without fighting Node/runtime timing. Instead, invoke the route
// handler directly (bypassing HTTP + the auth/validation middleware in front of it,
// which are exercised elsewhere) with a hand-rolled req/res whose `close` this test
// controls precisely — targeting exactly the code THIS fix touches (what happens once
// `clientAborted` is true), not the pre-existing close-detection wiring.

function getChatPostHandler(router: import('express').Router): (req: any, res: any) => Promise<void> {
  const layer = (router as any).stack.find((l: any) => l.route?.path === '/:jobId/chat' && l.route?.methods?.post);
  if (!layer) throw new Error('POST /:jobId/chat route not found on chatRouter');
  const stack = layer.route.stack as { handle: (...a: any[]) => any }[];
  return stack[stack.length - 1].handle; // last handler in the chain is the route's own async fn
}

function makeFakeReqRes(body: Record<string, unknown>) {
  const listeners: Record<string, (() => void)[]> = {};
  const req: any = {
    params: { jobId },
    user: { id: 'user-123' },
    body,
    on(event: string, cb: () => void) {
      (listeners[event] ||= []).push(cb);
    },
    emit(event: string) {
      (listeners[event] || []).forEach((cb) => cb());
    },
  };
  const res: any = {
    headersSent: false,
    statusCode: 200,
    jsonBody: undefined as unknown,
    writes: [] as string[],
    ended: false,
    status(code: number) {
      this.statusCode = code;
      return this;
    },
    json(payload: unknown) {
      this.jsonBody = payload;
      return this;
    },
    setHeader() {
      return this;
    },
    flushHeaders() {
      this.headersSent = true;
    },
    write(chunk: string) {
      this.writes.push(chunk);
      return true;
    },
    end() {
      this.ended = true;
    },
  };
  return { req, res };
}

describe('POST /api/jobs/:jobId/chat — AMEND: cost accounting on client abort', () => {
  it('persists usage accumulated so far and increments chatCostUsd when the client disconnects mid-stream', async () => {
    const { chatRouter } = await import('../chat.js');
    const handler = getChatPostHandler(chatRouter);
    const { req, res } = makeFakeReqRes({ message: 'hi' });

    // Round 1 (streamed) calls a read-only evidence tool and completes NORMALLY,
    // folding its usage into the turn's running total — exactly like a real multi-round
    // tool-resolution turn. Round 2 (tool-resolution rounds run unstreamed via
    // chatComplete) is where the disconnect actually lands: `req.emit('close')` is this
    // test's stand-in for the real socket teardown chat.ts's own `req.on('close')`
    // listens for, and the round throws — landing in the SAME `clientAborted` catch
    // branch a real abort would, with round 1's usage already accumulated.
    mockChatCompleteStream.mockResolvedValue([
      {
        choices: [
          { delta: { tool_calls: [{ index: 0, id: 'call_1', function: { name: 'get_pain_evidence', arguments: '' } }] } },
        ],
      },
      {
        choices: [
          { delta: { tool_calls: [{ index: 0, function: { arguments: '{"pain_title":"whatever"}' } }] } },
        ],
      },
      { choices: [], usage: { prompt_tokens: 30, completion_tokens: 15 } },
    ]);
    mockChatComplete.mockImplementationOnce(async () => {
      req.emit('close');
      throw new Error('connection reset — client already gone');
    });

    await handler(req, res);

    expect(mockChatMessageCreate).toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ truncated: true, costUsd: expect.any(Number) }) })
    );
    // The number itself must reflect round 1's real usage, not a zero/placeholder.
    const persistedCostUsd = mockChatMessageCreate.mock.calls[0][0].data.costUsd;
    expect(persistedCostUsd).toBeGreaterThan(0);
    expect(mockJobUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ data: { chatCostUsd: { increment: expect.any(Number) } } })
    );
    // Never leaves the socket hanging on this path either — nobody's listening, so the
    // handler returns without writing a terminal event, but it does return.
    expect(res.ended).toBe(false);
  });
});

describe('GET /api/jobs/:jobId/chat/history — AMEND: opening-message synthesis is concurrency-guarded', () => {
  it('persists exactly ONE opening message across two concurrent zero-history requests', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, status: 'AWAITING_SELECTION', niche: 'test niche', solutionIdeas: [] });
    mockChatMessageFindManyTop.mockResolvedValue([]); // both requests see empty history throughout

    // The advisory lock serializes the two transactions — the loser's re-check inside
    // the lock sees the winner's insert and skips its own.
    let insertCount = 0;
    mockChatMessageCount.mockImplementation(async () => insertCount);
    mockTxChatMessageCreate.mockImplementation(async () => {
      insertCount += 1;
      return {};
    });

    const [r1, r2] = await Promise.all([
      request(app).get(`/api/jobs/${jobId}/chat/history`).set(authHeaders),
      request(app).get(`/api/jobs/${jobId}/chat/history`).set(authHeaders),
    ]);

    expect(r1.status).toBe(200);
    expect(r2.status).toBe(200);
    expect(mockTxChatMessageCreate).toHaveBeenCalledTimes(1);
  });

  it('uses the same advisory-lock idiom (hashtext(jobId)) the turn-cap transaction uses', async () => {
    mockJobFindFirst.mockResolvedValue({ id: jobId, status: 'AWAITING_SELECTION', niche: 'test niche', solutionIdeas: [] });
    mockChatMessageFindManyTop.mockResolvedValue([]);
    mockChatMessageCount.mockResolvedValue(0);

    await request(app).get(`/api/jobs/${jobId}/chat/history`).set(authHeaders);

    expect(mockExecuteRaw).toHaveBeenCalled();
    const [strings, ...values] = mockExecuteRaw.mock.calls[0];
    expect(strings.join('?')).toContain('pg_advisory_xact_lock(hashtext(');
    expect(values).toContain(jobId);
  });
});
