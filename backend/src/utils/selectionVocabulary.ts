/**
 * Internal selection enums rendered as the words the product actually shows.
 *
 * These values are storage tokens (`VALIDATE_MORE`, `CTA_SMOKE_TEST`, `insufficient`,
 * `needs_reshape`). They exist so code can branch on them; they are not copy. Handed to a
 * reader — in a downloaded markdown artifact, a GitHub issue body, or an analyst prompt the
 * model then paraphrases — they read as jargon at best and as a verdict the product never
 * issued at worst. Every map below mirrors a label the UI already ships:
 *
 * - method / signal: frontend/src/lib/components/selection/ExperimentWorkspace.svelte
 * - handoff action:  frontend/src/lib/components/decision/DecisionHandoffPanel.svelte
 * - consensus:       frontend/src/lib/components/selection/EvidenceChallenge.svelte
 * - founder fit:     frontend/src/routes/(app)/jobs/[jobId]/selection/compare/+page.svelte
 *
 * An unmapped value falls back to its de-underscored lowercase form, so a new enum member
 * degrades to readable words instead of shouting a storage token.
 */

export function humanizeEnumToken(value: string): string {
  return value.trim().toLowerCase().replace(/_/g, ' ');
}

function label(map: Record<string, string>, value: string | null | undefined): string {
  const key = value?.trim();
  if (!key) return '';
  return map[key] ?? map[key.toUpperCase()] ?? map[key.toLowerCase()] ?? humanizeEnumToken(key);
}

const EXPERIMENT_METHOD: Record<string, string> = {
  CUSTOMER_INTERVIEWS: 'Customer interviews',
  SURVEY: 'Survey',
  CTA_SMOKE_TEST: 'CTA smoke test',
  BOOKED_CALL: 'Booked-call test',
  PREORDER: 'Preorder / deposit',
  CONCIERGE: 'Concierge test',
  PROTOTYPE: 'Prototype test',
  TECHNICAL_SPIKE: 'Technical spike',
  OTHER: 'Custom test',
};

const EVIDENCE_SIGNAL: Record<string, string> = {
  LANGUAGE: 'Language / context',
  STATED_PREFERENCE: 'Stated preference',
  CTA_INTEREST: 'CTA interest',
  SMALL_COMMITMENT: 'Small commitment',
  PAYMENT_INTENT: 'Payment intent',
  USAGE: 'Real usage',
};

/** Per-question outcome of an evidence check, compressed to fit one line. */
const CHALLENGE_CONSENSUS: Record<string, string> = {
  supported: 'evidence supports it',
  contradicted: 'evidence weakens it',
  mixed: 'evidence points both ways',
  disputed: 'the two reviewers disagreed',
  insufficient: 'evidence does not answer it',
};

const HANDOFF_ACTION: Record<string, string> = {
  BUILD: 'Build this',
  VALIDATE_MORE: 'Validate before building',
  PARK: 'Park this path',
  STOP: 'Stop this path',
};

const HOSTED_RUN_STATE: Record<string, string> = {
  OPEN: 'Launched, hosted run collecting responses',
  CLOSED: 'Launched, hosted run closed',
};

const FOUNDER_FIT_VERDICT: Record<string, string> = {
  fits: 'Fits your build limits',
  needs_reshape: 'Could fit with changes',
  blocked: 'Conflicts with a build limit',
  insufficient_evidence: 'Needs more evidence',
};

/** Wallet class of the niche. Long-form phrasing lives in routes/chat.ts WALLET_CLASS_PHRASE;
 *  these are the short forms for titles and one-line labels. */
const WALLET_CLASS: Record<string, string> = {
  paying: 'pays for tools',
  mixed: 'mixed — some pay, some do not',
  'free-culture': 'free-tool culture',
};

/**
 * `incumbent_parity` / `adjacent_market_parity` are stored as `"<class> by <vendor>: <evidence>"`
 * or `"<class> (<vendor>): <evidence>"` (UnifiedSolutionCrew), where class comes from the closed
 * vocabulary `shipped | partial | substitute | bundled_free`, plus the literal `"none found"`.
 * Only the CLASS is a token; the vendor and evidence are already prose. Rendered whole, the
 * analyst reads "substitute by Notion" and says it back.
 *
 * Wording mirrors what the shipped UI conveys — frontend/src/lib/utils/adversarialReview.ts and
 * SelectionWorkbench.svelte `incumbentName`, which parse these exact two shapes.
 */
const INCUMBENT_PARITY_NAMED: Record<string, string> = {
  shipped: 'Already shipped by %v',
  partial: 'Partly covered by %v',
  substitute: 'Buyers already get this outcome from %v',
  bundled_free: 'Already included free with %v',
};

/**
 * The same classes when the vendor slot holds no product.
 *
 * The adversarial review writes `red-team` / `evidence` into that slot, and the frontend
 * deliberately suppresses those from its "Incumbent: <name>" chip: such a finding names an
 * alternative CLASS, not a product, and calling it a competitor would lend it a vendor's
 * authority it never had. Same distinction, kept here.
 */
const INCUMBENT_PARITY_CLASS_ONLY: Record<string, string> = {
  shipped: 'This is already shipped elsewhere',
  partial: 'This is already partly covered elsewhere',
  substitute: 'Buyers already get this outcome another way',
  bundled_free: 'This is already available free elsewhere',
};

/** Said out loud so a class-only finding is never mistaken for a verified competitor. */
const CLASS_ONLY_SUFFIX = ' (an alternative class, no product named)';

/**
 * A "none" stamp is a RETRIEVAL RESULT, never a fact about the market. The parity probe builds
 * its queries out of the idea's OWN vocabulary, so the wording of the pitch decides the verdict:
 * a live run shipped "none found" for a #1 recommendation while a same-pain sibling carried
 * "partial by Synup". Measured over stored runs, 591 ideas carry a "none" stamp and ~90% of them
 * sit in a run that already names an incumbent on another idea. So the copy states the search
 * result and not the conclusion. Twin of the Python block's NONE_FOUND_NOTE
 * (src/nicheiq/report/idea_validation_block.py) and of the frontend copy of this helper — the
 * three stacks describe one finding and must not contradict each other in one product.
 *
 * ONE literal, on one line, in both copies: the anti-drift gate compares the two files' phrase
 * literals as text, and a concatenation split differently on the two sides would read as drift.
 */
export const NONE_SURFACED_PHRASE = "Our searches did not surface a direct competitor. They run on this idea's own wording, so a rival that describes itself differently can be missed.";

/** Vendor slots that are not vendors — see INCUMBENT_PARITY_CLASS_ONLY. */
const NOT_A_VENDOR = /^(?:red[-\s]?team|evidence)$/i;

/** `<class> by <vendor>: <evidence>` / `<class> (<vendor>): <evidence>`, either half optional. */
const PARITY_SHAPE = /^([a-z_]+)(?:\s+by\s+([^:]+?)|\s*\(([^)]*)\))?\s*(?::\s*([\s\S]*))?$/i;

/**
 * A parity finding with its class prefix turned into words. Free text that does not carry a known
 * class is returned untouched — it is already prose, and rewriting it would invent a claim.
 */
export function incumbentParityPhrase(value: string | null | undefined): string {
  const raw = value?.trim();
  if (!raw) return '';
  // The `/^none\b/` TEST is load-bearing and unchanged (~139 consumers parse this prefix);
  // only what it RENDERS changed — see NONE_SURFACED_PHRASE.
  if (/^none\b/i.test(raw)) return NONE_SURFACED_PHRASE;

  const match = PARITY_SHAPE.exec(raw);
  if (!match) return raw;
  const klass = match[1].toLowerCase();
  if (!(klass in INCUMBENT_PARITY_NAMED)) return raw;

  const vendor = (match[2] ?? match[3] ?? '').trim();
  const evidence = (match[4] ?? '').trim();
  const head =
    vendor && !NOT_A_VENDOR.test(vendor)
      ? INCUMBENT_PARITY_NAMED[klass].replace('%v', vendor)
      : INCUMBENT_PARITY_CLASS_ONLY[klass] + CLASS_ONLY_SUFFIX;
  return evidence ? joinParityEvidence(head, vendor, evidence) : head;
}

/**
 * Evidence routinely re-opens with the vendor as its SUBJECT ("X ships Y") — joining
 * that with a colon produced "…by X: X ships Y", a broken-reading template stitch
 * (twin of the Python block's `_display_parity` rule). A subject echo joins as its
 * own sentence; a duplicated LABEL echo ("X: Y") is dropped; anything else keeps the
 * colon join. Dashes stay out of the lookahead: an unspaced dash is a compound word.
 */
function joinParityEvidence(head: string, vendor: string, evidence: string): string {
  if (vendor) {
    const escaped = vendor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const m = evidence.match(new RegExp(`^${escaped}(?=[\\s:,]|$)([\\s:,\\-\\u2013\\u2014]*)`, 'i'));
    if (m) {
      const remainder = evidence.slice(m[0].length).trim();
      if (remainder) {
        if (/[:\-–—]/.test(m[1])) return `${head}: ${remainder}`;
        return `${head}. ${evidence}`;
      }
    }
  }
  return `${head}: ${evidence}`;
}

/**
 * `red_team_verdict` is an INTERNAL enum — `killed` | `weakened` | `survives` — and it is a
 * verdict on the PREMISE the adversarial review tested, never a risk and never a verdict on
 * the idea. The shipped product does not say "killed": typed findings supply reason-specific
 * counterevidence or incomplete-evidence copy, while legacy records retain "Premise unproven".
 * The idea keeps its rank and stays selectable. An unrecognised value maps to null and is
 * dropped, so a future enum member cannot leak by default.
 */
const ADVERSARIAL_REVIEW_LABEL: Record<string, string> = {
  killed: 'Premise unproven',
  weakened: 'a decision-critical objection',
  survives: 'no disqualifying objection',
};

export type RedTeamFindingKind =
  | 'verified_incumbent_overlap'
  | 'verified_free_or_bundled_alternative'
  | 'verified_payer_mismatch'
  | 'verified_modal_failure'
  | 'evidence_gap';

const AFFIRMATIVE_REVIEW_LABEL: Partial<Record<RedTeamFindingKind, string>> = {
  verified_incumbent_overlap: 'verified incumbent overlap',
  verified_free_or_bundled_alternative: 'a verified free or bundled alternative',
  verified_payer_mismatch: 'a verified payer mismatch',
  verified_modal_failure: 'a verified modal failure',
};

const RED_TEAM_FINDING_KINDS = new Set<RedTeamFindingKind>([
  ...Object.keys(AFFIRMATIVE_REVIEW_LABEL) as RedTeamFindingKind[],
  'evidence_gap',
]);

export interface AdversarialReviewPrimaryFinding {
  basis: 'counterevidence' | 'incomplete_evidence';
  kind: RedTeamFindingKind;
  claim: string;
  label: string;
}

export function validatedRedTeamFindings(value: unknown): Array<{
  kind: RedTeamFindingKind;
  claim: string;
  raw: Record<string, unknown>;
}> {
  if (!Array.isArray(value)) return [];
  return value.flatMap((finding) => {
    if (!finding || typeof finding !== 'object') return [];
    const { claim, kind } = finding as Record<string, unknown>;
    return typeof claim === 'string'
      && claim.trim().length > 0
      && RED_TEAM_FINDING_KINDS.has(kind as RedTeamFindingKind)
      ? [{
        kind: kind as RedTeamFindingKind,
        claim: claim.trim(),
        raw: { ...(finding as Record<string, unknown>), kind, claim: claim.trim() },
      }]
      : [];
  });
}

/** One atomic source for a review's reason-specific label and the claim that earns it. */
export function resolveAdversarialReviewPrimaryFinding(
  findings: unknown,
): AdversarialReviewPrimaryFinding | null {
  const typed = validatedRedTeamFindings(findings);
  const affirmative = typed.find((finding) => finding.kind in AFFIRMATIVE_REVIEW_LABEL);
  const finding = affirmative ?? typed.find((candidate) => candidate.kind === 'evidence_gap');
  if (!finding) {
    return Array.isArray(findings)
      ? {
        basis: 'incomplete_evidence',
        kind: 'evidence_gap',
        claim: 'The review did not establish decision-critical evidence.',
        label: 'incomplete decision-critical evidence',
      }
      : null;
  }
  return {
    basis: affirmative ? 'counterevidence' : 'incomplete_evidence',
    kind: finding.kind,
    claim: finding.claim,
    label: affirmative
      ? AFFIRMATIVE_REVIEW_LABEL[finding.kind] ?? 'verified counterevidence'
      : 'incomplete decision-critical evidence',
  };
}

function effectiveAdversarialReviewVerdict(value: unknown, findings: unknown): string {
  const verdict = typeof value === 'string' ? value.trim().toLowerCase() : '';
  if (verdict !== 'killed' || !Array.isArray(findings)) return verdict;
  const hasAffirmative = validatedRedTeamFindings(findings)
    .some((finding) => finding.kind in AFFIRMATIVE_REVIEW_LABEL);
  return hasAffirmative ? verdict : 'weakened';
}

export function adversarialReviewLabel(value: unknown, findings?: unknown): string | null {
  const verdict = effectiveAdversarialReviewVerdict(value, findings);
  if (verdict === 'killed' || verdict === 'weakened') {
    const primary = resolveAdversarialReviewPrimaryFinding(findings);
    if (primary) return primary.label;
  }
  return verdict ? ADVERSARIAL_REVIEW_LABEL[verdict] ?? null : null;
}

function primaryFindingFirst(value: unknown): Record<string, unknown>[] {
  const typed = validatedRedTeamFindings(value);
  const primary = resolveAdversarialReviewPrimaryFinding(value);
  if (!primary) return typed.map((finding) => finding.raw);
  const index = typed.findIndex(
    (finding) => finding.kind === primary.kind && finding.claim === primary.claim,
  );
  const ordered = index > 0
    ? [typed[index], ...typed.slice(0, index), ...typed.slice(index + 1)]
    : typed;
  return ordered.map((finding) => finding.raw);
}

/**
 * Every stored field whose value LEADS with a closed-vocabulary token, and the map that
 * turns that token into the words the product actually shows.
 *
 * Anything not a string is passed through untouched (a stored `null` stays `null`), and
 * `incumbentParityPhrase` returns free prose unchanged, so nothing here invents a claim.
 */
const PRESENTABLE_FIELDS: Record<string, (value: unknown) => unknown> = {
  red_team_verdict: (value) => (typeof value === 'string' ? adversarialReviewLabel(value) : value),
  incumbent_parity: (value) => (typeof value === 'string' ? incumbentParityPhrase(value) : value),
  adjacent_market_parity: (value) =>
    (typeof value === 'string' ? incumbentParityPhrase(value) : value),
};

/** Depth guard only — report/candidate records are plain JSON trees, never cyclic. */
const PRESENTABLE_MAX_DEPTH = 12;

/**
 * A stored record with every closed-vocabulary value replaced by its product wording.
 *
 * A model repeats the vocabulary it is handed, so a raw record must never be handed to one:
 * the analyst read `red_team_verdict: "killed"` off its own tool result and told the owner
 * their still-selectable candidate was killed. Record keys are preserved (report paths stay
 * quotable); recognised token values are mapped, invalid red-team finding entries are dropped
 * at the closed contract boundary, and every other branch of the tree is copied through as-is.
 */
export function presentableRecord<T>(value: T, depth = 0): T {
  if (depth >= PRESENTABLE_MAX_DEPTH || value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) {
    return value.map((item) => presentableRecord(item, depth + 1)) as unknown as T;
  }
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, child]) => {
      const present = PRESENTABLE_FIELDS[key];
      if (key === 'red_team_verdict') {
        const findings = (value as Record<string, unknown>).red_team_findings;
        return [key, typeof child === 'string' ? adversarialReviewLabel(child, findings) : child];
      }
      if (key === 'red_team_findings') {
        return [key, presentableRecord(primaryFindingFirst(child), depth + 1)];
      }
      return [key, present ? present(child) : presentableRecord(child, depth + 1)];
    }),
  ) as T;
}

/**
 * The same mapping for a value already detached from its key — evidence search returns
 * matched LEAVES, where the field name survives only as the last segment of the path.
 */
export function presentableFieldValue(fieldName: string, value: unknown): unknown {
  const present = PRESENTABLE_FIELDS[fieldName.replace(/\[\d+\]$/, '')];
  return present ? present(value) : value;
}

/** Evidence-check question ids are slugs (`buyer_will_pay`), never copy. */
export function challengeQuestionLabel(value: string): string {
  return humanizeEnumToken(value);
}

export const experimentMethodLabel = (value: string | null | undefined): string =>
  label(EXPERIMENT_METHOD, value);
export const evidenceSignalLabel = (value: string | null | undefined): string =>
  label(EVIDENCE_SIGNAL, value);
export const challengeConsensusLabel = (value: string | null | undefined): string =>
  label(CHALLENGE_CONSENSUS, value);
export const handoffActionLabel = (value: string | null | undefined): string =>
  label(HANDOFF_ACTION, value);
export const hostedRunStateLabel = (value: string | null | undefined): string =>
  label(HOSTED_RUN_STATE, value);
export const founderFitVerdictLabel = (value: string | null | undefined): string =>
  label(FOUNDER_FIT_VERDICT, value);
export const walletClassLabel = (value: string | null | undefined): string =>
  label(WALLET_CLASS, value);
