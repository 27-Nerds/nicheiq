<script lang="ts">
  import type { CatalogCollectionSummary } from "$lib/types/publicCatalog.js";
  import Sparkles from "lucide-svelte/icons/sparkles";
  import ArrowRight from "lucide-svelte/icons/arrow-right";

  // Inline accent card linking to a featured collection. Renders between the
  // "Top ideas" anchor section and the dense filterable AllIdeasSection on
  // category pages, when the current category appears in the collection's
  // server-computed `categorySlugs`. Skip silently when no collection maps —
  // no empty state.

  interface Props {
    collection: CatalogCollectionSummary;
  }

  let { collection }: Props = $props();

  const href = $derived(`/ideas?collection=${collection.slug}`);
</script>

<a class="teaser" {href} style={collection.colorAccent ? `--coll-accent: ${collection.colorAccent};` : ''}>
  <div class="copy">
    <span class="kicker">
      <Sparkles size={14} aria-hidden="true" />
      <span>Featured collection</span>
    </span>
    <h4>{collection.name}</h4>
    {#if collection.description}
      <p>{collection.description}</p>
    {/if}
  </div>
  <span class="open">
    <span>Open collection</span>
    <ArrowRight size={14} aria-hidden="true" />
  </span>
</a>

<style>
  .teaser {
    background: var(--color-bg-elevated, #fafafa);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 20px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    flex-wrap: wrap;
    color: inherit;
    text-decoration: none;
    margin: 0 0 24px;
    transition: border-color 0.12s, background 0.12s;
  }
  .teaser:hover {
    border-color: var(--color-border-emphasis);
    background: var(--color-surface, #fff);
  }
  .teaser:focus-visible {
    outline: 2px solid var(--coll-accent, var(--color-accent));
    outline-offset: 2px;
  }
  .copy {
    flex: 1;
    min-width: 240px;
  }
  .kicker {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--coll-accent, var(--color-accent));
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  h4 {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
    margin: 0 0 4px;
  }
  p {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    margin: 0;
    max-width: 560px;
  }
  .open {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-surface, #fff);
    padding: 7px 12px;
    border-radius: 6px;
    transition: color 0.12s, border-color 0.12s;
  }
  .teaser:hover .open {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
  }
</style>
