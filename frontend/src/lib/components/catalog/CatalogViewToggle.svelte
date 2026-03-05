<script lang="ts">
  import { buildCrossNavUrl } from "$lib/utils/catalog-utils";

  interface Props {
    activeView: 'ideas' | 'pain-points';
    category: string;
  }

  let { activeView, category }: Props = $props();

  const ideasHref = $derived(buildCrossNavUrl('/catalog/ideas', category));
  const painPointsHref = $derived(buildCrossNavUrl('/catalog/pain-points', category));
</script>

{#if category}
  <div class="flex items-center gap-1 mb-4">
    {#if activeView === 'ideas'}
      <span class="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent/10 text-accent border border-accent/30">
        Ideas
      </span>
      <a
        href={painPointsHref}
        class="px-3 py-1.5 text-xs font-medium rounded-lg text-text-muted border border-border hover:bg-bg-elevated transition-colors"
      >
        Pain Points
      </a>
    {:else}
      <a
        href={ideasHref}
        class="px-3 py-1.5 text-xs font-medium rounded-lg text-text-muted border border-border hover:bg-bg-elevated transition-colors"
      >
        Ideas
      </a>
      <span class="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent/10 text-accent border border-accent/30">
        Pain Points
      </span>
    {/if}
  </div>
{/if}
