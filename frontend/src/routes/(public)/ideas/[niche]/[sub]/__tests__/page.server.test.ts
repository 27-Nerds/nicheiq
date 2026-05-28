import { describe, it, expect, vi, beforeEach } from 'vitest';

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

// Two ideas, BOTH 'GO', and verdictGoCount intentionally omitted so we can prove
// the GO-count fallback is computed BEFORE the topIdeas array is trimmed.
function landingPayload() {
  return {
    category: {
      id: 'c2',
      name: 'LLM Tools',
      slug: 'llm-tools',
      description: 'LLM tooling',
      seoTitle: null,
      seoDescription: null,
      longDescription: 'A sub-niche we actively track.',
      faqJson: null,
      tags: [],
      isActive: true,
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-05-01T00:00:00.000Z',
    },
    parent: { id: 'c1', name: 'AI Tools', slug: 'ai-tools' },
    superGroup: null,
    children: [],
    siblings: [],
    // Backend returns the featured-only visible set (1 idea / 1 pain here); totals
    // and verdictGoCount reflect the full subtree.
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
        category: { name: 'LLM Tools', slug: 'llm-tools' },
      },
    ],
    topPainPoints: [
      { slug: 'pain-one', title: 'Pain One', severityScore: 0.9, mentionCount: 100, createdAt: '2026-01-02T00:00:00.000Z' },
    ],
    totalIdeas: 2,
    totalPainPoints: 2,
    // Server-authoritative locked-pain count. For a non-entitled response on
    // a leaf, this equals totalPainPoints - topPainPoints.length.
    lockedPainCount: 1,
    contentItemsMined: 80,
    sourceCommunities: 2,
    themes: null,
    audienceSegments: null,
    competitors: null,
    keywordClusters: null,
    subredditSources: null,
    nicheContext: null,
    audienceSignals: null,
    qualitySignals: null,
    // Backend aggregate GO-count across the full subtree (independent of the
    // featured-only visible set).
    verdictGoCount: 2,
    researchContext: null,
    researchSourceSubNiche: null,
    latestModifiedAt: '2026-05-01T00:00:00.000Z',
    sources: [],
  };
}

beforeEach(() => {
  fetchMock.mockImplementation((url: string) => {
    if (url.includes('/landing/')) return Promise.resolve(res(landingPayload()));
    return Promise.resolve(res({}, 404));
  });
});

async function runLoad() {
  const { load } = await import('../+page.server');
  return (await load({
    params: { niche: 'ai-tools', sub: 'llm-tools' },
    url: new URL('https://nicheiq.dev/ideas/ai-tools/llm-tools'),
    setHeaders: () => {},
  } as never)) as any;
}

describe('sub-niche loader redacts locked catalog items', () => {
  it('trims to one idea/pain and reports locked counts', async () => {
    const result = await runLoad();
    expect(result.payload.topIdeas).toHaveLength(1);
    expect(result.payload.topPainPoints).toHaveLength(1);
    expect(result.lockedIdeaCount).toBe(1);
    expect(result.lockedPainCount).toBe(1);
  });

  it('uses the backend aggregate verdictGoCount (not the visible set)', async () => {
    const result = await runLoad();
    // verdictGoCount=2 across the subtree even though only 1 idea is visible.
    expect(result.goCount).toBe(2);
  });

  it('omits locked items and idea/pain ItemLists from JSON-LD', async () => {
    const result = await runLoad();
    const json = JSON.stringify(result.jsonld);
    expect(json).not.toContain('idea-two');
    expect(json).not.toContain('pain-two');
    expect(json).not.toContain('ItemList');
    expect(json).not.toContain('/idea/');
    expect(json).not.toContain('/pain-point/');
  });
});
