<script lang="ts" module>
  function normalizeCommunityName(name: string): string {
    return name.trim().replace(/^r\//i, "").toLowerCase();
  }

  export function orderCommunitiesByPostCount(
    names: string[],
    postCounts?: Record<string, number>,
  ): string[] {
    if (!postCounts || Object.keys(postCounts).length === 0) return names;

    const namesByKey = new Map(names.map((name) => [normalizeCommunityName(name), name]));
    const weighted = Object.entries(postCounts)
      .map(([name, count], index) => ({ name: namesByKey.get(normalizeCommunityName(name)), count, index }))
      .filter((entry): entry is { name: string; count: number; index: number } => Boolean(entry.name))
      .sort((a, b) => b.count - a.count || a.index - b.index)
      .map(({ name }) => name);
    if (weighted.length === 0) return names;

    const weightedKeys = new Set(weighted.map(normalizeCommunityName));
    return [...weighted, ...names.filter((name) => !weightedKeys.has(normalizeCommunityName(name)))];
  }
</script>

<script lang="ts">
  interface Props {
    subredditNames?: string[];
    subredditPostCounts?: Record<string, number>;
    communityHubs?: string[];
    postsAnalyzed?: number;
    sourcesSearched?: Record<string, { enabled: boolean; posts_found: number }>;
  }

  let {
    subredditNames = [],
    subredditPostCounts,
    communityHubs = [],
    postsAnalyzed = 0,
    sourcesSearched,
  }: Props = $props();
  let showAllCommunities = $state(false);

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
      ? orderCommunitiesByPostCount(subredditNames, subredditPostCounts)
      : communityHubs
  );
  const visibleSources = $derived(
    showAllCommunities ? displaySources : displaySources.slice(0, 8),
  );
  const hiddenSourceCount = $derived(Math.max(0, displaySources.length - 8));
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
    <div class="source-grid" id="captured-community-list" aria-label="Captured communities">
      {#each visibleSources as source}
        <span class="source-pill" title={source}>{source}</span>
      {/each}
      {#if hiddenSourceCount > 0}
        <button
          type="button"
          class="source-more"
          onclick={() => (showAllCommunities = !showAllCommunities)}
          aria-expanded={showAllCommunities}
          aria-controls="captured-community-list"
        >
          {showAllCommunities ? "Show fewer communities" : `Show ${hiddenSourceCount} more communities`}
        </button>
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

  .source-more {
    max-width: 100%;
    padding: var(--space-1) var(--space-2);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    border-radius: var(--radius-full);
    background: transparent;
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    cursor: pointer;
    transition:
      color 180ms ease,
      border-color 180ms ease,
      background-color 180ms ease,
      transform 180ms ease;
  }

  .source-more:hover {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }

  .source-more:active {
    transform: scale(0.98);
  }

  .source-more:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: var(--space-1);
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
