<script lang="ts">
  import SolutionCard from "./SolutionCard.svelte";

  // Renders solution direction cards. Source: researchContext.alternativeSolutions
  // and/or selectedSolution. Per scope decision (separate lists, no row pairing),
  // each card displays the pain titles it `addresses` via pain_points_addressed.

  interface SolutionShape {
    solution_name?: string;
    solutionName?: string;
    name?: string;
    pain_points_addressed?: unknown;
    painPointsAddressed?: unknown;
    core_features?: unknown;
    coreFeatures?: unknown;
    [k: string]: unknown;
  }

  interface Props {
    /** Loose entries from researchContext (alternativeSolutions or selectedSolution). */
    solutions: unknown;
    /** When true, prepend a "Selected" badge to the first card. */
    markFirstAsSelected?: boolean;
  }

  let { solutions, markFirstAsSelected = false }: Props = $props();

  function asArray(raw: unknown): SolutionShape[] {
    if (Array.isArray(raw)) return raw as SolutionShape[];
    if (raw && typeof raw === "object") return [raw as SolutionShape];
    return [];
  }

  function strList(v: unknown): string[] {
    if (!Array.isArray(v)) return [];
    return (v as unknown[]).filter((x): x is string => typeof x === "string");
  }

  const list = $derived(
    asArray(solutions).map((s) => ({
      name: (s.solution_name as string) ?? (s.solutionName as string) ?? (s.name as string) ?? "Solution",
      addressesPains: strList(s.pain_points_addressed ?? s.painPointsAddressed),
      features: strList(s.core_features ?? s.coreFeatures),
    })),
  );
</script>

{#if list.length > 0}
  <div class="solutions-list">
    {#each list as s, i}
      <div class="solution-wrap">
        {#if markFirstAsSelected && i === 0}
          <span class="selected-tag">Selected</span>
        {/if}
        <SolutionCard
          name={s.name}
          addressesPains={s.addressesPains}
          features={s.features}
        />
      </div>
    {/each}
  </div>
{/if}

<style>
  .solutions-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 14px;
  }
  .solution-wrap {
    position: relative;
  }
  .selected-tag {
    position: absolute;
    top: -8px;
    right: 12px;
    z-index: 1;
    font-family: var(--font-mono);
    font-size: 9px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    padding: 3px 7px;
    border-radius: 3px;
    background: var(--color-success);
    color: var(--color-surface);
  }
</style>
