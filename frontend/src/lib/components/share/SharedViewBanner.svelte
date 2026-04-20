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

  const registerUrl = $derived(
    `/register?ref=shared-${variant}${shareToken ? `&t=${shareToken}` : ""}`,
  );
</script>

<div class="shared-banner">
  <div class="shared-banner-inner">
    <p class="shared-banner-label">
      <span class="shared-banner-tag">{tag}</span>
      <span class="shared-banner-sep">·</span>
      <span class="shared-banner-meta">view only</span>
    </p>
    <a href={registerUrl} class="shared-banner-cta">
      Research your own niche
      <ArrowRight class="shared-banner-icon" aria-hidden="true" />
    </a>
  </div>
</div>

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
    color: var(--color-accent);
    text-decoration: none;
    transition: color 150ms ease;
    white-space: nowrap;
  }

  .shared-banner-cta:hover {
    color: var(--color-accent-dark);
  }

  :global(.shared-banner-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  @media (max-width: 640px) {
    .shared-banner-meta,
    .shared-banner-sep {
      display: none;
    }
    .shared-banner-inner {
      padding: 0.625rem 0.75rem;
    }
  }
</style>
