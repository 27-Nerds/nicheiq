<script lang="ts">
  import { Heart } from "lucide-svelte";

  interface Props {
    count: number;
    total: number;
    voted: boolean;
    onVote: () => void;
    voting?: boolean;
    compact?: boolean;
  }

  let { count, total, voted, onVote, voting = false, compact = false }: Props = $props();

  const votePercent = $derived(total > 0 ? Math.round((count / total) * 100) : 0);

  function handleClick(e: MouseEvent) {
    e.stopPropagation();
    onVote();
  }
</script>

<div class="flex flex-col gap-1.5">
  <button
    type="button"
    onclick={handleClick}
    disabled={voting}
    class="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium transition-all
      {voted
        ? 'bg-accent/10 text-accent border border-accent/30'
        : 'bg-bg-elevated text-text-muted border border-border hover:border-accent/30 hover:text-accent'}"
    aria-label={voted ? 'Change vote' : 'Vote for this solution'}
  >
    <Heart class="w-3.5 h-3.5 {voted ? 'fill-current' : ''}" />
    <span>{count}</span>
  </button>
  {#if total > 0 && !compact}
    <div class="flex items-center gap-1.5">
      <div class="flex-1 h-1.5 bg-bg-elevated rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-500 {voted ? 'bg-accent' : 'bg-text-muted/30'}"
          style="width: {votePercent}%"
        ></div>
      </div>
      <span class="text-xs text-text-muted tabular-nums">{votePercent}%</span>
    </div>
  {/if}
</div>
