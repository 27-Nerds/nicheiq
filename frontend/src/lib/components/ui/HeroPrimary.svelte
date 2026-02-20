<script lang="ts">
  import type { ComponentType } from "svelte";
  import ProgressRing from "./ProgressRing.svelte";

  interface Props {
    value?: number; // 0-1 for percentage (optional when icon mode)
    label: string;
    sublabel?: string;
    color?: "auto" | "success" | "warning" | "error" | "accent";
    size?: number;
    strokeWidth?: number;
    showValue?: boolean;
    icon?: ComponentType; // NEW — triggers icon mode
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
    icon: Icon,
    class: className = "",
  }: Props = $props();

  // Determine color based on value if auto
  const effectiveColor = $derived.by(() => {
    if (color !== "auto") return color;
    if (value === undefined) return "accent";
    if (value >= 0.7) return "success";
    if (value >= 0.4) return "warning";
    return "error";
  });

  // Format percentage for display
  const displayValue = $derived(value !== undefined ? Math.round(value * 100) : 0);

  // Icon color CSS variable
  const iconColorVar = $derived.by(() => {
    const c = effectiveColor;
    if (c === "success") return "var(--color-success)";
    if (c === "warning") return "var(--color-warning)";
    if (c === "error") return "var(--color-error)";
    return "var(--color-accent)";
  });
</script>

<div class="hero-primary hero-primary--{effectiveColor} {className}">
  {#if Icon}
    <div class="hero-primary__icon-circle" style="--icon-color: {iconColorVar}">
      <Icon size={18} />
    </div>
  {:else if value !== undefined}
    <div class="hero-primary__ring">
      <ProgressRing
        {value}
        {size}
        {strokeWidth}
        color={effectiveColor}
        {showValue}
        flat={true}
      />
    </div>
  {/if}
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

  .hero-primary__icon-circle {
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--icon-color) 12%, transparent);
    border: 2px solid var(--icon-color);
    border-radius: 50%;
    color: var(--icon-color);
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
