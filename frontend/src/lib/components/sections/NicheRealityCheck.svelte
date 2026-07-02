<script lang="ts">
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import type { NicheDifficultyVerdict } from "$lib/types/report";

  interface Props {
    verdict: NicheDifficultyVerdict;
    context?: "discovery" | "report";
  }

  let { verdict, context = "report" }: Props = $props();

  // FIT visuals derive from software_addressability (cutoffs mirror the backend bands
  // 0.70 / 0.45 / 0.25 in niche_difficulty.py). The difficulty band measures overall
  // difficulty INCLUDING frictions and can be "high" on a strong-fit niche — deriving fit
  // labels from it printed "Hard to fully address with software" next to an 88% meter.
  const addr = $derived(verdict.software_addressability ?? 0);
  const fitBand = $derived(
    addr >= 0.7 ? "strong" : addr >= 0.45 ? "moderate" : addr >= 0.25 ? "limited" : "very_limited",
  );

  // Severity ramp — never `accent` (orange is brand/interactive only).
  const badgeVariant = $derived(
    fitBand === "strong"
      ? "success"
      : fitBand === "moderate"
        ? "info"
        : fitBand === "limited"
          ? "warning"
          : "error",
  );
  const fitLabel = $derived(
    fitBand === "strong"
      ? "Strong"
      : fitBand === "moderate"
        ? "Moderate"
        : fitBand === "limited"
          ? "Limited"
          : "Hard",
  );
  // Meter marker color matches the badge severity.
  const accentColor = $derived(
    fitBand === "strong"
      ? "var(--color-success)"
      : fitBand === "moderate"
        ? "var(--color-secondary)"
        : fitBand === "limited"
          ? "var(--color-warning)"
          : "var(--color-error)",
  );

  // Left = software can't fix it (HARD); right = software owns it (STRONG).
  const pct = $derived(Math.max(0, Math.min(100, Math.round(addr * 100))));
  const positive = $derived(fitBand === "strong");
  const pointsLabel = $derived(positive ? "What makes it strong" : "What makes it hard");

  // Qualitative addressability label — the meter bar is the visual gauge; the text never shows the raw %.
  const addrLabel = $derived(
    fitBand === "strong"
      ? "Mostly tool-addressable"
      : fitBand === "moderate"
        ? "Partly tool-addressable"
        : fitBand === "limited"
          ? "Hard to fully address with software"
          : "Largely beyond what software can fix",
  );
</script>

<InsightCard variant={badgeVariant} border="all" padding="lg" class="reality-check">
  {#snippet header()}
    <div class="rc-head">
      <div class="rc-titles">
        <p class="rc-eyebrow">Research Reality Check</p>
        <h3 class="rc-headline">{verdict.headline}</h3>
      </div>
      <Badge variant={badgeVariant} size="sm">Software Fit: {fitLabel}</Badge>
    </div>
  {/snippet}

  <div class="rc-body" style={`--rc-accent:${accentColor};--rc-pct:${pct}%`}>
    {#if context === "discovery"}
      <p class="rc-lead">The honest read before you choose what to build.</p>
    {/if}

    <!-- Software-addressability meter: how much of the niche's pain a tool can actually fix. -->
    <div class="rc-meter" role="img" aria-label={`Software addressability: ${addrLabel}`}>
      <div class="rc-meter-ends">
        <span>Software can't fix it</span>
        <span>Software owns it</span>
      </div>
      <div class="rc-track">
        <span class="rc-marker"></span>
      </div>
      <p class="rc-meter-value">{addrLabel}</p>
    </div>

    <p class="rc-narrative">{verdict.narrative_summary}</p>

    {#if verdict.key_challenges?.length}
      <p class="rc-points-label">{pointsLabel}</p>
      <ul class="rc-points">
        {#each verdict.key_challenges as point}
          <li>{point}</li>
        {/each}
      </ul>
    {/if}

    {#if verdict.low_confidence}
      <p class="rc-note">Limited sample — treat this as directional.</p>
    {/if}
  </div>
</InsightCard>

<style>
  .rc-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .rc-eyebrow {
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 0.25rem;
  }

  .rc-headline {
    font-size: 1.0625rem;
    font-weight: 650;
    line-height: 1.3;
    color: var(--color-text-primary);
    margin: 0;
  }

  .rc-lead {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    margin: 0 0 0.875rem;
  }

  .rc-meter {
    margin: 0 0 1rem;
  }

  .rc-meter-ends {
    display: flex;
    justify-content: space-between;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin-bottom: 0.375rem;
  }

  .rc-track {
    position: relative;
    height: 6px;
    border-radius: 999px;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
  }

  .rc-marker {
    position: absolute;
    top: 50%;
    left: var(--rc-pct);
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--rc-accent);
    transform: translate(-50%, -50%);
    box-shadow: 0 0 0 3px var(--color-bg-elevated);
  }

  .rc-meter-value {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--rc-accent);
    margin: 0.4rem 0 0;
  }

  .rc-narrative {
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--color-text-secondary);
    margin: 0;
  }

  .rc-points-label {
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0.875rem 0 0.4rem;
  }

  .rc-points {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .rc-points li {
    position: relative;
    padding-left: 1rem;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
  }

  .rc-points li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.5em;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--rc-accent, var(--color-text-muted));
  }

  .rc-note {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: 0.875rem 0 0;
    font-style: italic;
  }
</style>
