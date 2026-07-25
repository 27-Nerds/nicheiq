<script lang="ts">
  interface Props {
    subredditNames?: string[];
    communityHubs?: string[];
    postsAnalyzed?: number;
    sourcesSearched?: Record<string, { enabled: boolean; posts_found: number }>;
  }

  let {
    subredditNames = [],
    communityHubs = [],
    postsAnalyzed = 0,
    sourcesSearched,
  }: Props = $props();

  const PLATFORM_LABELS: Record<string, string> = {
    reddit: "Reddit",
    hackernews: "Hacker News",
    twitter: "Twitter",
    youtube: "YouTube",
  };

  const gapPlatforms = $derived(
    sourcesSearched
      ? Object.entries(sourcesSearched)
          .filter(([_, info]) => info.enabled && info.posts_found === 0)
          .map(([platform]) => PLATFORM_LABELS[platform] ?? platform)
      : []
  );

  const activePlatforms = $derived(
    sourcesSearched
      ? Object.entries(sourcesSearched)
          .filter(([_, info]) => info.enabled && info.posts_found > 0)
          .map(([platform, info]) => ({
            label: PLATFORM_LABELS[platform] ?? platform,
            count: info.posts_found,
          }))
      : [],
  );

  const displaySources = $derived(
    subredditNames.length > 0
      ? subredditNames
      : communityHubs
  );
  const visibleSources = $derived(displaySources.slice(0, 8));
  const hiddenSourceCount = $derived(Math.max(0, displaySources.length - visibleSources.length));
</script>

<div class="community">
  {#if postsAnalyzed > 0 || displaySources.length > 0}
    <span class="community-stat">
      {#if displaySources.length > 0}{displaySources.length} communities{/if}
      {#if displaySources.length > 0 && postsAnalyzed > 0} · {/if}
      {#if postsAnalyzed > 0}{postsAnalyzed.toLocaleString()} discussions analyzed{/if}
    </span>
  {/if}

  {#if visibleSources.length > 0}
    <div class="source-grid" aria-label="Captured communities">
      {#each visibleSources as source}
        <span class="source-pill" title={source}>{source}</span>
      {/each}
      {#if hiddenSourceCount > 0}
        <span class="source-pill">+{hiddenSourceCount} more</span>
      {/if}
    </div>
  {:else if postsAnalyzed === 0}
    <p class="community-empty">No discussion sources were captured for this report.</p>
  {/if}

  {#if activePlatforms.length > 0 || gapPlatforms.length > 0}
    <div class="source-grid">
      {#each activePlatforms as platform}
        <span class="source-pill">{platform.label} · {platform.count} captured</span>
      {/each}
      {#each gapPlatforms as platform}
        <span class="source-pill source-gap">{platform} · none captured</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .community {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .community-stat {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .source-grid {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .source-pill {
    max-width: 100%;
    padding: var(--space-1) var(--space-2);
    background: color-mix(in srgb, var(--color-bg-elevated) 78%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 36%, transparent);
    border-radius: var(--radius-full);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--color-text-secondary);
    overflow-wrap: anywhere;
  }

  .source-gap {
    border-style: dashed;
    color: var(--color-text-muted);
    opacity: 0.78;
  }

  .community-empty {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
  }
</style>
