<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import { page } from "$app/state";

  interface Props {
    variant?: "top" | "bottom";
    headline?: string;
    subhead?: string;
    href?: string;
    ctaLabel?: string;
  }

  let {
    variant = "bottom",
    headline = "Run research on your niche.",
    subhead = "NicheIQ scans real Reddit and Hacker News discussions, surfaces validated pain points and audience segments, and returns a launch-ready report in under an hour.",
    href,
    ctaLabel,
  }: Props = $props();

  const session = $derived(page.data.session);
  const resolvedHref = $derived(href ?? (session?.user ? "/new" : "/register"));
  const resolvedLabel = $derived(
    ctaLabel ?? (session?.user ? "Run your own research" : "Get started"),
  );
</script>

<aside class="public-cta public-cta--{variant}" aria-label="Call to action">
  <div class="public-cta-inner">
    <h2 class="public-cta-headline">{headline}</h2>
    {#if subhead}
      <p class="public-cta-subhead">{subhead}</p>
    {/if}
    <a
      class="public-cta-button"
      href={resolvedHref}
      data-sveltekit-preload-data="hover"
    >
      <span class="public-cta-label">{resolvedLabel}</span>
      <ArrowRight class="public-cta-icon" aria-hidden="true" />
    </a>
  </div>
</aside>

<style>
  .public-cta {
    margin: 3rem 0;
    padding: 2rem 1.5rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
  }

  @media (min-width: 768px) {
    .public-cta {
      padding: 3rem 2.5rem;
    }
  }

  .public-cta--top {
    /* Smaller / less prominent when used above the main content */
    padding: 1.5rem;
    margin: 0 0 2rem 0;
  }

  .public-cta-inner {
    max-width: 48rem;
    margin: 0 auto;
    text-align: center;
  }

  .public-cta-headline {
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 3vw, 2rem);
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    letter-spacing: -0.02em;
    margin: 0;
    text-wrap: balance;
  }

  .public-cta-subhead {
    margin: 0.875rem auto 0;
    max-width: 36rem;
    font-size: 0.9375rem;
    color: var(--color-text-muted);
    line-height: 1.6;
    text-wrap: pretty;
  }

  .public-cta-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1.5rem;
    padding: 0.75rem 1.5rem;
    font-weight: 600;
    color: var(--color-text-primary);
    background: transparent;
    border-radius: 0.5rem;
    text-decoration: none;
    transition: color 140ms ease, transform 60ms ease;
  }

  .public-cta-label {
    position: relative;
  }

  /* Underline-from-left on hover */
  .public-cta-label::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: -0.125rem;
    height: 1px;
    width: 0;
    background: var(--color-accent);
    transition: width 200ms ease;
  }

  .public-cta-button:hover .public-cta-label::after {
    width: 100%;
  }

  .public-cta-button:hover {
    color: var(--color-accent);
  }

  .public-cta-button:active {
    transform: scale(0.98);
  }

  :global(.public-cta-icon) {
    width: 1rem;
    height: 1rem;
  }

  @media (prefers-reduced-motion: reduce) {
    .public-cta-button,
    .public-cta-label::after {
      transition: none;
    }
  }
</style>
