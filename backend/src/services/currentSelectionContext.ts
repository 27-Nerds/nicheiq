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

/**
 * THE NINETEENTH SURFACE (2026-08-15) — the outcome of the idea check, readable at ANY status.
 *
 * `runArtifacts` is deliberately withheld outside `AWAITING_SELECTION` (line ~132 below),
 * because everything it exposes is a snapshot of the CANDIDATE POOL and the pool is
 * superseded once the run completes. Round 8 measured the consequence and recorded it as the
 * blocker for surface 18: at `COMPLETED`, `loadCurrentSelectionContext` resolves
 * `preview_unavailable` 100% of the time, so any consumer that asks "what may we claim about
 * the user's submitted idea?" through that door gets `unavailable` on every run, graded and
 * refused alike. The completed-report analyst prompt (`buildCompletedReportSystemPrompt`)
 * therefore had no way to learn the check had been refused, and told the model the report was
 * ABOUT the user's pitch — on every question the user asked, persisted forever as chat history.
 *
 * This record is the "new read path, not a new call site" that surface 18 said was needed. It
 * is narrow ON PURPOSE and must stay that way:
 *
 * - It carries ONLY the four values that answer "what may we assert about the submitted
 *   idea?" — the outcome and the two sentences the user was already shown. It carries no
 *   score, no candidate, no competitor, no pool count. Nothing here is a function of the
 *   candidate pool, so the pool-version binding that gates `runArtifacts` does not apply:
 *   the check runs once, in Phase 1, and no regeneration can turn a refusal into a grading.
 * - `headline` / `failureNextStep` are read VERBATIM off the artifact, which sources them
 *   from `SEED_FAILURE_COPY` (src/nicheiq/report/idea_validation_block.py). No consumer may
 *   write a refusal sentence of its own — this program has already found five.
 * - `null` means "we could not read it", which asserts NEITHER outcome. Same doctrine as
 *   `ResearchProgressScreen`'s `"unknown"` default and the emails' `unavailable`.
 */
export interface IdeaCheckRecord {
  /** The artifact's own `outcome` string. `not_evaluated` = the run refused to grade it. */
  readonly outcome: string;
  /** The spec's name when one was built; null on every refusal. */
  readonly ideaName: string | null;
  /** The pitch as submitted, from the artifact rather than the (truncated) `Job.niche`. */
  readonly userIdeaText: string | null;
  readonly headline: string | null;
  readonly failureNextStep: string | null;
}

/**
 * F-5 — THE NARROWNESS IS ENFORCED, NOT INTENDED.
 *
 * Everything the doc above argues rests on one fact: this record carries nothing that is a
 * function of the CANDIDATE POOL. That is what makes it legal to read outside the
 * pool-version binding that gates `runArtifacts`. Until this round the fact was a convention —
 * `ideaCheckFromPreview` happened to copy five scalars, and nothing failed if a later edit
 * added `alternatives`, `pivot` or `seed_display_composite_score`, each of which IS
 * pool-derived and each of which sits right beside them on the same artifact.
 *
 * Adding a field to `IdeaCheckRecord` without adding its name here is now a **tsc error**
 * (`IdeaCheckRecordIsNarrow` below), and adding it here is the deliberate act this comment
 * governs: a new member must answer "what may we assert about the user's submitted idea?" and
 * must be invariant under regeneration. `currentSelectionContext.narrow.test.ts` drives the
 * loader with a FULL 41-key `idea_validation` block and asserts that none of the other 36
 * values comes back — a measurement, not a restatement of this list.
 */
export const IDEA_CHECK_RECORD_FIELDS = [
  'outcome',
  'ideaName',
  'userIdeaText',
  'headline',
  'failureNextStep',
] as const;

/** `never` when the interface holds only the sanctioned fields; the offending key names
 *  otherwise, which makes the assignment below fail to compile and names what widened it. */
export type IdeaCheckRecordIsNarrow =
  Exclude<keyof IdeaCheckRecord, typeof IDEA_CHECK_RECORD_FIELDS[number]> extends never
    ? true
    : Exclude<keyof IdeaCheckRecord, typeof IDEA_CHECK_RECORD_FIELDS[number]>;

export const ideaCheckRecordIsNarrow: IdeaCheckRecordIsNarrow = true;

export interface CurrentSelectionContext {
  readonly job: {
    readonly status: string;
    readonly niche: string;
    readonly gateStage: number | null;
    readonly activeDispatchId: string | null;
    readonly entryMode: string | null;
  };
  readonly canonical: CanonicalSelectionPool;
  readonly runArtifacts: SelectionRunArtifacts;
  /**
   * The idea-check outcome, or null when this is not a `validate_idea` run or the artifact
   * could not be read. Independent of `runArtifacts` and of `job.status` — see the type doc.
   */
  readonly ideaCheck: IdeaCheckRecord | null;
  /** Binds persisted analyst openings to both the pool version and artifact trust state. */
  readonly openingOrigin: string;
}

/** The idea-check fields of a preview report, or null when the block is absent/malformed. */
function ideaCheckFromPreview(previewReport: unknown): IdeaCheckRecord | null {
  if (!previewReport || typeof previewReport !== 'object' || Array.isArray(previewReport)) {
    return null;
  }
  const iv = (previewReport as Record<string, unknown>).idea_validation;
  if (!iv || typeof iv !== 'object' || Array.isArray(iv)) return null;
  const block = iv as Record<string, unknown>;
  const outcome = typeof block.outcome === 'string' ? block.outcome : '';
  if (!outcome) return null;
  const str = (value: unknown) => (typeof value === 'string' && value ? value : null);
  return {
    outcome,
    ideaName: str(block.idea_name),
    userIdeaText: str(block.user_idea_text) ?? str(block.user_idea_brief),
    headline: str(block.headline),
    failureNextStep: str(block.failure_next_step),
  };
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
      entryMode: true,
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

  // Resolved SEPARATELY from `runArtifacts` and never gated on it — see `IdeaCheckRecord`.
  // The extra read happens only on `validate_idea` runs whose artifacts were withheld (any
  // status but AWAITING_SELECTION, or a version/content mismatch); when they were verified
  // the block is already in hand and no second read is issued. `previewReportCache` backs
  // `getPreviewReportForJob`, so even the extra path is not a fresh disk hit per turn.
  let ideaCheck: IdeaCheckRecord | null = null;
  if (job.entryMode === 'validate_idea') {
    if (runArtifacts.verification === 'verified') {
      ideaCheck = ideaCheckFromPreview(runArtifacts.previewReport);
    } else {
      const raw = await getPreviewReportForJob(jobId).catch((error) => {
        console.error(`[CurrentSelectionContext] idea-check read failed (jobId=${jobId}):`, error);
        return null;
      });
      ideaCheck = ideaCheckFromPreview(raw);
    }
  }

  return {
    job: {
      status: job.status,
      niche: job.niche,
      gateStage: job.gateStage,
      activeDispatchId: job.activeDispatchId,
      entryMode: job.entryMode ?? null,
    },
    canonical: {
      candidates,
      displayedCount: candidates.length,
      version: candidatePoolVersion,
    },
    runArtifacts,
    ideaCheck,
    openingOrigin: openingOriginForContext(candidatePoolVersion, runArtifacts),
  };
}
