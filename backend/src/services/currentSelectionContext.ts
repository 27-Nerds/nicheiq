import { createHash } from 'node:crypto';
import type { Prisma } from '@prisma/client';
import { getPreviewReportForJob } from './selectionBoundary/rawPreviewReport.js';
import { ensureIdeaIdentities, type IdeaRecord } from '../utils/ideaIdentity.js';
import { ideaPortfolioFingerprint } from '../utils/ideaPortfolioFingerprint.js';

export interface CanonicalSelectionPool {
  readonly candidates: readonly IdeaRecord[];
  readonly displayedCount: number;
  readonly version: CandidatePoolVersion | null;
}

const candidatePoolVersionBrand: unique symbol = Symbol('CandidatePoolVersion');

/** Opaque proof that a pool version came from CurrentSelectionContext. */
export type CandidatePoolVersion = number & {
  readonly [candidatePoolVersionBrand]: true;
};

const verifiedRunArtifactsBrand: unique symbol = Symbol('VerifiedRunArtifacts');

/** The only type that exposes preview-derived data. */
export interface VerifiedRunArtifacts {
  readonly verification: 'verified';
  readonly candidatePoolVersion: number;
  readonly previewReport: Readonly<Record<string, unknown>>;
  readonly [verifiedRunArtifactsBrand]: true;
}

export type UntrustedRunArtifactReason =
  | 'legacy_missing_version'
  | 'version_mismatch'
  | 'unresolvable_candidate_pool'
  | 'legacy_missing_fingerprint'
  | 'content_mismatch'
  | 'preview_unavailable';

/** Deliberately has no previewReport property and cannot satisfy VerifiedRunArtifacts. */
export interface UntrustedRunArtifacts {
  readonly verification: 'untrusted';
  readonly reason: UntrustedRunArtifactReason;
  readonly candidatePoolVersion: number | null;
  readonly artifactPoolVersion: number | null;
}

export type SelectionRunArtifacts = VerifiedRunArtifacts | UntrustedRunArtifacts;

export interface CurrentSelectionContext {
  readonly job: {
    readonly status: string;
    readonly niche: string;
    readonly gateStage: number | null;
    readonly activeDispatchId: string | null;
  };
  readonly canonical: CanonicalSelectionPool;
  readonly runArtifacts: SelectionRunArtifacts;
  /** Binds persisted analyst openings to both the pool version and artifact trust state. */
  readonly openingOrigin: string;
}

function openingOriginForContext(
  candidatePoolVersion: number | null,
  runArtifacts: SelectionRunArtifacts,
): string {
  const binding = runArtifacts.verification === 'verified'
    ? `verified:${candidatePoolVersion}`
    : `untrusted:${candidatePoolVersion}:${runArtifacts.artifactPoolVersion}:${runArtifacts.reason}`;
  const digest = createHash('sha256').update(binding).digest('hex').slice(0, 28);
  return `opening:cv:${digest}`;
}

function untrusted(
  reason: UntrustedRunArtifactReason,
  candidatePoolVersion: number | null,
  artifactPoolVersion: number | null,
): UntrustedRunArtifacts {
  return {
    verification: 'untrusted',
    reason,
    candidatePoolVersion,
    artifactPoolVersion,
  };
}

/**
 * The sole loader for the selection candidate pool and its run-level preview artifacts.
 * Callers receive canonical candidates in every state; preview data exists in the type system
 * only after the Job and PREVIEW_REPORT versions match.
 */
export async function loadCurrentSelectionContext(
  tx: Prisma.TransactionClient,
  jobId: string,
): Promise<CurrentSelectionContext | null> {
  const job = await tx.job.findUnique({
    where: { id: jobId },
    select: {
      status: true,
      niche: true,
      solutionIdeas: true,
      candidatePoolVersion: true,
      gateStage: true,
      activeDispatchId: true,
    },
  });
  if (!job) return null;

  const previewAsset = await tx.jobAsset.findUnique({
    where: { jobId_assetType: { jobId, assetType: 'PREVIEW_REPORT' } },
    select: { candidatePoolVersion: true },
  });
  const candidatePoolVersion = job.candidatePoolVersion === null
    ? null
    : job.candidatePoolVersion as CandidatePoolVersion;
  const artifactPoolVersion = previewAsset?.candidatePoolVersion ?? null;
  const canonicalFingerprint = ideaPortfolioFingerprint(job.solutionIdeas);
  const poolResolvable = Array.isArray(job.solutionIdeas) && canonicalFingerprint !== null;
  // Canonical chat remains usable for legacy/malformed arrays; normalization is never
  // evidence that run-level artifacts are trustworthy.
  const candidates = Array.isArray(job.solutionIdeas)
    ? ensureIdeaIdentities(jobId, job.solutionIdeas)
    : [];

  let runArtifacts: SelectionRunArtifacts;
  if (!poolResolvable || !canonicalFingerprint) {
    runArtifacts = untrusted(
      'unresolvable_candidate_pool', candidatePoolVersion, artifactPoolVersion,
    );
  } else if (candidatePoolVersion === null || artifactPoolVersion === null) {
    runArtifacts = untrusted('legacy_missing_version', candidatePoolVersion, artifactPoolVersion);
  } else if (candidatePoolVersion !== artifactPoolVersion) {
    runArtifacts = untrusted('version_mismatch', candidatePoolVersion, artifactPoolVersion);
  } else if (job.status !== 'AWAITING_SELECTION') {
    runArtifacts = untrusted('preview_unavailable', candidatePoolVersion, artifactPoolVersion);
  } else {
    const previewReport = await getPreviewReportForJob(jobId).catch((error) => {
      console.error(`[CurrentSelectionContext] preview read failed (jobId=${jobId}):`, error);
      return null;
    });
    if (!previewReport || typeof previewReport !== 'object' || Array.isArray(previewReport)) {
      runArtifacts = untrusted('preview_unavailable', candidatePoolVersion, artifactPoolVersion);
    } else {
      const previewRecord = previewReport as Record<string, unknown>;
      const storedFingerprint = typeof previewRecord.idea_portfolio_summary_fingerprint === 'string'
        ? previewRecord.idea_portfolio_summary_fingerprint
        : null;
      if (!storedFingerprint) {
        runArtifacts = untrusted(
          'legacy_missing_fingerprint', candidatePoolVersion, artifactPoolVersion,
        );
      } else if (storedFingerprint !== canonicalFingerprint) {
        runArtifacts = untrusted('content_mismatch', candidatePoolVersion, artifactPoolVersion);
      } else {
        // The asset read is outside PostgreSQL, so close the split-snapshot window before
        // minting the verified brand. Once parsed, previewRecord is an in-memory snapshot.
        const [latestJob, latestAsset] = await Promise.all([
          tx.job.findUnique({
            where: { id: jobId },
            select: { candidatePoolVersion: true },
          }),
          tx.jobAsset.findUnique({
            where: { jobId_assetType: { jobId, assetType: 'PREVIEW_REPORT' } },
            select: { candidatePoolVersion: true },
          }),
        ]);
        if (
          latestJob?.candidatePoolVersion !== candidatePoolVersion
          || latestAsset?.candidatePoolVersion !== artifactPoolVersion
        ) {
          runArtifacts = untrusted(
            'version_mismatch', latestJob?.candidatePoolVersion ?? null,
            latestAsset?.candidatePoolVersion ?? null,
          );
        } else {
          runArtifacts = {
            verification: 'verified',
            candidatePoolVersion,
            previewReport: previewRecord,
            [verifiedRunArtifactsBrand]: true,
          };
        }
      }
    }
  }

  if (runArtifacts.verification === 'untrusted') {
    console.warn(
      `[CurrentSelectionContext] run-level artifacts withheld (jobId=${jobId}, `
      + `reason=${runArtifacts.reason}, poolVersion=${candidatePoolVersion ?? 'null'}, `
      + `artifactVersion=${artifactPoolVersion ?? 'null'})`,
    );
  }

  return {
    job: {
      status: job.status,
      niche: job.niche,
      gateStage: job.gateStage,
      activeDispatchId: job.activeDispatchId,
    },
    canonical: {
      candidates,
      displayedCount: candidates.length,
      version: candidatePoolVersion,
    },
    runArtifacts,
    openingOrigin: openingOriginForContext(candidatePoolVersion, runArtifacts),
  };
}
