<script lang="ts">
  // Display-only chips for one idea-tag facet group (no filtering this round, so no button
  // affordance / hover-lift). Each chip explains itself on hover. See docs/IDEA_TAGS.md.
  import Tooltip from "$lib/components/ui/Tooltip.svelte";

  interface ChipItem {
    label: string;
    /** Hover explanation: what the tag means / why it was added. */
    description?: string;
  }
  interface Props {
    label: string;
    items: ChipItem[];
    tone?: "neutral" | "info" | "warning" | "risk";
  }
  let { label, items, tone = "neutral" }: Props = $props();
</script>

{#if items.length > 0}
  <div class="facet-group">
    <span class="mono-label">{label}</span>
    <div class="facet-chips">
      {#each items as item}
        {#if item.description}
          <Tooltip content={item.description} class="cursor-help">
            {#snippet children()}
              <span class="facet-chip facet-chip-{tone}">{item.label}</span>
            {/snippet}
          </Tooltip>
        {:else}
          <span class="facet-chip facet-chip-{tone}">{item.label}</span>
        {/if}
      {/each}
    </div>
  </div>
{/if}

<style>
  .facet-group {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }
  .facet-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }
  .facet-chip {
    font-size: 0.6875rem;
    line-height: 1.2;
    padding: 0.1875rem 0.5rem;
    border-radius: 0.375rem;
    border: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .facet-chip-info {
    color: var(--color-secondary-dark);
    border-color: color-mix(in srgb, var(--color-info) 30%, transparent);
  }
  .facet-chip-warning {
    color: var(--color-warning-dark);
    border-color: color-mix(in srgb, var(--color-warning) 35%, transparent);
  }
  /* Matches the ranked list's .tag-risk so a watch-out reads the same in both places. */
  .facet-chip-risk {
    color: var(--color-error-dark);
    border-color: color-mix(in srgb, var(--color-error) 30%, transparent);
    background: var(--color-error-subtle);
  }
</style>
