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
  }

  let { value, showNumber = true }: Props = $props();

  const safe = $derived(
    value == null || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(100, value)),
  );
  const tone = $derived(
    safe >= 75 ? "var(--color-error, #dc2626)" : safe >= 60 ? "var(--color-accent)" : "var(--color-info)",
  );
</script>

<div class="severity-bar">
  <div class="track">
    <div class="fill" style="width: {safe}%; background: {tone};"></div>
  </div>
  {#if showNumber}
    <span class="num">{value == null ? "—" : Math.round(safe)}</span>
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
</style>
