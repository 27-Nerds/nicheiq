<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    children: Snippet;
  }

  let { children }: Props = $props();
</script>

<div class="ideas-shell">
  {@render children()}
</div>

<style>
  .ideas-shell {
    max-width: 56rem;
    margin: 0 auto;
    padding: 2rem 1rem 4rem;
  }

  @media (min-width: 768px) {
    .ideas-shell {
      padding: 3rem 1.5rem 6rem;
    }
  }
</style>
