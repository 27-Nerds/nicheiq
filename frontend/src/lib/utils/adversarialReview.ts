import type { RedTeamFinding, RedTeamFindingKind } from "$lib/types/job";

type AdversarialReviewFields = {
  incumbent_parity?: unknown;
  red_team_verdict?: unknown;
  red_team_caveats?: unknown;
  red_team_findings?: unknown;
};

interface NormalizedAdversarialReviewFields {
  incumbentParity: string;
  verdict: string;
  caveats: string[];
  findings: RedTeamFinding[];
}

export type AdversarialSeverity = "killed" | "weakened";

export interface AdversarialReviewPrimaryFinding {
  basis: "counterevidence" | "incomplete_evidence";
  kind: RedTeamFindingKind;
  claim: string;
  label: string;
  chipLabel: string;
  summaryOpener: string;
}

export interface AdversarialReviewFinding {
  /** Section/card heading, e.g. "Adversarial review: Premise unproven". */
  label: string;
  /** Compact chip text for rows and facet strips. */
  chipLabel: string;
  details: string[];
  severity: AdversarialSeverity;
  /** Atomic authority for both the reason-specific label and the claim it describes. */
  primary?: AdversarialReviewPrimaryFinding;
}

const AFFIRMATIVE_FINDING_KINDS = new Set<RedTeamFindingKind>([
  "verified_incumbent_overlap",
  "verified_free_or_bundled_alternative",
  "verified_payer_mismatch",
  "verified_modal_failure",
]);

const FINDING_KINDS = new Set<RedTeamFindingKind>([
  ...AFFIRMATIVE_FINDING_KINDS,
  "evidence_gap",
]);

const TYPED_REVIEW_COPY: Record<RedTeamFindingKind, {
  label: string;
  chipLabel: string;
  summaryOpener: string;
}> = {
  verified_incumbent_overlap: {
    label: "Verified incumbent overlap",
    chipLabel: "Incumbent overlap",
    summaryOpener: "The adversarial review found verified incumbent overlap",
  },
  verified_free_or_bundled_alternative: {
    label: "Verified free or bundled alternative",
    chipLabel: "Free or bundled alternative",
    summaryOpener: "The adversarial review found a verified free or bundled alternative",
  },
  verified_payer_mismatch: {
    label: "Verified payer mismatch",
    chipLabel: "Payer mismatch",
    summaryOpener: "The adversarial review found a verified payer mismatch",
  },
  verified_modal_failure: {
    label: "Verified modal failure",
    chipLabel: "Modal failure",
    summaryOpener: "The adversarial review found a verified modal failure",
  },
  evidence_gap: {
    label: "Evidence incomplete",
    chipLabel: "Evidence incomplete",
    summaryOpener: "The adversarial review found the decision-critical evidence incomplete",
  },
};

const GENERIC_INCOMPLETE_EVIDENCE_CLAIM =
  "The review did not establish decision-critical evidence.";

function isRedTeamFindingKind(value: unknown): value is RedTeamFindingKind {
  return typeof value === "string" && FINDING_KINDS.has(value as RedTeamFindingKind);
}

function normalizedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function validTypedFindings(value: unknown): RedTeamFinding[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((finding): RedTeamFinding[] => {
    if (!finding || typeof finding !== "object") return [];
    const record = finding as Record<string, unknown>;
    const claim = normalizedString(record.claim);
    if (!claim || !isRedTeamFindingKind(record.kind)) return [];
    return [{ claim, kind: record.kind }];
  });
}

function normalizeAdversarialReviewFields(
  idea: AdversarialReviewFields,
): NormalizedAdversarialReviewFields {
  const findings = validTypedFindings(idea.red_team_findings);
  const caveats = Array.isArray(idea.red_team_caveats)
    ? idea.red_team_caveats.map(normalizedString).filter(Boolean)
    : [];
  const storedVerdict = normalizedString(idea.red_team_verdict);
  const verdict = storedVerdict.toLowerCase() === "killed"
    && Array.isArray(idea.red_team_findings)
    && !findings.some((finding) => AFFIRMATIVE_FINDING_KINDS.has(finding.kind))
      ? "weakened"
      : storedVerdict;
  return {
    incumbentParity: normalizedString(idea.incumbent_parity),
    verdict,
    caveats,
    findings,
  };
}

export function resolveAdversarialReviewPrimaryFinding(
  findings: unknown,
): AdversarialReviewPrimaryFinding | undefined {
  const typed = validTypedFindings(findings);
  const affirmative = typed.find((finding) => AFFIRMATIVE_FINDING_KINDS.has(finding.kind));
  const finding = affirmative ?? typed.find((candidate) => candidate.kind === "evidence_gap");
  if (!finding) {
    return Array.isArray(findings)
      ? {
          basis: "incomplete_evidence",
          kind: "evidence_gap",
          claim: GENERIC_INCOMPLETE_EVIDENCE_CLAIM,
          ...TYPED_REVIEW_COPY.evidence_gap,
        }
      : undefined;
  }
  return {
    basis: affirmative ? "counterevidence" : "incomplete_evidence",
    kind: finding.kind,
    claim: finding.claim.trim(),
    ...TYPED_REVIEW_COPY[finding.kind],
  };
}

/**
 * User-facing name for the internal `red_team_verdict === "killed"` state.
 *
 * "Killed" is our word, not the user's, and it reads as a verdict on the whole idea.
 * The review only ever tested the PREMISE — usually that a reachable buyer wants this —
 * and reported that it could not find evidence for it. "Premise unproven" says that,
 * and leaves room for the premise to turn out true. The field name stays `killed`.
 */
export const PREMISE_UNPROVEN_LABEL = "Premise unproven";

/**
 * Why a premise-unproven idea can still carry high scores. Every other criterion rates
 * the idea CONDITIONALLY — market fit, novelty and feasibility all describe the world in
 * which the premise holds — so a top score sitting next to this finding is the system
 * working, not a contradiction.
 */
export const PREMISE_UNPROVEN_CODA =
  "This is a verdict on the premise, not on the idea: the other scores describe how well "
  + "it would work if the premise holds, which is why they can stay high. Test the premise "
  + "before you build. The idea keeps its rank and stays selectable.";

/** One-line score framing for surfaces that list the individual criteria. */
export const PREMISE_UNPROVEN_SCORE_NOTE =
  "These scores assume the premise holds. The adversarial review could not confirm it, so "
  + "read them as the upside if it does.";

/** Selection-eligibility gate over the effective typed/legacy review state. */
export function isPremiseUnproven(
  idea: Pick<AdversarialReviewFields, "red_team_verdict" | "red_team_findings">,
): boolean {
  return normalizeAdversarialReviewFields(idea).verdict.toLowerCase() === "killed";
}

/**
 * Explains the split a user sees when the highest-scoring idea is not the recommended one:
 * the top score is real, but the review either found typed counterevidence or could not
 * establish the premise, so the recommendation moves down the list. Both ideas keep their place.
 */
export function recommendationSplitNote(
  topTitle: string,
  recommendedTitle: string,
  topIdea?: Pick<AdversarialReviewFields, "red_team_findings">,
): string {
  const primary = resolveAdversarialReviewPrimaryFinding(topIdea?.red_team_findings);
  const reason = primary
    ? `${primary.summaryOpener.replace(/^The /, "the ")}: ${primary.claim}`
    : "the adversarial review could not confirm its premise";
  return `${topTitle} scores highest, but ${reason}, `
    + `so the recommendation goes to ${recommendedTitle}: the strongest idea that `
    + `came through review intact. ${topTitle} keeps its rank and you can still shortlist it.`;
}

const EVIDENCE_PREFIX = /^shipped by evidence\s*:\s*/i;

export function isAdversarialEvidenceParity(value: unknown): boolean {
  return EVIDENCE_PREFIX.test(normalizedString(value));
}

export function directIncumbentParity(
  idea: Pick<AdversarialReviewFields, "incumbent_parity">,
): string | null {
  const parity = normalizeAdversarialReviewFields(idea).incumbentParity;
  if (
    !parity
    || parity.toLowerCase().startsWith("none")
    || isAdversarialEvidenceParity(parity)
  ) {
    return null;
  }
  return parity;
}

export function noDirectIncumbentFound(
  idea: Pick<AdversarialReviewFields, "incumbent_parity">,
): boolean {
  return normalizeAdversarialReviewFields(idea).incumbentParity
    .toLowerCase().startsWith("none");
}

// Parity findings are stored with a closed-vocabulary class prefix
// ("shipped by X: …", "bundled_free (X): …"). The class carries meaning the bare token
// does not, so rendering it raw shows the user an internal enum. These phrasings mirror
// `backend/src/utils/selectionVocabulary.ts` exactly — the analyst says the same words
// about the same finding, and the two must not drift.
const PARITY_NAMED: Record<string, string> = {
  shipped: "Already shipped by %v",
  partial: "Partly covered by %v",
  substitute: "Buyers already get this outcome from %v",
  bundled_free: "Already included free with %v",
};

// The same classes when the vendor slot holds no product. The review writes `red-team` /
// `evidence` there: such a finding names an alternative CLASS, not a product, and calling
// it a competitor would lend it a vendor's authority it never had.
const PARITY_CLASS_ONLY: Record<string, string> = {
  shipped: "This is already shipped elsewhere",
  partial: "This is already partly covered elsewhere",
  substitute: "Buyers already get this outcome another way",
  bundled_free: "This is already available free elsewhere",
};

const CLASS_ONLY_SUFFIX = " (an alternative class, no product named)";

/**
 * A "none" stamp is a RETRIEVAL RESULT, never a fact about the market. The parity probe builds
 * its queries out of the idea's OWN vocabulary, so the wording of the pitch decides the verdict:
 * a live run shipped "none found" for a #1 recommendation while a same-pain sibling carried
 * "partial by Synup". Measured over stored runs, 591 ideas carry a "none" stamp and ~90% of them
 * sit in a run that already names an incumbent on another idea. So the copy states the search
 * result and not the conclusion. Twin of the Python block's NONE_FOUND_NOTE
 * (src/nicheiq/report/idea_validation_block.py) and of the backend copy of this helper — the
 * three stacks describe one finding and must not contradict each other in one product.
 */
// ONE literal, on one line, in both copies: the anti-drift gate compares the two files'
// phrase literals as text, and a concatenation split differently on the two sides would read
// as drift.
export const NONE_SURFACED_PHRASE = "Our searches did not surface a direct competitor. They run on this idea's own wording, so a rival that describes itself differently can be missed.";

const NOT_A_VENDOR = /^(?:red[-\s]?team|evidence)$/i;
/** `<class> by <vendor>: <evidence>` / `<class> (<vendor>): <evidence>`, either half optional. */
const PARITY_SHAPE = /^([a-z_]+)(?:\s+by\s+([^:]+?)|\s*\(([^)]*)\))?\s*(?::\s*([\s\S]*))?$/i;

/**
 * A parity finding with its class prefix turned into words. Free prose carrying no known
 * class is returned untouched — it is already readable, and rewriting it would invent a claim.
 */
export function incumbentParityPhrase(value: unknown): string {
  const raw = normalizedString(value);
  if (!raw) return "";
  // The `/^none\b/` TEST is load-bearing and unchanged (~139 consumers parse this prefix);
  // only what it RENDERS changed — see NONE_SURFACED_PHRASE.
  if (/^none\b/i.test(raw)) return NONE_SURFACED_PHRASE;

  const match = PARITY_SHAPE.exec(raw);
  if (!match) return raw;
  const klass = match[1].toLowerCase();
  if (!(klass in PARITY_NAMED)) return raw;

  const vendor = (match[2] ?? match[3] ?? "").trim();
  const evidence = (match[4] ?? "").trim();
  const head = vendor && !NOT_A_VENDOR.test(vendor)
    ? PARITY_NAMED[klass].replace("%v", vendor)
    : PARITY_CLASS_ONLY[klass] + CLASS_ONLY_SUFFIX;
  return evidence ? joinParityEvidence(head, vendor, evidence) : head;
}

/**
 * Evidence routinely re-opens with the vendor as its SUBJECT ("X ships Y") — joining
 * that with a colon produced "…by X: X ships Y", a broken-reading template stitch
 * (twin of the backend's selectionVocabulary rule and the Python block's
 * `_display_parity`). A subject echo joins as its own sentence; a duplicated LABEL
 * echo ("X: Y") is dropped; anything else keeps the colon join.
 */
function joinParityEvidence(head: string, vendor: string, evidence: string): string {
  if (vendor) {
    const escaped = vendor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const m = evidence.match(new RegExp(`^${escaped}(?=[\\s:,]|$)([\\s:,\\-\\u2013\\u2014]*)`, "i"));
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

export function adversarialReviewFinding(
  idea: AdversarialReviewFields,
): AdversarialReviewFinding | null {
  const normalized = normalizeAdversarialReviewFields(idea);
  const verdict = normalized.verdict;
  const parity = normalized.incumbentParity;
  const evidenceDetail = isAdversarialEvidenceParity(parity)
    ? parity.replace(EVIDENCE_PREFIX, "").trim()
    : "";
  const typedFindings = normalized.findings;
  // Pass the raw field so [] / all-invalid arrays remain distinguishable from legacy
  // records where the typed field was omitted or null.
  const primary = resolveAdversarialReviewPrimaryFinding(idea.red_team_findings);
  const details = [
    primary?.claim ?? "",
    ...typedFindings.map((finding) => finding.claim),
    ...normalized.caveats,
    evidenceDetail,
  ]
    .filter((detail, index, all) => detail && all.indexOf(detail) === index);

  const v = verdict?.toLowerCase();
  const killed = v === "killed";
  const weakened = v === "weakened";
  // killed + evidence-marked render exactly as today (incl. empty details);
  // a bare `weakened` with nothing citable is an unfalsifiable label — suppress it.
  if (!killed && !evidenceDetail && !(weakened && details.length > 0)) return null;
  const severity: AdversarialSeverity = killed ? "killed" : "weakened";

  // A killed verdict is renamed for the reader; every other verdict keeps its own word.
  const typedCopy = primary ?? null;
  const verdictLabel = typedCopy?.label ?? (killed
    ? PREMISE_UNPROVEN_LABEL
    : verdict
      ? verdict.charAt(0).toUpperCase() + verdict.slice(1).toLowerCase()
      : null);
  return {
    label: verdictLabel ? `Adversarial review: ${verdictLabel}` : "Adversarial review",
    chipLabel: typedCopy?.chipLabel ?? (killed ? PREMISE_UNPROVEN_LABEL : "Weakened"),
    details,
    severity,
    ...(primary ? { primary } : {}),
  };
}

/**
 * Compact one-liner for chip tooltips: what the finding means, the first objection's
 * opening sentence, and a count of the rest. The full findings render in the idea
 * overlay, not the tooltip.
 */
export interface AdversarialSummaryContext {
  /** True when the caller is already INSIDE the idea overlay. "Open the idea for the
   *  full review" is a dead instruction there — the review is on the same screen. */
  inIdeaDetail?: boolean;
}

export function adversarialReviewSummary(
  finding: AdversarialReviewFinding,
  context: AdversarialSummaryContext = {},
): string {
  const killed = finding.severity === "killed";
  const typedCopy = finding.primary ?? null;
  // Same pointer, phrased for where the reader actually is.
  const whereSentence = context.inIdeaDetail
    ? "The full review is in this idea's findings below."
    : "Open the idea for the full review.";
  const whereClause = context.inIdeaDetail
    ? "see the full review in this idea's findings below."
    : "open the idea for the full review.";
  const opener = typedCopy?.summaryOpener ?? (killed
    ? "The adversarial review could not find evidence for this idea's premise"
    : "");
  const first = finding.details[0]?.trim() ?? "";
  if (!first) {
    if (killed) {
      return `${opener}. The other scores describe how well it would work if the premise `
        + `holds. ${whereSentence}`;
    }
    return `The adversarial review recorded a decision-critical objection — ${whereClause}`;
  }
  const sentenceEnd = first.indexOf(". ");
  let lead = sentenceEnd > 0 && sentenceEnd <= 200 ? first.slice(0, sentenceEnd + 1) : first;
  if (lead.length > 200) lead = `${lead.slice(0, 200).trimEnd()}…`;
  const rest = finding.details.length - 1;
  if (typedCopy) {
    const more = rest > 0 ? ` +${rest} more finding${rest === 1 ? "" : "s"}.` : ".";
    return `${opener}: ${lead}${more} ${whereSentence}`;
  }
  if (killed) {
    const more = rest > 0 ? ` +${rest} more objection${rest === 1 ? "" : "s"}.` : "";
    return `${opener}: ${lead}${more} The other scores describe how well it would work if `
      + `the premise holds. ${whereSentence}`;
  }
  const more = rest > 0 ? ` +${rest} more objection${rest === 1 ? "" : "s"} —` : " —";
  return `${lead}${more} ${whereClause}`;
}

/** Complete verdict copy for surfaces that render the review as a paragraph. */
export function adversarialReviewVerdictSummary(
  idea: AdversarialReviewFields,
  context: AdversarialSummaryContext = {},
): string | null {
  const finding = adversarialReviewFinding(idea);
  if (finding) return adversarialReviewSummary(finding, context);

  const verdict = normalizeAdversarialReviewFields(idea).verdict.toLowerCase();
  if (verdict === "survives") {
    return "Our adversarial reviewer raised no killing objection. Residual risks:";
  }
  if (verdict === "weakened") {
    return "Our adversarial reviewer found real weaknesses. The objections that stuck:";
  }
  return null;
}

export function adversarialReviewCoda(
  finding: AdversarialReviewFinding,
  context: "decision" | "scores",
): string {
  if (finding.primary?.basis === "counterevidence") {
    return context === "scores"
      ? "These scores do not erase the verified counterevidence. Weigh that finding before you build."
      : "This is verified counterevidence, not missing evidence. The candidate keeps its rank and stays selectable; weigh the finding before committing.";
  }
  if (finding.severity === "weakened") {
    return "This candidate remains available — review these concerns before committing to it.";
  }
  return context === "scores" ? PREMISE_UNPROVEN_SCORE_NOTE : PREMISE_UNPROVEN_CODA;
}
