import { describe, it, expect, vi, beforeEach } from 'vitest';

// $env virtual modules aren't auto-resolved under vitest (see sitemap test).
vi.mock('$env/dynamic/private', () => ({
  env: {
    BACKEND_URL: 'http://backend.test',
    INTERNAL_SERVICE_SECRET: 'test-secret',
    SEO_LAUNCH_GATE: 'false',
  },
}));
vi.mock('$env/dynamic/public', () => ({
  env: { PUBLIC_SITE_ORIGIN: 'https://nicheiq.dev' },
}));

const fetchMock = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', fetchMock);
});

function res(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

// Landing payload with TWO ideas + TWO pain points so we can prove the loader
// only ever returns one of each to the client.
function landingPayload() {
  return {
    category: {
      id: 'c1',
      name: 'AI Tools',
      slug: 'ai-tools',
      description: 'AI tooling',
      seoTitle: null,
      seoDescription: null,
      longDescription: 'A niche we actively track.',
      faqJson: null,
      tags: [],
      isActive: true,
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-05-01T00:00:00.000Z',
    },
    parent: null,
    superGroup: null,
    children: [],
    siblings: [],
    // The backend now returns the FEATURED-ONLY visible set (1 here), while the
    // totals reflect the full subtree. The loader passes the set through and
    // derives lockedCount = total − shown. (A would-be locked "idea-two"/"pain-two"
    // never leaves the backend, so it must not appear anywhere client-side.)
    topIdeas: [
      {
        slug: 'idea-one',
        solution_name: 'Idea One',
        created_at: '2026-01-02T00:00:00.000Z',
        updated_at: '2026-01-02T00:00:00.000Z',
        market_fit_score: 0.9,
        technical_feasibility_score: 0.8,
        seo_scalability_score: 0.7,
        source_verdict: 'GO',
        category: { name: 'AI Tools', slug: 'ai-tools' },
      },
    ],
    topPainPoints: [
      { slug: 'pain-one', title: 'Pain One', severityScore: 0.9, mentionCount: 100, createdAt: '2026-01-02T00:00:00.000Z' },
    ],
    totalIdeas: 2,
    totalPainPoints: 2,
    // Server-authoritative locked-pain count. The fixture represents a
    // non-entitled response where total=2 and visible=1, so the deficit is 1.
    lockedPainCount: 1,
    contentItemsMined: 120,
    sourceCommunities: 3,
    themes: null,
    audienceSegments: null,
    competitors: null,
    keywordClusters: null,
    subredditSources: null,
    nicheContext: null,
    audienceSignals: null,
    qualitySignals: null,
    verdictGoCount: 1,
    researchContext: null,
    researchSourceSubNiche: null,
    latestModifiedAt: '2026-05-01T00:00:00.000Z',
    sources: [],
  };
}

beforeEach(() => {
  fetchMock.mockImplementation((url: string) => {
    if (url.includes('/landing/')) return Promise.resolve(res(landingPayload()));
    if (url.includes('/collections')) return Promise.resolve(res({ collections: [] }));
    return Promise.resolve(res({}, 404));
  });
});

async function runLoad() {
  const { load } = await import('../+page.server');
  return (await load({
    params: { niche: 'ai-tools' },
    url: new URL('https://nicheiq.dev/ideas/ai-tools'),
    setHeaders: () => {},
  } as never)) as any;
}

describe('niche loader: featured-only passthrough + locked counts', () => {
  it('passes the backend featured-only set through and reports locked counts', async () => {
    const result = await runLoad();
    expect(result.kind).toBe('category');
    expect(result.payload.topIdeas).toHaveLength(1);
    expect(result.payload.topPainPoints).toHaveLength(1);
    expect(result.lockedIdeaCount).toBe(1);
    expect(result.lockedPainCount).toBe(1);
  });

  it('omits locked items and idea/pain ItemLists from JSON-LD', async () => {
    const result = await runLoad();
    const json = JSON.stringify(result.jsonld);
    // No locked slugs anywhere in structured data.
    expect(json).not.toContain('idea-two');
    expect(json).not.toContain('pain-two');
    // includeItemLists:false → no ItemList enumerating gated detail URLs.
    expect(json).not.toContain('ItemList');
    expect(json).not.toContain('/idea/');
    expect(json).not.toContain('/pain-point/');
  });
});
