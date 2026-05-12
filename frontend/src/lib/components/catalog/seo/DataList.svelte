<script lang="ts">
  import type { Snippet } from 'svelte';

  // Chrome-less wrapper for a stack of <DataRow> rows. Strips the last
  // child's bottom border + padding so the dashed separator doesn't dangle
  // below the final row. Caller provides whatever container chrome the
  // surrounding context needs (.sketch card, .score-panel, .cat-aside, etc.).

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<div class="data-list">{@render children()}</div>

<style>
  .data-list {
    display: flex;
    flex-direction: column;
  }
  .data-list > :global(*:last-child) {
    border-bottom: none;
    padding-bottom: 0;
  }
</style>
