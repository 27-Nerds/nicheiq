<script lang="ts">
  // Horizontal labeled progress bar — alt for the Trifecta dial in dense
  // layouts (e.g., idea-detail dashboard variant). 0-100 input.

  type BarType = "demand" | "feasibility" | "opportunity" | "originality" | "soloDev";

  interface Props {
    label: string;
    /** 0-100. Clamped defensively. */
    value: number | null | undefined;
    type?: BarType;
  }

  let { label, value, type = "demand" }: Props = $props();

  const safe = $derived(
    value == null || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(100, value)),
  );
  const tone = $derived.by(() => {
    switch (type) {
      case "demand": return "var(--color-accent)";
      case "feasibility": return "var(--color-info)";
      case "opportunity": return "var(--color-success)";
      case "originality": return "var(--color-secondary, #6366F1)";
      case "soloDev": return "var(--color-text-secondary, #52525B)";
    }
  });
</script>

<div class="score-bar">
  <span class="label">{label}</span>
  <div class="track">
    <div class="fill" style="width: {safe}%; background: {tone};"></div>
  </div>
  <span class="num">{value == null ? "—" : Math.round(safe)}</span>
</div>

<style>
  .score-bar {
    display: grid;
    grid-template-columns: 90px 1fr 36px;
    gap: 10px;
    align-items: center;
    font-size: 12px;
  }
  .label {
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 10px;
    font-weight: 600;
  }
  .track {
    height: 5px;
    background: var(--color-border);
    border-radius: 3px;
    overflow: hidden;
    position: relative;
  }
  .fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.8s ease;
  }
  .num {
    font-family: var(--font-mono);
    color: var(--color-text-primary);
    font-weight: 600;
    text-align: right;
  }
</style>
