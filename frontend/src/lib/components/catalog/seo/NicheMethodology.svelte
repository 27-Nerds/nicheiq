<script lang="ts">
  import type { NicheContext, QualitySignals } from "$lib/types/publicCatalog.js";

  // "About this niche" — methodology footer for sub-niche pages.
  // Renders the scope / market-segments / research-metadata that previously
  // lived in the hero. Editorial-quiet treatment so it reads as supplementary
  // context after the main report content.

  interface Props {
    nicheContext?: NicheContext | null;
    /** Items mined from social discussions for this niche. Pass through
     *  `data.payload.contentItemsMined`. */
    contentItemsMined?: number | null;
    /** Number of unique source communities (subreddits, forums, etc.).
     *  Backend exposes as a number, NOT an array. */
    sourceCommunities?: number | null;
    /** Quality signals (content tier, confidence). When null, omit. */
    qualitySignals?: QualitySignals | null;
  }

  let {
    nicheContext = null,
    contentItemsMined = null,
    sourceCommunities = null,
    qualitySignals = null,
  }: Props = $props();

  const industryBoundaries = $derived(nicheContext?.industryBoundaries ?? null);
  const marketSegments = $derived(nicheContext?.marketSegments ?? null);

  // Map the raw enum value to a human-readable label.
  function tierLabel(tier: string | null | undefined): string | null {
    if (!tier) return null;
    switch (tier) {
      case "EXCELLENT":
        return "Excellent quality";
      case "GOOD":
        return "Good quality";
      case "MINIMAL":
        return "Minimal data";
      case "INSUFFICIENT":
        return "Insufficient data";
      default:
        return null;
    }
  }

  const tierText = $derived(tierLabel(qualitySignals?.contentTier));
  const confidenceText = $derived(
    qualitySignals?.confidenceScore != null
      ? `${qualitySignals.confidenceScore.toFixed(2)} confidence`
      : null,
  );

  const hasMetadataRow = $derived(
    contentItemsMined != null ||
      sourceCommunities != null ||
      tierText != null ||
      confidenceText != null,
  );

  const hasContent = $derived(
    !!industryBoundaries ||
      (marketSegments && marketSegments.length > 0) ||
      hasMetadataRow,
  );
</script>

{#if hasContent}
  <section class="nm" aria-label="About this niche">
    {#if industryBoundaries}
      <div class="nm-block">
        <span class="nm-kicker">Industry scope</span>
        <p class="nm-prose">{industryBoundaries}</p>
      </div>
    {/if}

    {#if marketSegments && marketSegments.length > 0}
      <div class="nm-block">
        <span class="nm-kicker">
          Primary segments
          <span class="nm-kicker-sep" aria-hidden="true">·</span>
          <span class="nm-kicker-count">{marketSegments.length}</span>
        </span>
        <ul class="nm-segments">
          {#each marketSegments as seg, _i (seg)}
            <li title={seg}>
              <span class="nm-bullet" aria-hidden="true">·</span>
              <span class="nm-text">{seg}</span>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if hasMetadataRow}
      <div class="nm-meta">
        {#if contentItemsMined != null}
          <span class="nm-meta-cell">
            <strong>{contentItemsMined.toLocaleString()}</strong> items analyzed
          </span>
        {/if}
        {#if sourceCommunities != null && sourceCommunities > 0}
          <span class="nm-meta-cell">
            <strong>{sourceCommunities}</strong> communities
          </span>
        {/if}
        {#if tierText}
          <span class="nm-meta-cell nm-tier" data-tier={qualitySignals?.contentTier?.toLowerCase()}>
            {tierText}
          </span>
        {/if}
        {#if confidenceText}
          <span class="nm-meta-cell">{confidenceText}</span>
        {/if}
      </div>
    {/if}
  </section>
{/if}

<style>
  .nm {
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 22px 24px;
    margin: 16px 0 32px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .nm-block {
    min-width: 0;
  }
  .nm-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin: 0 0 8px;
  }
  .nm-kicker-sep {
    opacity: 0.55;
    margin: 0 4px;
  }
  .nm-kicker-count {
    color: var(--color-text-secondary);
  }
  .nm-prose {
    font-size: 12.5px;
    line-height: 1.65;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 720px;
    margin: 0;
    overflow-wrap: anywhere;
  }
  .nm-segments {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 24px;
    row-gap: 4px;
  }
  .nm-segments li {
    display: grid;
    grid-template-columns: 12px 1fr;
    gap: 8px;
    align-items: baseline;
    padding: 4px 0;
  }
  .nm-bullet {
    font-family: var(--font-mono);
    color: var(--color-accent-muted, rgba(154, 52, 18, 0.7));
    font-size: 14px;
    line-height: 1;
    align-self: center;
  }
  .nm-text {
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--color-text-primary);
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }

  .nm-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    align-items: baseline;
    padding-top: 14px;
    border-top: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
  }
  .nm-meta-cell strong {
    color: var(--color-text-primary);
    font-weight: 700;
  }
  .nm-tier {
    font-weight: 600;
  }
  .nm-tier[data-tier="excellent"],
  .nm-tier[data-tier="good"] {
    color: var(--color-success-dark);
  }
  .nm-tier[data-tier="minimal"],
  .nm-tier[data-tier="insufficient"] {
    color: var(--color-text-muted);
  }

  @media (max-width: 640px) {
    .nm {
      padding: 18px 18px;
    }
    .nm-segments {
      grid-template-columns: 1fr;
    }
    .nm-text {
      -webkit-line-clamp: 3;
      line-clamp: 3;
    }
  }
</style>
