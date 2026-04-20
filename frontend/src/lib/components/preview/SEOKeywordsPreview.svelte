<script lang="ts">
  import { placeholderSEOStrategy } from "$lib/data/previewPlaceholders";

  interface Props {
    nicheName: string;
  }

  let { nicheName }: Props = $props();

  const data = $derived(placeholderSEOStrategy(nicheName));

  const tierCounts = $derived({
    0: data?.analytics?.tier0_count ?? 3,
    1: data?.analytics?.tier1_count ?? 8,
    2: data?.analytics?.tier2_count ?? 15,
    3: data?.analytics?.tier3_count ?? 22,
    4: data?.analytics?.tier4_count ?? 12,
  });
  const maxTierCount = $derived(Math.max(...Object.values(tierCounts), 1));
  const tiers = $derived([
    { label: "Tier 0 · Money Intent",  count: tierCounts[0], fillPct: (tierCounts[0] / maxTierCount) * 100 },
    { label: "Tier 1 · High Intent",   count: tierCounts[1], fillPct: (tierCounts[1] / maxTierCount) * 100 },
    { label: "Tier 2 · Informational", count: tierCounts[2], fillPct: (tierCounts[2] / maxTierCount) * 100 },
    { label: "Tier 3 · Geographic",    count: tierCounts[3], fillPct: (tierCounts[3] / maxTierCount) * 100 },
    { label: "Tier 4 · Category",      count: tierCounts[4], fillPct: (tierCounts[4] / maxTierCount) * 100 },
  ]);

  const topKeywords = $derived((data?.strategy?.tier_0_keywords ?? []).slice(0, 3));
  const sampleKeyword = $derived(topKeywords[0] ?? null);
  const blurredKeywords = $derived(topKeywords.slice(1));

  function formatVolume(n: number | undefined | null): string {
    if (n == null || !Number.isFinite(n)) return "0";
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return String(Math.round(n));
  }
</script>

<section id="seo" class="seo-preview">
  <span class="seo-preview-eyebrow">SEO Keyword Strategy</span>

  <div class="seo-preview-hero">
    <div class="seo-preview-score">
      <span class="preview-blur preview-locked" aria-hidden="true">
        {formatVolume(data?.analytics?.total_search_volume)}
      </span>
      <span class="seo-preview-score-unit">/month</span>
    </div>
    <div class="seo-preview-hero-meta">
      <span class="seo-preview-hero-label">Search Volume</span>
      <span class="seo-preview-hero-support">
        across
        <span class="preview-blur preview-locked" aria-hidden="true">{data?.analytics?.total_keywords ?? 60}</span>
        validated keywords
      </span>
    </div>
  </div>

  <div class="seo-preview-section">
    <h4 class="seo-preview-section-title">Keyword Tiers</h4>
    {#each tiers as tier (tier.label)}
      <div class="seo-preview-tier">
        <span class="seo-preview-tier-label">{tier.label}</span>
        <div class="seo-preview-tier-bar">
          <div
            class="seo-preview-tier-fill preview-blur preview-locked"
            style:width="{tier.fillPct}%"
            aria-hidden="true"
          ></div>
        </div>
      </div>
    {/each}
  </div>

  <div class="seo-preview-section">
    <h4 class="seo-preview-section-title">Top Keywords</h4>
    <div class="seo-preview-table">
      <div class="seo-preview-table-row seo-preview-table-header">
        <span>Keyword</span>
        <span>Volume</span>
        <span>Difficulty</span>
      </div>

      {#if sampleKeyword}
        <div class="seo-preview-table-row seo-preview-table-row--sample">
          <span class="sample-cell">
            {sampleKeyword.keyword}
            <span class="sample-badge">sample</span>
          </span>
          <span>{formatVolume(sampleKeyword.search_volume)}</span>
          <span>{sampleKeyword.keyword_difficulty ?? 0}</span>
        </div>
      {/if}

      {#each blurredKeywords as kw (kw.keyword)}
        <div class="seo-preview-table-row">
          <span class="preview-blur preview-locked" aria-hidden="true">{kw.keyword}</span>
          <span class="preview-blur preview-locked" aria-hidden="true">{formatVolume(kw.search_volume)}</span>
          <span class="preview-blur preview-locked" aria-hidden="true">{kw.keyword_difficulty ?? 0}</span>
        </div>
      {/each}
    </div>
  </div>
</section>

<style>
  .seo-preview {
    background: transparent;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 12%, transparent);
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 12%, transparent);
    padding: 2rem 0;
    margin-bottom: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .seo-preview-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
  }

  .seo-preview-hero {
    display: flex;
    align-items: center;
    gap: 1.25rem;
  }

  .seo-preview-score {
    display: flex;
    align-items: baseline;
    gap: 0.25rem;
    font-family: var(--font-display);
    font-weight: 800;
    line-height: 1;
    color: var(--color-text-primary);
  }
  .seo-preview-score > span:first-child {
    font-size: 2.5rem;
  }
  .seo-preview-score-unit {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
  }

  .seo-preview-hero-meta {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .seo-preview-hero-label {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .seo-preview-hero-support {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .seo-preview-section-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin: 0 0 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--color-border);
  }

  .seo-preview-tier {
    display: grid;
    grid-template-columns: 180px 1fr;
    align-items: center;
    gap: 0.75rem;
    padding: 0.375rem 0;
  }
  .seo-preview-tier-label {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-primary);
  }
  .seo-preview-tier-bar {
    height: 6px;
    background: var(--color-bg-surface);
    border-radius: 3px;
    overflow: hidden;
  }
  .seo-preview-tier-fill {
    height: 100%;
    background: var(--color-text-secondary);
    border-radius: 3px;
  }

  .seo-preview-table {
    display: flex;
    flex-direction: column;
  }
  .seo-preview-table-row {
    display: grid;
    grid-template-columns: 1fr 80px 80px;
    gap: 1rem;
    padding: 0.5rem 0;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    border-bottom: 1px solid var(--color-border);
  }
  .seo-preview-table-header {
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .seo-preview-table-header + .seo-preview-table-row {
    padding-top: 0.625rem;
  }

  .seo-preview-table-row--sample {
    color: var(--color-text-primary);
  }
  .sample-cell {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }
  .sample-badge {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
  }

  .preview-blur {
    filter: blur(5px);
    opacity: 0.5;
  }
  .preview-locked {
    user-select: none;
    pointer-events: none;
  }

  @media (max-width: 640px) {
    .seo-preview {
      padding: 1.5rem 0;
    }
    .seo-preview-hero {
      flex-direction: column;
      align-items: flex-start;
    }
    .seo-preview-tier {
      grid-template-columns: 1fr;
      gap: 0.375rem;
    }
  }
</style>
