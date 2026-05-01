<script lang="ts">
  import type { SubredditSource } from "$lib/types/publicCatalog.js";
  import SourceChip from "./SourceChip.svelte";

  interface Props {
    sources: SubredditSource[];
  }

  let { sources }: Props = $props();
</script>

<div class="sources">
  {#each sources as s}
    <SourceChip platform="reddit" label={s.name.startsWith("r/") ? s.name : `r/${s.name}`} count={s.postCount} />
  {/each}
</div>

<style>
  .sources {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
</style>
