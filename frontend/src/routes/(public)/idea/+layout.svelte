<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<div class="catalog-shell">
  {@render children()}
</div>

<style>
  /* Catalog v2 — shared shell width with /ideas. Without this layout,
     /idea/[slug] renders flush against the viewport's left edge. */
  .catalog-shell {
    max-width: 75rem;
    margin: 0 auto;
    padding: 1.5rem 1.5rem 4rem;
  }

  @media (min-width: 1024px) {
    .catalog-shell {
      padding: 2rem 1.5rem 6rem;
    }
  }
</style>
