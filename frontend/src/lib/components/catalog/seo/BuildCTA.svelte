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
    transition: all 0.12s ease;
    white-space: nowrap;
  }
  .btn-accent {
    background: var(--color-accent);
    color: var(--color-surface, #fff);
  }
  .btn-accent:hover {
    background: var(--color-accent-hover, var(--color-accent-dark));
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
