<script lang="ts">
  import type { SubredditSource } from "$lib/types/publicCatalog.js";
  import SourceChip from "./SourceChip.svelte";

  // Platform-agnostic source-community chips. Today the backend only
  // serializes Reddit subreddits via `topSubreddits` → `SubredditSource[]`,
  // but the pipeline already mines Hacker News and may add others. Naming
  // (and the optional `platform` field) is forward-compatible — when the
  // backend distinguishes platform per entry, the route passes it through
  // and SourceChip styles/prefixes the label appropriately.

  interface SourceEntry extends SubredditSource {
    platform?: "reddit" | "hackernews" | string;
  }

  interface Props {
    sources: SourceEntry[];
  }

  let { sources }: Props = $props();

  function platformOf(s: SourceEntry): "reddit" | "hackernews" {
    return s.platform === "hackernews" ? "hackernews" : "reddit";
  }

  function labelOf(s: SourceEntry): string {
    if (platformOf(s) === "hackernews") return s.name;
    return s.name.startsWith("r/") ? s.name : `r/${s.name}`;
  }
</script>

<div class="sources">
  {#each sources as s}
    <SourceChip platform={platformOf(s)} label={labelOf(s)} count={s.postCount} />
  {/each}
</div>

<style>
  .sources {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
</style>
