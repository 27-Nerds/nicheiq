<script lang="ts">
  import type { Snippet } from "svelte";
  import SolutionCard from "$lib/components/SolutionCard.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { computeCompositeScore } from "$lib/utils/solution-utils";

  interface Props {
    solutions: SolutionPreview[];
    onOpen?: (globalIndex: number) => void;
    voteCounts?: Record<string, number>;
    // Owner select mode (omit to disable the checkbox)
    onSelect?: (name: string) => void;
    selectedNames?: Set<string>;
    maxSelections?: number;
    selectLoading?: boolean;
    // Visitor action slot (parametrized by current card)
    actionSlot?: Snippet<[{ solution: SolutionPreview; index: number }]>;
  }

  let {
    solutions,
    onOpen,
    voteCounts = {},
    onSelect,
    selectedNames,
    maxSelections = 3,
    selectLoading = false,
    actionSlot,
  }: Props = $props();

  const topPick = $derived.by(() => {
    if (solutions.length === 0) return null;
    let best = solutions[0];
    for (const s of solutions) {
      if (computeCompositeScore(s) > computeCompositeScore(best)) best = s;
    }
    return best;
  });

  const remaining = $derived(
    solutions.filter((s) => s.solution_name !== topPick?.solution_name),
  );

  function globalIndexOf(name: string): number {
    return solutions.findIndex((s) => s.solution_name === name);
  }

  function selectionIndexOf(name: string): number {
    if (!selectedNames) return 0;
    let i = 1;
    for (const n of selectedNames) {
      if (n === name) return i;
      i++;
    }
    return 0;
  }
</script>

{#if topPick}
  {@const pick = topPick}
  {@const pickIdx = globalIndexOf(pick.solution_name)}
  <div class="top-pick-section">
    {#snippet topPickAction()}
      {#if actionSlot}{@render actionSlot({ solution: pick, index: pickIdx })}{/if}
    {/snippet}
    <SolutionCard
      solution={pick}
      isTopPick={true}
      {onSelect}
      isSelected={selectedNames?.has(pick.solution_name) ?? false}
      selectionIndex={selectionIndexOf(pick.solution_name)}
      maxReached={selectedNames ? selectedNames.size >= maxSelections : false}
      disabled={selectLoading}
      voteCount={voteCounts[pick.solution_name] ?? 0}
      onOpen={() => onOpen?.(pickIdx)}
      actionSlot={actionSlot ? topPickAction : undefined}
    />
  </div>
{/if}

{#if remaining.length > 0}
  <div class="remaining-grid">
    {#each remaining as solution, i (solution.solution_name)}
      {@const gIdx = globalIndexOf(solution.solution_name)}
      {#snippet cardAction()}
        {#if actionSlot}{@render actionSlot({ solution, index: gIdx })}{/if}
      {/snippet}
      <SolutionCard
        {solution}
        {onSelect}
        isSelected={selectedNames?.has(solution.solution_name) ?? false}
        selectionIndex={selectionIndexOf(solution.solution_name)}
        maxReached={selectedNames ? selectedNames.size >= maxSelections : false}
        disabled={selectLoading}
        voteCount={voteCounts[solution.solution_name] ?? 0}
        onOpen={() => onOpen?.(gIdx)}
        index={i}
        actionSlot={actionSlot ? cardAction : undefined}
      />
    {/each}
  </div>
{/if}

<style>
  .top-pick-section {
    width: 100%;
  }
  .remaining-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }
  @media (min-width: 640px) {
    .remaining-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
