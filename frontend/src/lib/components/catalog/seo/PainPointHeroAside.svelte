<script lang="ts">
  // Right rail of PainPointHeroV2 — pain-score panel. Thin wrapper over the
  // shared <ScorePanel>: severity + WTP render as score bars (themed red),
  // opportunity as a categorical pill, the quality tier as a header badge, and
  // mention count + source platforms as the footer. Composite is the mean of
  // the two 0-100 scores.

  import type { QualitySignals } from "$lib/types/publicCatalog.js";
  import QualityTierBadge from "./QualityTierBadge.svelte";
  import ScorePanel, { type ScoreRow } from "./ScorePanel.svelte";

  interface Props {
    /** 0-100 (already scaled at the route). */
    severity: number | null;
    /** 0-100 (already scaled at the route). */
    commercialIntent: number | null;
    /** Pre-normalized at the route — high/medium/low/null. */
    opportunity: "high" | "medium" | "low" | null;
    /** Quality signals from the research context. Drives the tier badge. */
    qualitySignals?: QualitySignals | null;
    /** Optional explicit composite (0-100). When omitted, mean of finite [severity, WTP]. */
    composite?: number | null;
    /** Mention count surfaced in the footer. */
    mentionCount?: number | null;
    /** Source platforms surfaced as mono chips in the footer. */
    sourcePlatforms?: string[] | null;
  }

  let {
    severity,
    commercialIntent,
    opportunity,
    qualitySignals = null,
    composite = null,
    mentionCount = null,
    sourcePlatforms = null,
  }: Props = $props();

  const computedComposite = $derived.by<number | null>(() => {
    if (composite != null && Number.isFinite(composite)) return composite;
    const vals = [severity, commercialIntent].filter(
      (v): v is number => v != null && Number.isFinite(v),
    );
    if (vals.length === 0) return null;
    return vals.reduce((s, v) => s + v, 0) / vals.length;
  });

  const compositeRounded = $derived(
    computedComposite == null ? null : Math.round(computedComposite),
  );

  // Provenance note for the big number — only when the frontend mean path
  // computed it (composite prop absent). A backend-supplied composite may use
  // a different formula, so no claim is made for it. Prevents the "why is a
  // 70 'critical' when severity is 85?" misread.
  const formulaNote = $derived(
    composite == null && compositeRounded != null
      ? "avg of severity + commercial intent"
      : null,
  );

  const tierLabel = $derived.by<string | null>(() => {
    if (compositeRounded == null) return null;
    if (compositeRounded >= 70) return "Critical pain · ship this";
    if (compositeRounded >= 55) return "High-impact · validate then ship";
    if (compositeRounded >= 40) return "Notable · niche play";
    return "Minor signal";
  });

  const platformChips = $derived(
    Array.isArray(sourcePlatforms)
      ? sourcePlatforms.filter((s): s is string => typeof s === "string" && s.trim() !== "")
      : [],
  );

  const rows = $derived.by<ScoreRow[]>(() => {
    const out: ScoreRow[] = [
      { kind: "bar", label: "Severity", value: severity, tone: "var(--color-error)" },
      { kind: "bar", label: "Commercial intent", value: commercialIntent, tone: "var(--color-accent)" },
    ];
    if (opportunity) {
      out.push({ kind: "pill", label: "Opportunity", text: opportunity, tier: opportunity });
    }
    return out;
  });

  const footerStats = $derived(
    mentionCount != null && mentionCount > 0
      ? [{ value: mentionCount.toLocaleString(), label: "Discussions" }]
      : [],
  );

  const footerChips = $derived(
    platformChips.length > 0 ? { label: "Reported on", items: platformChips } : null,
  );
</script>

{#snippet qualityBadge()}
  {#if qualitySignals}
    <QualityTierBadge signals={qualitySignals} />
  {/if}
{/snippet}

<ScorePanel
  label="Pain score"
  composite={computedComposite}
  tier={tierLabel}
  {formulaNote}
  accent="var(--color-error)"
  headerExtra={qualitySignals ? qualityBadge : undefined}
  {rows}
  {footerStats}
  {footerChips}
/>
