<script lang="ts">
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import SolutionDetail from "./SolutionDetail.svelte";
  import { ListChecks, Clock } from "lucide-svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { computeCompositeScore, solutionStrengthBadge } from "$lib/utils/solution-utils";

  interface Props {
    selectedNames: string[];
    solutionIdeas: SolutionPreview[];
    primaryWinner?: string | null;
    status: string;
  }

  let { selectedNames, solutionIdeas, primaryWinner = null, status }: Props = $props();

  let modalIndex = $state<number | null>(null);

  const selectedSolutions = $derived(
    selectedNames
      .map((name) => solutionIdeas.find((s) => s.solution_name === name))
      .filter((s): s is SolutionPreview => !!s),
  );

  const isCollapsible = $derived(status === "COMPLETED");
</script>

{#if selectedSolutions.length > 0}
  {#if isCollapsible}
    <ExpandableSection title="Your Selections ({selectedSolutions.length})" icon={ListChecks} variant="accent">
      {@render summaryContent()}
    </ExpandableSection>
  {:else}
    <InsightCard variant="accent" border="left" padding="md">
      {#snippet header()}
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <ListChecks class="w-4 h-4 text-accent" />
            <span class="font-display font-semibold text-sm text-text-primary">
              {selectedSolutions.length === 1 ? "Your Selection" : `Your Selections (${selectedSolutions.length})`}
            </span>
          </div>
        </div>
      {/snippet}

      {@render summaryContent()}
    </InsightCard>
  {/if}
{/if}

{#snippet summaryContent()}
  <div class="grid grid-cols-1 {selectedSolutions.length > 1 ? `sm:grid-cols-${Math.min(selectedSolutions.length, 3)}` : ''} gap-3">
    {#each selectedSolutions as solution, i}
      {@const score = computeCompositeScore(solution)}
      {@const superpower = solutionStrengthBadge(solution, true)}
      <button
        type="button"
        class="flex items-center gap-3 p-3 rounded-lg border border-border text-left cursor-pointer transition-colors hover:border-border-hover
          {solution.solution_name === primaryWinner ? 'bg-accent/5 border-accent/20' : ''}"
        onclick={() => modalIndex = i}
      >
        <ProgressRing value={score} size={selectedSolutions.length === 1 ? 48 : 40} animate={true} showTooltip={false} flat={true} />
        <div class="flex-1 min-w-0">
          <h4 class="text-base font-semibold text-text-primary leading-snug truncate">{solution.solution_name}</h4>
          <p class="mt-1 text-xs text-text-muted italic truncate">{solution.value_proposition}</p>
          <div class="flex items-center flex-wrap gap-1.5 mt-1.5">
            {#if solution.solution_name === primaryWinner}
              <Badge variant="accent" size="sm">Top Recommended</Badge>
            {:else if superpower}
              <Badge variant={superpower.variant} size="sm">{superpower.label}</Badge>
            {/if}
            {#if solution.project_type}
              <span class="text-[0.625rem] px-2 py-1 rounded-full bg-bg-elevated border border-border text-text-muted leading-none">
                {solution.project_type}
              </span>
            {/if}
            {#if solution.estimated_development_time}
              {@const devTime = solution.estimated_development_time}
              {@const match = devTime.match(/^[\d\-\+]+\s*(?:weeks?|months?|days?)/i)}
              {@const short = match ? match[0] : devTime.length <= 20 ? devTime : devTime.slice(0, 17) + '...'}
              <span class="text-xs text-text-muted inline-flex items-center gap-1" title={devTime}>
                <Clock class="w-3 h-3" />{short}
              </span>
            {/if}
          </div>
        </div>
      </button>
    {/each}
  </div>
{/snippet}

{#if modalIndex !== null && selectedSolutions[modalIndex]}
  <SolutionDetail
    open={true}
    solution={selectedSolutions[modalIndex]}
    solutions={selectedSolutions}
    currentIndex={modalIndex}
    isSelected={true}
    disabled={true}
    maxReached={true}
    onSelect={() => {}}
    onNavigate={(idx) => modalIndex = idx}
    onClose={() => modalIndex = null}
  />
{/if}
