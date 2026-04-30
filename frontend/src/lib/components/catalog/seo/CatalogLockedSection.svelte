<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  // Phase 5.3 lock pattern. Renders summary-only — NO real data behind blur.
  // Security boundary: filter:blur is cosmetic (DevTools leaks blurred text);
  // we render zero real-content DOM and lean on the typographic + accent-ring
  // chrome to communicate "locked".
  //
  // No Lock icon: anti-slop call. The padlock glyph is the universal SaaS
  // gating cliché; the badge copy + accent ring carry the signal alone.
  interface Props {
    title: string;        // e.g., "GTM Playbook"
    summary: string;      // 1–2 sentence value description
    ctaHref: string;      // e.g., "/register?ref=catalog&unlock=gtm"
    ctaLabel?: string;
  }

  let {
    title,
    summary,
    ctaHref,
    ctaLabel = "See the full research file",
  }: Props = $props();
</script>

<div class="cat-locked">
  <header class="cat-locked-header">
    <h2 class="cat-locked-title">{title}</h2>
    <span class="cat-locked-badge">Subscribe to unlock</span>
  </header>
  <p class="cat-locked-summary">{summary}</p>
  <a class="cat-locked-cta" href={ctaHref} data-sveltekit-preload-data="hover">
    <span class="cat-locked-cta-label">{ctaLabel}</span>
    <ArrowRight class="cat-locked-arrow" aria-hidden="true" />
  </a>
</div>

<style>
  .cat-locked {
    display: flex;
    flex-direction: column;
    gap: 0.875rem;
  }

  .cat-locked-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .cat-locked-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    letter-spacing: -0.01em;
  }

  /* Accent-ring badge — 1px exactly. Signals "you can get this" without
     the filled-pill loudness of a Subscribe CTA. NO padlock icon, NO
     backdrop-blur. */
  .cat-locked-badge {
    display: inline-block;
    padding: 0.25rem 0.625rem;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    background: transparent;
    box-shadow: inset 0 0 0 1px var(--color-accent);
    border-radius: 999px;
  }

  .cat-locked-summary {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.0625rem;
    font-weight: 500;
    line-height: 1.55;
    color: var(--color-text-muted);
    max-width: 65ch;
    text-wrap: pretty;
  }

  .cat-locked-cta {
    display: inline-flex;
    align-items: baseline;
    gap: 0.375rem;
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    text-decoration: none;
    transition: color 140ms ease;
  }

  .cat-locked-cta-label {
    background-image: linear-gradient(currentColor, currentColor);
    background-position: 0 100%;
    background-size: 0% 1px;
    background-repeat: no-repeat;
    transition: background-size 200ms ease;
  }

  .cat-locked-cta:hover {
    color: var(--color-accent);
  }

  .cat-locked-cta:hover .cat-locked-cta-label {
    background-size: 100% 1px;
  }

  :global(.cat-locked-arrow) {
    width: 0.875rem;
    height: 0.875rem;
    align-self: center;
  }

  @media (prefers-reduced-motion: reduce) {
    .cat-locked-cta,
    .cat-locked-cta-label {
      transition: none;
    }
  }
</style>
