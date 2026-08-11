import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Prisma } from '@prisma/client';
import {
  loadCurrentSelectionContext,
  type UntrustedRunArtifacts,
  type VerifiedRunArtifacts,
} from '../currentSelectionContext.js';

const mockGetPreviewReportForJob = vi.fn();

vi.mock('../selectionBoundary/rawPreviewReport.js', () => ({
  getPreviewReportForJob: (...args: unknown[]) => mockGetPreviewReportForJob(...args),
}));

const ideas = [{
  idea_id: 'idea-current',
  idea_revision: 2,
  solution_name: 'Current idea',
  market_fit_score: 0.72,
}];
const fingerprint = '{"version":1,"ideas":[["idea-current",2]]}';

function transaction(args: {
  solutionIdeas?: unknown;
  jobVersion?: number | null;
  assetVersion?: number | null;
}) {
  const job = {
    status: 'AWAITING_SELECTION',
    niche: 'test niche',
    solutionIdeas: args.solutionIdeas ?? ideas,
    candidatePoolVersion: args.jobVersion === undefined ? 3 : args.jobVersion,
    gateStage: null,
    activeDispatchId: null,
  };
  return {
    job: { findUnique: vi.fn().mockResolvedValue(job) },
    jobAsset: {
      findUnique: vi.fn().mockResolvedValue({
        candidatePoolVersion: args.assetVersion === undefined ? 3 : args.assetVersion,
      }),
    },
  } as unknown as Prisma.TransactionClient;
}

describe('CurrentSelectionContext', () => {
  beforeEach(() => mockGetPreviewReportForJob.mockReset());

  it('brands run-level artifacts only when pool, asset, and content versions match', async () => {
    mockGetPreviewReportForJob.mockResolvedValue({
      idea_portfolio_summary_fingerprint: fingerprint,
      idea_portfolio_summary: 'Current framing',
    });

    const context = await loadCurrentSelectionContext(transaction({}), 'job-1');

    expect(context?.canonical).toMatchObject({ displayedCount: 1, version: 3 });
    expect(context?.runArtifacts.verification).toBe('verified');
    expect(context?.openingOrigin).toMatch(/^opening:cv:[a-f0-9]{28}$/);
  });

  it('withholds run-level artifacts when the persisted versions mismatch while keeping chat candidates usable', async () => {
    const context = await loadCurrentSelectionContext(
      transaction({ jobVersion: 4, assetVersion: 3 }),
      'job-1',
    );

    expect(context?.runArtifacts).toMatchObject({
      verification: 'untrusted',
      reason: 'version_mismatch',
    });
    expect(context?.canonical.candidates).toHaveLength(1);
    expect(context?.openingOrigin).toMatch(/^opening:cv:/);
    expect(mockGetPreviewReportForJob).not.toHaveBeenCalled();
  });

  it('treats a missing legacy version as untrusted while preserving canonical chat', async () => {
    const context = await loadCurrentSelectionContext(
      transaction({ jobVersion: null, assetVersion: null }),
      'job-1',
    );

    expect(context?.runArtifacts).toMatchObject({
      verification: 'untrusted',
      reason: 'legacy_missing_version',
    });
    expect(context?.canonical.candidates[0]).toMatchObject({ solution_name: 'Current idea' });
    expect(context?.openingOrigin).toMatch(/^opening:cv:/);
  });

  it('treats malformed candidate identity as unresolvable before compatibility identities are added', async () => {
    const context = await loadCurrentSelectionContext(
      transaction({ solutionIdeas: [{ solution_name: 'Legacy malformed idea' }] }),
      'job-1',
    );

    expect(context?.runArtifacts).toMatchObject({
      verification: 'untrusted',
      reason: 'unresolvable_candidate_pool',
    });
    expect(context?.canonical.candidates).toHaveLength(1);
    expect(context?.canonical.candidates[0]?.idea_id).toMatch(/^idea_/);
    expect(context?.openingOrigin).toMatch(/^opening:cv:/);
  });

  it('withholds a matching-version preview whose embedded content fingerprint mismatches', async () => {
    mockGetPreviewReportForJob.mockResolvedValue({
      idea_portfolio_summary_fingerprint: '{"version":1,"ideas":[["idea-old",1]]}',
      idea_portfolio_summary: 'Stale framing',
    });

    const context = await loadCurrentSelectionContext(transaction({}), 'job-1');

    expect(context?.runArtifacts).toMatchObject({
      verification: 'untrusted',
      reason: 'content_mismatch',
    });
  });

  it('does not mint the verified type when the pool version changes during the asset read', async () => {
    mockGetPreviewReportForJob.mockResolvedValue({
      idea_portfolio_summary_fingerprint: fingerprint,
      idea_portfolio_summary: 'Version-three framing',
    });
    const tx = transaction({});
    vi.mocked(tx.job.findUnique)
      .mockResolvedValueOnce({
        status: 'AWAITING_SELECTION',
        niche: 'test niche',
        solutionIdeas: ideas,
        candidatePoolVersion: 3,
        gateStage: null,
        activeDispatchId: null,
      } as any)
      .mockResolvedValueOnce({ candidatePoolVersion: 4 } as any);

    const context = await loadCurrentSelectionContext(tx, 'job-1');

    expect(context?.runArtifacts).toMatchObject({
      verification: 'untrusted',
      reason: 'version_mismatch',
      candidatePoolVersion: 4,
    });
  });

  it('keeps the database trigger as the sole monotonic pool-version owner', () => {
    const sql = readFileSync(
      new URL('../../../prisma/migrations/20260809180000_candidate_pool_version/migration.sql', import.meta.url),
      'utf8',
    );

    expect(sql).toContain('NEW."solutionIdeas" IS DISTINCT FROM OLD."solutionIdeas"');
    expect(sql).toContain('COALESCE(OLD."candidatePoolVersion", 0) + 1');
    expect(sql).toContain('BEFORE UPDATE OF "solutionIdeas", "candidatePoolVersion" ON "Job"');
    expect(sql).toContain('NEW."candidatePoolVersion" := OLD."candidatePoolVersion"');
  });
});

function requiresVerifiedArtifacts(_artifacts: VerifiedRunArtifacts): void {}

if (false) {
  const stale = {} as UntrustedRunArtifacts;
  // Compile-time proof: removing the distinct type makes this directive fail as unused.
  // @ts-expect-error Untrusted artifacts cannot cross the verified preview boundary.
  requiresVerifiedArtifacts(stale);
}
