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
  /* Catalog v2 — wider editorial container (1200px) for browse/index density.
     Per design rebuild: catalog content needs more lateral room than article-
     style content. Padding scales modestly on mobile. Same shell is duplicated
     on /idea/[slug] and /pain-point/[slug] layouts so the visual rhythm
     persists across the catalog. */
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
