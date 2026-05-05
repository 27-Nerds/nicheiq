<script lang="ts">
  // Inline severity bar for pain-point tables. 0-100 input. Color shifts at
  // configurable thresholds:
  //   >= 75 → error (red)
  //   >= 60 → accent (orange)
  //   else  → info (blue)
  //
  // For pain-point severity (stored 0-1), use scaleSeverity(value, 'pain') first.
  // For theme severity (stored 0-100), pass raw.

  interface Props {
    /** 0-100 severity. Clamped defensively. */
    value: number | null | undefined;
    /** Show the numeric label after the bar (default true). */
    showNumber?: boolean;
    /** Show the visible HIGH/MED/LOW tier pill after the number (default true).
     *  When false, the tier name still ships in the wrapper's aria-label so
     *  screen-reader output isn't reduced — only the visible pill is omitted.
     *  Used by PainPointRankTable to match image #10's clean treatment. */
    showTier?: boolean;
  }

  let { value, showNumber = true, showTier = true }: Props = $props();

  const safe = $derived(
    value == null || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(100, value)),
  );
  const tone = $derived(
    safe >= 75 ? "var(--color-error, #dc2626)" : safe >= 60 ? "var(--color-accent)" : "var(--color-info)",
  );
  // Text tier alongside the bar — users with color-vision deficiencies can
  // distinguish severity levels without relying on color alone.
  const tier = $derived(safe >= 75 ? "High" : safe >= 60 ? "Med" : "Low");
  const a11yLabel = $derived(
    value == null
      ? "Severity: not scored"
      : `Severity: ${Math.round(safe)} of 100 (${tier})`,
  );
</script>

<div class="severity-bar" role="img" aria-label={a11yLabel}>
  <div class="track">
    <div class="fill" style="width: {safe}%; background: {tone};"></div>
  </div>
  {#if showNumber}
    <span class="num">{value == null ? "—" : Math.round(safe)}</span>
    {#if showTier}
      <span class="tier" data-tier={tier.toLowerCase()} aria-hidden="true">{tier}</span>
    {/if}
  {/if}
</div>

<style>
  .severity-bar {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .track {
    width: 48px;
    height: 4px;
    background: var(--color-border);
    border-radius: 2px;
    overflow: hidden;
    position: relative;
  }
  .fill {
    height: 100%;
    border-radius: 2px;
  }
  .num {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-primary);
    font-weight: 600;
    min-width: 24px;
    text-align: right;
  }
  .tier {
    font-family: var(--font-mono);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid var(--color-border);
  }
  .tier[data-tier="high"] {
    color: var(--color-error, #dc2626);
    border-color: currentColor;
  }
  .tier[data-tier="med"] {
    color: var(--color-accent);
    border-color: currentColor;
  }
  .tier[data-tier="low"] {
    color: var(--color-info);
    border-color: currentColor;
  }
</style>
