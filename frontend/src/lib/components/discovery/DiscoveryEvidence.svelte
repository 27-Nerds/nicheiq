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
    gap: var(--space-6);
    margin-top: var(--space-4);
  }

  .evidence-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .evidence-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
  }

  /* Tier bar overrides for custom fill width */
  .dist-bars :global(.tier-bar-fill) {
    transform: scaleX(0);
  }
  .dist-bars :global(.tier-bar.visible .tier-bar-fill) {
    transform: scaleX(var(--fill-pct));
  }

  /* ===== Source Feed (HackerNews style) ===== */
  .source-feed {
    display: flex;
    flex-direction: column;
    gap: 1px;
    background: var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .source-row {
    display: grid;
    grid-template-columns: 3.5rem 1fr;
    grid-template-rows: auto auto;
    gap: 0 var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--color-bg-elevated);
    text-decoration: none;
    transition: background-color var(--duration-fast) ease;
  }

  .source-row:hover {
    background: var(--color-bg-hover);
  }

  .source-row:active {
    transform: scale(0.998);
  }

  .source-score {
    grid-row: 1 / -1;
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: var(--text-sm);
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
    text-align: right;
    padding-top: 0.125rem;
  }

  .source-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .source-meta {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    display: flex;
    gap: var(--space-2);
  }

  .source-comments {
    opacity: 0.7;
  }

  /* ===== Shared ===== */
  .expand-btn {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-text-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
    align-self: center;
  }

  .expand-btn:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
  }

  .expand-btn:active {
    transform: scale(0.98);
  }
</style>
