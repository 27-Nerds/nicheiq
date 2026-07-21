<script lang="ts">
  import type { Competitor } from "$lib/types/publicCatalog.js";
  import PositionChip from "./PositionChip.svelte";

  interface Props {
    competitor: Competitor;
  }

  let { competitor }: Props = $props();

  // Strip protocol for display.
  const displayUrl = $derived(
    competitor.url ? competitor.url.replace(/^https?:\/\//, "").replace(/\/$/, "") : null,
  );
</script>

<article class="comp">
  <div class="body">
    <h4>{competitor.name}</h4>
    {#if displayUrl}
      <a class="url" href={competitor.url ?? "#"} target="_blank" rel="noopener noreferrer">
        {displayUrl}
      </a>
    {/if}
    <p class="desc">{competitor.description}</p>
  </div>
  <PositionChip position={competitor.position} />
</article>

<style>
  .comp {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 16px;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px;
    align-items: start;
  }
  .body {
    min-width: 0;
  }
  h4 {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.2;
    margin: 0 0 4px;
    color: var(--color-text-primary);
  }
  .url {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-accent);
    margin-bottom: 6px;
    display: inline-block;
    text-decoration: none;
  }
  .url:hover {
    text-decoration: underline;
  }
  .desc {
    font-size: 12.5px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    margin: 0;
  }
</style>
