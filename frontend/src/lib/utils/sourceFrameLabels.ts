/**
 * Display label for an idea's `source_frame` — which generation FRAME's cell minted it under
 * the Multi-Frame Idea Generation Portfolio (CODE-FILLED, never an LLM self-report; see
 * docs/JSON_REPORT_SCHEMA.md). Rendered as a single neutral "generation lens" chip.
 *
 * Closed vocabulary — unlike ideaAngleLabels, there is NO humanized fallback: an unrecognized
 * or missing value must render nothing (never a bare/guessed value).
 */
const SOURCE_FRAME_LABELS: Record<string, string> = {
  pain: "Pain-point lens",
  gap: "Competitor-gap lens",
  data_asset: "Data-asset lens",
  spend_adjacent: "Adjacent-spend lens",
  workflow: "Workflow lens",
  user_seed: "Submitted idea",
  owner_synthesis: "Branched direction",
  additional_batch: "Additional batch",
};

/** Display label for a source_frame value, or empty string if unknown/unset. */
export function sourceFrameLabel(value?: string | null): string {
  if (!value) return "";
  return SOURCE_FRAME_LABELS[value] ?? "";
}
