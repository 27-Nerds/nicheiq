<script lang="ts">
  import { ArrowRight } from "lucide-svelte";

  type Variant = "report" | "discovery" | "sample";

  interface Props {
    variant: Variant;
    shareToken?: string;
  }

  let { variant, shareToken }: Props = $props();

  const tag = $derived(
    variant === "report" ? "Shared report"
    : variant === "discovery" ? "Shared discovery"
    : "Sample report",
  );

  const accessState = $derived(
    variant === "discovery" ? "Voting enabled" : "Read-only copy",
  );

  const registerUrl = $derived.by(() => {
    const params = new URLSearchParams({ ref: `shared-${variant}` });
    if (shareToken) params.set("t", shareToken);
    return `/register?${params.toString()}`;
  });
</script>

<aside class="shared-banner" aria-label={`${tag}: ${accessState}`}>
  <div class="shared-banner-inner">
    <p class="shared-banner-label">
      <span class="shared-banner-tag">{tag}</span>
      <span class="shared-banner-sep">·</span>
      <span class="shared-banner-meta">{accessState}</span>
    </p>
    <a href={registerUrl} class="shared-banner-cta">
      Research your own niche
      <ArrowRight class="shared-banner-icon" aria-hidden="true" />
    </a>
  </div>
</aside>

<style>
  .shared-banner {
    background: transparent;
    border-bottom: 1px solid var(--color-border);
  }

  .shared-banner-inner {
    max-width: 80rem;
    margin: 0 auto;
    padding: 0.75rem 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .shared-banner-label {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    white-space: nowrap;
  }

  .shared-banner-tag {
    color: var(--color-text-secondary);
    font-weight: 600;
  }

  .shared-banner-sep {
    opacity: 0.4;
  }

  .shared-banner-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 600;
    min-height: 2rem;
    padding-inline: 0.25rem;
    border-radius: var(--radius-sm);
    color: var(--color-accent-dark);
    text-decoration: none;
    transition:
      background-color var(--duration-fast) var(--ease-default),
      transform var(--duration-fast) var(--ease-default);
    white-space: nowrap;
  }

  .shared-banner-cta:hover {
    background: var(--color-bg-hover);
  }

  .shared-banner-cta:focus-visible {
    outline: 2px solid var(--color-accent-dark);
    outline-offset: 2px;
  }

  .shared-banner-cta:active {
    transform: scale(0.98);
  }

  :global(.shared-banner-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  @media (max-width: 640px) {
    .shared-banner-tag,
    .shared-banner-sep {
      display: none;
    }
    .shared-banner-inner {
      padding: 0.625rem 0.75rem;
    }
  }
</style>
