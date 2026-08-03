import { beforeEach, describe, expect, it, vi } from 'vitest';

const { fetchBackend } = vi.hoisted(() => ({ fetchBackend: vi.fn() }));

vi.mock('$lib/backend', () => ({ fetchBackend }));

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('/sample-report loader', () => {
  it('loads only the exact 22-character configured share', async () => {
    fetchBackend
      .mockResolvedValueOnce(response({ url: '/shared/abcdefghijklmnopqrstuv' }))
      .mockResolvedValueOnce(response({ niche: 'Bookkeepers', selected_solution_name: 'Close Desk' }));
    const { load } = await import('./+page.server');

    const result = await load({} as never) as { report: Record<string, unknown> | null };

    expect(fetchBackend).toHaveBeenNthCalledWith(1, '/api/settings/sample-report-url');
    expect(fetchBackend).toHaveBeenNthCalledWith(2, '/api/shared/abcdefghijklmnopqrstuv');
    expect(result.report?.selected_solution_name).toBe('Close Desk');
  });

  it('does not request a public report for a malformed or stale setting', async () => {
    fetchBackend.mockResolvedValueOnce(response({ url: '/shared/abc123' }));
    const { load } = await import('./+page.server');

    const result = await load({} as never) as { report: unknown };

    expect(result.report).toBeNull();
    expect(fetchBackend).toHaveBeenCalledTimes(1);
  });
});
