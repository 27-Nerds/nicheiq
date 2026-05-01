<script lang="ts">
  import type { QualitySignals } from "$lib/types/publicCatalog.js";

  // Phase 5.5 — small pill in the category hero showing the data quality
  // tier alongside the confidence percent. Hidden when no usable signal.
  // Pain-point tier (GOLD/SILVER/BRONZE) takes precedence over content tier
  // (EXCELLENT/GOOD/MINIMAL/INSUFFICIENT) because it's the more user-facing
  // grade. Confidence percent is appended when present.

  interface Props {
    signals: QualitySignals;
  }

  let { signals }: Props = $props();

  type Tone = "gold" | "silver" | "bronze" | "muted";

  const tier = $derived(
    signals.painPointTier ??
      (signals.contentTier === "EXCELLENT"
        ? "GOLD"
        : signals.contentTier === "GOOD"
          ? "SILVER"
          : signals.contentTier === "MINIMAL"
            ? "BRONZE"
            : null),
  );

  const tone: Tone = $derived(
    tier === "GOLD"
      ? "gold"
      : tier === "SILVER"
        ? "silver"
        : tier === "BRONZE"
          ? "bronze"
          : "muted",
  );

  const confidencePct = $derived(
    signals.confidenceScore != null
      ? Math.round(signals.confidenceScore * 100)
      : null,
  );

  const visible = $derived(tier != null || confidencePct != null);
</script>

{#if visible}
  <span class="quality-pill" data-tone={tone} title="Data quality signals">
    {#if tier}<span class="tier">{tier}</span>{/if}
    {#if tier && confidencePct != null}<span class="dot">·</span>{/if}
    {#if confidencePct != null}<span class="conf">{confidencePct}%</span>{/if}
  </span>
{/if}

<style>
  .quality-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    border: 1px solid var(--color-border);
    background: var(--color-surface, #fff);
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .quality-pill[data-tone="gold"] {
    color: #b8860b; /* dark gold — readable on light backgrounds */
    border-color: rgba(184, 134, 11, 0.3);
    background: rgba(184, 134, 11, 0.04);
  }
  .quality-pill[data-tone="silver"] {
    color: #6b7280;
    border-color: rgba(107, 114, 128, 0.3);
  }
  .quality-pill[data-tone="bronze"] {
    color: #92400e;
    border-color: rgba(146, 64, 14, 0.3);
  }
  .dot {
    color: var(--color-text-muted);
    opacity: 0.6;
  }
  .conf {
    font-feature-settings: "tnum" 1;
  }
</style>
