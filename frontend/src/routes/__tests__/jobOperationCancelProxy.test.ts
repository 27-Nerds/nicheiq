import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ fetchBackend: vi.fn() }));
vi.mock('$lib/backend', () => ({ fetchBackend: mocks.fetchBackend }));

import { POST } from '../api/jobs/[jobId]/operations/[operationId]/cancel/+server';

const locals = {
  auth: vi.fn().mockResolvedValue({ user: { id: 'owner-1' } }),
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
    status: 'cancelled',
    operationId: 'operation-1',
    operationState: 'CANCELLED',
    creditRefunded: 15,
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }));
});

describe('exact selection-operation cancel proxy', () => {
  it('forwards the exact operation and owner identity', async () => {
    const response = await POST({
      params: { jobId: 'job-1', operationId: 'operation-1' },
      locals,
    } as never);

    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      '/api/jobs/job-1/operations/operation-1/cancel',
      {
        method: 'POST',
        headers: { 'X-User-ID': 'owner-1' },
      },
    );
    expect(await response.json()).toEqual(expect.objectContaining({
      operationId: 'operation-1',
      creditRefunded: 15,
    }));
  });
});
