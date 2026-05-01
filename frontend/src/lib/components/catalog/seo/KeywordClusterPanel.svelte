<script lang="ts">
  import type { KeywordCluster } from "$lib/types/publicCatalog.js";
  import KeywordClusterCard from "./KeywordClusterCard.svelte";

  interface Props {
    clusters: KeywordCluster[];
  }

  let { clusters }: Props = $props();
</script>

<div class="keywords-grid">
  {#each clusters as c}
    <KeywordClusterCard cluster={c} />
  {/each}
</div>

<style>
  .keywords-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  @media (max-width: 800px) {
    .keywords-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
