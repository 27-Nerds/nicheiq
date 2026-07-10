/**
 * "Why this score" rationale for the Phase-1 idea cards + pop-up.
 *
 * Composes a short, human-readable explanation for each displayed score from the
 * scorer's OWN grounded rationale fields already on the preview object — no invented
 * calculation claims. Returns `null` when no grounded text exists, so callers show no
 * tooltip rather than fabricating one.
 */
import type { SolutionPreview } from "$lib/types/job";

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
  return s.length <= MAX_LEN ? s : s.slice(0, MAX_LEN - 1).trimEnd() + "…";
}

function firstNonEmpty(...vals: (string | null | undefined)[]): string {
  for (const v of vals) {
    const c = clean(v);
    if (c) return c;
  }
  return "";
}

// Mirrors settings.payability_low_threshold (src/nicheiq/config/settings.py) — segment
// payability below this counts as LOW, same bar the backend cap uses.
const PAYABILITY_LOW_THRESHOLD = 0.35;

/**
 * Names the single most-restrictive market_fit ceiling that likely applied to this idea,
 * mirroring `_validate_idea_caps` rules (b)/(d)/(e) in unified_solution_crew.py. Each rule is
 * downgrade-only and they compose via min() — so when more than one condition is detected here,
 * the clause for the SMALLEST cap wins (e.g. a 'substitute' parity finding against a thin-wallet
 * segment mirrors the backend's 0.35 substitute+weak-wallet cap, tighter than either alone).
 * Returns null when no cap condition is detected on the idea.
 */
function marketFitCapHint(idea: SolutionPreview): string | null {
  const dam = clean(idea.data_access_model).toLowerCase();
  const parity = clean(idea.incumbent_parity).toLowerCase();
  const pay = idea.source_segment_payability;
  const payLow = typeof pay === "number" && pay < PAYABILITY_LOW_THRESHOLD;

  const candidates: { cap: number; clause: string }[] = [];

  if (dam === "unofficial" || dam === "restricted" || dam === "blocked") {
    candidates.push({ cap: 0.4, clause: "capped at 0.40 — the data route is unverified" });
  }
  if (payLow) {
    candidates.push({ cap: 0.55, clause: "capped — this buyer segment rarely pays for tooling" });
  }
  if (parity.startsWith("shipped")) {
    candidates.push({ cap: 0.45, clause: "held at/below 0.45 — a verified incumbent ships this mechanism" });
  } else if (parity.startsWith("partial")) {
    candidates.push({ cap: 0.55, clause: "capped — an incumbent partially covers this position" });
  } else if (parity.startsWith("substitute")) {
    candidates.push({ cap: payLow ? 0.35 : 0.5, clause: "capped — a free/DIY route covers the core outcome" });
  }

  if (!candidates.length) return null;
  const tightest = candidates.reduce((a, b) => (b.cap < a.cap ? b : a));
  return `${tightest.clause} (thin early signal; Deep Research validates)`;
}

/**
 * Returns a short "why we gave this score" string for `key`, or null when the idea
 * carries no grounded rationale for it.
 */
export function scoreRationale(
  idea: SolutionPreview | null | undefined,
  key: ScoreKey,
): string | null {
  if (!idea) return null;

  let why = "";
  switch (key) {
    case "market_fit": {
      why = firstNonEmpty(idea.why_it_works_short, idea.why_it_works, idea.value_proposition);
      const capHint = marketFitCapHint(idea);
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
      why = note ? (access ? `Data (${access}): ${note}` : note) : "";
      break;
    }

    case "seo":
      // SEO now reflects the realistic indexable-page count; it's a preliminary estimate
      // refined by keyword research for the idea you pursue.
      why = firstNonEmpty(idea.programmatic_seo_opportunity);
      if (why) why = `${why} (preliminary estimate, refined after keyword research)`;
      break;

    case "novelty": {
      // Prefer the angle-aware, project-type-grounded rationale when present and non-empty
      // (angle eval on) — it explains why a low mechanism-novelty isn't a flaw for, e.g., a catalog.
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
      if (why) why = `Overall: blends fit, feasibility, novelty & SEO. ${why}`;
      break;
  }

  why = clamp(clean(why));
  return why || null;
}
