import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.fn();

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.stubGlobal('fetch', fetchMock);
});

async function renderSitemap(gate: 'true' | 'false'): Promise<string> {
  vi.doMock('$env/dynamic/private', () => ({
    env: {
      BACKEND_URL: 'http://backend.test',
      INTERNAL_SERVICE_SECRET: 'test-secret',
      SEO_LAUNCH_GATE: gate,
    },
  }));

  const { GET } = await import('../+server');
  const response = await GET({
    url: new URL('https://nicheiq.dev/sitemap.xml'),
  } as any);
  return response.text();
}

function okJson(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response;
}

describe('sitemap.xml launch gate', () => {
  it('omits /ideas and catalog URLs while SEO_LAUNCH_GATE is true', async () => {
    fetchMock.mockResolvedValueOnce(okJson({ reportShares: [], discoveryShares: [] }));

    const xml = await renderSitemap('true');

    expect(xml).not.toContain('<loc>https://nicheiq.dev/ideas</loc>');
    expect(xml).not.toContain('https://nicheiq.dev/idea/');
    expect(xml).not.toContain('https://nicheiq.dev/pain-point/');
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toContain('/api/sitemap/entries');
  });

  it('emits /ideas and canonical catalog URLs when SEO_LAUNCH_GATE is false', async () => {
    fetchMock
      .mockResolvedValueOnce(okJson({ reportShares: [], discoveryShares: [] }))
      .mockResolvedValueOnce(
        okJson({
          categories: [
            {
              slug: 'saas',
              parentSlug: null,
              updatedAt: '2026-04-27T00:00:00.000Z',
              ideaCount: 1,
              painPointCount: 0,
            },
            {
              slug: 'b2b-tools',
              parentSlug: 'saas',
              updatedAt: '2026-04-27T00:00:00.000Z',
              ideaCount: 1,
              painPointCount: 1,
            },
          ],
          ideas: [{ slug: 'idea-one-saas', updatedAt: '2026-04-27T00:00:00.000Z' }],
          painPoints: [{ slug: 'pain-one-saas', updatedAt: '2026-04-27T00:00:00.000Z' }],
        }),
      );

    const xml = await renderSitemap('false');

    expect(xml).toContain('<loc>https://nicheiq.dev/ideas</loc>');
    expect(xml).toContain('<loc>https://nicheiq.dev/ideas/b2b-saas</loc>');
    expect(xml).toContain('<loc>https://nicheiq.dev/ideas/saas</loc>');
    expect(xml).toContain('<loc>https://nicheiq.dev/ideas/saas/b2b-tools</loc>');
    // Detail pages are login-gated and intentionally excluded from the sitemap.
    expect(xml).not.toContain('<loc>https://nicheiq.dev/idea/idea-one-saas</loc>');
    expect(xml).not.toContain('<loc>https://nicheiq.dev/pain-point/pain-one-saas</loc>');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toContain('/api/public/catalog/sitemap');
  });
});
