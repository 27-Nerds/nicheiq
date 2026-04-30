<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import { page } from "$app/state";
  import type {
    CatalogResearchContext,
    PainPointPreview,
  } from "$lib/types/catalog-landing";

  interface Props {
    painPoint: PainPointPreview;
    researchContext: CatalogResearchContext | null;
  }

  let { painPoint, researchContext }: Props = $props();

  const session = $derived(page.data.session);
  const subscribeHref = $derived(
    session?.user
      ? "/new"
      : `/register?ref=catalog&slug=${encodeURIComponent(painPoint.slug)}`,
  );

  const updatedLabel = $derived(
    painPoint.updatedAt
      ? new Date(painPoint.updatedAt).toLocaleDateString("en-GB", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })
      : null,
  );

  const tags = $derived.by(() => {
    const out: string[] = [];
    if (painPoint.opportunityLevel)
      out.push(`${painPoint.opportunityLevel} opportunity`);
    if (painPoint.affectedSegments?.length)
      out.push(painPoint.affectedSegments[0]);
    return out.slice(0, 4);
  });

  const showsTier = $derived(
    researchContext?.dataQualityTier === "GOLD" ||
      researchContext?.dataQualityTier === "SILVER",
  );

  function pct(v: number | null | undefined): string {
    return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
  }
</script>

<header class="pp-hero">
  <h1 class="pp-hero-title marker-rule">{painPoint.title}</h1>

  {#if painPoint.description}
    <p class="pp-hero-dek">{painPoint.description.slice(0, 200)}</p>
  {/if}

  {#if tags.length > 0}
    <ul class="pp-hero-tags" aria-label="Tags">
      {#each tags as tag}
        <li class="tag-chip">{tag}</li>
      {/each}
    </ul>
  {/if}

  <p class="pp-hero-provenance">
    <span>Research file</span>
    <span class="prov-sep">·</span>
    <span>Reddit · Hacker News</span>
    {#if updatedLabel}
      <span class="prov-sep">·</span>
      <span>Updated {updatedLabel}</span>
    {/if}
    {#if showsTier}
      <span class="prov-sep">·</span>
      <span>{researchContext!.dataQualityTier} tier</span>
    {/if}
  </p>

  <div class="pp-hero-metrics" aria-label="Pain point metrics">
    <div class="metric-cell">
      <div class="metric-value tabular-nums">{pct(painPoint.severityScore)}</div>
      <div class="metric-label">SEVERITY</div>
    </div>
    <div class="metric-cell">
      <div class="metric-value tabular-nums">{pct(painPoint.willingnessToPayScore)}</div>
      <div class="metric-label">WILLINGNESS</div>
    </div>
    <div class="metric-cell">
      <div class="metric-value tabular-nums">{painPoint.mentionCount ?? 0}</div>
      <div class="metric-label">MENTIONS</div>
    </div>
    <div class="metric-cell">
      <div class="metric-value tabular-nums">
        {Array.isArray(painPoint.representativeQuotes)
          ? painPoint.representativeQuotes.length
          : 0}
      </div>
      <div class="metric-label">QUOTES</div>
    </div>
  </div>

  <div class="pp-hero-cta">
    <a class="subscribe-button" href={subscribeHref} data-sveltekit-preload-data="hover">
      <span>Subscribe</span>
      <ArrowRight class="subscribe-icon" aria-hidden="true" />
    </a>
  </div>
</header>

<style>
  .pp-hero {
    margin-bottom: 3rem;
  }

  .pp-hero-title {
    font-family: var(--font-display);
    font-size: clamp(2rem, 5vw, 3.5rem);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.025em;
    color: var(--color-text-primary);
    margin: 0 0 0.5rem 0;
    text-wrap: balance;
  }

  .pp-hero-dek {
    font-size: 1.125rem;
    line-height: 1.6;
    color: var(--color-text-muted);
    margin: 1.25rem 0 0;
    text-wrap: pretty;
    max-width: 60ch;
  }

  .pp-hero-tags {
    list-style: none;
    padding: 0;
    margin: 1.25rem 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .tag-chip {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: transparent;
  }

  .pp-hero-provenance {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: 1.5rem 0 0;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem 0.5rem;
    font-feature-settings: "tnum" 1, "ss01" 1;
  }

  .prov-sep {
    color: var(--color-border);
  }

  .pp-hero-metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    margin-top: 2rem;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }

  @media (max-width: 640px) {
    .pp-hero-metrics {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .metric-cell {
    padding: 1.125rem 1rem;
    border-left: 1px solid var(--color-border);
    text-align: center;
  }

  .metric-cell:first-child {
    border-left: none;
  }

  @media (max-width: 640px) {
    .metric-cell:nth-child(odd) {
      border-left: none;
    }
    .metric-cell:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }
  }

  .metric-value {
    font-family: var(--font-display);
    font-size: 1.625rem;
    font-weight: 700;
    line-height: 1.1;
    color: var(--color-text-primary);
  }

  .metric-label {
    margin-top: 0.375rem;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .pp-hero-cta {
    display: flex;
    justify-content: flex-end;
    margin-top: 2rem;
  }

  @media (max-width: 640px) {
    .pp-hero-cta {
      justify-content: stretch;
    }
  }

  .subscribe-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: white;
    background: var(--color-accent);
    border-radius: 999px;
    text-decoration: none;
    transition:
      background-color 140ms ease,
      transform 60ms ease;
  }

  @media (max-width: 640px) {
    .subscribe-button {
      width: 100%;
      justify-content: center;
    }
  }

  .subscribe-button:hover {
    background: var(--color-accent-hover, var(--color-accent));
  }

  .subscribe-button:active {
    transform: scale(0.98);
  }

  :global(.subscribe-icon) {
    width: 1rem;
    height: 1rem;
  }

  @media (prefers-reduced-motion: reduce) {
    .subscribe-button {
      transition: none;
    }
  }
</style>
