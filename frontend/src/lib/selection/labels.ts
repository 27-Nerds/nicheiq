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

// ── Next-step panel ──

export const GUIDE_EYEBROW = "Analyst · Suggested next";

export const ACTION_TITLES: Record<SelectionDecisionNextActionKind, string> = {
  select_candidate: "Review the top candidate",
  add_decision_context: "Add your decision context",
  analyze_founder_fit: "Review fit for you",
  stress_test_evidence: "Challenge the evidence",
  capture_assumption: "Track the biggest unknown",
  draft_test: "Plan a test",
  review_test_brief: "Review the test brief",
  launch_test: "Launch the test",
  monitor_test: "Review the active test",
  record_conclusion: "Record the test conclusion",
  start_deep_research: "Start Deep Research",
};

/** Per-kind card prose. Overrides the server `reason`; the server string is
 *  only used for a kind this map does not know about. */
const ACTION_BODIES: Record<SelectionDecisionNextActionKind, string> = {
  select_candidate:
    "Open the top candidate, check its pain evidence against your own read, and shortlist it if it holds up.",
  add_decision_context:
    "Save your build constraints once: time, budget, skills, and reach. Comparisons use them without changing the research score.",
  analyze_founder_fit:
    "Check each shortlisted pick against the time, budget, and reach you actually have.",
  stress_test_evidence:
    "Check whether the evidence behind this pick is strong enough and see what is still missing.",
  capture_assumption:
    "Write down the riskiest assumption behind this pick so it is tracked, not forgotten.",
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
    "When you are ready, start Deep Research from the bar below.",
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
  if (title && action.kind === "stress_test_evidence") return `Stress-test ${title}`;
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
export const STRESS_TEST_EVIDENCE_LABEL = "Challenge the evidence";
export const DRAFT_TEST_BRIEF_LABEL = "Plan a test";
export const SHAPE_LABEL = "Explore variants";

export function founderContextLabel(hasProfile: boolean): string {
  return hasProfile ? "Edit build constraints" : "Add build constraints";
}

export const SAVE_FOUNDER_CONTEXT_LABEL = "Save build constraints";
export const FOUNDER_CONTEXT_OVERLAY_TITLE = "Your build constraints";

/** Named-lens stress-test CTA: "Stress-test {lens} evidence" once a lens is
 *  known; falls back to the generic label otherwise. */
export function stressTestLabel(lensLabel?: string | null): string {
  return lensLabel ? `Stress-test ${lensLabel.toLowerCase()} evidence` : STRESS_TEST_EVIDENCE_LABEL;
}

/** Shared receipt copy for the constraint-led variant twins
 *  (FounderFitReshapePanel / ExperimentNarrowingPanel). */
export const EVALUATED_ACCEPTED_LABEL = "Evaluated. Added to ranked candidates.";
export const EVALUATED_DEMOTED_LABEL = "Evaluated. This variant did not clear the market-fit bar.";

// ── Canonical tool names ──
//
// ONE name per tool, used by the decision rail, the workspace nav, the page
// headings, and the analyst. These names previously drifted across surfaces
// ("Check the biggest uncertainty" / "Challenge" / "Biggest unknowns" all named
// the same tool), so a novice had to re-recognize each tool three times.

export const TOOL_NAMES = {
  compare: "Compare finalists",
  challenge: "Check the evidence",
  test: "Plan a test",
  shape: SHAPE_LABEL,
  newBatch: "More ideas",
} as const;

/** Sub-nav of the selection workspace. Labels match TOOL_NAMES exactly; only
 *  the supporting line differs per surface. */
export const WORKSPACE_ROUTES = [
  { slug: "compare", label: TOOL_NAMES.compare, detail: "See the trade-offs" },
  { slug: "risks", label: TOOL_NAMES.challenge, detail: "Find the biggest unknown" },
  { slug: "tests", label: TOOL_NAMES.test, detail: "Define decision evidence" },
  { slug: "alternatives", label: TOOL_NAMES.shape, detail: "Branch into new directions" },
] as const;

/**
 * The two decision-critical tools for picking what to pay to research: compare
 * the finalists, and check whether the evidence holds up. These are foregrounded
 * as navigation. "Plan a test" and "Explore variants" are real, but they are a
 * post-selection activity and a divergence escape-hatch respectively — reached
 * contextually (from an evidence gap / a "none of these fit?" action), never as
 * co-equal nav. Presenting all four equally was the felt complexity.
 */
export const PRIMARY_TOOL_SLUGS: readonly string[] = ["compare", "risks"];
export const SECONDARY_TOOL_SLUGS: readonly string[] = ["tests", "alternatives"];

// ── Shape (ConceptForge) panel copy ──

export const SHAPE_PANEL_EYEBROW = SHAPE_LABEL;
export const SHAPE_PANEL_TITLE = "Explore variants";
export const SHAPE_PANEL_INTRO =
  "This branches one or two exact candidate revisions into a small set of unevaluated directions. Your originals stay unchanged, their scores do not transfer, and only a direction you explicitly confirm enters paid evaluation.";
export const SHAPE_PURPOSE_LABEL = "Shape purpose";
export const CLOSE_SHAPE_LABEL = "Close Shape";
export const GENERATE_DIRECTIONS_LABEL = "Generate directions";
export const GENERATING_DIRECTIONS_LABEL = "Generating directions…";

// ── Cockpit tab groups (Wave 3 split: compare vs. pressure-test) ──

export type CockpitMode = "risk" | "assumptions" | "market" | "fit" | "challenge";
export type CockpitTabGroup = "compare" | "pressure";

export const COCKPIT_GROUP_MODES: Record<CockpitTabGroup, CockpitMode[]> = {
  compare: ["market", "fit"],
  pressure: ["challenge", "risk", "assumptions"],
};

export function groupForMode(mode: CockpitMode): CockpitTabGroup {
  return COCKPIT_GROUP_MODES.pressure.includes(mode) ? "pressure" : "compare";
}

interface CockpitGroupCopy {
  eyebrow: string;
  heading: string;
  intro: string;
  dialogLabel: string;
  closeLabel: string;
}

export const COCKPIT_GROUP_COPY: Record<CockpitTabGroup, CockpitGroupCopy> = {
  compare: {
    eyebrow: "Compare",
    heading: "Compare shortlist",
    intro:
      "Research findings stay separate from your preference. Compare the evidence and trade-offs; this view does not recalculate or override the research ranking.",
    dialogLabel: "Compare shortlisted ideas",
    closeLabel: "Close comparison",
  },
  pressure: {
    eyebrow: "Evidence review",
    heading: "Challenge the shortlist",
    intro:
      "Stress-check the evidence behind each pick, surface the decision risks, and turn the ones that matter into tracked assumptions. Nothing here changes your ranking or shortlist; that moves only when you choose an action.",
    dialogLabel: "Review evidence for shortlisted ideas",
    closeLabel: "Close evidence review",
  },
};

/** Leading label of the cockpit scope strip (uppercase comes from CSS). */
export const COCKPIT_SCOPE_LABEL = "Scope";

/** Scope record line for all-candidate cockpit views: `Scope · All 3 shortlisted`.
 *  A single candidate is named instead: `Scope · {name}`. Mono/uppercase comes
 *  from CSS. */
export function cockpitScopeLine(count: number, soloName?: string | null): string {
  const name = soloName?.trim();
  if (count === 1 && name) return `Scope · ${name}`;
  return `Scope · All ${count} shortlisted`;
}

/** Regenerate overlay CTA: price stays at the gate. */
export function generateNewBatchLabel(seedCost: number | null | undefined): string {
  const cost = seedCost ?? null;
  return cost != null && cost > 0
    ? `Generate ${TOOL_NAMES.newBatch.toLowerCase()} · ${costLine(cost)}`
    : `Generate ${TOOL_NAMES.newBatch.toLowerCase()}`;
}

/** Lock hints for steps that need a shortlist first. These name the action that
 *  unlocks the step, not the fact that it is locked. */
export const STEP_LOCK_HINTS = {
  compare: "Shortlist two ideas to compare them",
  challenge: "Shortlist an idea to check its evidence",
  test: "Shortlist an idea to plan a test",
  shape: "Shortlist an idea to branch it",
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

/** Memo state line: `2 SHORTLISTED · 3 CHECKS · CONTEXT SAVED`. */
export function guideRecordLine(input: {
  shortlisted: number;
  checks: number;
  stale: number;
  contextSaved: boolean;
}): string {
  const parts = [
    `${input.shortlisted} SHORTLISTED`,
    `${checkCount(input.checks)}${staleSuffix(input.stale)}`,
  ];
  if (input.contextSaved) parts.push("CONTEXT SAVED");
  return parts.join(" · ");
}

/** Null-safe seed-cost phrase, e.g. "2 credits". Price surfaces at the gate;
 *  callers compose the sentence. */
export function costLine(seedCost: number | null | undefined): string {
  if (seedCost == null || !Number.isFinite(seedCost)) return "credits";
  return `${seedCost} credit${seedCost === 1 ? "" : "s"}`;
}

/** Shape's single upstream price mention (guardrail 14): the tile tooltip and
 *  the forge's first screen state the same sentence; the gate itself is the
 *  per-option Evaluate button. Null-safe via costLine. */
export function shapeCostNote(seedCost: number | null | undefined): string {
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

// ── Below-table IA (Phase 1b) ──

export const VERDICT_EYEBROW = "Analyst verdict";
export const APPENDIX_EYEBROW = "Appendix · Analysis & context";
export const FOUNDER_CONTEXT_SAVED = "Build constraints saved";

/** Header stats as ONE record line: `12 candidates · Top score 82 · 4 segments`.
 *  Mono/uppercase comes from CSS; null metrics are omitted, never "--". */
export function candidateStatsLine(input: {
  candidates: number;
  topScore: number | null;
  segments: number | null;
}): string {
  const parts = [`${input.candidates} candidate${input.candidates === 1 ? "" : "s"}`];
  if (input.topScore != null) parts.push(`Top score ${input.topScore}`);
  if (input.segments != null) parts.push(`${input.segments} segment${input.segments === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

/** Appendix header meta: `Analyst notes 3 · Collaborator 2 · Ruled out 4`.
 *  ONE plain mono record line; zero counts are omitted (guardrail 8). */
export function appendixMetaLine(input: {
  analystNotes: number;
  collaborator: number;
  ruledOut: number;
}): string {
  const parts: string[] = [];
  if (input.analystNotes > 0) parts.push(`Analyst notes ${input.analystNotes}`);
  if (input.collaborator > 0) parts.push(`Collaborator ${input.collaborator}`);
  if (input.ruledOut > 0) parts.push(`Ruled out ${input.ruledOut}`);
  return parts.join(" · ");
}

// ── Commit bar ──

export const COMMIT_BAR_EMPTY = "Shortlist an idea to begin.";
export const START_DEEP_RESEARCH_LABEL = "Start Deep Research";

/** The single priced line page-wide: `15 CREDITS · BALANCE 42`. */
export function commitCostLine(cost: number, balance: number): string {
  return `${cost} CREDITS · BALANCE ${balance}`;
}

/** Memo panel: shown under the actions for any optional (non-required) next
 *  action other than the two the panel already renders its own CTA for. */
export const MEMO_OPTIONAL_ESCAPE =
  "Optional. You can start Deep Research whenever you are ready.";
