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
    // Audience framing (output lens only). audienceLabel = the user's stated audience
    // ("For {x}" eyebrow); primaryAudience = the resolved segment_name to split the grid on
    // (segment_of_niche). Both null => current niche-mode layout, unchanged.
    primaryAudience?: string | null;
    audienceLabel?: string | null;
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
    primaryAudience = null,
    audienceLabel = null,
  }: Props = $props();

  const eyebrowLabel = $derived((audienceLabel ?? "").trim());
  const framingOn = $derived(eyebrowLabel.length > 0);
  const splitOn = $derived(framingOn && (primaryAudience ?? "").trim().length > 0);

  function isPrimary(s: SolutionPreview): boolean {
    // Prefer the explicit per-idea audience-fit flag (semantic, set post-generation);
    // fall back to the source_segment === resolved-audience match when it's absent.
    if (typeof s.audience_fit === "boolean") return s.audience_fit;
    const pa = (primaryAudience ?? "").trim().toLowerCase();
    return pa.length > 0 && (s.source_segment ?? "").trim().toLowerCase() === pa;
  }

  const byComposite = (a: SolutionPreview, b: SolutionPreview) =>
    computeCompositeScore(b) - computeCompositeScore(a);

  const primaryGroup = $derived.by(() =>
    splitOn ? solutions.filter(isPrimary).sort(byComposite) : [],
  );
  const adjacentGroup = $derived.by(() =>
    splitOn ? solutions.filter((s) => !isPrimary(s)).sort(byComposite) : [],
  );
  // Segment layout only when BOTH groups are non-empty — otherwise (no fit, or every idea
  // fits) fall back to the single-eyebrow layout so we never render an empty "For" group or a
  // pointless empty "Also worth exploring".
  const segmentMode = $derived(
    splitOn && primaryGroup.length > 0 && adjacentGroup.length > 0,
  );

  let adjacentOpen = $state(false);

  // Niche/community layout: global top pick (highest composite) + the rest. In community mode
  // "Highest viability" is still globally true, so the top-pick highlight is kept.
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

{#snippet card(solution: SolutionPreview, i: number, isTopPick: boolean)}
  {@const gIdx = globalIndexOf(solution.solution_name)}
  {#snippet cardAction()}
    {#if actionSlot}{@render actionSlot({ solution, index: gIdx })}{/if}
  {/snippet}
  <SolutionCard
    {solution}
    {isTopPick}
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
{/snippet}

{#if segmentMode}
  <p class="audience-eyebrow">For {eyebrowLabel}</p>
  <div class="remaining-grid">
    {#each primaryGroup as solution, i (solution.solution_name)}
      {@render card(solution, i, false)}
    {/each}
  </div>

  {#if adjacentGroup.length > 0}
    <button
      type="button"
      class="audience-eyebrow disclosure"
      aria-expanded={adjacentOpen}
      onclick={() => (adjacentOpen = !adjacentOpen)}
    >
      <span class="caret" class:open={adjacentOpen} aria-hidden="true">▸</span>
      Also worth exploring · {adjacentGroup.length}
    </button>
    {#if adjacentOpen}
      <div class="remaining-grid">
        {#each adjacentGroup as solution, i (solution.solution_name)}
          {@render card(solution, i, false)}
        {/each}
      </div>
    {/if}
  {/if}
{:else}
  {#if framingOn}
    <p class="audience-eyebrow">For {eyebrowLabel}</p>
  {/if}
  {#if topPick}
    <div class="top-pick-section">
      {@render card(topPick, 0, true)}
    </div>
  {/if}
  {#if remaining.length > 0}
    <div class="remaining-grid">
      {#each remaining as solution, i (solution.solution_name)}
        {@render card(solution, i, false)}
      {/each}
    </div>
  {/if}
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
  /* Audience-framing eyebrow — mono uppercase muted (entity-eyebrow recipe; no orange). */
  .audience-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    line-height: 1.2;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    margin: var(--space-3) 0 var(--space-2);
  }
  .disclosure {
    display: inline-flex;
    align-items: center;
    gap: 0.45em;
    background: none;
    border: none;
    padding: var(--space-2) 0;
    cursor: pointer;
  }
  .disclosure:focus-visible {
    outline: 2px solid var(--color-border-emphasis);
    outline-offset: 3px;
    border-radius: 2px;
  }
  .caret {
    display: inline-block;
    transition: transform 120ms ease;
  }
  .caret.open {
    transform: rotate(90deg);
  }
  @media (prefers-reduced-motion: reduce) {
    .caret {
      transition: none;
    }
  }
</style>
