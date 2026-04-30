/**
 * @vitest-environment node
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// Mock SvelteKit env before importing the module under test.
vi.mock('$env/dynamic/private', () => ({
  env: {
    BACKEND_URL: 'http://test-backend',
    INTERNAL_SERVICE_SECRET: 'test-secret',
  },
}));

import {
  isLegacyCatalogPath,
  resolveLegacyPath,
  __resetLegacyRedirectCache,
} from '$lib/server/legacy-redirects';

const fetchMock = vi.fn();
const HUB = '/ideas';

beforeEach(() => {
  __resetLegacyRedirectCache();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function ok(target: string | null) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ target }),
  } as unknown as Response;
}

describe('resolveLegacyPath — static paths', () => {
  it('only classifies /catalog and /catalog/* as legacy catalog paths', () => {
    expect(isLegacyCatalogPath('/catalog')).toBe(true);
    expect(isLegacyCatalogPath('/catalog/ideas')).toBe(true);
    expect(isLegacyCatalogPath('/catalogue')).toBe(false);
    expect(isLegacyCatalogPath('/catalogue/ideas')).toBe(false);
  });

  it('redirects /catalog → /ideas', async () => {
    const target = await resolveLegacyPath('/catalog', new URLSearchParams());
    expect(target).toBe(HUB);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('redirects /catalog/browse → /ideas', async () => {
    const target = await resolveLegacyPath('/catalog/browse', new URLSearchParams());
    expect(target).toBe(HUB);
  });

  it('redirects /catalog/ideas with no query → /ideas', async () => {
    const target = await resolveLegacyPath('/catalog/ideas', new URLSearchParams());
    expect(target).toBe(HUB);
  });

  it('redirects unknown /catalog/anything → /ideas (catch-all)', async () => {
    const target = await resolveLegacyPath('/catalog/random-junk', new URLSearchParams());
    expect(target).toBe(HUB);
  });
});

describe('resolveLegacyPath — listing with ?category= override', () => {
  it('looks up category and redirects to /ideas/{niche}', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas'));
    const target = await resolveLegacyPath(
      '/catalog/ideas',
      new URLSearchParams('category=saas'),
    );
    expect(target).toBe('/ideas/saas');
    expect(fetchMock).toHaveBeenCalledOnce();
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain('kind=category');
    expect(url).toContain('key=saas');
  });

  it('redirects to nested /ideas/{niche}/{sub} for child slug', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas/b2b-tools'));
    const target = await resolveLegacyPath(
      '/catalog/pain-points',
      new URLSearchParams('category=saas-b2b-tools'),
    );
    expect(target).toBe('/ideas/saas/b2b-tools');
  });

  it('falls through to hub when category unknown', async () => {
    fetchMock.mockResolvedValueOnce(ok(null));
    const target = await resolveLegacyPath(
      '/catalog/ideas',
      new URLSearchParams('category=unknown-slug'),
    );
    expect(target).toBe(HUB);
  });

  it('rejects non-slug category param without hitting backend', async () => {
    const target = await resolveLegacyPath(
      '/catalog/ideas',
      new URLSearchParams('category=Foo!Bar'),
    );
    expect(target).toBe(HUB);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('resolveLegacyPath — categories/[slug]', () => {
  it('redirects to top-level /ideas/{niche}', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas'));
    const target = await resolveLegacyPath('/catalog/categories/saas', new URLSearchParams());
    expect(target).toBe('/ideas/saas');
  });

  it('redirects to nested /ideas/{niche}/{sub}', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas/b2b-tools'));
    const target = await resolveLegacyPath(
      '/catalog/categories/saas-b2b-tools',
      new URLSearchParams(),
    );
    expect(target).toBe('/ideas/saas/b2b-tools');
  });

  it('handles trailing slash by normalizing', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas'));
    const target = await resolveLegacyPath('/catalog/categories/saas/', new URLSearchParams());
    expect(target).toBe('/ideas/saas');
  });

  it('handles uppercase by lowercasing', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas'));
    const target = await resolveLegacyPath('/CATALOG/CATEGORIES/SAAS', new URLSearchParams());
    expect(target).toBe('/ideas/saas');
  });
});

describe('resolveLegacyPath — ideas/[uuid] and pain-points/[uuid]', () => {
  it('redirects /catalog/ideas/<uuid> → /idea/<slug>', async () => {
    fetchMock.mockResolvedValueOnce(ok('/idea/ai-invoice-parser-saas'));
    const target = await resolveLegacyPath(
      '/catalog/ideas/12345678-1234-1234-1234-1234567890ab',
      new URLSearchParams(),
    );
    expect(target).toBe('/idea/ai-invoice-parser-saas');
  });

  it('redirects /catalog/pain-points/<uuid> → /pain-point/<slug>', async () => {
    fetchMock.mockResolvedValueOnce(ok('/pain-point/missing-tooling-saas'));
    const target = await resolveLegacyPath(
      '/catalog/pain-points/12345678-1234-1234-1234-1234567890ab',
      new URLSearchParams(),
    );
    expect(target).toBe('/pain-point/missing-tooling-saas');
  });

  it('redirects /catalog/ideas/<slug> → /idea/<slug>', async () => {
    fetchMock.mockResolvedValueOnce(ok('/idea/ai-invoice-parser-saas'));
    const target = await resolveLegacyPath(
      '/catalog/ideas/ai-invoice-parser-saas',
      new URLSearchParams(),
    );
    expect(target).toBe('/idea/ai-invoice-parser-saas');
  });

  it('redirects /catalog/pain-points/<slug> → /pain-point/<slug>', async () => {
    fetchMock.mockResolvedValueOnce(ok('/pain-point/missing-tooling-saas'));
    const target = await resolveLegacyPath(
      '/catalog/pain-points/missing-tooling-saas',
      new URLSearchParams(),
    );
    expect(target).toBe('/pain-point/missing-tooling-saas');
  });

  it('falls through to hub when slug unknown', async () => {
    fetchMock.mockResolvedValueOnce(ok(null));
    const target = await resolveLegacyPath(
      '/catalog/ideas/12345678-1234-1234-1234-1234567890ab',
      new URLSearchParams(),
    );
    expect(target).toBe(HUB);
  });
});

describe('resolveLegacyPath — failure modes', () => {
  it('falls through to hub on backend 500', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as unknown as Response);
    const target = await resolveLegacyPath('/catalog/categories/saas', new URLSearchParams());
    expect(target).toBe(HUB);
  });

  it('falls through to hub on backend exception', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network'));
    const target = await resolveLegacyPath('/catalog/categories/saas', new URLSearchParams());
    expect(target).toBe(HUB);
  });
});

describe('resolveLegacyPath — caching', () => {
  it('caches successful lookups (second call hits cache)', async () => {
    fetchMock.mockResolvedValueOnce(ok('/ideas/saas'));
    const t1 = await resolveLegacyPath('/catalog/categories/saas', new URLSearchParams());
    const t2 = await resolveLegacyPath('/catalog/categories/saas', new URLSearchParams());
    expect(t1).toBe('/ideas/saas');
    expect(t2).toBe('/ideas/saas');
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('caches negative lookups (no double-fetch on miss)', async () => {
    fetchMock.mockResolvedValueOnce(ok(null));
    const t1 = await resolveLegacyPath('/catalog/categories/unknown', new URLSearchParams());
    const t2 = await resolveLegacyPath('/catalog/categories/unknown', new URLSearchParams());
    expect(t1).toBe(HUB);
    expect(t2).toBe(HUB);
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
