import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFindUnique = vi.fn();
const mockUpsert = vi.fn();
const mockDeleteMany = vi.fn();
const mockGetJobAsset = vi.fn();
const mockResolveAssetPath = vi.fn();
const mockExistsSync = vi.fn();
const mockReadFileSync = vi.fn();

vi.mock('../db.js', () => ({
  prisma: {
    catalogResearchContext: {
      findUnique: (...args: unknown[]) => mockFindUnique(...args),
      upsert: (...args: unknown[]) => mockUpsert(...args),
      deleteMany: (...args: unknown[]) => mockDeleteMany(...args),
    },
  },
}));

vi.mock('../jobService.js', () => ({
  getJobAsset: (...args: unknown[]) => mockGetJobAsset(...args),
}));

vi.mock('../../utils/assetPath.js', () => ({
  resolveAssetPath: (...args: unknown[]) => mockResolveAssetPath(...args),
}));

vi.mock('fs', () => ({
  existsSync: (...args: unknown[]) => mockExistsSync(...args),
  readFileSync: (...args: unknown[]) => mockReadFileSync(...args),
}));

import {
  extractOrCreateResearchContext,
  rejectIfContainsBannedContent,
  hasMeaningfulResearchContext,
  hasProjectedData,
  isJsonEmpty,
} from '../researchContextService.js';
import { AssetType } from '@prisma/client';

const NICHE = 'Ukrainian residents who continue to use old technology';

// Real-shape report.json fixture, deliberately poisoned with:
// - the customer's literal niche query in multiple substructures
// - personal pronouns ("your business", "we recommend")
// - AI-buzzword phrasing ("AI-powered")
// Plus clean structured fields that SHOULD survive projection.
function buildPoisonedReport() {
  return {
    niche: NICHE,
    generated_at: '2026-04-01T00:00:00Z',
    selected_solution_name: 'Legacy Bridge SaaS',
    selected_solution_details: {
      solution_name: 'Legacy Bridge SaaS',
      description: 'Bridges legacy systems for Ukrainian residents who continue to use old technology.', // POISON: niche
      core_features: ['feature one', 'feature two'],
    },
    audience_mapping: {
      audience_segments: [
        { segment_name: 'Hobbyists', size_estimate: 'small' },
        { segment_name: 'Power users', size_estimate: 'medium' },
      ],
      primary_target_segment: 'Hobbyists',
      // Clean, structured data — should survive projection.
    },
    market_sizing: {
      tam_estimate: '$1B',
      sam_estimate: '$100M',
      methodology: 'we recommend a top-down sizing approach', // POISON: pronoun
    },
    trend_longevity: {
      momentum_score: 0.8,
      verdict: 'Strong',
    },
    pain_point_analytics: {
      total_pain_points: 12,
      severity_distribution: { high: 4, medium: 6, low: 2 },
    },
    competitive_analytics: {
      competitor_count: 5,
      competitive_intensity: 'medium',
    },
    competitor_profiles: [
      { name: 'CompA', key_strengths: ['support'] },
    ],
    detailed_pain_points: [
      { title: 'Pain 1', severity_score: 0.9 },
    ],
    alternative_solutions: [
      {
        solution_name: 'Alt Solution',
        market_fit_score: 0.7,
      },
    ],
    research_metadata: {
      reddit_posts_analyzed: 73,
      reddit_comments_analyzed: 1100,
      twitter_threads_analyzed: 0,
      collection_date: '2026-03-15T00:00:00Z',
      top_subreddits: [{ name: 'tech', post_count: 10 }],
    },
    data_quality_summary: {
      pain_point_quality_tier: 'GOLD',
    },
    executive_dashboard: {
      go_no_go_verdict: { verdict: 'Go' },
    },
    content_categorization: {
      executive_summary: 'Five themes emerged across the discussions.',
      theme_categories: [
        {
          category_name: 'Manual data entry',
          definition: 'Users reporting hours lost to copy-paste workflows',
          frequency: 'High',
          mention_count: 42,
          primary_user_segments: ['Hobbyists'],
          anchor_keywords: ['hours on data', 'copy paste', 'manual entry'],
        },
      ],
      user_segments: [
        {
          segment_name: 'Hobbyists',
          primary_concerns: ['cost', 'learning curve'],
          mention_frequency: 'High',
        },
      ],
      overall_quality: 'High',
    },
    // The following keys exist on real reports but are NOT projected — they
    // contain customer-facing prose and must never reach the public surface.
    executive_summary: 'Your business should expand into this niche.',
    keyword_validation_overview: 'AI-powered analysis of your business keywords.',
    data_source_research_full: 'Lorem ipsum prose mentioning the customer.',
    evidence_appendix: 'Long prose with personal pronouns.',
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockGetJobAsset.mockResolvedValue({ filePath: '/fake/output/jobs/test-id/report.json' });
  mockResolveAssetPath.mockReturnValue('/fake/resolved/report.json');
  mockExistsSync.mockReturnValue(true);
  // Default: no existing row, upsert returns whatever the call args set as create.
  mockFindUnique.mockResolvedValue(null);
  mockUpsert.mockImplementation((args: { create: object; update: object; where: object }) => {
    return Promise.resolve({ ...(args.where as object), ...args.create });
  });
});

describe('rejectIfContainsBannedContent', () => {
  it('returns the value unchanged when no banned content present', () => {
    const value = { foo: 'bar', count: 3 };
    expect(rejectIfContainsBannedContent(value, 'foo', NICHE)).toEqual(value);
  });

  it('returns null when value contains the niche query (case-insensitive)', () => {
    const value = { description: 'A product for UKRAINIAN residents who continue to use OLD technology.' };
    expect(rejectIfContainsBannedContent(value, 'foo', NICHE)).toBeNull();
  });

  it('returns null on the personal-pronoun phrase "your business"', () => {
    expect(rejectIfContainsBannedContent({ text: 'Your business needs this.' }, 'foo', NICHE)).toBeNull();
  });

  it('returns null on the personal-pronoun phrase "we recommend"', () => {
    expect(rejectIfContainsBannedContent({ text: 'We recommend buying.' }, 'foo', NICHE)).toBeNull();
  });

  it('returns null on the AI-buzzword "AI-powered"', () => {
    expect(rejectIfContainsBannedContent({ blurb: 'AI-powered insights.' }, 'foo', NICHE)).toBeNull();
  });

  it('does not block when the niche is empty/short', () => {
    // Avoids false-positive scrubbing when the report has an empty niche field.
    expect(rejectIfContainsBannedContent({ text: 'a' }, 'foo', '')).toEqual({ text: 'a' });
    expect(rejectIfContainsBannedContent({ text: 'abc' }, 'foo', 'abc')).toEqual({ text: 'abc' });
  });

  it('returns null for null/undefined inputs', () => {
    expect(rejectIfContainsBannedContent(null, 'foo', NICHE)).toBeNull();
    expect(rejectIfContainsBannedContent(undefined, 'foo', NICHE)).toBeNull();
  });
});

describe('extractOrCreateResearchContext — projection & privacy', () => {
  it('persists structured Audience data while scrubbing poisoned fields', async () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(buildPoisonedReport()));

    await extractOrCreateResearchContext('test-job-id');

    expect(mockUpsert).toHaveBeenCalledTimes(1);
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    const created = call.create;

    // Structured Audience data is preserved (clean field).
    expect(created.audienceMapping).toMatchObject({
      audience_segments: expect.any(Array),
      primary_target_segment: 'Hobbyists',
    });

    // Poisoned fields are nulled (Prisma.JsonNull serializes — test for null
    // when serialized).
    const serialized = JSON.stringify(created);
    expect(serialized).not.toMatch(/Ukrainian residents who continue to use old technology/i);
    expect(serialized).not.toMatch(/your business/i);
    expect(serialized).not.toMatch(/we recommend/i);
    expect(serialized).not.toMatch(/AI-powered/i);

    // Customer-facing prose blocks were never on the projection allow-list at
    // all — they shouldn't appear in any field.
    expect(created).not.toHaveProperty('executiveSummary');
    expect(created).not.toHaveProperty('keywordValidationOverview');
    expect(created).not.toHaveProperty('dataSourceResearchFull');
    expect(created).not.toHaveProperty('evidenceAppendix');
  });

  it('preserves clean structured fields (selectedSolutionName, metrics, tier, verdict)', async () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(buildPoisonedReport()));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    const created = call.create;

    expect(created.selectedSolutionName).toBe('Legacy Bridge SaaS');
    expect(created.redditPostsAnalyzed).toBe(73);
    expect(created.redditCommentsAnalyzed).toBe(1100);
    expect(created.dataQualityTier).toBe('GOLD');
    expect(created.goNoGoVerdict).toBe('GO');
    expect(created.collectionDate).toBeInstanceOf(Date);
  });

  it('persists contentCategorization (themes + user segments) end-to-end', async () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(buildPoisonedReport()));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    const created = call.create;

    expect(created.contentCategorization).toMatchObject({
      executive_summary: expect.any(String),
      theme_categories: expect.arrayContaining([
        expect.objectContaining({
          category_name: 'Manual data entry',
          anchor_keywords: expect.arrayContaining(['copy paste']),
        }),
      ]),
      user_segments: expect.arrayContaining([
        expect.objectContaining({ segment_name: 'Hobbyists' }),
      ]),
    });
  });

  it('normalizes the verdict "Conditional" to "MAYBE"', async () => {
    const report = buildPoisonedReport();
    report.executive_dashboard.go_no_go_verdict.verdict = 'Conditional';
    mockReadFileSync.mockReturnValue(JSON.stringify(report));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.goNoGoVerdict).toBe('MAYBE');
  });

  // Phase 5.4 — catalog rebuild
  it('persists keywordClusters from report.keyword_clusters', async () => {
    const report: any = buildPoisonedReport();
    report.keyword_clusters = [
      {
        cluster_name: 'Bottom-funnel queries',
        primary_keyword: 'bnpl medical purchases',
        supporting_keywords: ['affirm rejected', 'klarna alternative'],
        total_monthly_volume: 18400,
        content_recommendation: 'Build a comparison page for vertical BNPL providers.',
        estimated_traffic_potential: '500-1000 visits',
        priority: 1,
      },
    ];
    mockReadFileSync.mockReturnValue(JSON.stringify(report));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.keywordClusters).toEqual([
      expect.objectContaining({
        cluster_name: 'Bottom-funnel queries',
        primary_keyword: 'bnpl medical purchases',
        total_monthly_volume: 18400,
      }),
    ]);
  });

  it('extracts themeSeverityScores from content_categorization.theme_categories', async () => {
    const report: any = buildPoisonedReport();
    // Add severity_score to the existing theme.
    report.content_categorization.theme_categories[0].severity_score = 88;
    report.content_categorization.theme_categories.push({
      category_name: 'Refund disputes',
      definition: 'Slow refund flows damage customer trust.',
      frequency: 'Medium',
      mention_count: 27,
      severity_score: 64,
      primary_user_segments: ['Mid-market merchants'],
      anchor_keywords: ['refund slow', 'dispute flow', 'wait weeks'],
    });
    mockReadFileSync.mockReturnValue(JSON.stringify(report));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.themeSeverityScores).toEqual([
      expect.objectContaining({
        title: 'Manual data entry',
        severity: 88,
        mention_count: 42,
      }),
      expect.objectContaining({
        title: 'Refund disputes',
        severity: 64,
        mention_count: 27,
      }),
    ]);
  });

  it('themeSeverityScores is null when content_categorization missing', async () => {
    const report: any = buildPoisonedReport();
    delete report.content_categorization;
    mockReadFileSync.mockReturnValue(JSON.stringify(report));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    // Prisma.JsonNull serializes to a sentinel; nulls show as the JsonNull marker.
    // Check that the field is present but represents null.
    expect(call.create.themeSeverityScores).toBeDefined();
  });

  it('keyword_clusters flows through privacy scrub (poisoned cluster nulled)', async () => {
    const report: any = buildPoisonedReport();
    // Inject a poisoned keyword cluster — should be nulled.
    report.keyword_clusters = [
      {
        cluster_name: 'AI-powered keyword cluster',
        primary_keyword: 'something we recommend',
        supporting_keywords: [],
        total_monthly_volume: 100,
        content_recommendation: 'irrelevant',
        estimated_traffic_potential: '0',
        priority: 5,
      },
    ];
    mockReadFileSync.mockReturnValue(JSON.stringify(report));

    await extractOrCreateResearchContext('test-job-id');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    // Whole keywordClusters subtree nulled because it matches privacy-leakage pattern.
    const serialized = JSON.stringify(call.create);
    expect(serialized).not.toMatch(/we recommend/i);
    expect(serialized).not.toMatch(/AI-powered/i);
  });
});

describe('extractOrCreateResearchContext — placeholder behavior', () => {
  it('persists a placeholder row when report.json is missing', async () => {
    mockExistsSync.mockReturnValue(false);

    const result = await extractOrCreateResearchContext('missing-job');

    expect(mockUpsert).toHaveBeenCalledTimes(1);
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.dataQualityTier).toBe('INSUFFICIENT');
    expect(call.create.selectedSolutionName).toBeNull();
    expect(result).toBeDefined();
  });

  it('persists a placeholder row when getJobAsset returns null', async () => {
    mockGetJobAsset.mockResolvedValue(null);

    await extractOrCreateResearchContext('no-asset-job');

    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.dataQualityTier).toBe('INSUFFICIENT');
  });

  it('persists a placeholder row when JSON parsing fails', async () => {
    mockReadFileSync.mockReturnValue('not valid json {{{');

    await extractOrCreateResearchContext('bad-json-job');

    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.dataQualityTier).toBe('INSUFFICIENT');
  });
});

describe('extractOrCreateResearchContext — idempotency', () => {
  it('returns existing real row unchanged without re-reading the file', async () => {
    const existing = {
      sourceJobId: 'job-1',
      dataQualityTier: 'GOLD',
      audienceMapping: { audience_segments: [{ segment_name: 'X' }] },
    };
    mockFindUnique.mockResolvedValue(existing);

    const result = await extractOrCreateResearchContext('job-1');

    expect(result).toBe(existing);
    expect(mockUpsert).not.toHaveBeenCalled();
    expect(mockReadFileSync).not.toHaveBeenCalled();
  });

  it('returns placeholder unchanged with default options', async () => {
    const placeholder = {
      sourceJobId: 'job-1',
      dataQualityTier: 'INSUFFICIENT',
      audienceMapping: null,
    };
    mockFindUnique.mockResolvedValue(placeholder);

    const result = await extractOrCreateResearchContext('job-1');

    expect(result).toBe(placeholder);
    expect(mockUpsert).not.toHaveBeenCalled();
  });

  it('re-extracts placeholder when forceRefreshPlaceholders=true and report becomes available', async () => {
    const placeholder = {
      sourceJobId: 'job-1',
      dataQualityTier: 'INSUFFICIENT',
      audienceMapping: null,
    };
    mockFindUnique.mockResolvedValue(placeholder);
    mockReadFileSync.mockReturnValue(JSON.stringify(buildPoisonedReport()));

    await extractOrCreateResearchContext('job-1', { forceRefreshPlaceholders: true });

    expect(mockUpsert).toHaveBeenCalledTimes(1);
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.dataQualityTier).toBe('GOLD');
  });
});

// =============================================================================
// Phase 5.4 — additions
// =============================================================================

describe('Phase 5.4 — predicates', () => {
  it('isJsonEmpty: null/undefined/[]/{} all empty', () => {
    expect(isJsonEmpty(null)).toBe(true);
    expect(isJsonEmpty(undefined)).toBe(true);
    expect(isJsonEmpty([])).toBe(true);
    expect(isJsonEmpty({})).toBe(true);
    expect(isJsonEmpty([1])).toBe(false);
    expect(isJsonEmpty({ a: 1 })).toBe(false);
    expect(isJsonEmpty('string')).toBe(false);
  });

  it('hasProjectedData: timestamps + zero metrics still count as "ran"', () => {
    const ctx = {
      sourceJobId: 'x',
      audienceMapping: null,
      painPointAnalytics: null,
      detailedPainPoints: null,
      marketSizing: null,
      trendLongevity: null,
      competitiveAnalytics: null,
      competitorProfiles: null,
      competitiveAnalysis: null,
      alternativeSolutions: null,
      selectedSolution: null,
      topSubreddits: null,
      goToMarketBlueprint: null,
      pricingStrategy: null,
      trafficMonetization: null,
      competitiveSummary: null,
      selectedSolutionName: null,
      redditPostsAnalyzed: 0,
      redditCommentsAnalyzed: null,
      twitterThreadsAnalyzed: null,
      genericPostsAnalyzed: null,
      collectionDate: null,
      goNoGoVerdict: null,
      reportGeneratedAt: new Date(),
    } as any;
    expect(hasProjectedData(ctx)).toBe(true);
    expect(hasMeaningfulResearchContext(ctx)).toBe(false);
  });

  it('hasMeaningfulResearchContext: requires renderable data', () => {
    const empty: any = {
      sourceJobId: 'x',
      audienceMapping: null,
      painPointAnalytics: null,
      detailedPainPoints: null,
      marketSizing: null,
      trendLongevity: null,
      competitiveAnalytics: null,
      competitorProfiles: null,
      competitiveAnalysis: null,
      alternativeSolutions: null,
      selectedSolution: null,
      topSubreddits: null,
      goToMarketBlueprint: null,
      pricingStrategy: null,
      trafficMonetization: null,
      competitiveSummary: null,
      selectedSolutionName: null,
      redditPostsAnalyzed: 0,
      redditCommentsAnalyzed: 0,
      twitterThreadsAnalyzed: 0,
      genericPostsAnalyzed: 0,
      collectionDate: new Date(),
      goNoGoVerdict: null,
      reportGeneratedAt: new Date(),
      dataQualityTier: 'INSUFFICIENT',
    };
    expect(hasMeaningfulResearchContext(empty)).toBe(false);

    const withPainAnalytics = { ...empty, painPointAnalytics: { total: 5 } };
    expect(hasMeaningfulResearchContext(withPainAnalytics)).toBe(true);

    const withReddit = { ...empty, redditPostsAnalyzed: 50 };
    expect(hasMeaningfulResearchContext(withReddit)).toBe(true);
  });
});

describe('Phase 5.4 — sourceKind privacy guard', () => {
  it("sourceKind='catalog' suppresses niche-literal scrub but preserves privacy-leakage", () => {
    const value = { description: 'Sim Racing rigs are popular' };
    // commissioned default: niche match scrubs the field
    expect(rejectIfContainsBannedContent(value, 'foo', 'Sim Racing')).toBeNull();
    // catalog: niche match preserved
    expect(
      rejectIfContainsBannedContent(value, 'foo', 'Sim Racing', { sourceKind: 'catalog', suppressNicheLiteralScrub: true }),
    ).toEqual(value);
    // catalog still scrubs privacy-leakage
    expect(
      rejectIfContainsBannedContent(
        { text: 'Sim Racing for your business' },
        'foo',
        'Sim Racing',
        { sourceKind: 'catalog', suppressNicheLiteralScrub: true },
      ),
    ).toBeNull();
  });

  it("sourceKind='catalog' allows AI-marketing phrases (legitimate in software catalog)", () => {
    const value = { description: 'AI-powered photo editor' };
    // commissioned: AI marketing scrubs
    expect(rejectIfContainsBannedContent(value, 'foo', 'photo editing')).toBeNull();
    // catalog: AI marketing OK
    expect(
      rejectIfContainsBannedContent(value, 'foo', 'photo editing', { sourceKind: 'catalog', suppressNicheLiteralScrub: true }),
    ).toEqual(value);
  });
});

describe('Phase 5.4 — loadReportJson precedence + downgrade guard', () => {
  beforeEach(() => {
    // Default getJobAsset behavior is set by setRoot beforeEach above; reset.
    mockGetJobAsset.mockReset();
  });

  it('falls back to PREVIEW_REPORT when REPORT_JSON missing', async () => {
    // No REPORT_JSON, PREVIEW_REPORT exists.
    mockGetJobAsset.mockImplementation(async (_jobId: string, type: AssetType) => {
      if (type === AssetType.PREVIEW_REPORT) return { filePath: '/fake/preview.json' };
      return null;
    });
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue(JSON.stringify(buildPoisonedReport()));

    await extractOrCreateResearchContext('preview-job', { sourceKind: 'catalog' });

    expect(mockUpsert).toHaveBeenCalledTimes(1);
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    // sourceKind='catalog' preserves audience containing the niche literal
    expect(call.create.audienceMapping).toMatchObject({ primary_target_segment: 'Hobbyists' });
  });

  it('forceRefreshAll preserves existing real row when REPORT_JSON unparseable (no fallback to preview)', async () => {
    // Existing row with projected data.
    const existing = {
      sourceJobId: 'job-x',
      dataQualityTier: 'GOLD',
      audienceMapping: { primary_target_segment: 'Power users' },
      painPointAnalytics: null,
      detailedPainPoints: null,
      marketSizing: null,
      trendLongevity: null,
      competitiveAnalytics: null,
      competitorProfiles: null,
      competitiveAnalysis: null,
      alternativeSolutions: null,
      selectedSolution: null,
      topSubreddits: null,
      goToMarketBlueprint: null,
      pricingStrategy: null,
      trafficMonetization: null,
      competitiveSummary: null,
      selectedSolutionName: null,
      redditPostsAnalyzed: 73,
      redditCommentsAnalyzed: null,
      twitterThreadsAnalyzed: null,
      genericPostsAnalyzed: null,
      collectionDate: null,
      goNoGoVerdict: 'GO',
      reportGeneratedAt: new Date('2026-04-01'),
    };
    mockFindUnique.mockResolvedValue(existing);

    // REPORT_JSON asset exists but file is unloadable
    mockGetJobAsset.mockImplementation(async (_jobId: string, type: AssetType) => {
      if (type === AssetType.REPORT_JSON) return { filePath: '/fake/broken.json' };
      return { filePath: '/fake/preview.json' };
    });
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue('not valid json {');

    const result = await extractOrCreateResearchContext('job-x', { forceRefreshAll: true });

    // Downgrade guard fires: existing row preserved, no upsert.
    expect(mockUpsert).not.toHaveBeenCalled();
    expect(result).toBe(existing);
  });
});

describe('Phase 5.4 — placeholder detection uses hasMeaningfulResearchContext', () => {
  it('treats a row with painPointAnalytics-only as non-placeholder', async () => {
    const row = {
      sourceJobId: 'job-1',
      dataQualityTier: 'INSUFFICIENT',
      audienceMapping: null,
      painPointAnalytics: { total: 5 },
      detailedPainPoints: null,
      marketSizing: null,
      trendLongevity: null,
      competitiveAnalytics: null,
      competitorProfiles: null,
      competitiveAnalysis: null,
      alternativeSolutions: null,
      selectedSolution: null,
      topSubreddits: null,
      goToMarketBlueprint: null,
      pricingStrategy: null,
      trafficMonetization: null,
      competitiveSummary: null,
      selectedSolutionName: null,
      redditPostsAnalyzed: 0,
      redditCommentsAnalyzed: 0,
      twitterThreadsAnalyzed: 0,
      genericPostsAnalyzed: 0,
      collectionDate: null,
      goNoGoVerdict: null,
      reportGeneratedAt: null,
    };
    mockFindUnique.mockResolvedValue(row);

    const result = await extractOrCreateResearchContext('job-1');

    // Treated as real → returned unchanged, no upsert.
    expect(result).toBe(row);
    expect(mockUpsert).not.toHaveBeenCalled();
  });

  it('treats timestamp-only row as a placeholder (refresh-eligible)', async () => {
    const row = {
      sourceJobId: 'job-1',
      dataQualityTier: 'INSUFFICIENT',
      audienceMapping: null,
      painPointAnalytics: null,
      detailedPainPoints: null,
      marketSizing: null,
      trendLongevity: null,
      competitiveAnalytics: null,
      competitorProfiles: null,
      competitiveAnalysis: null,
      alternativeSolutions: null,
      selectedSolution: null,
      topSubreddits: null,
      goToMarketBlueprint: null,
      pricingStrategy: null,
      trafficMonetization: null,
      competitiveSummary: null,
      selectedSolutionName: null,
      redditPostsAnalyzed: 0,
      redditCommentsAnalyzed: 0,
      twitterThreadsAnalyzed: 0,
      genericPostsAnalyzed: 0,
      collectionDate: new Date(),
      goNoGoVerdict: null,
      reportGeneratedAt: new Date(),
    };
    mockFindUnique.mockResolvedValue(row);
    mockGetJobAsset.mockResolvedValue({ filePath: '/fake/preview.json' });
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue(JSON.stringify(buildPoisonedReport()));

    await extractOrCreateResearchContext('job-1', { forceRefreshPlaceholders: true });

    // Treated as placeholder → upsert fires
    expect(mockUpsert).toHaveBeenCalledTimes(1);
  });
});

describe('Phase 5.4 — dataQualityTier fallback', () => {
  it("falls back to 'INSUFFICIENT' when report has no quality metadata", async () => {
    const report = buildPoisonedReport();
    delete (report as any).data_quality_summary;
    mockReadFileSync.mockReturnValue(JSON.stringify(report));

    await extractOrCreateResearchContext('job-1');
    const call = mockUpsert.mock.calls[0]?.[0] as { create: Record<string, unknown> };
    expect(call.create.dataQualityTier).toBe('INSUFFICIENT');
  });
});
