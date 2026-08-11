/**
 * Finding D2 on the public share URL.
 *
 * The share serves the LIVE candidate pool (`share.job.solutionIdeas`) beside a preview
 * snapshot that belongs to whatever pool the run last produced. Before this test the two
 * were shipped together with no version and no fingerprint check, so a summary written
 * against 6 ideas could steer a stranger's vote on a 12-idea pool. The owner-side
 * boundary (loadCurrentSelectionContext) already refuses that pairing; the share must
 * refuse it in the same states.
 */
import { readFileSync } from 'node:fs';
import express, { type Express } from 'express';
import request from 'supertest';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ideaPortfolioFingerprint } from '../../utils/ideaPortfolioFingerprint.js';
import {
  applyPreviewFieldAllowlist,
  NESTED_FIELD_SCOPE,
  PREVIEW_FIELD_SCOPE,
} from '../schemas/sharedDiscoveryPayload.js';
import previewReportTopLevelKeys from './fixtures/previewReportTopLevelKeys.json' with { type: 'json' };
import previewReportNestedKeys from './fixtures/previewReportNestedKeys.json' with { type: 'json' };

/**
 * The fingerprint cases are NOT written here. They live once, in
 * `contracts/ideaPortfolioFingerprintCases.json`, read by this suite, by
 * `frontend/src/lib/selection/__tests__/ideaPortfolioFingerprint.test.ts` and by
 * `tests/unit/test_idea_portfolio_summary.py`. Three copy-pasted tables meant a lockstep
 * edit to one implementation and its own table left the other two undetected — and Python,
 * the implementation that WRITES the stored fingerprint, was held to none of the cases.
 */
type SharedFingerprintCase = {
  name: string;
  candidates: Array<Record<string, unknown> | null>;
  fingerprint: string | null;
};
type DivergentFingerprintCase = {
  name: string;
  candidates: Array<Record<string, unknown> | null>;
  fingerprint: { python: string | null; typescript: string | null };
};
const FINGERPRINT_CONTRACT = JSON.parse(
  readFileSync(
    new URL('../../../../contracts/ideaPortfolioFingerprintCases.json', import.meta.url),
    'utf8',
  ),
) as { shared: SharedFingerprintCase[]; divergences: DivergentFingerprintCase[] };

const shareToken = 'b'.repeat(22);
const jobId = '00000000-0000-0000-0000-0000000000d2';

const mockShareFindUnique = vi.fn();
const mockShareUpdate = vi.fn();
const mockGetPreviewReport = vi.fn();
const mockJobAssetFindUnique = vi.fn();

vi.mock('../../services/db.js', () => ({
  prisma: {
    discoveryShare: {
      findUnique: (...args: any[]) => mockShareFindUnique(...args),
      update: (...args: any[]) => mockShareUpdate(...args),
    },
    discoveryVote: {
      groupBy: vi.fn().mockResolvedValue([]),
      count: vi.fn().mockResolvedValue(0),
      findMany: vi.fn().mockResolvedValue([]),
    },
    jobAsset: {
      findUnique: (...args: any[]) => mockJobAssetFindUnique(...args),
    },
    jobProgress: { findMany: vi.fn().mockResolvedValue([]) },
  },
}));

vi.mock('../../services/assetService.js', () => ({
  getDiscoveryDataForJob: vi.fn().mockResolvedValue(null),
}));
vi.mock('../../services/selectionBoundary/rawPreviewReport.js', () => ({
  getPreviewReportForJob: (...args: any[]) => mockGetPreviewReport(...args),
}));
vi.mock('../../services/jobService.js', () => ({ getJob: vi.fn().mockResolvedValue(null) }));
vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (_req: any, _res: any, next: any) => next(),
  verifyOwnership: () => true,
  AuthenticatedRequest: {},
}));
vi.mock('../../config.js', () => ({
  CONFIG: { nodeEnv: 'test', ipHashSalt: 'test-salt' },
}));
vi.mock('express-rate-limit', () => ({
  default: () => (_req: any, _res: any, next: any) => next(),
}));

/** Six ideas: the pool the analyst summary was written against. */
const ORIGINAL_POOL = Array.from({ length: 6 }, (_, index) => ({
  solution_name: `Idea ${index + 1}`,
  idea_id: `idea-${index + 1}`,
  idea_revision: 1,
  description: `Concept ${index + 1}`,
  value_proposition: 'Saves a manual pass',
}));

/** Twelve ideas: the pool a visitor actually votes on after a regenerate batch landed. */
const GROWN_POOL = Array.from({ length: 12 }, (_, index) => ({
  solution_name: `Idea ${index + 1}`,
  idea_id: `idea-${index + 1}`,
  idea_revision: 1,
  description: `Concept ${index + 1}`,
  value_proposition: 'Saves a manual pass',
}));

const STALE_SUMMARY = 'Idea 1 and Idea 5 most deserve deeper validation.';

function previewReport(pool: Array<Record<string, unknown>>) {
  return {
    niche: 'appliance repair shops',
    generated_at: '2026-08-01T00:00:00.000Z',
    idea_portfolio_summary: STALE_SUMMARY,
    idea_portfolio_summary_fingerprint: ideaPortfolioFingerprint(pool),
    overlap_groups: [{ group_id: 'g1', member_idea_ids: ['idea-1', 'idea-5'] }],
    idea_theses: { theses: [], uncovered_families: [] },
    examined_ruled_out: [{ idea_name: 'Ruled out concept' }],
    // The full ranked snapshot the pipeline writes unconditionally
    // (research_flow.py `report["alternative_solutions"]`): scores, verdicts, statuses.
    alternative_solutions: pool.map((idea, index) => ({
      ...idea,
      market_fit_score: (60 - index) / 100,
      red_team_verdict: 'conditional',
      candidate_status: 'active',
      winning_angle: 'workflow',
    })),
    // quality_caveats carries per-idea calibration notes in real assets.
    data_quality_summary: {
      quality_caveats: [
        'Thin weekend coverage',
        `Calibration note for "${pool[0]?.solution_name}" cites an unverified data route.`,
      ],
    },
    // Niche-scoped framing: true of the market regardless of which ideas exist.
    market_reality: { headline: 'Fragmented, low-tooling market' },
    niche_difficulty_verdict: {
      headline: 'Software Fit: Strong',
      // Pool-scoped notice nested in a niche-scoped verdict: it describes the
      // recommendation, which _refresh_recommendation_audience_drift derives from the
      // recommended candidates.
      audience_drift_notice: {
        requested_audience: 'independent repair shops',
        message: 'the recommendation is built for “franchise service managers”',
      },
    },
    research_metadata: {
      reddit_posts_analyzed: 240,
      // Pool-scoped count nested inside niche-scoped operational metadata.
      funnel_counts: { pains_identified: 20, candidates_shown: pool.length },
    },
  };
}

function share(
  pool: Array<Record<string, unknown>>,
  {
    status = 'AWAITING_SELECTION',
    candidatePoolVersion = null,
  }: { status?: string; candidatePoolVersion?: number | null } = {},
) {
  return {
    id: 'share-d2',
    jobId,
    isActive: true,
    allowIndexing: false,
    job: {
      id: jobId,
      niche: 'appliance repair shops',
      status,
      activeDispatchId: null,
      dispatches: [],
      solutionIdeas: pool,
      candidatePoolVersion,
    },
  };
}

let app: Express;

beforeEach(async () => {
  vi.clearAllMocks();
  mockShareUpdate.mockResolvedValue({});
  // Default: no PREVIEW_REPORT asset row version recorded — the legacy path.
  mockJobAssetFindUnique.mockResolvedValue(null);
  app = express();
  app.use(express.json());
  const { publicDiscoveryShareRouter } = await import('../discoveryShares.js');
  app.use('/api/shared/discovery', publicDiscoveryShareRouter);
});

describe('public discovery share — pool-scoped guidance is bound to the pool it describes', () => {
  it('pins the fingerprint contract to the literal the frontend asserts against', () => {
    // The job-page test in frontend/src/routes/(app)/jobs/[jobId]/__tests__/
    // portfolioSummary.test.ts hard-codes this string. Both ends fail together if the
    // contract moves, instead of quietly agreeing on a re-implemented hash.
    expect(ideaPortfolioFingerprint([
      { solution_name: 'Alpha Idea', idea_id: 'idea-alpha', idea_revision: 1 },
      { solution_name: 'Beta Idea', idea_id: 'idea-beta', idea_revision: 1 },
    ])).toBe('{"version":1,"ideas":[["idea-alpha",1],["idea-beta",1]]}');
  });

  it('reads the same case file the frontend and Python suites read', () => {
    expect(FINGERPRINT_CONTRACT.shared.length).toBeGreaterThanOrEqual(11);
    expect(FINGERPRINT_CONTRACT.divergences.length).toBeGreaterThanOrEqual(2);
  });

  it.each(FINGERPRINT_CONTRACT.shared)(
    // The same file drives the frontend authority in
    // frontend/src/lib/selection/__tests__/ideaPortfolioFingerprint.test.ts and Python's
    // TestPortfolioFingerprintContract; a rule that moves on one side fails on all three.
    'shared contract case: $name',
    ({ candidates, fingerprint }) => {
      expect(ideaPortfolioFingerprint(candidates)).toBe(fingerprint);
    },
  );

  it.each(FINGERPRINT_CONTRACT.divergences)(
    // Documented, non-blocking, and pinned so nobody "fixes" one silently. See the
    // `verdict` field on each case in the contract file.
    'known divergence from Python: $name',
    ({ candidates, fingerprint }) => {
      expect(ideaPortfolioFingerprint(candidates)).toBe(fingerprint.typescript);
    },
  );

  it('withholds a 6-idea summary from the 12-idea pool a visitor votes on', async () => {
    mockShareFindUnique.mockResolvedValue(share(GROWN_POOL));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.solutions).toHaveLength(12);
    expect(response.body.previewReport).not.toHaveProperty('idea_portfolio_summary');
    expect(response.body.previewReport).not.toHaveProperty('idea_portfolio_summary_fingerprint');
    expect(response.body.previewReport).not.toHaveProperty('overlap_groups');
    expect(response.body.previewReport).not.toHaveProperty('idea_theses');
    expect(response.body.previewReport).not.toHaveProperty('examined_ruled_out');
    expect(response.body.evidenceFramingWithheld).toBe(true);
    // The stale prose must not survive anywhere in the payload, not merely go unrendered.
    expect(JSON.stringify(response.body)).not.toContain(STALE_SUMMARY);
    // Niche-scoped framing is not a claim about the candidate list, so it stays.
    expect(response.body.previewReport.market_reality).toEqual({
      headline: 'Fragmented, low-tooling market',
    });
  });

  it('withholds the ranked snapshot and the stale candidate count, not just the prose', async () => {
    // `evidenceFramingWithheld: true` has to be a true statement about the whole payload.
    // Before the classification inversion the response still carried a full 6-idea ranked
    // list with scores and verdicts, plus funnel_counts.candidates_shown = 6, beside the
    // 12 solutions the visitor was voting on.
    mockShareFindUnique.mockResolvedValue(share(GROWN_POOL));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.solutions).toHaveLength(12);
    expect(response.body.previewReport).not.toHaveProperty('alternative_solutions');
    expect(response.body.previewReport).not.toHaveProperty('data_quality_summary');
    expect(response.body.previewReport.research_metadata).toEqual({
      reddit_posts_analyzed: 240,
    });
    expect(response.body.previewReport.niche_difficulty_verdict).toEqual({
      headline: 'Software Fit: Strong',
    });
    // Nothing pool-scoped survives ANYWHERE, by classification rather than by name list.
    for (const key of Object.keys(response.body.previewReport)) {
      expect(PREVIEW_FIELD_SCOPE.get(key)).toBe('niche');
    }
  });

  it('serves the guidance when it still describes the pool being voted on', async () => {
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport.idea_portfolio_summary).toBe(STALE_SUMMARY);
    expect(response.body.previewReport.idea_portfolio_summary_fingerprint)
      .toBe(ideaPortfolioFingerprint(ORIGINAL_POOL));
    expect(response.body.previewReport.overlap_groups).toHaveLength(1);
    expect(response.body.previewReport.alternative_solutions).toHaveLength(6);
    expect(response.body.previewReport.research_metadata.funnel_counts.candidates_shown).toBe(6);
    expect(response.body.previewReport.niche_difficulty_verdict.audience_drift_notice)
      .toBeDefined();
    expect(response.body.evidenceFramingWithheld).toBe(false);
  });

  it('drops an unclassified upstream field while the pool is current', async () => {
    // The classification used to run only on the withheld branch, so a field added upstream
    // shipped publicly whenever the pool happened to be current — the one state where
    // nothing else was being withheld and nobody was looking.
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL));
    mockGetPreviewReport.mockResolvedValue({
      ...previewReport(ORIGINAL_POOL),
      brand_new_upstream_field_2027: [{ idea_id: 'idea-1', rank: 1 }],
    });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.evidenceFramingWithheld).toBe(false);
    expect(response.body.previewReport).not.toHaveProperty('brand_new_upstream_field_2027');
    expect(JSON.stringify(response.body)).not.toContain('brand_new_upstream_field_2027');
    // Serving is still the point of this branch: the pool-scoped guidance survives.
    expect(response.body.previewReport.idea_portfolio_summary).toBe(STALE_SUMMARY);
    // Every served key is classified, on this branch as much as on the withheld one.
    for (const key of Object.keys(response.body.previewReport)) {
      expect(PREVIEW_FIELD_SCOPE.get(key)).toBeDefined();
    }
  });

  it('drops an unclassified upstream field while the pool is stale', async () => {
    mockShareFindUnique.mockResolvedValue(share(GROWN_POOL));
    mockGetPreviewReport.mockResolvedValue({
      ...previewReport(ORIGINAL_POOL),
      brand_new_upstream_field_2027: [{ idea_id: 'idea-1', rank: 1 }],
    });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.evidenceFramingWithheld).toBe(true);
    expect(JSON.stringify(response.body)).not.toContain('brand_new_upstream_field_2027');
  });

  it.each(['serve', 'withhold'] as const)(
    // R1: the top-level allowlist was total, but the nested layer was three hand-written
    // pool-scoped names — the denylist shape one level down. A brand-new nested key shipped
    // on BOTH dispositions, and the producer-side {text, scope} change queued upstream does
    // not cover a key nobody has classified.
    'drops an unclassified NESTED field on the %s disposition',
    async (disposition) => {
      const pool = disposition === 'serve' ? ORIGINAL_POOL : GROWN_POOL;
      const report = previewReport(ORIGINAL_POOL) as Record<string, any>;
      report.research_metadata.NESTED_UNCLASSIFIED_LEAK = { candidates_ranked: 6 };
      mockShareFindUnique.mockResolvedValue(share(pool));
      mockGetPreviewReport.mockResolvedValue(report);

      const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

      expect(response.status).toBe(200);
      expect(response.body.evidenceFramingWithheld).toBe(disposition === 'withhold');
      expect(response.body.previewReport.research_metadata)
        .not.toHaveProperty('NESTED_UNCLASSIFIED_LEAK');
      expect(JSON.stringify(response.body)).not.toContain('NESTED_UNCLASSIFIED_LEAK');
      // Every surviving nested key of every classified container is classified too.
      for (const [container, scopes] of NESTED_FIELD_SCOPE) {
        const value = response.body.previewReport[container];
        if (value === null || typeof value !== 'object') continue;
        for (const key of Object.keys(value)) {
          expect(scopes.get(key)).toBeDefined();
        }
      }
    },
  );

  it('keeps every classified nested key on the serve path — no over-blocking', async () => {
    // The other half of the nested allowlist: failing closed is only correct if it does not
    // also blank the real payload. Both niche-scoped siblings and the pool-scoped
    // funnel_counts survive while the pool is the one the snapshot describes.
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.body.previewReport.research_metadata).toEqual({
      reddit_posts_analyzed: 240,
      funnel_counts: { pains_identified: 20, candidates_shown: 6 },
    });
    expect(response.body.previewReport.niche_difficulty_verdict).toEqual({
      headline: 'Software Fit: Strong',
      audience_drift_notice: {
        requested_audience: 'independent repair shops',
        message: 'the recommendation is built for “franchise service managers”',
      },
    });
  });

  it('fails closed on a legacy report that carries no fingerprint at all', async () => {
    const legacy = previewReport(ORIGINAL_POOL) as Record<string, unknown>;
    delete legacy.idea_portfolio_summary_fingerprint;
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL));
    mockGetPreviewReport.mockResolvedValue(legacy);

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport).not.toHaveProperty('idea_portfolio_summary');
    expect(response.body.evidenceFramingWithheld).toBe(true);
  });

  it('withholds while the pool is mid-regeneration, matching the owner-side boundary', async () => {
    // REGENERATING keeps the share open (discoveryShareLifecycle), and the fingerprint
    // still matches until the new batch lands. The owner sees no framing in this state,
    // so neither may a visitor.
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL, { status: 'REGENERATING' }));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.solutions).toHaveLength(6);
    expect(response.body.previewReport).not.toHaveProperty('idea_portfolio_summary');
    expect(response.body.evidenceFramingWithheld).toBe(true);
  });

  it('withholds when the job and its preview asset name different pool versions', async () => {
    // The supplementary binding loadCurrentSelectionContext enforces (checks 3, 4 and 9).
    // The fingerprint still matches here — a rewritten snapshot for a mutated pool can —
    // so the version pair is the only thing that catches it.
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL, { candidatePoolVersion: 4 }));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));
    mockJobAssetFindUnique.mockResolvedValue({ candidatePoolVersion: 3 });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport).not.toHaveProperty('idea_portfolio_summary');
    expect(response.body.evidenceFramingWithheld).toBe(true);
    expect(mockJobAssetFindUnique).toHaveBeenCalledWith({
      where: { jobId_assetType: { jobId, assetType: 'PREVIEW_REPORT' } },
      select: { candidatePoolVersion: true },
    });
  });

  it('serves when the job and its preview asset agree on the pool version', async () => {
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL, { candidatePoolVersion: 4 }));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));
    mockJobAssetFindUnique.mockResolvedValue({ candidatePoolVersion: 4 });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport.idea_portfolio_summary).toBe(STALE_SUMMARY);
    expect(response.body.evidenceFramingWithheld).toBe(false);
  });

  it('keeps serving legacy shares whose Job row has no pool version yet', async () => {
    // Migration 20260809180000 leaves Job.candidatePoolVersion NULL until the next
    // solutionIdeas write. Failing closed on a null would blank every pre-deploy share
    // the moment the migration lands — publicly.
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL, { candidatePoolVersion: null }));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));
    mockJobAssetFindUnique.mockResolvedValue({ candidatePoolVersion: 7 });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport.idea_portfolio_summary).toBe(STALE_SUMMARY);
    expect(response.body.evidenceFramingWithheld).toBe(false);
    // A null on the Job side is decided without a second query.
    expect(mockJobAssetFindUnique).not.toHaveBeenCalled();
  });

  it('keeps serving legacy shares whose preview asset has no pool version yet', async () => {
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL, { candidatePoolVersion: 4 }));
    mockGetPreviewReport.mockResolvedValue(previewReport(ORIGINAL_POOL));
    mockJobAssetFindUnique.mockResolvedValue({ candidatePoolVersion: null });

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport.idea_portfolio_summary).toBe(STALE_SUMMARY);
    expect(response.body.evidenceFramingWithheld).toBe(false);
  });

  it('reports nothing withheld when the run produced no preview at all', async () => {
    mockShareFindUnique.mockResolvedValue(share(ORIGINAL_POOL));
    mockGetPreviewReport.mockResolvedValue(null);

    const response = await request(app).get(`/api/shared/discovery/${shareToken}`);

    expect(response.status).toBe(200);
    expect(response.body.previewReport).toBeNull();
    expect(response.body.evidenceFramingWithheld).toBe(false);
  });
});

/**
 * A five-name denylist is structurally the same fragility as a phrase blacklist: the next
 * pool-scoped field leaks by omission. The boundary is inverted instead — every top-level
 * key is classified and only `niche` is served — and this suite is what keeps the
 * classification total as the pipeline grows.
 *
 * The fixture is the real key universe of the PREVIEW_REPORT asset from two independent
 * sources (60 real assets under output/checkpoints/, and the `report["<key>"] = ...`
 * assignments in ResearchFlow._materialize_preview_report). See its `_source` field.
 */
describe('preview-report field classification is total', () => {
  it('classifies every top-level key the preview-report writer produces', () => {
    const unclassified = Object.keys(previewReportTopLevelKeys.keys)
      .filter((key) => PREVIEW_FIELD_SCOPE.get(key) === undefined);

    expect(unclassified).toEqual([]);
  });

  it('withholds an unclassified field instead of assuming it is safe', () => {
    const served = applyPreviewFieldAllowlist({
      niche: 'appliance repair shops',
      // A field this boundary has never reasoned about — the shape every future
      // pool-scoped addition arrives in.
      some_future_field: [{ idea_id: 'idea-1', rank: 1 }],
    }, 'withhold');

    expect(served).toEqual({ niche: 'appliance repair shops' });
  });

  it('withholds an unclassified field on the serve disposition too', () => {
    // A current pool is evidence about the classified pool-scoped fields. It is no
    // evidence at all about a key nobody has classified, so `serve` may not widen the
    // allowlist — otherwise the contract this file's header states holds on one branch.
    const served = applyPreviewFieldAllowlist({
      niche: 'appliance repair shops',
      idea_portfolio_summary: 'Idea 1 and Idea 5 most deserve deeper validation.',
      some_future_field: [{ idea_id: 'idea-1', rank: 1 }],
    }, 'serve');

    expect(served).toEqual({
      niche: 'appliance repair shops',
      idea_portfolio_summary: 'Idea 1 and Idea 5 most deserve deeper validation.',
    });
  });

  it('does not treat inherited Object properties as classified', () => {
    for (const disposition of ['withhold', 'serve'] as const) {
      const served = applyPreviewFieldAllowlist({
        niche: 'appliance repair shops',
        constructor: 'not a classification',
        toString: 'not a classification',
      }, disposition);

      expect(served).toEqual({ niche: 'appliance repair shops' });
    }
  });
});

/**
 * R1: the nested layer used to be three hand-written pool-scoped names — structurally the
 * denylist the top level had already replaced. `NESTED_FIELD_SCOPE` is an allowlist with
 * the same rule, and this suite keeps it total for the containers it covers.
 *
 * The nested key universe comes from the same two independent sources as the top-level
 * fixture: the 60 real PREVIEW_REPORT assets and the writer (the dict literal in
 * `_materialize_preview_report` plus the Pydantic models). See previewReportNestedKeys.json.
 */
describe('nested preview-report field classification is total', () => {
  const containers = previewReportNestedKeys.containers as Record<string, {
    keys: Record<string, { observedIn: number; strippedAsForbidden?: boolean }>;
  }>;

  it('covers exactly the containers the boundary reaches into', () => {
    expect(Object.keys(containers).sort()).toEqual([...NESTED_FIELD_SCOPE.keys()].sort());
  });

  it.each(Object.keys(containers))(
    'classifies every second-level key of %s that survives sanitisation',
    (container) => {
      const scopes = NESTED_FIELD_SCOPE.get(container)!;
      const unclassified = Object.entries(containers[container].keys)
        .filter(([, meta]) => meta.strippedAsForbidden !== true)
        .map(([key]) => key)
        .filter((key) => scopes.get(key) === undefined);

      expect(unclassified).toEqual([]);
    },
  );

  it.each(Object.keys(containers))(
    // The inverse: a classification for a key no writer produces, or for one the forbidden
    // strip already removed, is a guess — and a guess is how a name list drifts out of
    // contact with the payload it claims to describe.
    'classifies nothing in %s beyond what the writer produces',
    (container) => {
      const classifiable = Object.entries(containers[container].keys)
        .filter(([, meta]) => meta.strippedAsForbidden !== true)
        .map(([key]) => key);

      expect([...NESTED_FIELD_SCOPE.get(container)!.keys()].sort())
        .toEqual(classifiable.sort());
    },
  );

  it.each(['withhold', 'serve'] as const)(
    'withholds an unclassified nested field on the %s disposition',
    (disposition) => {
      const served = applyPreviewFieldAllowlist({
        niche: 'appliance repair shops',
        research_metadata: {
          reddit_posts_analyzed: 240,
          // The shape every future nested addition arrives in.
          NESTED_UNCLASSIFIED_LEAK: { candidates_ranked: 6 },
        },
      }, disposition) as Record<string, any>;

      expect(served.research_metadata).toEqual({ reddit_posts_analyzed: 240 });
    },
  );

  it('warns once per call, naming top-level and nested unclassified keys together', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    try {
      applyPreviewFieldAllowlist({
        niche: 'appliance repair shops',
        brand_new_upstream_field_2027: [{ idea_id: 'idea-1' }],
        research_metadata: {
          reddit_posts_analyzed: 240,
          NESTED_UNCLASSIFIED_LEAK: { candidates_ranked: 6 },
        },
      }, 'serve');

      expect(warn).toHaveBeenCalledTimes(1);
      const message = String(warn.mock.calls[0][0]);
      expect(message).toContain('brand_new_upstream_field_2027');
      expect(message).toContain('research_metadata.NESTED_UNCLASSIFIED_LEAK');
    } finally {
      warn.mockRestore();
    }
  });

  it('leaves a niche-scoped container the boundary does not reach into untouched', () => {
    // Two levels deep, not arbitrarily deep — stated in NESTED_FIELD_SCOPE and asserted
    // here so the limit is a decision on the record rather than an oversight.
    const served = applyPreviewFieldAllowlist({
      niche_context: { anything: 1, at_all: 2 },
    }, 'withhold');

    expect(served).toEqual({ niche_context: { anything: 1, at_all: 2 } });
  });
});
