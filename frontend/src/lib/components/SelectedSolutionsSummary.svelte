<script lang="ts">
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import SolutionDetail from "./SolutionDetail.svelte";
  import { ListChecks, Clock } from "lucide-svelte";
  import type { SelectionDraftItem, SolutionPreview } from "$lib/types/job";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import { displayCompositeScore, solutionStrengthBadge } from "$lib/utils/solution-utils";

  interface Props {
    selectedNames: string[];
    selectedItems?: SelectionDraftItem[];
    solutionIdeas: SolutionPreview[];
    primaryWinner?: string | null;
    primaryWinnerRef?: Pick<SelectionDraftItem, "ideaId" | "ideaRevision"> | null;
    showIdentity?: boolean;
    status: string;
    jobId?: string;
  }

  let {
    selectedNames,
    selectedItems = [],
    solutionIdeas,
    primaryWinner = null,
    primaryWinnerRef = null,
    showIdentity = false,
    status,
    jobId,
  }: Props = $props();

  let modalIndex = $state<number | null>(null);

  const selectionResolution = $derived.by(() => {
    if (selectedItems.length > 0) {
      const ideas = selectedItems
        .map((item) => solutionIdeas.find((idea) =>
          idea.idea_id === item.ideaId
          && (idea.idea_revision ?? 1) === item.ideaRevision
        ))
        .filter((idea): idea is SolutionPreview => Boolean(idea));
      return { ideas, unresolved: selectedItems.length - ideas.length };
    }

    // Legacy reports persisted names only. A name is safe only when it resolves to one
    // candidate; never choose arbitrarily between duplicate-name revisions.
    const ideas: SolutionPreview[] = [];
    let unresolved = 0;
    for (const name of selectedNames) {
      const matches = solutionIdeas.filter((idea) => idea.solution_name === name);
      if (matches.length === 1) ideas.push(matches[0]);
      else unresolved += 1;
    }
    return { ideas, unresolved };
  });
  const selectedSolutions = $derived(selectionResolution.ideas);

  const isCollapsible = $derived(status === "COMPLETED");
  const lifecycle = $derived<"running" | "completed" | "reference">(
    status === "COMPLETED"
      ? "completed"
      : status === "RUNNING_PHASE2" || status === "QUEUED" || status === "PENDING"
        ? "running"
        : "reference",
  );

  function shortIdeaId(ideaId: string): string {
    return ideaId.length <= 16 ? ideaId : `${ideaId.slice(0, 12)}…`;
  }

  function isPrimaryWinner(solution: SolutionPreview): boolean {
    if (primaryWinnerRef) {
      return solution.idea_id === primaryWinnerRef.ideaId
        && (solution.idea_revision ?? 1) === primaryWinnerRef.ideaRevision;
    }
    if (!primaryWinner) return false;
    const matches = solutionIdeas.filter((candidate) => candidate.solution_name === primaryWinner);
    return matches.length === 1 && matches[0] === solution;
  }
</script>

{#if showIdentity && selectedItems.length > 0}
  <div class="selection-identity-receipt" aria-label="Exact Deep Research selection">
    <span>Exact selection</span>
    <ul>
      {#each selectedItems as item (`${item.ideaId}:${item.ideaRevision}`)}
        <li title={`${item.ideaId} · revision ${item.ideaRevision}`}>
          Idea {shortIdeaId(item.ideaId)} · rev {item.ideaRevision}
        </li>
      {/each}
    </ul>
  </div>
{/if}

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

{#if selectionResolution.unresolved > 0}
  <p class="selection-resolution-note" role="status">
    {selectionResolution.unresolved} selected candidate
    {selectionResolution.unresolved === 1 ? " is" : "s are"} no longer available at the saved revision.
  </p>
{/if}

{#snippet summaryContent()}
  <div class="grid grid-cols-1 {selectedSolutions.length > 1 ? `sm:grid-cols-${Math.min(selectedSolutions.length, 3)}` : ''} gap-3">
    {#each selectedSolutions as solution, i}
      {@const score = displayCompositeScore(solution)}
      {@const superpower = solutionStrengthBadge(solution, true)}
      <button
        type="button"
        class="flex items-center gap-3 p-3 rounded-lg border border-border text-left cursor-pointer transition-colors hover:border-border-hover
          {isPrimaryWinner(solution) ? 'bg-accent/5 border-accent/20' : ''}"
        onclick={() => modalIndex = i}
      >
        <span class="inline-flex cursor-help" title={SCORE_DEFINITIONS.composite}>
          {#if score !== null}
            <ProgressRing value={score} size={selectedSolutions.length === 1 ? 48 : 40} animate={true} showTooltip={false} flat={true} />
          {:else}
            <span class="score-unavailable" aria-label="Research score not available">--</span>
          {/if}
        </span>
        <div class="flex-1 min-w-0">
          <h4 class="text-base font-semibold text-text-primary leading-snug truncate">{solution.solution_name}</h4>
          <p class="mt-1 text-xs text-text-muted italic truncate">{solution.value_proposition}</p>
          <div class="flex items-center flex-wrap gap-1.5 mt-1.5">
            {#if isPrimaryWinner(solution)}
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
    {jobId}
    {lifecycle}
    onNavigate={(idx) => modalIndex = idx}
    onClose={() => modalIndex = null}
  />
{/if}

<style>
  .selection-identity-receipt {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
    align-items: center;
    margin: 0 0 var(--space-3);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .selection-identity-receipt > span {
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .selection-identity-receipt ul {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .selection-identity-receipt li + li::before {
    margin-right: var(--space-2);
    color: var(--color-border-emphasis);
    content: "·";
  }

  .score-unavailable {
    display: inline-grid;
    width: var(--space-10);
    height: var(--space-10);
    place-items: center;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
  }

  .selection-resolution-note {
    margin: var(--space-3) 0 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.5;
  }
</style>
