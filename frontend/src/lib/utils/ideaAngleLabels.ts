/**
 * Display labels + hover descriptions for an idea's WINNING ANGLE — the GTM angle the
 * angle-aware evaluator judged best for it (see docs/SCORING_METHODOLOGY.md).
 *
 * The three angles are PEERS, not a ranking — no angle is "better". So they share one neutral
 * visual treatment (no severity colors); the label names the play and the description explains
 * where its differentiation lives, so a low off-axis score reads as expected, not as a flaw.
 */
const ANGLE_LABELS: Record<string, string> = {
  distribution_seo: "Distribution / SEO",
  novel_differentiation: "Differentiation",
  vertical_workflow: "Workflow",
};

const ANGLE_DESCRIPTIONS: Record<string, string> = {
  distribution_seo:
    "Wins by being found — its edge is how it represents, slices, or keeps data fresh, not an unusual mechanism. A familiar mechanism is not a flaw here.",
  novel_differentiation:
    "Wins on a distinct mechanism or insight that rivals can't easily copy — the mechanism is the moat.",
  vertical_workflow:
    "Wins by owning a deep workflow for a specific user — the edge is a workflow step rivals miss, plus the switching cost it creates.",
};

/** Short display label for an angle value (empty string if unknown/unset). */
export function angleLabel(value?: string | null): string {
  if (!value) return "";
  return (
    ANGLE_LABELS[value] ??
    value
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  );
}

/** One-line hover explanation for an angle value (empty string if unknown/unset). */
export function angleDescription(value?: string | null): string {
  return value ? (ANGLE_DESCRIPTIONS[value] ?? "") : "";
}
