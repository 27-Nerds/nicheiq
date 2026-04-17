<script lang="ts">
  import { Sparkles } from "lucide-svelte";

  interface CatalogItem {
    id: string;
    title?: string;
    description: string;
    severityScore?: number;
    mentionCount?: number;
  }

  interface Props {
    painPoints: CatalogItem[];
    hasCatalogData: boolean;
    onselect: (text: string) => void;
    onsurprise: () => void;
    surpriseLoading: boolean;
  }

  let {
    painPoints,
    hasCatalogData,
    onselect,
    onsurprise,
    surpriseLoading,
  }: Props = $props();

  let selectedId = $state<string | null>(null);
  let selectionTimer = $state<ReturnType<typeof setTimeout> | null>(null);

  function selectItem(id: string, text: string) {
    if (selectionTimer) clearTimeout(selectionTimer);
    selectedId = id;
    onselect(text);
    selectionTimer = setTimeout(() => { selectedId = null; }, 700);
  }

  function severityColor(score: number): string {
    if (score > 0.7) return "bg-error";
    if (score > 0.4) return "bg-warning";
    return "bg-text-muted";
  }
</script>

{#if !hasCatalogData}
  <!-- Empty state -->
  <div class="rounded-lg border border-dashed border-border p-6 text-center">
    <p class="text-sm font-medium text-text-secondary mb-1">Trends coming soon</p>
    <p class="text-xs text-text-muted mb-4 max-w-md mx-auto">
      In the meantime, we'll surprise you with a random topic — or type your own below.
    </p>
    <button
      type="button"
      onclick={onsurprise}
      disabled={surpriseLoading}
      class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white font-medium text-sm
             hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {#if surpriseLoading}
        <Sparkles class="w-4 h-4 animate-spin" />
        Generating...
      {:else}
        <Sparkles class="w-4 h-4" />
        Surprise me
      {/if}
    </button>
  </div>
{:else}
  <div class="space-y-4">
    <!-- Pain Points Grid -->
    {#if painPoints.length > 0}
      <div>
        <h3 class="text-sm font-semibold text-text-primary mb-3">
          Problems People Are Talking About
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {#each painPoints as pp}
            <button
              type="button"
              onclick={() =>
                selectItem(pp.id, pp.title ?? pp.description.substring(0, 100))}
              class="text-left p-3 rounded-lg border transition-all group
                {selectedId === pp.id ? 'border-accent bg-accent/10' : 'border-border bg-bg-surface hover:border-accent/40 hover:bg-accent/5'}"
            >
              <div class="flex items-center gap-2">
                <p
                  class="text-sm font-medium text-text-primary group-hover:text-accent line-clamp-1 flex-1"
                >
                  {pp.title}
                </p>
              </div>
              <p class="text-xs text-text-muted mt-1 line-clamp-2">
                {pp.description}
              </p>
              <div class="flex items-center gap-3 mt-2">
                {#if pp.severityScore != null}
                  <span class="flex items-center gap-1 text-xs text-text-muted">
                    <span class="w-1.5 h-1.5 rounded-full {severityColor(pp.severityScore)}"></span>
                    Severity: {(pp.severityScore * 100).toFixed(0)}%
                  </span>
                {/if}
                {#if pp.mentionCount != null && pp.mentionCount > 0}
                  <span class="text-xs text-text-muted"
                    >{pp.mentionCount} {pp.mentionCount === 1 ? 'mention' : 'mentions'}</span
                  >
                {/if}
              </div>
            </button>
          {/each}
        </div>
      </div>
    {/if}

  </div>
{/if}
