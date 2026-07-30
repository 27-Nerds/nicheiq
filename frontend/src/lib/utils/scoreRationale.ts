/**
 * "Why this score" rationale for the Phase-1 idea cards + pop-up.
 *
 * Composes a short, human-readable explanation for each displayed score from the
 * scorer's OWN grounded rationale fields already on the preview object — no invented
 * calculation claims. Returns `null` when no grounded text exists, so callers show no
 * tooltip rather than fabricating one.
 */
import type { SolutionPreview } from "$lib/types/job";
import type { SelectionCapThresholds } from "$lib/types/selectionMetricExplanation";

export type ScoreKey =
  | "composite"
  | "market_fit"
  | "technical_feasibility"
  | "data_feasibility"
  | "seo"
  | "novelty"
  | "solo_dev";

// Keep hover tooltip rationale compact enough to scan without covering the card.
const MAX_LEN = 240;

function clean(s?: string | null): string {
  return (s ?? "").replace(/\s+/g, " ").trim();
}

function clamp(s: string): string {
  if (s.length <= MAX_LEN) return s;
  // Never cut inside a word: back up to the last complete word before the limit.
  // clean() has already collapsed all whitespace to single spaces.
  const cut = s.slice(0, MAX_LEN - 1);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd() + "…";
}

function firstNonEmpty(...vals: (string | null | undefined)[]): string {
  for (const v of vals) {
    const c = clean(v);
    if (c) return c;
  }
  return "";
}

// Fallback cap thresholds mirroring the DEFAULTS in src/nicheiq/config/settings.py
// (payability_low_threshold=0.35, payability_market_fit_cap=0.55, parity_shipped=0.45,
// parity_partial=0.55, parity_substitute=0.50, parity_substitute_weak_wallet=0.35,
// parity_bundled_free=0.40). The backend serves the LIVE (env-resolved) values on
// /api/selection/metric-explanations as `capThresholds`; pages inject them via
// setServedCapThresholds (or per-call via opts.capThresholds) so a prod env override
// can't silently falsify this copy. These constants are only the no-payload fallback.
export const DEFAULT_CAP_THRESHOLDS: SelectionCapThresholds = {
  payabilityLowThreshold: 0.35,
  payabilityMarketFitCap: 0.55,
  parityShippedMarketFitCap: 0.45,
  parityPartialMarketFitCap: 0.55,
  paritySubstituteMarketFitCap: 0.5,
  paritySubstituteWeakWalletCap: 0.35,
  parityBundledFreeCap: 0.4,
};

// Backend-served thresholds, injected once per page init from the metric-explanations
// payload. Module-level (not reactive): the values are static per deployment, and pages
// call the setter during component init — before any cap-hint derivation runs.
let servedCapThresholds: SelectionCapThresholds | null = null;

/** Inject the backend-served cap thresholds; pass null/undefined to keep defaults. */
export function setServedCapThresholds(caps: SelectionCapThresholds | null | undefined): void {
  servedCapThresholds = caps ?? null;
}

// A cap "plausibly bound" when the displayed score sits at/above (cap − epsilon);
// the backend only clamps when the raw score exceeded the cap, so a score well
// below the cap means the ceiling never bit.
const CAP_EPSILON = 0.005;

/**
 * Names the single most-restrictive market_fit ceiling that likely applied to this idea,
 * mirroring `_validate_idea_caps` rules (b)/(d)/(e) in unified_solution_crew.py. Each rule is
 * downgrade-only and they compose via min() — so when more than one condition is detected here,
 * the clause for the SMALLEST cap wins (e.g. a 'substitute' parity finding against a thin-wallet
 * segment mirrors the backend's 0.35 substitute+weak-wallet cap, tighter than either alone).
 * Returns null when no cap condition is detected on the idea.
 *
 * `caps` defaults to the backend-served thresholds when injected, else the Python
 * defaults — so a prod env override of a cap setting flows into this copy.
 */
function marketFitCapHint(
  idea: SolutionPreview,
  caps: SelectionCapThresholds = servedCapThresholds ?? DEFAULT_CAP_THRESHOLDS,
): string | null {
  const dam = clean(idea.data_access_model).toLowerCase();
  const parity = clean(idea.incumbent_parity).toLowerCase();
  const pay = idea.source_segment_payability;
  const payLow = typeof pay === "number" && pay < caps.payabilityLowThreshold;

  const candidates: { cap: number; clause: string }[] = [];

  if (dam === "unofficial" || dam === "restricted" || dam === "blocked") {
    // 0.40 is HARDCODED in the Python cap rule (unified_solution_crew rule (b)),
    // not env-overridable — the only literal cap that stays a constant here.
    candidates.push({ cap: 0.4, clause: "the fit signal was reduced because the required data route is not verified" });
  }
  if (payLow) {
    candidates.push({ cap: caps.payabilityMarketFitCap, clause: "the fit signal was reduced because this buyer segment shows weak evidence of paying for tools" });
  }
  if (parity.startsWith("shipped by evidence:")) {
    candidates.push({
      cap: caps.parityShippedMarketFitCap,
      clause: "the fit signal was reduced because adversarial evidence challenged the core mechanism",
    });
  } else if (parity.startsWith("shipped")) {
    candidates.push({
      cap: caps.parityShippedMarketFitCap,
      clause: "the fit signal was reduced because a verified incumbent already provides the core mechanism",
    });
  } else if (parity.startsWith("partial")) {
    candidates.push({ cap: caps.parityPartialMarketFitCap, clause: "the fit signal was reduced because an incumbent already covers part of this position" });
  } else if (parity.startsWith("substitute")) {
    candidates.push({
      cap: payLow ? caps.paritySubstituteWeakWalletCap : caps.paritySubstituteMarketFitCap,
      clause: "the fit signal was reduced because a free or do-it-yourself route already covers the core outcome",
    });
  }

  if (!candidates.length) return null;
  const tightest = candidates.reduce((a, b) => (b.cap < a.cap ? b : a));
  // Behavior choice: a cap CONDITION alone doesn't prove the cap bound. Assert
  // "capped" only when the displayed market_fit_score is at/above (cap − epsilon);
  // otherwise OMIT the clause entirely (no conditional rewording), so this popover
  // never claims a cap that didn't bite. A missing score also omits — we can't
  // verify the assertion.
  const mf = idea.market_fit_score;
  if (typeof mf !== "number" || !Number.isFinite(mf) || mf < tightest.cap - CAP_EPSILON) return null;
  return `${tightest.clause}. Deep Research can verify this early signal`;
}

/**
 * Returns a short "why we gave this score" string for `key`, or null when the idea
 * carries no grounded rationale for it.
 *
 * Pass `{ full: true }` to skip the popover-sized 240-char clamp — for surfaces with
 * room for the whole rationale (e.g. the overlay's "Decision rationale" panel).
 *
 * Pass `{ capThresholds }` to override the cap thresholds for this call; otherwise the
 * backend-served values (setServedCapThresholds) apply, falling back to the Python
 * defaults — existing consumers keep working unchanged.
 */
export function scoreRationale(
  idea: SolutionPreview | null | undefined,
  key: ScoreKey,
  opts: { full?: boolean; capThresholds?: SelectionCapThresholds } = {},
): string | null {
  if (!idea) return null;

  let why = "";
  switch (key) {
    case "market_fit": {
      why = firstNonEmpty(idea.why_it_works_short, idea.why_it_works, idea.value_proposition);
      const capHint = marketFitCapHint(
        idea,
        opts.capThresholds ?? servedCapThresholds ?? DEFAULT_CAP_THRESHOLDS,
      );
      if (capHint) {
        why = why ? `${why} — ${capHint}` : capHint.charAt(0).toUpperCase() + capHint.slice(1);
      }
      break;
    }

    case "technical_feasibility":
      why = firstNonEmpty(idea.technical_approach, idea.data_acquisition_notes);
      break;

    case "data_feasibility": {
      const note = firstNonEmpty(idea.data_acquisition_notes);
      const access = clean(idea.data_access_model);
      const accessLabel = access
        ? access.charAt(0).toUpperCase() + access.slice(1).replaceAll("_", " ")
        : "";
      why = note ? (accessLabel ? `Data access: ${accessLabel}. ${note}` : note) : "";
      break;
    }

    case "seo":
      // SEO now reflects the realistic indexable-page count; it's a preliminary estimate
      // refined by keyword research for the idea you pursue.
      why = firstNonEmpty(idea.programmatic_seo_opportunity);
      if (why) why = `${why} Keyword demand has not been checked in depth yet.`;
      break;

    case "novelty": {
      // Prefer the angle-aware, project-type-grounded rationale when present and non-empty
      // (angle eval on) — it explains why a familiar mechanism is not necessarily a flaw
      // for a distribution-led product such as a catalog.
      const angleNov = clean(idea.novelty_rationale);
      if (angleNov) {
        why = angleNov;
        break;
      }
      const innov = clean(idea.innovation_angle);
      const conv = clean(idea.conventional_approach);
      why = innov && conv
        ? `Differs from the usual (${conv}) — ${innov}`
        : firstNonEmpty(idea.innovation_angle, idea.why_it_works);
      break;
    }

    case "solo_dev": {
      const dt = clean(idea.estimated_development_time);
      const note = clean(idea.data_acquisition_notes);
      // Surface an ops/cold-start burden only when the data note actually flags one.
      const opsHint = /moderat|seed|cold[-\s]?start|community|manual/i.test(note) ? note : "";
      why = [dt && `Est. build: ${dt}`, opsHint].filter(Boolean).join(". ");
      break;
    }

    case "composite":
      why = firstNonEmpty(idea.why_it_works_short, idea.why_it_works);
      break;
  }

  why = clean(why);
  if (!opts.full) why = clamp(why);
  return why || null;
}
