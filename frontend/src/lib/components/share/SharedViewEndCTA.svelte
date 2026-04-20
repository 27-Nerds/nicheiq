<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  type Variant = "report" | "discovery" | "sample";

  interface Props {
    variant: Variant;
    shareToken?: string;
  }

  let { variant, shareToken }: Props = $props();

  const eyebrow = $derived(
    variant === "report" ? "Shared report · end"
    : variant === "discovery" ? "Shared discovery · end"
    : "Sample report · end",
  );

  const headline = $derived(
    variant === "discovery"
      ? { primary: "You saw one niche discovered.", secondary: "Now run the research on yours." }
      : { primary: "You saw one niche analyzed.", secondary: "Now do the same for yours." },
  );

  const registerUrl = $derived(
    `/register?ref=shared-${variant}-end${shareToken ? `&t=${shareToken}` : ""}`,
  );
</script>

<section class="end-cta">
  <div class="end-cta-inner">
    <span class="end-cta-eyebrow">{eyebrow}</span>
    <h2 class="end-cta-title">
      {headline.primary}<br />{headline.secondary}
    </h2>
    <div class="end-cta-row">
      <a href={registerUrl} class="end-cta-primary">
        Research your own niche
        <ArrowRight class="end-cta-arrow" aria-hidden="true" />
      </a>
      <p class="end-cta-trust">
        No subscription · Pay per report · Credits valid forever
      </p>
    </div>
  </div>
</section>

<style>
  .end-cta {
    margin: 2rem 0 3rem;
    padding: 3rem 0;
    border-top: 1px solid var(--color-border-emphasis);
    border-bottom: 1px solid var(--color-border-emphasis);
  }

  .end-cta-inner {
    max-width: 40rem;
    margin: 0 auto;
    padding: 0 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .end-cta-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
  }

  .end-cta-title {
    font-family: var(--font-display);
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    margin: 0;
  }

  .end-cta-row {
    display: flex;
    align-items: center;
    gap: 1.25rem;
    flex-wrap: wrap;
    margin-top: 0.5rem;
  }

  .end-cta-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.875rem 1.5rem;
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-family: var(--font-body);
    font-size: 0.9375rem;
    font-weight: 600;
    text-decoration: none;
    transition: background-color 150ms ease;
    white-space: nowrap;
  }

  .end-cta-primary:hover {
    background: var(--color-accent-dark);
  }

  .end-cta-primary:active {
    transform: scale(0.98);
  }

  :global(.end-cta-arrow) {
    width: 1rem;
    height: 1rem;
  }

  .end-cta-trust {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    letter-spacing: 0.03em;
    margin: 0;
  }

  @media (max-width: 640px) {
    .end-cta {
      padding: 2rem 0;
    }
    .end-cta-title {
      font-size: 1.375rem;
    }
  }
</style>
