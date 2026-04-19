<script lang="ts">
  import type { RedditThread } from "$lib/types/report";

  interface Props {
    subredditNames?: string[];
    communityHubs?: string[];
    topThreads?: RedditThread[];
    postsAnalyzed?: number;
    sourcesSearched?: Record<string, { enabled: boolean; posts_found: number }>;
  }

  let {
    subredditNames = [],
    communityHubs = [],
    topThreads = [],
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

  const displaySources = $derived(
    subredditNames.length > 0
      ? subredditNames
      : communityHubs
  );

  // Subreddit chip grid moved to AudienceSection (community_hubs per segment).
  // This section now owns the methodology summary + platform gap indicators only.
</script>

<div class="community">
  {#if postsAnalyzed > 0 || displaySources.length > 0}
    <span class="community-stat">
      {#if displaySources.length > 0}{displaySources.length} communities{/if}
      {#if displaySources.length > 0 && postsAnalyzed > 0} · {/if}
      {#if postsAnalyzed > 0}{postsAnalyzed.toLocaleString()} discussions analyzed{/if}
    </span>
  {/if}

  {#if gapPlatforms.length > 0}
    <div class="source-grid">
      {#each gapPlatforms as platform}
        <span class="source-pill source-gap">{platform} · 0 posts</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .community {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .community-stat {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .source-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .source-pill {
    padding: 0.25rem 0.625rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    white-space: nowrap;
  }

  .source-gap {
    border-style: dashed;
    color: var(--color-text-muted);
    opacity: var(--opacity-muted);
  }
</style>
