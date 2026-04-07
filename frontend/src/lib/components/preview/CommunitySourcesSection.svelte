<script lang="ts">
  import type { RedditThread } from "$lib/types/report";

  interface Props {
    subredditNames?: string[];
    communityHubs?: string[];
    topThreads?: RedditThread[];
    postsAnalyzed?: number;
  }

  let {
    subredditNames = [],
    communityHubs = [],
    topThreads = [],
    postsAnalyzed = 0,
  }: Props = $props();

  const displaySources = $derived(
    subredditNames.length > 0
      ? subredditNames
      : communityHubs
  );

  const visibleThreads = $derived(topThreads.slice(0, 5));
  const remainingCount = $derived(Math.max(0, topThreads.length - 5));
</script>

<div class="community">
  {#if postsAnalyzed > 0 || displaySources.length > 0}
    <p class="community-intro">
      Research sourced from <strong>{postsAnalyzed.toLocaleString()}</strong> discussions
      {#if displaySources.length > 0}across <strong>{displaySources.length}</strong> communities{/if}
    </p>
  {/if}

  {#if displaySources.length > 0}
    <div class="source-grid">
      {#each displaySources as source}
        <div class="source-card">
          <span class="source-name">{source.startsWith('r/') ? source : `r/${source}`}</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if visibleThreads.length > 0}
    <div class="threads-section">
      <h4 class="threads-label">Top evidence threads</h4>
      <div class="threads-list">
        {#each visibleThreads as thread}
          <div class="thread-item">
            <span class="thread-score">{thread.score?.toLocaleString() ?? '—'}</span>
            <div class="thread-content">
              <span class="thread-title">{thread.key_insight ?? thread.title}</span>
              <span class="thread-source">r/{thread.subreddit}</span>
            </div>
            {#if thread.url}
              <a href={thread.url} target="_blank" rel="noopener noreferrer" class="thread-link">View</a>
            {/if}
          </div>
        {/each}
      </div>
      {#if remainingCount > 0}
        <p class="threads-more">+{remainingCount} more in full report</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .community {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .community-intro {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .community-intro strong {
    color: var(--color-text-primary);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .source-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .source-card {
    padding: 0.5rem 0.875rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .source-name {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }

  .threads-section {
    padding-top: 0.25rem;
  }

  .threads-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 0.75rem;
  }

  .threads-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .thread-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font-size: 0.8125rem;
  }

  .thread-score {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--color-accent);
    min-width: 2.5rem;
    text-align: right;
    flex-shrink: 0;
  }

  .thread-content {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .thread-title {
    color: var(--color-text-primary);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .thread-source {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .thread-link {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-accent);
    text-decoration: none;
    flex-shrink: 0;
  }

  .thread-link:hover {
    text-decoration: underline;
  }

  .threads-more {
    margin-top: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  @media (max-width: 640px) {
    .thread-content {
      flex-direction: column;
      gap: 0.125rem;
    }

    .thread-title {
      white-space: normal;
    }
  }
</style>
