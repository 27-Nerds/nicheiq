import type { SolutionPreview } from "$lib/types/job";

const FINGERPRINT_VERSION = 1;

/**
 * The single frontend authority for the candidate-pool fingerprint.
 *
 * Mirrors `backend/src/utils/ideaPortfolioFingerprint.ts`, which in turn mirrors Python's
 * `idea_portfolio_fingerprint` — the value the pipeline stores as
 * `idea_portfolio_summary_fingerprint`. Any surface that decides whether pool-scoped
 * guidance still describes the ideas on screen must call THIS, never a local copy: a copy
 * that drifts by one rule silently withholds guidance that is in fact current (round 14),
 * or shows guidance that is not.
 *
 * Contract, in the order the divergences actually bit:
 *  - `demoted` / `absorbed` candidates are skipped, matching Python's `visible_ideas()`.
 *  - a candidate with no `idea_id`, or a non-integer / sub-1 `idea_revision`, makes the
 *    whole pool unfingerprintable — null, which every caller treats as "not current".
 *  - an ABSENT `idea_revision` defaults to 1; a PRESENT one that is not an integer >= 1 —
 *    explicit `null` included — is unfingerprintable. Python reads
 *    `idea.get("idea_revision", 1)` and the backend reads `hasOwnProperty`, so a `?? 1`
 *    here would call a null-revision pool current while both others called it stale.
 *  - refs sort by (id, revision) so pool ORDER never changes the fingerprint.
 *  - a pool ELEMENT that is not a plain object, and an `idea_id` that is not a string,
 *    make the pool unfingerprintable — the backend's guards, mirrored. This file is
 *    reached from a `$derived`, where a TypeError does not fail closed: it breaks the
 *    workbench render. `ensureIdeaIdentities` keeps both shapes off the wire today, but
 *    an authority that throws where the other two return null is not an authority.
 */
export function ideaPortfolioFingerprint(
  candidates: readonly SolutionPreview[],
): string | null {
  const refs: [string, number][] = [];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
    const status = candidate.candidate_status;
    if (status === "demoted" || status === "absorbed") continue;

    const ideaId = typeof candidate.idea_id === "string" ? candidate.idea_id.trim() : "";
    const revision = Object.prototype.hasOwnProperty.call(candidate, "idea_revision")
      ? candidate.idea_revision
      : 1;
    if (
      !ideaId
      || typeof revision !== "number"
      || !Number.isInteger(revision)
      || revision < 1
    ) {
      return null;
    }
    refs.push([ideaId, revision]);
  }

  refs.sort(([aId, aRevision], [bId, bRevision]) => (
    aId < bId ? -1 : aId > bId ? 1 : aRevision - bRevision
  ));
  return JSON.stringify({ version: FINGERPRINT_VERSION, ideas: refs });
}
