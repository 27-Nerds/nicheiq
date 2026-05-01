<script lang="ts">
  import type { Competitor } from "$lib/types/publicCatalog.js";
  import CompetitorCard from "./CompetitorCard.svelte";

  interface Props {
    competitors: Competitor[];
  }

  let { competitors }: Props = $props();
</script>

<div class="competitors-grid">
  {#each competitors as c}
    <CompetitorCard competitor={c} />
  {/each}
</div>

<style>
  .competitors-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  @media (max-width: 800px) {
    .competitors-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
