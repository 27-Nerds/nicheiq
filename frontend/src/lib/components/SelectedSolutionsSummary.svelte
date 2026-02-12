<script lang="ts">
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import { Target } from "lucide-svelte";
  import type { SolutionPreview } from "$lib/types/job";

  interface Props {
    selectedNames: string[];
    solutionIdeas: SolutionPreview[];
    primaryWinner?: string | null;
    status: string;
  }

  let { selectedNames, solutionIdeas, primaryWinner = null, status }: Props = $props();

  const selectedSolutions = $derived(
    selectedNames
      .map((name) => solutionIdeas.find((s) => s.solution_name === name))
      .filter((s): s is SolutionPreview => !!s),
  );

  const SUPERPOWER_MAP: Record<string, { label: string; variant: "success" | "accent" | "info" | "warning" }> = {
    market_fit_score: { label: "Strong Market Fit", variant: "success" },
    seo_scalability_score: { label: "SEO Powerhouse", variant: "accent" },
    novelty_score: { label: "Innovator", variant: "info" },
    technical_feasibility_score: { label: "Quick to Build", variant: "warning" },
    solo_dev_feasibility: { label: "Solo-Friendly", variant: "success" },
  };

  function getSuperpower(solution: SolutionPreview) {
    const scores: [string, number][] = [
      ["market_fit_score", solution.market_fit_score ?? 0],
      ["seo_scalability_score", solution.seo_scalability_score ?? 0],
      ["novelty_score", solution.novelty_score ?? 0],
      ["technical_feasibility_score", solution.technical_feasibility_score ?? 0],
      ["solo_dev_feasibility", solution.solo_dev_feasibility ?? 0],
    ];
    scores.sort((a, b) => b[1] - a[1]);
    return SUPERPOWER_MAP[scores[0][0]];
  }

  function getCompositeScore(solution: SolutionPreview): number {
    if (solution.adjusted_composite_score != null) return solution.adjusted_composite_score;
    const scores = [
      solution.market_fit_score ?? 0,
      solution.technical_feasibility_score ?? 0,
      solution.seo_scalability_score ?? 0,
      solution.novelty_score ?? 0,
      solution.solo_dev_feasibility ?? 0,
    ];
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  }

  const isCollapsible = $derived(status === "COMPLETED");
</script>

{#if selectedSolutions.length > 0}
  {#if isCollapsible}
    <ExpandableSection title="Your Selections ({selectedSolutions.length})" icon={Target} variant="accent">
      {@render summaryContent()}
    </ExpandableSection>
  {:else}
    <InsightCard variant="accent" border="left" padding="md">
      {#snippet header()}
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Target class="w-4 h-4 text-accent" />
            <span class="font-display font-semibold text-sm text-text-primary">
              {selectedSolutions.length === 1 ? "Your Selection" : `Your Selections (${selectedSolutions.length})`}
            </span>
          </div>
          {#if primaryWinner}
            <Badge variant="accent" size="sm">Primary: {primaryWinner}</Badge>
          {/if}
        </div>
      {/snippet}

      {@render summaryContent()}
    </InsightCard>
  {/if}
{/if}

{#snippet summaryContent()}
  <div class="grid grid-cols-1 {selectedSolutions.length > 1 ? `sm:grid-cols-${Math.min(selectedSolutions.length, 3)}` : ''} gap-3">
    {#each selectedSolutions as solution}
      {@const score = getCompositeScore(solution)}
      {@const superpower = getSuperpower(solution)}
      <div class="flex items-center gap-3 p-3 rounded-lg border border-border
        {solution.solution_name === primaryWinner ? 'bg-accent/5 border-accent/20' : ''}">
        <ProgressRing value={score} size={selectedSolutions.length === 1 ? 48 : 40} animate={true} showTooltip={false} flat={true} />
        <div class="flex-1 min-w-0">
          <h4 class="text-base font-semibold text-text-primary leading-snug truncate">{solution.solution_name}</h4>
          <p class="mt-1 text-xs text-text-muted italic truncate">{solution.value_proposition}</p>
          <div class="flex flex-wrap gap-1.5 mt-1.5">
            <Badge variant={superpower.variant} size="sm">{superpower.label}</Badge>
            {#if solution.project_type}
              <Badge size="sm">{solution.project_type}</Badge>
            {/if}
            {#if solution.estimated_development_time}
              <span class="text-xs text-text-muted">{solution.estimated_development_time}</span>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
{/snippet}
