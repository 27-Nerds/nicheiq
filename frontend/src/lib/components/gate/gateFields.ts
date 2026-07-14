// Shared G1/G2 gate patch-field display helpers — used by ChatThread's patch
// proposal cards and GateWorkbench's applied-change receipts, so both render a
// patch field the same way (label + one display line).

/** Mono field labels per UX §4's canonical diff-card spec. */
export const GATE_FIELD_LABEL: Record<string, string> = {
  niche_description: "Niche description",
  market_segments: "Market segments",
  industry_boundaries: "Industry boundaries",
  user_target_audience: "Target audience",
  primary_target_segment: "Primary segment",
  excluded_segments: "Excluded segments",
  segment_emphasis: "Segment emphasis",
  pain_scope: "Pain scope",
};

/** Render a patch field value (or a gateArtifact "before" value) as one display line. */
export function formatGateFieldValue(field: string, value: unknown): string {
  if (value == null || value === "") return "(not set)";
  if (field === "pain_scope" && typeof value === "object") {
    const v = value as { excluded_titles?: string[]; pinned_titles?: string[] };
    const parts: string[] = [];
    if (v.excluded_titles?.length) parts.push(`exclude: ${v.excluded_titles.join(", ")}`);
    if (v.pinned_titles?.length) parts.push(`pin: ${v.pinned_titles.join(", ")}`);
    return parts.length ? parts.join(" · ") : "(no change)";
  }
  if (field === "segment_emphasis" && typeof value === "object") {
    const entries = Object.entries(value as Record<string, string>);
    return entries.length ? entries.map(([k, v2]) => `${k}: ${v2}`).join(", ") : "(none)";
  }
  if (Array.isArray(value)) return value.length ? value.join(", ") : "(none)";
  return String(value);
}
