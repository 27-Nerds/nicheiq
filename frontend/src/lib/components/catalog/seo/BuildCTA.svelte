<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import Sparkles from "lucide-svelte/icons/sparkles";

  interface Props {
    headline?: string;
    body?: string;
    ctaLabel?: string;
    ctaHref: string;
    secondaryLabel?: string | null;
    secondaryHref?: string | null;
  }

  let {
    headline = "Ready to build?",
    body = "Generate a 30-day GTM plan, landing-page copy, and outbound list — all tuned to this idea's audience and verdict.",
    ctaLabel = "Generate plan",
    ctaHref,
    secondaryLabel = null,
    secondaryHref = null,
  }: Props = $props();
</script>

<section class="build-cta">
  <div class="copy">
    <h3>{headline}</h3>
    <p>{body}</p>
  </div>
  <div class="actions">
    <a class="btn-accent" href={ctaHref} data-sveltekit-preload-data="hover">
      <Sparkles size={14} />
      <span>{ctaLabel}</span>
    </a>
    {#if secondaryLabel && secondaryHref}
      <a class="btn-ghost" href={secondaryHref}>
        <span>{secondaryLabel}</span>
        <ArrowRight size={14} />
      </a>
    {/if}
  </div>
</section>

<style>
  .build-cta {
    background: var(--color-surface-elevated, #fafafa);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 28px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    flex-wrap: wrap;
    margin: 48px 0;
  }
  .copy {
    max-width: 560px;
  }
  h3 {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.015em;
    margin: 0 0 6px;
    color: var(--color-text-primary);
  }
  p {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.55;
    margin: 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .btn-accent,
  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    border: 1px solid transparent;
    transition: background-color 140ms ease, box-shadow 140ms ease,
      transform 140ms ease, color 140ms ease, border-color 140ms ease;
    white-space: nowrap;
    will-change: transform;
  }
  /* Three-layer shadow anatomy on the primary CTA. Brand-tinted ambient
     ties depth to the accent identity rather than defaulting to neutral.
     Active-state press compresses the stack and applies a 0.98 scale. */
  .btn-accent {
    background: var(--color-accent);
    color: var(--color-surface, #fff);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.18),
      0 1px 2px rgba(154, 52, 18, 0.18),
      0 6px 14px rgba(154, 52, 18, 0.10);
  }
  .btn-accent:hover {
    background: var(--color-accent-hover, var(--color-accent-dark));
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.20),
      0 2px 4px rgba(154, 52, 18, 0.22),
      0 8px 18px rgba(154, 52, 18, 0.12);
  }
  .btn-accent:active {
    transform: scale(0.98);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.12),
      0 1px 1px rgba(154, 52, 18, 0.20);
  }
  .btn-accent:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .btn-ghost {
    color: var(--color-text-secondary, var(--color-text-primary));
    border-color: var(--color-border-emphasis);
    background: var(--color-surface, #fff);
  }
  .btn-ghost:hover {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
  }
</style>
