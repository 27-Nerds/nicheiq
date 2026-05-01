<script lang="ts">
  import type { DifficultyBucket } from "$lib/types/publicCatalog.js";
  import DifficultyChip from "./DifficultyChip.svelte";

  interface Props {
    term: string;
    volume: number;
    difficulty: DifficultyBucket;
  }

  let { term, volume, difficulty }: Props = $props();

  const volLabel = $derived(
    volume >= 1000 ? `${(volume / 1000).toFixed(1).replace(/\.0$/, "")}K` : String(volume),
  );
</script>

<div class="kw-row">
  <span class="term">{term}</span>
  <span class="vol">{volume === 0 ? "—" : volLabel}</span>
  <DifficultyChip {difficulty} />
</div>

<style>
  .kw-row {
    padding: 8px 14px;
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 12px;
    align-items: center;
    border-bottom: 1px solid var(--color-border);
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .kw-row:last-child {
    border-bottom: none;
  }
  .term {
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .vol {
    color: var(--color-text-muted);
    min-width: 54px;
    text-align: right;
  }
</style>
