<script lang="ts">
  import ProgressRing from "./ProgressRing.svelte";

  interface Props {
    value: number; // 0-1 for percentage
    label: string;
    sublabel?: string;
    color?: "auto" | "success" | "warning" | "error" | "accent";
    size?: number;
    strokeWidth?: number;
    showValue?: boolean;
    class?: string;
  }

  let {
    value,
    label,
    sublabel,
    color = "auto",
    size = 56,
    strokeWidth = 6,
    showValue = true,
    class: className = "",
  }: Props = $props();

  // Determine color based on value if auto
  const effectiveColor = $derived.by(() => {
    if (color !== "auto") return color;
    if (value >= 0.7) return "success";
    if (value >= 0.4) return "warning";
    return "error";
  });

  // Format percentage for display
  const displayValue = $derived(Math.round(value * 100));
</script>

<div class="hero-primary hero-primary--{effectiveColor} {className}">
  <div class="hero-primary__ring">
    <ProgressRing
      {value}
      {size}
      {strokeWidth}
      color={effectiveColor}
      {showValue}
      glow={true}
    />
  </div>
  <div class="hero-primary__content">
    <span class="hero-primary__label">{label}</span>
    {#if sublabel}
      <span class="hero-primary__sublabel">{sublabel}</span>
    {:else}
      <span class="hero-primary__value">{displayValue}%</span>
    {/if}
  </div>
</div>

<style>
  .hero-primary {
    display: flex;
    align-items: center;
    gap: 0.875rem;
  }

  .hero-primary__ring {
    flex-shrink: 0;
  }

  .hero-primary__content {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .hero-primary__label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-muted);
  }

  .hero-primary__value {
    font-family: var(--font-display);
    font-size: 1.375rem;
    font-weight: 800;
    line-height: 1.1;
    color: var(--color-text-primary);
  }

  .hero-primary__sublabel {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  /* Color-coded value */
  .hero-primary--success .hero-primary__value,
  .hero-primary--success .hero-primary__sublabel {
    color: var(--color-success);
  }

  .hero-primary--warning .hero-primary__value,
  .hero-primary--warning .hero-primary__sublabel {
    color: var(--color-warning);
  }

  .hero-primary--error .hero-primary__value,
  .hero-primary--error .hero-primary__sublabel {
    color: var(--color-error);
  }

  .hero-primary--accent .hero-primary__value,
  .hero-primary--accent .hero-primary__sublabel {
    color: var(--color-accent);
  }

  /* Responsive */
  @media (max-width: 768px) {
    .hero-primary__value {
      font-size: 1.25rem;
    }

    .hero-primary__sublabel {
      font-size: 0.875rem;
    }
  }
</style>
