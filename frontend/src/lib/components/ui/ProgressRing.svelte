<script lang="ts">
  import Tooltip from "$lib/components/ui/Tooltip.svelte";

  interface Props {
    value: number;
    size?: number;
    strokeWidth?: number;
    color?: "accent" | "success" | "error" | "warning" | "auto" | string;
    showValue?: boolean;
    showLabel?: boolean;
    label?: string;
    description?: string;
    animate?: boolean;
    showTooltip?: boolean;
    glow?: boolean;
    thick?: boolean;
    class?: string;
  }

  let {
    value,
    size = 80,
    strokeWidth = 6,
    color = "auto",
    showValue = true,
    showLabel = false,
    label = "",
    description = "",
    animate = true,
    showTooltip = true,
    glow = false,
    thick = false,
    class: className = "",
  }: Props = $props();

  // Adjust stroke width for thick variant
  const effectiveStrokeWidth = $derived(
    thick ? Math.max(strokeWidth, 7) : strokeWidth,
  );
  const radius = $derived((size - effectiveStrokeWidth) / 2);
  const circumference = $derived(2 * Math.PI * radius);
  const progress = $derived(Math.min(Math.max(value, 0), 1));
  const offset = $derived(circumference - progress * circumference);

  // Check if color is a custom hex/rgb value
  const isCustomColor = $derived(
    color.startsWith("#") || color.startsWith("rgb"),
  );

  // Auto color based on value thresholds
  const computedColor = $derived.by(() => {
    if (isCustomColor) return color;
    if (color !== "auto") return color;
    if (value >= 0.7) return "success";
    if (value >= 0.4) return "warning";
    return "error";
  });

  const colorVar = $derived.by(() => {
    if (isCustomColor) return computedColor;
    if (computedColor === "accent") return "var(--color-accent)";
    if (computedColor === "success") return "var(--color-success)";
    if (computedColor === "error") return "var(--color-error)";
    if (computedColor === "warning") return "var(--color-warning)";
    return "var(--color-accent)";
  });

  // Score interpretation for tooltip
  const scoreInterpretation = $derived.by(() => {
    const percentage = Math.round(value * 100);
    if (percentage >= 80) return "Excellent";
    if (percentage >= 70) return "Strong";
    if (percentage >= 50) return "Moderate";
    if (percentage >= 40) return "Needs Work";
    return "Critical";
  });

  // Build tooltip content string
  const tooltipContent = $derived.by(() => {
    const parts: string[] = [];
    if (description) parts.push(description);
    parts.push(`${Math.round(value * 100)}% — ${scoreInterpretation}`);
    if (label) parts.push(label);
    return parts.join("\n");
  });

  let visible = $state(false);
  let isHovered = $state(false);
  let ref: HTMLDivElement;

  $effect(() => {
    if (ref && animate) {
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            visible = true;
            observer.disconnect();
          }
        },
        { threshold: 0.3 },
      );
      observer.observe(ref);
      return () => observer.disconnect();
    } else if (!animate) {
      visible = true;
    }
  });
</script>

{#snippet ring()}
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div
    bind:this={ref}
    class="progress-ring {className}"
    class:hovered={isHovered}
    class:glow
    role="img"
    aria-label="{label || 'Score'}: {Math.round(value * 100)}%"
    onmouseenter={() => (isHovered = true)}
    onmouseleave={() => (isHovered = false)}
    style:--ring-color={colorVar}
  >
    <svg
      width={size}
      height={size}
      class="progress-ring-svg"
      overflow="visible"
    >
      <!-- Glow filter definition -->
      {#if glow}
        <defs>
          <filter id="glow-{size}" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
      {/if}
      <!-- Background circle -->
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="var(--color-bg-surface)"
        stroke-width={effectiveStrokeWidth}
        class="progress-ring-bg"
      />
      <!-- Progress circle -->
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={colorVar}
        stroke-width={effectiveStrokeWidth}
        stroke-linecap="round"
        stroke-dasharray={circumference}
        stroke-dashoffset={visible ? offset : circumference}
        class="progress-ring-progress"
        class:animate={animate && visible}
        class:hovered={isHovered}
        filter={glow ? `url(#glow-${size})` : undefined}
      />
    </svg>
    {#if showValue || showLabel}
      <div class="progress-ring-content">
        {#if showValue}
          <span class="progress-ring-value" style:color={colorVar}>
            {Math.round(value * 100)}
          </span>
        {/if}
        {#if showLabel && label}
          <span class="progress-ring-label">{label}</span>
        {/if}
      </div>
    {/if}
  </div>
{/snippet}

{#if showTooltip}
  <Tooltip content={tooltipContent} position="top">
    {#snippet children()}
      {@render ring()}
    {/snippet}
  </Tooltip>
{:else}
  {@render ring()}
{/if}

<style>
  .progress-ring {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    overflow: visible;
    cursor: help;
    transition: transform 0.2s ease;
  }

  .progress-ring:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 50%;
  }

  .progress-ring.hovered {
    transform: scale(1.06);
  }

  .progress-ring-svg {
    transform: rotate(-90deg);
  }

  .progress-ring-bg {
    opacity: 0.3;
  }

  .progress-ring-progress {
    filter: drop-shadow(0 0 4px currentColor);
    transition:
      stroke-dashoffset 0s,
      filter 0.2s ease;
  }

  .progress-ring-progress.animate {
    transition:
      stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1),
      filter 0.2s ease;
  }

  .progress-ring-progress.hovered {
    filter: drop-shadow(0 0 10px currentColor);
  }

  /* Enhanced glow effect */
  .progress-ring.glow .progress-ring-progress {
    filter: drop-shadow(0 0 6px var(--ring-color, currentColor));
  }

  .progress-ring.glow.hovered .progress-ring-progress {
    filter: drop-shadow(0 0 12px var(--ring-color, currentColor));
  }

  .progress-ring-content {
    position: absolute;
    inset: 4px; /* Match container padding to center over ring */
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.125rem;
  }

  .progress-ring-value {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1;
    transition: transform 0.2s ease;
  }

  .progress-ring.hovered .progress-ring-value {
    transform: scale(1.05);
  }

  .progress-ring-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }
</style>
