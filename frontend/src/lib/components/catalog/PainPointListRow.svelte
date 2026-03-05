<script lang="ts">
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import { fly } from "svelte/transition";

  interface Props {
    painPoint: any;
    isSelected: boolean;
    onclick: () => void;
    index?: number;
  }

  let { painPoint, isSelected, onclick, index = 0 }: Props = $props();

  const wtpPercent = $derived(
    painPoint.willingnessToPayScore != null
      ? Math.round(painPoint.willingnessToPayScore * 100)
      : null
  );
</script>

<button
  type="button"
  class="pp-list-row"
  class:selected={isSelected}
  {onclick}
  in:fly={{ y: 12, duration: 400, delay: index * 30 }}
>
  <div class="flex items-center gap-2.5 w-full min-w-0">
    <!-- Severity ring -->
    <div class="shrink-0">
      <ProgressRing
        value={painPoint.severityScore ?? 0}
        size={32}
        flat={true}
        animate={false}
        showTooltip={false}
        showValue={true}
        color="auto"
      />
    </div>

    <!-- Content -->
    <div class="flex-1 min-w-0">
      <span class="text-sm font-semibold text-text-primary truncate block leading-tight">
        {painPoint.title}
      </span>
      {#if wtpPercent != null}
        <span class="text-[11px] text-text-muted mt-0.5 block">
          {wtpPercent}% <span class="mono-label" style="font-size: 0.55rem;">WTP</span>
        </span>
      {/if}
    </div>
  </div>
</button>

<style>
  .pp-list-row {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 0.625rem 0.75rem;
    border-left: 3px solid transparent;
    background: transparent;
    text-align: left;
    cursor: pointer;
    transition:
      background var(--duration-normal) ease,
      border-color var(--duration-normal) ease;
  }

  .pp-list-row:hover {
    background: var(--color-bg-hover, rgba(255, 255, 255, 0.04));
  }

  .pp-list-row:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
    border-radius: var(--radius-sm);
  }

  .pp-list-row.selected {
    border-left-color: var(--color-accent);
    background: linear-gradient(135deg, rgba(240, 96, 48, 0.08), transparent);
  }
</style>
