type AdversarialReviewFields = {
  incumbent_parity?: string | null;
  red_team_verdict?: string | null;
  red_team_caveats?: string[] | null;
};

export type AdversarialSeverity = "killed" | "weakened";

export interface AdversarialReviewFinding {
  /** Section/card heading, e.g. "Adversarial review: Premise unproven". */
  label: string;
  /** Compact chip text for rows and facet strips. */
  chipLabel: string;
  details: string[];
  severity: AdversarialSeverity;
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

/** True when the adversarial review returned the internal `killed` verdict. */
export function isPremiseUnproven(
  idea: Pick<AdversarialReviewFields, "red_team_verdict">,
): boolean {
  return idea.red_team_verdict?.trim().toLowerCase() === "killed";
}

/**
 * Explains the split a user sees when the highest-scoring idea is not the recommended one:
 * the top score is real, the premise behind it is not established, so the recommendation
 * moves down the list. Both ideas keep their place.
 */
export function recommendationSplitNote(topTitle: string, recommendedTitle: string): string {
  return `${topTitle} scores highest, but the adversarial review could not confirm its `
    + `premise, so the recommendation goes to ${recommendedTitle}: the strongest idea that `
    + `came through review intact. ${topTitle} keeps its rank and you can still shortlist it.`;
}

const EVIDENCE_PREFIX = /^shipped by evidence\s*:\s*/i;

export function isAdversarialEvidenceParity(value: string | null | undefined): boolean {
  return EVIDENCE_PREFIX.test(value?.trim() ?? "");
}

export function directIncumbentParity(
  idea: Pick<AdversarialReviewFields, "incumbent_parity">,
): string | null {
  const parity = idea.incumbent_parity?.trim();
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
  return idea.incumbent_parity?.trim().toLowerCase().startsWith("none") ?? false;
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
const NOT_A_VENDOR = /^(?:red[-\s]?team|evidence)$/i;
/** `<class> by <vendor>: <evidence>` / `<class> (<vendor>): <evidence>`, either half optional. */
const PARITY_SHAPE = /^([a-z_]+)(?:\s+by\s+([^:]+?)|\s*\(([^)]*)\))?\s*(?::\s*([\s\S]*))?$/i;

/**
 * A parity finding with its class prefix turned into words. Free prose carrying no known
 * class is returned untouched — it is already readable, and rewriting it would invent a claim.
 */
export function incumbentParityPhrase(value: string | null | undefined): string {
  const raw = value?.trim();
  if (!raw) return "";
  if (/^none\b/i.test(raw)) return "No competing product found";

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
  const verdict = idea.red_team_verdict?.trim();
  const parity = idea.incumbent_parity?.trim();
  const evidenceDetail = isAdversarialEvidenceParity(parity)
    ? parity!.replace(EVIDENCE_PREFIX, "").trim()
    : "";
  const details = [...(idea.red_team_caveats ?? []), evidenceDetail]
    .map((detail) => detail.trim())
    .filter((detail, index, all) => detail && all.indexOf(detail) === index);

  const v = verdict?.toLowerCase();
  const killed = v === "killed";
  const weakened = v === "weakened";
  // killed + evidence-marked render exactly as today (incl. empty details);
  // a bare `weakened` with nothing citable is an unfalsifiable label — suppress it.
  if (!killed && !evidenceDetail && !(weakened && details.length > 0)) return null;
  const severity: AdversarialSeverity = killed ? "killed" : "weakened";

  // A killed verdict is renamed for the reader; every other verdict keeps its own word.
  const verdictLabel = killed
    ? PREMISE_UNPROVEN_LABEL
    : verdict
      ? verdict.charAt(0).toUpperCase() + verdict.slice(1).toLowerCase()
      : null;
  return {
    label: verdictLabel ? `Adversarial review: ${verdictLabel}` : "Adversarial review",
    chipLabel: killed ? PREMISE_UNPROVEN_LABEL : "Weakened",
    details,
    severity,
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
  // Same pointer, phrased for where the reader actually is.
  const whereSentence = context.inIdeaDetail
    ? "The full review is in this idea's findings below."
    : "Open the idea for the full review.";
  const whereClause = context.inIdeaDetail
    ? "see the full review in this idea's findings below."
    : "open the idea for the full review.";
  const opener = killed
    ? "The adversarial review could not find evidence for this idea's premise"
    : "";
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
  if (killed) {
    const more = rest > 0 ? ` +${rest} more objection${rest === 1 ? "" : "s"}.` : "";
    return `${opener}: ${lead}${more} The other scores describe how well it would work if `
      + `the premise holds. ${whereSentence}`;
  }
  const more = rest > 0 ? ` +${rest} more objection${rest === 1 ? "" : "s"} —` : " —";
  return `${lead}${more} ${whereClause}`;
}
