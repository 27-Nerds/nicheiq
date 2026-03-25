<script lang="ts">
  import type { StageCosts } from "$lib/types/job";

  interface Props {
    stageCosts: StageCosts;
  }

  let { stageCosts }: Props = $props();
</script>

<div class="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs">
  <!-- Step 1: Discover -->
  <div class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-accent shrink-0"></span>
    <span class="text-text-secondary font-medium">Discover ideas</span>
    <span class="font-mono text-text-muted">{stageCosts.discovery} cr · ~5 min</span>
  </div>

  <span class="text-text-muted/40 hidden sm:inline">—</span>

  <!-- Step 2: Pick -->
  <div class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
    <span class="text-text-muted">You pick the best</span>
    <span class="font-mono text-text-muted/60">free</span>
  </div>

  <span class="text-text-muted/40 hidden sm:inline">—</span>

  <!-- Step 3: Validate -->
  <div class="flex items-center gap-1.5">
    <span class="w-2 h-2 rounded-full bg-border shrink-0"></span>
    <span class="text-text-muted">Full validation</span>
    <span class="font-mono text-text-muted/60">{stageCosts.deep_research} cr · ~20 min</span>
  </div>
</div>
