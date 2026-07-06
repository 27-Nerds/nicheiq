<script lang="ts">
  import { scrollVisible } from "$lib/actions/scrollVisible";
  import type { DiscoveryData } from "$lib/types/discovery";

  interface Props {
    data: DiscoveryData | null;
  }

  let { data }: Props = $props();

  // Source posts: show first 3, expand to all
  let showAllSources = $state(false);
  const INITIAL_SOURCE_COUNT = 5;
  const displayedSources = $derived(
    data?.social_posts_sample
      ? (showAllSources ? data.social_posts_sample : data.social_posts_sample.slice(0, INITIAL_SOURCE_COUNT))
      : []
  );
  const totalSources = $derived(data?.social_posts_sample?.length ?? 0);

  // Source distribution: use real post counts when available, fall back to sample
  const subredditDistribution = $derived.by(() => {
    let entries: [string, number][];

    if (data?.subreddit_post_counts && Object.keys(data.subreddit_post_counts).length > 0) {
      // Real counts from full dataset (150+ posts)
      entries = Object.entries(data.subreddit_post_counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
    } else {
      // Fallback: compute from 10-item sample (legacy jobs)
      const counts: Record<string, number> = {};
      for (const post of data?.social_posts_sample ?? []) {
        counts[post.subreddit] = (counts[post.subreddit] ?? 0) + 1;
      }
      entries = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
    }

    const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
    return entries.map(([name, count], i) => ({
      name,
      count,
      percent: Math.round(count / total * 100),
      opacity: 1 - (i * 0.15),
    }));
  });

  // Hide distribution bars when distribution is flat (all bars ~equal = no insight)
  const isDistributionFlat = $derived(
    subredditDistribution.length > 0 &&
    subredditDistribution[0].percent <= (subredditDistribution[subredditDistribution.length - 1].percent * 2)
  );
</script>

{#if data}
  <div class="evidence">
    <!-- Source Distribution Bars (hidden when flat/uniform) -->
    {#if subredditDistribution.length > 0 && !isDistributionFlat}
      <div class="evidence-section">
        <span class="evidence-label">Source Distribution</span>
        <div class="dist-bars">
          {#each subredditDistribution as sub (sub.name)}
            <div class="tier-bar" use:scrollVisible>
              <span class="tier-bar-label">{sub.name}</span>
              <div class="tier-bar-track">
                <div
                  class="tier-bar-fill"
                  style="--fill-pct: {sub.percent / 100}; background: var(--color-accent); opacity: {sub.opacity}"
                ></div>
              </div>
              <span class="tier-bar-count">{sub.percent}%</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Source Feed (HackerNews style) -->
    {#if displayedSources.length > 0}
      <div class="evidence-section">
        <span class="evidence-label">Real Conversations</span>
        <div class="source-feed">
          {#each displayedSources as post (post.url)}
            <a href={post.url} target="_blank" rel="noopener noreferrer" class="source-row">
              <span class="source-score">{post.score.toLocaleString()}</span>
              <span class="source-title">{post.title}</span>
              <span class="source-meta">
                {post.subreddit}
                <span class="source-comments">{post.num_comments} comments</span>
              </span>
            </a>
          {/each}
        </div>
        {#if totalSources > INITIAL_SOURCE_COUNT}
          <button
            type="button"
            class="expand-btn"
            onclick={() => { showAllSources = !showAllSources; }}
          >
            {showAllSources ? "Show fewer" : `Show all ${totalSources} sources \u2192`}
          </button>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .evidence {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 0.84rem;
  }

  .evidence-section {
    display: flex;
    flex-direction: column;
    gap: 0.64rem;
  }

  .evidence-label {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }

  /* Tier bar overrides for custom fill width */
  .dist-bars {
    display: grid;
    gap: 0.44rem;
    padding: 0.66rem 0.72rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
    border-radius: 0.72rem;
    background: color-mix(in srgb, var(--color-bg-surface) 62%, transparent);
  }

  .tier-bar {
    display: grid;
    grid-template-columns: 6.8rem minmax(0, 1fr) 2.35rem;
    align-items: center;
    gap: 0.75rem;
  }

  .tier-bar-label {
    min-width: 0;
    color: var(--color-text-secondary);
    font-size: 0.78rem;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tier-bar-track {
    height: 0.36rem;
    overflow: hidden;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-border) 52%, transparent);
  }

  .tier-bar-fill {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    transform-origin: left center;
    transition: transform 560ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .tier-bar-count {
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.74rem;
    font-weight: 780;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .dist-bars :global(.tier-bar-fill) {
    transform: scaleX(0);
  }
  .dist-bars :global(.tier-bar.visible .tier-bar-fill) {
    transform: scaleX(var(--fill-pct));
  }

  .source-feed {
    display: flex;
    flex-direction: column;
    gap: 0;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
  }

  .source-row {
    display: grid;
    grid-template-columns: 3.4rem 1fr;
    grid-template-rows: auto auto;
    gap: 0.04rem 0.78rem;
    padding: 0.58rem 0.12rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 68%, transparent);
    background: transparent;
    text-decoration: none;
    transition:
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .source-row:last-child {
    border-bottom: 0;
  }

  .source-row:hover {
    transform: translateX(2px);
  }

  .source-row:active {
    transform: scale(0.998);
  }

  .source-score {
    grid-row: 1 / -1;
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 0.78rem;
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
    text-align: right;
    padding-top: 0.125rem;
  }

  .source-title {
    font-size: 0.78rem;
    font-weight: 620;
    color: var(--color-text-primary);
    line-height: 1.4;
    text-wrap: pretty;
    transition: color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .source-row:hover .source-title {
    color: var(--color-accent);
  }

  .source-meta {
    font-family: var(--font-mono);
    font-size: 0.66rem;
    color: var(--color-text-muted);
    display: flex;
    gap: 0.5rem;
  }

  .source-comments {
    opacity: 0.7;
  }

  /* ===== Shared ===== */
  .expand-btn {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 650;
    color: var(--color-text-muted);
    background: color-mix(in srgb, var(--color-bg-elevated) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 40%, transparent);
    cursor: pointer;
    padding: 0.4rem 0.72rem;
    border-radius: 999px;
    transition:
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
    align-self: center;
  }

  .expand-btn:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
  }

  .expand-btn:active {
    transform: scale(0.98);
  }

  @media (max-width: 640px) {
    .tier-bar {
      grid-template-columns: minmax(4.8rem, 0.42fr) minmax(0, 1fr) 2.2rem;
      gap: 0.52rem;
    }

    .source-row {
      grid-template-columns: 2.8rem 1fr;
    }
  }
</style>
