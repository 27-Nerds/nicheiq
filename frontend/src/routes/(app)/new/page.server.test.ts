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

describe('/new loader sample availability', () => {
  it('exposes only backend-verified sample availability to the form', async () => {
    fetchBackend.mockImplementation((path: string) => Promise.resolve(
      path.includes('/catalog/discover')
        ? response({ items: [{ id: 'pain-1' }] })
        : response({ url: '/shared/abcdefghijklmnopqrstuv' }),
    ));
    const { load } = await import('./+page.server');

    const result = await load({
      parent: async () => ({ session: { user: { id: 'user-1' } } }),
    } as never) as { hasCatalogData: boolean; sampleReportAvailable: boolean };

    expect(result.hasCatalogData).toBe(true);
    expect(result.sampleReportAvailable).toBe(true);
    expect(fetchBackend).toHaveBeenCalledWith('/api/settings/sample-report-url');
  });

  it('fails closed when no verified sample URL is returned', async () => {
    fetchBackend.mockImplementation((path: string) => Promise.resolve(
      path.includes('/catalog/discover') ? response({ items: [] }) : response({ url: null }),
    ));
    const { load } = await import('./+page.server');

    const result = await load({
      parent: async () => ({ session: { user: { id: 'user-1' } } }),
    } as never) as { sampleReportAvailable: boolean };

    expect(result.sampleReportAvailable).toBe(false);
  });
});
