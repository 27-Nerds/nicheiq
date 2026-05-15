<script lang="ts">
  // Niche-wide top Reddit threads. Renders evidence_appendix.top_reddit_threads
  // (projected on CatalogResearchContext) as hairline-bordered cards with
  // a 3px accent left-stripe — matches the catalog's existing .approach-card
  // / .callout idiom. Each card links to the actual Reddit thread.

  import type { TopRedditThread } from "$lib/types/catalog-landing.js";

  interface Props {
    threads: TopRedditThread[];
    /** Cap visible threads. Default: render all. Pain pages pass 3, niche
     *  pages omit (renders all 5). */
    limit?: number;
  }

  let { threads, limit }: Props = $props();
  const visible = $derived(typeof limit === 'number' ? threads.slice(0, limit) : threads);
</script>

{#if visible.length > 0}
  <ul class="threads">
    {#each visible as t}
      <li>
        <a class="thread" href={t.url} target="_blank" rel="noopener">
          <header>
            <span class="sub">r/{t.subreddit}</span>
            <span class="meta">
              <span class="metric">{t.score.toLocaleString()}↑</span>
              <span class="metric">{t.numComments.toLocaleString()} comments</span>
            </span>
          </header>
          <h4>{t.title}</h4>
          {#if t.keyInsight && t.keyInsight !== t.title}
            <p class="insight">"{t.keyInsight}"</p>
          {/if}
        </a>
      </li>
    {/each}
  </ul>
{/if}

<style>
  .threads {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .thread {
    display: block;
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-accent);
    border-radius: 0 6px 6px 0;
    padding: 14px 18px;
    background: var(--color-surface, #fff);
    color: inherit;
    text-decoration: none;
    transition: background-color 120ms ease;
  }
  .thread:hover {
    background: var(--color-surface-elevated, #fafafa);
  }
  .thread header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 6px;
  }
  .sub {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    color: var(--color-accent);
    letter-spacing: 0.04em;
  }
  .meta {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .metric {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  h4 {
    margin: 0 0 4px;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.4;
    color: var(--color-text-primary);
  }
  .insight {
    margin: 4px 0 0;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--color-text-secondary, var(--color-text-primary));
    font-style: italic;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>
