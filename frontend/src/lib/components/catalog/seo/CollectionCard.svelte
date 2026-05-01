<script lang="ts">
  import type { CatalogCollectionSummary } from "$lib/types/publicCatalog.js";
  import ArrowRight from "lucide-svelte/icons/arrow-right";

  interface Props {
    collection: CatalogCollectionSummary;
  }

  let { collection }: Props = $props();

  // Defer dedicated /ideas/collections/[slug] page; link to a filtered ideas
  // index for v1 per plan (out-of-scope item).
  const href = $derived(`/ideas?collection=${collection.slug}`);
</script>

<a class="coll-card" {href} style={collection.colorAccent ? `--coll-accent: ${collection.colorAccent};` : ''}>
  {#if collection.tagline}
    <div class="coll-tag">{collection.tagline}</div>
  {/if}
  <h4>{collection.name}</h4>
  {#if collection.description}
    <p>{collection.description}</p>
  {/if}
  <div class="coll-foot">
    <span>
      <span class="num">{collection.itemCount.toLocaleString()}</span>
      ideas inside
    </span>
    <span class="arrow"><ArrowRight size={14} /></span>
  </div>
</a>

<style>
  .coll-card {
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 18px;
    cursor: pointer;
    transition: all 0.15s ease;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 160px;
    position: relative;
    overflow: hidden;
    color: inherit;
    text-decoration: none;
  }
  .coll-card:hover {
    border-color: var(--color-border-emphasis);
  }
  .coll-tag {
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--coll-accent, var(--color-accent));
    font-weight: 600;
  }
  h4 {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.015em;
    line-height: 1.2;
    color: var(--color-text-primary);
    margin: 0;
  }
  p {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    flex: 1;
    margin: 0;
  }
  .coll-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: var(--color-text-muted);
    margin-top: auto;
    padding-top: 8px;
    border-top: 1px solid var(--color-border);
  }
  .num {
    font-family: var(--font-mono);
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .arrow {
    color: var(--color-text-secondary, var(--color-text-primary));
    display: inline-flex;
  }
</style>
