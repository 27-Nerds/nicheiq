import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

const createMockRequest = (body: unknown) => ({
  json: async () => body,
});

const createMockLocals = (userId: string | null) => ({
  auth: async () => (userId ? { user: { id: userId } } : null),
});

describe('POST /api/jobs/:jobId/generate-landing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('forwards the confirmed landing-page cost to the backend', async () => {
    mockFetch.mockResolvedValueOnce({
      status: 200,
      json: async () => ({ status: 'queued', creditCharged: 5 }),
    });

    const { POST } = await import('../+server');
    const response = await POST({
      params: { jobId: 'job-123' },
      request: createMockRequest({ expectedCost: 5 }),
      locals: createMockLocals('user-123'),
    } as never);

    expect(response.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/jobs/job-123/generate-landing'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-User-ID': 'user-123',
        }),
        body: JSON.stringify({ expectedCost: 5 }),
      }),
    );
  });
});
