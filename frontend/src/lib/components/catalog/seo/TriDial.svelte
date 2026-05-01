<script lang="ts">
  // Catalog rebuild Tier 1 primitive — single concentric SVG ring gauge.
  // Used by Trifecta to render the demand/feasibility/opportunity score ring.
  // Pure presentational: no data fetching, no derived business logic.

  type DialType = "demand" | "feasibility" | "opportunity";
  type DialSize = "md" | "lg" | "xl";

  interface Props {
    type: DialType;
    /** 0-100. Clamped defensively. */
    value: number | null | undefined;
    size?: DialSize;
  }

  let { type, value, size = "md" }: Props = $props();

  // Stroke is fixed in pixels; SVG viewBox is 44 so the geometry doesn't
  // change with `size`. Outer pixel size comes from CSS `--s` per .lg/.xl.
  const radius = 18;
  const circumference = 2 * Math.PI * radius;

  const safeValue = $derived(
    value == null || !Number.isFinite(value) ? 0 : Math.max(0, Math.min(100, value)),
  );
  const dashOffset = $derived(circumference - (safeValue / 100) * circumference);

  const tone = $derived(
    type === "demand"
      ? "var(--color-accent)"
      : type === "feasibility"
        ? "var(--color-info)"
        : "var(--color-success)",
  );
</script>

<div class="tri-dial size-{size}" data-type={type}>
  <svg viewBox="0 0 44 44" aria-hidden="true">
    <circle cx="22" cy="22" r={radius} class="bg" />
    <circle
      cx="22"
      cy="22"
      r={radius}
      class="fg"
      style="stroke: {tone}; stroke-dasharray: {circumference}; stroke-dashoffset: {dashOffset};"
    />
  </svg>
  <span class="v">{value == null ? "—" : Math.round(safeValue)}</span>
</div>

<style>
  .tri-dial {
    position: relative;
    width: var(--s, 26px);
    height: var(--s, 26px);
    flex-shrink: 0;
  }
  .size-lg {
    --s: 60px;
  }
  .size-xl {
    --s: 88px;
  }
  .tri-dial svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  .bg {
    fill: none;
    stroke: var(--color-border);
    stroke-width: 3;
  }
  .fg {
    fill: none;
    stroke-width: 3;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.8s ease;
  }
  .size-xl .bg,
  .size-xl .fg {
    stroke-width: 4;
  }
  .v {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .size-lg .v {
    font-size: 14px;
  }
  .size-xl .v {
    font-size: 22px;
    font-weight: 600;
  }
</style>
