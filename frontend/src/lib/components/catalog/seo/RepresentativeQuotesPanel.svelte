<script lang="ts">
  // Extracted from PainPointCardV2.svelte:45-51 (and the article-variant clone
  // at 69-75) so the standalone /pain-point/[slug] page can render full quote
  // panels while the same component re-skins down to a compact single-quote
  // chip inside cards.
  //
  // When quoteSources is present, each quote becomes a clickable link to its
  // actual Reddit thread with mono attribution `r/{subreddit} · {score}↑`.
  // Falls back to the generic-platform path when sources are absent.

  import type { QuoteSource } from "$lib/types/catalog-landing.js";

  interface Props {
    quotes: string[];
    sourcePlatforms?: string[] | null;
    mentionCount?: number | null;
    /** Hard cap on visible quotes. Cards pass `1` for compact variant.
     *  Default: render all (subject to defaultLimit toggle). */
    maxQuotes?: number;
    /** 'panel' = full multi-quote layout (default); 'compact' = card style. */
    variant?: 'panel' | 'compact';
    /** Per-quote Reddit attribution with subreddit + post_id + upvote score.
     *  Backend pre-sorts by score desc. When present, replaces the generic
     *  platform-chip rendering with linked source-attributed bubbles. */
    quoteSources?: QuoteSource[] | null;
    /** When total quotes exceed this number AND variant === 'panel', render
     *  the first `defaultLimit` and put the rest behind a `<details>` toggle.
     *  Hidden quotes stay in DOM (server-rendered) for SEO. Cards ignore this
     *  (they pass maxQuotes={1}). Set to a falsy value to disable. */
    defaultLimit?: number;
  }

  let {
    quotes,
    sourcePlatforms = null,
    mentionCount = null,
    maxQuotes,
    variant = 'panel',
    quoteSources = null,
    defaultLimit = 5,
  }: Props = $props();

  // Sources path takes priority when populated. Strings path is the legacy fallback.
  const fullSources = $derived.by<QuoteSource[] | null>(() => {
    if (!Array.isArray(quoteSources) || quoteSources.length === 0) return null;
    return typeof maxQuotes === 'number' ? quoteSources.slice(0, Math.max(0, maxQuotes)) : quoteSources;
  });

  const fullStrings = $derived.by<string[]>(() => {
    if (fullSources) return [];  // sources path takes over
    if (!Array.isArray(quotes)) return [];
    const cleaned = quotes.filter((q) => typeof q === 'string' && q.trim().length > 0);
    return typeof maxQuotes === 'number' ? cleaned.slice(0, Math.max(0, maxQuotes)) : cleaned;
  });

  // Split visible (default-shown) vs deferred (behind details toggle).
  // Compact variant skips the toggle entirely (cards never overflow).
  const useToggle = $derived(
    variant === 'panel' &&
      typeof defaultLimit === 'number' &&
      defaultLimit > 0 &&
      ((fullSources?.length ?? 0) > defaultLimit || fullStrings.length > defaultLimit),
  );

  const headSources = $derived(useToggle && fullSources ? fullSources.slice(0, defaultLimit) : fullSources);
  const tailSources = $derived(useToggle && fullSources ? fullSources.slice(defaultLimit) : null);
  const headStrings = $derived(useToggle ? fullStrings.slice(0, defaultLimit) : fullStrings);
  const tailStrings = $derived(useToggle ? fullStrings.slice(defaultLimit) : null);

  const totalCount = $derived(fullSources?.length ?? fullStrings.length);

  function redditUrl(s: QuoteSource): string {
    return `https://reddit.com/r/${s.subreddit}/comments/${s.postId}`;
  }
</script>

{#if fullSources && fullSources.length > 0}
  {#if variant === 'compact'}
    <a class="quote quote-link" href={redditUrl(fullSources[0])} target="_blank" rel="noopener">
      "{fullSources[0].quote}"
      <span class="src-line">r/{fullSources[0].subreddit} · {fullSources[0].score.toLocaleString()}↑</span>
    </a>
  {:else}
    <ul class="panel">
      {#each headSources ?? [] as s}
        <li class="bubble">
          <a class="bubble-link" href={redditUrl(s)} target="_blank" rel="noopener">
            <p class="text">"{s.quote}"</p>
            <span class="src-line">
              r/{s.subreddit} · {s.score.toLocaleString()}↑ · {s.postId}
            </span>
          </a>
        </li>
      {/each}
    </ul>
    {#if useToggle && tailSources && tailSources.length > 0}
      <details class="show-all">
        <summary>Show all {totalCount} quotes</summary>
        <ul class="panel panel-extra">
          {#each tailSources as s}
            <li class="bubble">
              <a class="bubble-link" href={redditUrl(s)} target="_blank" rel="noopener">
                <p class="text">"{s.quote}"</p>
                <span class="src-line">
                  r/{s.subreddit} · {s.score.toLocaleString()}↑ · {s.postId}
                </span>
              </a>
            </li>
          {/each}
        </ul>
      </details>
    {/if}
    {#if mentionCount}
      <p class="footer-line">
        <span class="num">{mentionCount.toLocaleString()}</span> total similar mentions across the dataset
      </p>
    {/if}
  {/if}
{:else if fullStrings.length > 0}
  {#if variant === 'compact'}
    <!-- Legacy: single-quote inline block, no source link. -->
    <div class="quote">
      "{fullStrings[0]}"
      {#if mentionCount}
        <span class="src-line">{mentionCount.toLocaleString()} similar mentions</span>
      {/if}
    </div>
  {:else}
    <ul class="panel">
      {#each headStrings as q, i}
        <li class="bubble">
          <p class="text">"{q}"</p>
          {#if Array.isArray(sourcePlatforms) && sourcePlatforms[i]}
            <span class="src-line">from {sourcePlatforms[i]}</span>
          {/if}
        </li>
      {/each}
    </ul>
    {#if useToggle && tailStrings && tailStrings.length > 0}
      <details class="show-all">
        <summary>Show all {totalCount} quotes</summary>
        <ul class="panel panel-extra">
          {#each tailStrings as q, i}
            <li class="bubble">
              <p class="text">"{q}"</p>
              {#if Array.isArray(sourcePlatforms) && sourcePlatforms[i + (defaultLimit ?? 0)]}
                <span class="src-line">from {sourcePlatforms[i + (defaultLimit ?? 0)]}</span>
              {/if}
            </li>
          {/each}
        </ul>
      </details>
    {/if}
    {#if mentionCount}
      <p class="footer-line">
        <span class="num">{mentionCount.toLocaleString()}</span> total similar mentions across the dataset
      </p>
    {/if}
  {/if}
{/if}

<style>
  /* Compact card variant — preserves PainPointCardV2 .quote / .src-line look. */
  .quote {
    border-left: 2px solid var(--color-border-emphasis);
    padding: 10px 12px;
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    background: var(--color-surface-elevated, #fafafa);
    border-radius: 0 4px 4px 0;
  }
  /* Linked compact variant uses the same shell as .quote. */
  .quote-link {
    display: block;
    color: inherit;
    text-decoration: none;
    transition: background-color 120ms ease;
  }
  .quote-link:hover {
    background: var(--color-bg-hover, #ebebeb);
  }
  .quote-link .src-line {
    color: var(--color-accent);
  }

  /* Panel variant — multi-bubble vertical stack for the standalone pain page. */
  .panel {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  /* Show-all toggle. <details>/<summary> keeps hidden quotes in DOM
     (server-rendered, SEO-indexable) while collapsing visual monotony. */
  .show-all {
    margin-top: 10px;
  }
  .show-all > summary {
    list-style: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
    transition: background-color 120ms ease, color 120ms ease;
    user-select: none;
  }
  .show-all > summary::-webkit-details-marker { display: none; }
  .show-all > summary::after {
    content: '+';
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--color-accent);
  }
  .show-all[open] > summary::after { content: '−'; }
  .show-all > summary:hover {
    background: var(--color-bg-hover, #ebebeb);
    color: var(--color-text-primary);
  }
  .show-all > .panel-extra {
    margin-top: 10px;
  }
  .bubble {
    border-left: 3px solid var(--color-border-emphasis);
    padding: 14px 18px;
    background: var(--color-surface-elevated, #fafafa);
    border-radius: 0 6px 6px 0;
  }
  /* Linked panel bubble. Color-only hover per feedback_no_ai_slop_hover. */
  .bubble-link {
    display: block;
    color: inherit;
    text-decoration: none;
    margin: -14px -18px;
    padding: 14px 18px;
    border-radius: 0 6px 6px 0;
    transition: background-color 120ms ease;
  }
  .bubble-link:hover {
    background: var(--color-bg-hover, #ebebeb);
  }
  .bubble-link .src-line {
    color: var(--color-accent);
  }
  .text {
    font-size: 14px;
    line-height: 1.55;
    color: var(--color-text-primary);
    margin: 0;
  }

  .src-line {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-muted);
    margin-top: 6px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .footer-line {
    margin: 14px 0 0;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
  }
  .footer-line .num {
    color: var(--color-text-primary);
    font-weight: 600;
  }
</style>
