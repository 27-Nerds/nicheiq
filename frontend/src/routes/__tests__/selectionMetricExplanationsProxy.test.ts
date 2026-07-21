import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ fetchBackend: vi.fn() }));

vi.mock('$lib/backend', () => ({ fetchBackend: mocks.fetchBackend }));

import { GET } from '../api/selection/metric-explanations/+server';

const locals = {
  auth: vi.fn().mockResolvedValue({ user: { id: 'owner-1' } }),
};

describe('selection metric explanations proxy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    locals.auth.mockResolvedValue({ user: { id: 'owner-1' } });
    mocks.fetchBackend.mockResolvedValue(new Response(JSON.stringify({
      schemaVersion: 1,
      metrics: [],
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
  });

  it('requires the signed-in user and prevents shared caching', async () => {
    const response = await GET({ locals } as never);

    expect(mocks.fetchBackend).toHaveBeenCalledWith(
      '/api/selection/metric-explanations',
      { headers: { 'X-User-ID': 'owner-1' } },
    );
    expect(response.headers.get('cache-control')).toBe('private, no-store');
    await expect(response.json()).resolves.toEqual({ schemaVersion: 1, metrics: [] });
  });
});
