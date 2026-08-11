/**
 * Canonical client copy for the Decision Lab guidance spine.
 *
 * This module is the single source of truth for guide/toolbox/commit copy
 * (plan: quiet-nibbling-plum, Phase 1). Server-projected `reason` strings are
 * a fallback only; the per-kind copy here overrides them.
 *
 * Copy rules (binding, grep-gated):
 * - No em or en dashes anywhere in this module.
 * - Banned words: confidence, conviction, insight(s), smarter, powerful,
 *   supercharge, unlock. "Validate" is reserved for Deep Research.
 * - Record-line values are plain text; mono/uppercase comes from CSS.
 */

import type {
  SelectionDecisionNextAction,
  SelectionDecisionNextActionKind,
} from "$lib/types/selectionDecisionState";

// ── Core noun: the pool of ideas being assembled ──
//
// ONE word for the saved collection ("shortlist"). "Choose ideas" is the verb
// for adding to it, never a name for the collection itself. The synonyms
// "Selection", "Ranked candidates", and "candidates" (as the primary noun) are
// retired; a ranked LIST heading may still read "Ranked ideas".

/** Inline lowercase noun for the saved collection, e.g. "your shortlist". */
export const SHORTLIST_NOUN = "shortlist";
/** Breadcrumb / page title for the collection. */
export const SHORTLIST_TITLE = "Research shortlist";
/** Verb/action for adding an idea to the shortlist (never the collection noun). */
export const CHOOSE_IDEAS_LABEL = "Choose ideas";
/** Heading for the ranked pool of ideas (replaces "Ranked candidates"). */
export const RANKED_LIST_HEADING = "Ranked ideas";

// ── Next-step panel ──

export const GUIDE_EYEBROW = "Analyst · Suggested next";

export const ACTION_TITLES: Record<SelectionDecisionNextActionKind, string> = {
  select_candidate: "Review the top idea",
  add_decision_context: "Add build limits",
  analyze_founder_fit: "Review fit for you",
  stress_test_evidence: "Check the evidence",
  capture_assumption: "Save a question to resolve",
  draft_test: "Plan a test",
  review_test_brief: "Review the test brief",
  launch_test: "Launch the test",
  monitor_test: "Review the active test",
  record_conclusion: "Record the test conclusion",
  start_deep_research: "Review and start",
};

/** Per-kind card prose. Overrides the server `reason`; the server string is
 *  only used for a kind this map does not know about. */
const ACTION_BODIES: Record<SelectionDecisionNextActionKind, string> = {
  select_candidate:
    "Open the top candidate, check its pain evidence against your own read, and shortlist it if it holds up.",
  add_decision_context:
    "Save your build limits once: time, budget, build model, and reach. Comparisons use them without changing the research score.",
  analyze_founder_fit:
    "Check each shortlisted pick against the time, budget, and reach you actually have.",
  stress_test_evidence:
    "Review one question that could change what you research. This uses sources already saved with this project.",
  capture_assumption:
    "Save an unanswered question so you can revisit it or turn it into a small test.",
  draft_test:
    "Draft the cheapest test that would answer the open question on this pick.",
  review_test_brief:
    "A test brief is drafted. Review it and decide whether to launch.",
  launch_test:
    "The test brief is locked. Launch it to collect real signal.",
  monitor_test:
    "A test is running. Review the signal collected so far.",
  record_conclusion:
    "The test window is complete. Record the outcome so your docket reflects it.",
  start_deep_research:
    "Confirm the selected ideas and total cost before Deep Research starts.",
};

/** Re-do suggestions for already-completed steps (backend `variant` field;
 *  coded defensively, the field may be absent). */
const VARIANT_BODIES: Record<"rerun" | "refresh", string> = {
  rerun: "Your evidence changed. This check is worth re-running.",
  refresh: "Your shortlist changed. Refresh founder fit to match.",
};

export function actionBody(action: SelectionDecisionNextAction): string {
  const variant = action.variant;
  if (variant && VARIANT_BODIES[variant]) return VARIANT_BODIES[variant];
  return ACTION_BODIES[action.kind] ?? action.reason;
}

/** Primary-button label: verb plus the concrete candidate when one is named. */
export function actionCta(action: SelectionDecisionNextAction): string {
  const title = action.ideas[0]?.title?.trim();
  if (title && action.kind === "select_candidate") return `Review ${title}`;
  if (title && action.kind === "stress_test_evidence") return `Check the evidence for ${title}`;
  return ACTION_TITLES[action.kind] ?? action.reason;
}

export function docketReadyTitle(candidates: number, checks: number): string {
  const candidateNoun = candidates === 1 ? "candidate" : "candidates";
  const checkNoun = checks === 1 ? "check" : "checks";
  return `Docket ready: ${candidates} ${candidateNoun}, ${checks} ${checkNoun} on file`;
}

export const GUIDE_FALLBACK_TITLE = "Choose a decision tool";
export const GUIDE_FALLBACK_BODY =
  "The suggested next step is unavailable right now. Every decision tool below stays open.";
export const GUIDE_LOADING = "Updating the suggested next step…";
export const GUIDE_RETRY_NOTICE = "We could not refresh the suggested next step.";
export const GUIDE_RETRY_ACTION = "Retry suggestion";

// ── Canonical action-label family ──

export const ASK_ANALYST_LABEL = "Ask analyst";
export const STRESS_TEST_EVIDENCE_LABEL = "Check the evidence";
export const DRAFT_TEST_BRIEF_LABEL = "Plan a test";

export function founderContextLabel(hasProfile: boolean): string {
  return hasProfile ? "Edit build limits" : "Add build limits";
}

export const SAVE_FOUNDER_CONTEXT_LABEL = "Save build limits";
export const FOUNDER_CONTEXT_OVERLAY_TITLE = "Your build limits";

/** Named-lens stress-test CTA: "Stress-test {lens} evidence" once a lens is
 *  known; falls back to the generic label otherwise. */
export function stressTestLabel(lensLabel?: string | null): string {
  return lensLabel ? `Review: ${lensLabel}` : STRESS_TEST_EVIDENCE_LABEL;
}

/** Shared receipt copy for the constraint-led variant twins
 *  (FounderFitReshapePanel / ExperimentNarrowingPanel). */
export const EVALUATED_ACCEPTED_LABEL = "Evaluated. Added to ranked ideas.";
export const EVALUATED_DEMOTED_LABEL = "Evaluated. This variant did not clear the market-fit bar.";

// ── Canonical tool names ──
//
// ONE name per tool, used by the decision rail, the workspace nav, the page
// headings, and the analyst. These names previously drifted across surfaces
// ("Check the biggest uncertainty" / "Challenge" / "Biggest unknowns" all named
// the same tool), so a novice had to re-recognize each tool three times.

export const TOOL_NAMES = {
  compare: "Compare trade-offs",
  challenge: "Check the evidence",
  test: "Plan a test",
  /** Divergence op (a): branch new directions from the CURRENT ideas. */
  branch: "Branch a new direction",
  /** Divergence op (b): generate a fresh batch of ideas from scratch. */
  newBatch: "Add another batch",
} as const;

// ── Divergence ops: two DISTINCT operations, kept apart on purpose ──
//
// (a) BRANCH: take one or two selected ideas and branch a new direction from
//     them (the ConceptForge branch form). This is distinct from generating a
//     new batch from scratch.
// (b) NEW BATCH: generate a fresh batch of ideas unrelated to the shortlist
//     (the regenerate overlay). Previously "More ideas".
export const BRANCH_DIRECTION_LABEL = TOOL_NAMES.branch;
export const GENERATE_BATCH_LABEL = TOOL_NAMES.newBatch;

/** Optional eyebrow for the evidence tool's page. Purges "confidence". */
export const EVIDENCE_CHECK_EYEBROW = "Optional evidence check";

// ── Compare sub-views ──
// Two views of the same comparison; the label is identical everywhere it
// appears (page tab, action title). "Fit for you", never "Fit for me".
export const COMPARE_VIEW_MARKET_LABEL = "Research evidence";
export const COMPARE_VIEW_FOUNDER_LABEL = "Fit for you";

// ── Commit CTA ──
// "Review and start" everywhere BEFORE the review page; the priced
// "Start Deep Research · N credits" only on the review page itself.
export const REVIEW_AND_START_LABEL = "Review and start";
/** Priced commit CTA, review page only. */
export function startDeepResearchLabel(credits: number): string {
  return `Start Deep Research · ${costLine(credits)}`;
}

/** Sub-nav of the selection workspace. Labels match TOOL_NAMES exactly; only
 *  the supporting line differs per surface. */
export const WORKSPACE_ROUTES = [
  { slug: "compare", label: TOOL_NAMES.compare, detail: "See the important trade-offs" },
  { slug: "risks", label: TOOL_NAMES.challenge, detail: "Review a question that could change your scope" },
] as const;

/**
 * The two decision-critical tools for picking what to pay to research: compare
 * the finalists, and check whether the evidence holds up. These are foregrounded
 * as navigation. "Plan a test" and "Branch a new direction" are real, but they
 * are a post-selection activity and a divergence escape-hatch respectively —
 * reached contextually (from an evidence gap / a "none of these fit?" action),
 * never as co-equal nav. Presenting all four equally was the felt complexity.
 */
export const PRIMARY_TOOL_SLUGS: readonly string[] = ["compare", "risks"];

// ── Branch-a-direction (ConceptForge) panel copy — divergence op (a) ──

/** Cluster eyebrow, deliberately NOT the tool name: the overlay title already
 *  reads "Branch a new direction", so repeating it verbatim above itself said
 *  nothing. */
export const BRANCH_PANEL_EYEBROW = "Decision tools";
export const BRANCH_PANEL_TITLE = "Branch a new direction";
export const BRANCH_PANEL_INTRO =
  "This branches one or two exact candidate revisions into a small set of unevaluated directions. Your originals stay unchanged, their scores do not transfer, and only a direction you explicitly confirm enters paid evaluation.";
export const BRANCH_PURPOSE_LABEL = "Direction purpose";
export const CLOSE_BRANCH_LABEL = "Close direction brief";
export const GENERATE_DIRECTIONS_LABEL = "Generate directions";
export const GENERATING_DIRECTIONS_LABEL = "Generating directions…";

/** Regenerate overlay CTA — divergence op (b). Price stays at the gate. */
export function generateNewBatchLabel(seedCost: number | null | undefined): string {
  const cost = seedCost ?? null;
  return cost != null && cost > 0
    ? `${TOOL_NAMES.newBatch} · ${costLine(cost)}`
    : TOOL_NAMES.newBatch;
}

/** Lock hints for steps that need a shortlist first. These name the action that
 *  unlocks the step, not the fact that it is locked. */
export const STEP_LOCK_HINTS = {
  compare: "Shortlist two ideas to compare them",
  challenge: "Shortlist an idea to check the evidence",
  test: "Shortlist an idea to plan a test",
  branch: "Shortlist an idea to branch it",
} as const;

export const FIT_SAVED_RECORD = "FIT · SAVED";

// ── Record-line helpers (Phase-0 adjudication: one global tally) ──

/** CHECK = one completed challenge run that is still current. */
export function checkCount(n: number): string {
  return `${n} CHECK${n === 1 ? "" : "S"}`;
}

/** Staleness is a suffix; omitted entirely at 0. */
export function staleSuffix(s: number): string {
  return s > 0 ? ` · ${s} STALE` : "";
}

export function briefCount(n: number): string {
  return `${n} BRIEF${n === 1 ? "" : "S"}`;
}

/** First-hand evidence the owner saved themselves ("Your evidence" in the ledger),
 *  counted separately from CHECKS: a check is a run, this is material the owner
 *  supplied. */
export function ownerEvidenceCount(n: number): string {
  return `${n} EVIDENCE ADDED`;
}

/** Memo state line: `2 SHORTLISTED · 3 CHECKS · 1 EVIDENCE ADDED · CONTEXT SAVED`. */
export function guideRecordLine(input: {
  shortlisted: number;
  checks: number;
  stale: number;
  contextSaved: boolean;
  ownerEvidence?: number;
}): string {
  const parts = [
    `${input.shortlisted} SHORTLISTED`,
    `${checkCount(input.checks)}${staleSuffix(input.stale)}`,
  ];
  // Omitted at 0 (unlike CHECKS, which is a required-looking tally): an untaken
  // optional step should not read as a gap in the record.
  if (input.ownerEvidence) parts.push(ownerEvidenceCount(input.ownerEvidence));
  if (input.contextSaved) parts.push("CONTEXT SAVED");
  return parts.join(" · ");
}

/** Null-safe seed-cost phrase, e.g. "2 credits". Price surfaces at the gate;
 *  callers compose the sentence. */
export function costLine(seedCost: number | null | undefined): string {
  if (seedCost == null || !Number.isFinite(seedCost)) return "credits";
  return `${seedCost} credit${seedCost === 1 ? "" : "s"}`;
}

/** The branch panel's single upstream price mention (guardrail 14): the tile
 *  tooltip and the forge's first screen state the same sentence; the gate itself
 *  is the per-option Evaluate button. Null-safe via costLine. */
export function branchCostNote(seedCost: number | null | undefined): string {
  return `Generating directions is free. Evaluating a direction costs ${costLine(seedCost)}.`;
}

// ── Paid-action error and long-run copy ──

/** 409 PRICE_CHANGED after the price was successfully re-fetched. */
export const PRICE_CHANGED_RETRY =
  "The price changed. Review the new cost and try again.";
/** 409 PRICE_CHANGED when the re-fetch itself failed. */
export const PRICE_CHANGED_RELOAD =
  "The price changed. Reload the page to see the new cost.";

/** Shown after ~20s of an in-flight generation. */
export const STILL_GENERATING_NOTE = "Still generating. Long runs are normal.";

/** Footer line after a failed generation run. Replaces the "free" pitch,
 *  which read as a re-advertisement right under an error. */
export const FORGE_RETRY_NOTE = "Generation failed. You can try again at no cost.";

// ── Below-table IA (Phase 1b) ──

export const VERDICT_EYEBROW = "Analyst verdict";
export const APPENDIX_EYEBROW = "Discovery appendix";
export const FOUNDER_CONTEXT_SAVED = "Build limits saved";

/** Header stats as ONE record line: `12 ideas · Top score 82 · 4 segments`.
 *  Mono/uppercase comes from CSS; null metrics are omitted, never "--". */
export function candidateStatsLine(input: {
  candidates: number;
  topScore: number | null;
  segments: number | null;
}): string {
  const parts = [`${input.candidates} idea${input.candidates === 1 ? "" : "s"}`];
  if (input.topScore != null) parts.push(`Top score ${input.topScore}`);
  if (input.segments != null) parts.push(`${input.segments} segment${input.segments === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

/** Appendix header meta: `3 analyst notes · 2 feedback notes · 4 ideas ruled out`.
 *  ONE plain record line; zero counts are omitted (guardrail 8). */
export function appendixMetaLine(input: {
  analystNotes: number;
  collaborator: number;
  ruledOut: number;
}): string {
  const parts: string[] = [];
  if (input.analystNotes > 0) {
    parts.push(`${input.analystNotes} analyst note${input.analystNotes === 1 ? "" : "s"}`);
  }
  if (input.collaborator > 0) {
    parts.push(`${input.collaborator} feedback note${input.collaborator === 1 ? "" : "s"}`);
  }
  if (input.ruledOut > 0) {
    parts.push(`${input.ruledOut} idea${input.ruledOut === 1 ? "" : "s"} ruled out`);
  }
  return parts.join(" · ");
}

// ── Degraded run artifacts ──
//
// The pool of ideas and the run's written analysis of that pool are bound by a version plus
// a content fingerprint. When that binding cannot be CHECKED, the pool is still current and
// votable, but every claim ABOUT the pool is withheld.
//
// "Cannot be checked" is not the same as "is stale", and the banner may only make the
// weakest claim true in every state that raises it. All six `UntrustedRunArtifactReason`
// values (backend/src/services/currentSelectionContext.ts) raise it, and only TWO are
// staleness:
//   - version_mismatch  the analysis was written against a different pool version.
//   - content_mismatch  the stored fingerprint disagrees with the ideas on screen.
// The other FOUR are UNVERIFIABILITY, where the analysis may describe these very ideas:
//   - legacy_missing_version / legacy_missing_fingerprint: every job created before
//     migration 20260809180000_candidate_pool_version, which leaves the binding NULL
//     because the historical value "cannot be reconstructed safely", so the check fails
//     closed. That is every pre-migration job sitting in AWAITING_SELECTION.
//   - unresolvable_candidate_pool: the pool could not be read, so nothing was compared.
//   - preview_unavailable: returned purely on `status !== 'AWAITING_SELECTION'`, which
//     includes REGENERATING. The backend asserts (discoveryShares.portfolioSummary.test.ts)
//     that the fingerprint STILL MATCHES until the new batch lands, so a flat "out of date"
//     would be false on every "generate more ideas" click.
// Hence "we cannot confirm", never "this is out of date".
//
// NICHE-scoped framing is NOT withheld ON THE PUBLIC SHARE: `market_reality` and
// `niche_difficulty_verdict` are classified `niche` in
// backend/src/routes/schemas/sharedDiscoveryPayload.ts and keep serving, so the Reality
// Check card can render beside this banner there.
// It does NOT render beside the banner on either owner surface. The backend already sends
// `previewReport: null` whenever verification is untrusted (backend/src/routes/jobs.ts,
// the /solutions response), and both clients drop it again: the job page derives
// `serverPreviewReport` as null on untrusted, and selection/+layout.server.ts only fills
// `verifiedPreviewReport` when verification === "verified". So the owner sees this banner
// with no market framing next to it at all. That asymmetry is exactly why sentence 3 is
// written as a conditional rather than a statement about what is on screen.
//
// Three surfaces report this state (the job page, every /selection/* route, and the public
// share view), so the sentence lives here once and all three read it from this constant.
// That means the words must be true on the WEAKEST of the three: a read-only share visitor
// who changed nothing, on a /selection/* subroute that renders no market framing at all.
// Constraints the wording is held to, and the reason each exists:
//   - Name no artifact the viewer cannot see on the page. Two earlier drafts named the
//     "ranked snapshot" (only ever rendered by the Phase 2/3 full report) while a ranked
//     list of ideas sat directly under the banner, so the banner contradicted the screen.
//   - No second-person change attribution ("your latest change"). On the share the viewer
//     is `interactive={false}` and can only vote or comment.
//   - No internal vocabulary: "snapshot", "version", "artifact", "evidence framing" have
//     no referent for a buyer.
//   - Module noun rules apply. "shortlist" is the user's SAVED collection (see the top of
//     this file) and "candidates" is a retired synonym, so neither can name the pool here;
//     "these ideas" is what every one of the three surfaces actually shows.
//   - Sentence 3 is written as a conditional ("anything still shown") so it stays true on
//     subroutes that render no market framing.
//   - Assert no EXISTENCE for the analysis: the sentence must stay true whether or not a
//     stored analysis is actually sitting there.
//     NOT because the client is blind to the state. `artifactReason` IS projected to both
//     owner surfaces (backend/src/routes/jobs.ts -> jobs/[jobId]/+page.server.ts and
//     jobs/[jobId]/selection/+layout.server.ts) and already reaches the DOM as
//     `data-artifact-reason`. Three of the six values even imply existence:
//     content_mismatch and legacy_missing_fingerprint are reachable only after the stored
//     preview parsed as an object, and version_mismatch implies a versioned
//     PREVIEW_REPORT row.
//     The narrower true reason is the other three, plus the share. Nothing distinguishes
//     "exists but unbindable" from "absent" for preview_unavailable,
//     legacy_missing_version or unresolvable_candidate_pool; and the public share payload
//     deliberately carries no reason code at all (discoveryShares.ts, the
//     `evidenceFramingWithheld` field: "the public payload states the fact, not the
//     internal artifact state that produced it"). One constant read by all three surfaces
//     therefore has to be existence-neutral, because in those cases existence is unknown.
//     Recorded so it is not re-derived: sentence 2's "keeping it off this page" does NOT
//     remove an existence presupposition, and was never worth a claim that it did. The
//     presupposition rides on the definite noun phrase "the written analysis", which the
//     earlier "holding it back" shares, so the net truth gain of that swap is zero. The
//     wording is harmless and stays; the constraint above is what does the work.
//
// Module copy rule applies: no em or en dashes in the string below.

export const EVIDENCE_WITHHELD_TITLE = "We can't confirm the analysis matches these ideas";
export const EVIDENCE_WITHHELD_DETAIL =
  "The ideas themselves are current. We cannot confirm the written analysis still "
  + "describes them, so we are keeping it off this page instead of showing guidance for a "
  + "different set of ideas. Anything still shown about the market describes the niche as "
  + "a whole, not these ideas.";

/** The ranked pool itself failed to load. Distinct from the withheld case above: here
 *  there is nothing to rank, so the page must not present an empty pool as a finished
 *  result. Module noun rules apply: "candidates" is retired and "shortlist" names the
 *  user's SAVED collection, so neither can name the pool that failed to arrive. */
export const CANDIDATES_UNAVAILABLE_TITLE = "Couldn't load the ranked ideas";
export const CANDIDATES_UNAVAILABLE_DETAIL =
  "Something went wrong fetching the ideas for this run.";
