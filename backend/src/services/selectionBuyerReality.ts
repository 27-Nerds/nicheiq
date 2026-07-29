import { getSelectionCapThresholds } from '../config.js';

/**
 * Run-level buyer-wallet reality, distilled from the preview report.
 *
 * WHY THIS EXISTS
 * The Python pipeline demotes ideas whose matched segment cannot pay
 * (`_sweep_no_buyer_demote`), and records each one in `examined_ruled_out` with
 * `source: 'no_buyer'`. That evidence reaches the backend inside the preview report —
 * but the generative "make me a new candidate" services only ever hashed the report for
 * cache invalidation, so they were structurally blind to it. The observed failure: in a
 * run where 7 of 9 ideas had already died in one segment at payability 0.15, Concept
 * Forge produced three more options aimed at that same segment, and the pipeline
 * promptly demoted the one the owner evaluated.
 *
 * The pipeline has no single field answering "which segments here have thin wallets?"
 * (`market_reality.wallet` is niche-level; `payability_score` is per-segment; the death
 * counts are only derivable by grouping `examined_ruled_out`). So this module derives it.
 *
 * Everything here is READ-ONLY inference over an artifact that is already fetched. It
 * adds no I/O and no LLM calls.
 */

/** Niche-level norm from the wallet probe. Not the same vocabulary as a segment class. */
export type NicheWalletClass = 'paying' | 'mixed' | 'free-culture';

export interface BuyerRealitySegment {
  name: string;
  payability: number | null;
  payabilityClass: string | null;
  /** Mirrors the demoter's own disjunction — see `thinWallet()`. */
  thin: boolean;
  /** How many ideas anchored to this segment have already been ruled out. */
  ruledOutCount: number;
  /** Of those, how many died specifically on the buyer bar. */
  noBuyerCount: number;
}

export interface BuyerRealityDigest {
  walletClass: NicheWalletClass | null;
  walletEvidence: string | null;
  buyerClass: string | null;
  buyerClassNote: string | null;
  segments: BuyerRealitySegment[];
  /** Segment names that fail the wallet bar AND have already lost ideas. */
  provenThinSegments: string[];
  /** Best-paying segment that has not been shown to be thin, if any. */
  strongestSegment: { name: string; payability: number | null } | null;
  /** Total ruled-out ideas attributed to a `no_buyer` demotion. */
  noBuyerDeaths: number;
}

/**
 * The demoter's test, mirrored: `pay < payability_low_threshold` OR class is
 * `personal-wallet` (unified_solution_crew.py `_sweep_no_buyer_demote`). Threshold is
 * read from the shared env mirror rather than hardcoded, so a prod override moves both
 * sides together.
 */
export function thinWallet(payability: number | null, payabilityClass: string | null): boolean {
  const { payabilityLowThreshold } = getSelectionCapThresholds();
  if (typeof payability === 'number' && Number.isFinite(payability) && payability < payabilityLowThreshold) {
    return true;
  }
  return (payabilityClass ?? '').trim().toLowerCase() === 'personal-wallet';
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** "Buyers in this segment (X) rarely pay…" — the only place the segment survives when
 *  a ruled-out entry lost its nested `idea` payload. */
const SEGMENT_IN_REASON = /buyers in this segment \(([^)]+)\)/i;

function ruledOutSegment(entry: Record<string, unknown>): string | null {
  const idea = entry.idea;
  if (idea && typeof idea === 'object') {
    const named = text((idea as Record<string, unknown>).source_segment);
    if (named) return named;
  }
  return text(entry.reason)?.match(SEGMENT_IN_REASON)?.[1]?.trim() ?? null;
}

/**
 * Build the digest. Fail-soft by design: a missing or malformed report yields a digest
 * with no segments, which every consumer treats as "no evidence to respect" rather than
 * as a reason to block generation.
 */
export function buildBuyerRealityDigest(report: unknown): BuyerRealityDigest {
  const empty: BuyerRealityDigest = {
    walletClass: null,
    walletEvidence: null,
    buyerClass: null,
    buyerClassNote: null,
    segments: [],
    provenThinSegments: [],
    strongestSegment: null,
    noBuyerDeaths: 0,
  };
  if (!report || typeof report !== 'object' || Array.isArray(report)) return empty;
  const root = report as Record<string, unknown>;

  const wallet = ((root.market_reality as Record<string, unknown> | undefined)?.wallet ?? {}) as Record<string, unknown>;
  const rawWalletClass = text(wallet.wallet_class)?.toLowerCase() ?? null;
  const walletClass: NicheWalletClass | null =
    rawWalletClass === 'paying' || rawWalletClass === 'mixed' || rawWalletClass === 'free-culture'
      ? rawWalletClass
      : null;

  const verdict = (root.niche_difficulty_verdict ?? {}) as Record<string, unknown>;

  // Death counts, grouped by the segment each ruled-out idea was anchored to.
  const ruledOut = Array.isArray(root.examined_ruled_out) ? root.examined_ruled_out : [];
  const deaths = new Map<string, { total: number; noBuyer: number }>();
  let noBuyerDeaths = 0;
  for (const raw of ruledOut) {
    if (!raw || typeof raw !== 'object') continue;
    const entry = raw as Record<string, unknown>;
    // Branch on `source`, never on the reason prose — the reason literal has already
    // changed once between revisions and is not a stable contract.
    const isNoBuyer = text(entry.source) === 'no_buyer';
    if (isNoBuyer) noBuyerDeaths += 1;
    const segment = ruledOutSegment(entry);
    if (!segment) continue;
    const key = segment.toLowerCase();
    const bucket = deaths.get(key) ?? { total: 0, noBuyer: 0 };
    bucket.total += 1;
    if (isNoBuyer) bucket.noBuyer += 1;
    deaths.set(key, bucket);
  }

  const rawSegments = ((root.audience_mapping as Record<string, unknown> | undefined)?.audience_segments ?? []) as unknown[];
  const segments: BuyerRealitySegment[] = [];
  for (const raw of rawSegments) {
    if (!raw || typeof raw !== 'object') continue;
    const s = raw as Record<string, unknown>;
    const name = text(s.segment_name);
    if (!name) continue;
    const payability = num(s.payability_score);
    const payabilityClass = text(s.payability_class);
    const bucket = deaths.get(name.toLowerCase()) ?? { total: 0, noBuyer: 0 };
    segments.push({
      name,
      payability,
      payabilityClass,
      thin: thinWallet(payability, payabilityClass),
      ruledOutCount: bucket.total,
      noBuyerCount: bucket.noBuyer,
    });
  }

  // "Proven" thin, not merely scored thin: the wallet bar failed AND the run has already
  // spent ideas there. A low score alone is a prior; a score plus corpses is evidence.
  const provenThinSegments = segments
    .filter((segment) => segment.thin && segment.ruledOutCount > 0)
    .map((segment) => segment.name);

  const strongestSegment =
    segments
      .filter((segment) => !segment.thin)
      .sort((a, b) => (b.payability ?? -1) - (a.payability ?? -1))
      .map((segment) => ({ name: segment.name, payability: segment.payability }))[0] ?? null;

  return {
    walletClass,
    walletEvidence: text(wallet.evidence),
    buyerClass: text(verdict.buyer_class),
    buyerClassNote: text(verdict.buyer_class_note),
    segments,
    provenThinSegments,
    strongestSegment,
    noBuyerDeaths,
  };
}

/**
 * Whether a generator must be told to consider moving the buyer.
 *
 * Deliberately conservative: it fires only when the run has actually lost ideas in a
 * thin segment, so a fresh run with no demotions never constrains generation.
 */
export function hasProvenBuyerProblem(digest: BuyerRealityDigest): boolean {
  return digest.provenThinSegments.length > 0;
}

/** Case-insensitive membership, for matching a parent's segment against the thin list. */
export function segmentIsProvenThin(digest: BuyerRealityDigest, segment: string | null | undefined): boolean {
  const needle = (segment ?? '').trim().toLowerCase();
  if (!needle) return false;
  return digest.provenThinSegments.some((name) => name.toLowerCase() === needle);
}
