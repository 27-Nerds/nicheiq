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
    case "market_fit":
      why = firstNonEmpty(idea.why_it_works_short, idea.why_it_works, idea.value_proposition);
      break;

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
