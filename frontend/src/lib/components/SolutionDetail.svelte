<script lang="ts">
  import {
    CheckCircle,
    Circle,
    ChevronDown,
    ChevronUp,
    ChevronLeft,
    ChevronRight,
    X,
  } from "lucide-svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressBar from "$lib/components/ui/ProgressBar.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { renderTechnicalContent } from "$lib/utils/format";

  interface Props {
    open: boolean;
    solution: SolutionPreview;
    solutions: SolutionPreview[];
    currentIndex: number;
    isSelected?: boolean;
    disabled?: boolean;
    onSelect: (name: string) => void;
    onNavigate: (index: number) => void;
    onClose: () => void;
  }

  let {
    open = $bindable(false),
    solution,
    solutions,
    currentIndex,
    isSelected = false,
    disabled = false,
    onSelect,
    onNavigate,
    onClose,
  }: Props = $props();

  let expandedSections = $state<Set<string>>(new Set());
  let modalEl: HTMLDivElement | undefined = $state();

  // Reset expanded sections when navigating to a different solution
  $effect(() => {
    // Track currentIndex — when it changes, reset
    currentIndex;
    expandedSections = new Set();
  });

  // Focus trap: focus modal when opened
  $effect(() => {
    if (open && modalEl) {
      modalEl.focus();
    }
  });

  const total = $derived(solutions.length);

  const scores = $derived([
    { label: "Market Fit", value: solution.market_fit_score },
    { label: "Feasibility", value: solution.technical_feasibility_score },
    { label: "SEO Potential", value: solution.seo_scalability_score },
    { label: "Novelty", value: solution.novelty_score },
    { label: "Solo Dev", value: solution.solo_dev_feasibility },
  ]);

  // Composite score for ProgressRing (0-1)
  const compositeScore = $derived.by(() => {
    if (solution.adjusted_composite_score != null) return solution.adjusted_composite_score;
    const vals = [
      solution.market_fit_score ?? 0,
      solution.technical_feasibility_score ?? 0,
      solution.seo_scalability_score ?? 0,
      solution.novelty_score ?? 0,
      solution.solo_dev_feasibility ?? 0,
    ];
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  });

  // Score color (matches ProgressRing auto logic)
  const scoreColor = $derived.by(() => {
    if (compositeScore >= 0.7) return 'var(--color-success)';
    if (compositeScore >= 0.4) return 'var(--color-warning)';
    return 'var(--color-error)';
  });

  // Superpower badge
  const SUPERPOWER_MAP: Record<string, { label: string; variant: "success" | "accent" | "info" | "warning" }> = {
    market_fit_score: { label: "Strong Market Fit", variant: "success" },
    seo_scalability_score: { label: "SEO Powerhouse", variant: "accent" },
    novelty_score: { label: "Innovator", variant: "info" },
    technical_feasibility_score: { label: "Quick to Build", variant: "warning" },
    solo_dev_feasibility: { label: "Solo-Friendly", variant: "success" },
  };

  const superpower = $derived.by(() => {
    const entries: [string, number][] = [
      ["market_fit_score", solution.market_fit_score ?? 0],
      ["seo_scalability_score", solution.seo_scalability_score ?? 0],
      ["novelty_score", solution.novelty_score ?? 0],
      ["technical_feasibility_score", solution.technical_feasibility_score ?? 0],
      ["solo_dev_feasibility", solution.solo_dev_feasibility ?? 0],
    ];
    entries.sort((a, b) => b[1] - a[1]);
    return SUPERPOWER_MAP[entries[0][0]];
  });

  // Dev time parsing
  const devTimeParsed = $derived.by(() => {
    const devTime = solution.estimated_development_time;
    if (!devTime) return null;
    const match = devTime.match(/^[\d\-\+]+\s*(?:weeks?|months?|days?)/i);
    if (match) return { short: match[0], full: devTime };
    if (devTime.length <= 20) return { short: devTime, full: devTime };
    return { short: devTime.slice(0, 17) + "...", full: devTime };
  });

  // Expandable sections config
  const detailSections = $derived.by(() => {
    const sections: { id: string; label: string; hasContent: boolean }[] = [];

    if (solution.pricing_strategy) sections.push({ id: 'pricing', label: 'Pricing Strategy', hasContent: true });
    if (solution.conventional_approach || solution.innovation_angle || solution.why_it_works)
      sections.push({ id: 'innovation', label: 'Innovation Breakdown', hasContent: true });
    if (solution.core_features && solution.core_features.length > 0)
      sections.push({ id: 'features', label: 'Core Features', hasContent: true });
    if (solution.pain_points_addressed && solution.pain_points_addressed.length > 0)
      sections.push({ id: 'painpoints', label: 'Pain Points', hasContent: true });
    if (solution.differentiation_factors && solution.differentiation_factors.length > 0)
      sections.push({ id: 'differentiation', label: 'Differentiation', hasContent: true });
    if (solution.target_personas && solution.target_personas.length > 0)
      sections.push({ id: 'personas', label: 'Target Personas', hasContent: true });
    if (solution.programmatic_seo_opportunity)
      sections.push({ id: 'seo', label: 'SEO Opportunity', hasContent: true });
    if (solution.estimated_cac_organic)
      sections.push({ id: 'cac', label: 'Estimated CAC', hasContent: true });
    if (solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0)
      sections.push({ id: 'queries', label: 'Organic Queries', hasContent: true });

    return sections;
  });

  function toggleSection(id: string) {
    const next = new Set(expandedSections);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    expandedSections = next;
  }

  function handleSelect() {
    if (!disabled) onSelect(solution.solution_name);
  }

  function navigatePrev() {
    const prev = currentIndex <= 0 ? total - 1 : currentIndex - 1;
    onNavigate(prev);
  }

  function navigateNext() {
    const next = currentIndex >= total - 1 ? 0 : currentIndex + 1;
    onNavigate(next);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowLeft') { e.preventDefault(); navigatePrev(); }
    if (e.key === 'ArrowRight') { e.preventDefault(); navigateNext(); }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    aria-label="Solution details: {solution.solution_name}"
    tabindex="-1"
  >
    <!-- Nav arrow: Previous -->
    {#if total > 1}
      <button
        type="button"
        class="nav-arrow nav-arrow-left"
        onclick={navigatePrev}
        aria-label="Previous solution"
      >
        <ChevronLeft class="w-6 h-6" />
      </button>
    {/if}

    <!-- Modal card -->
    <div
      bind:this={modalEl}
      class="modal-card bg-bg-surface border border-border rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col"
      tabindex="-1"
    >
      <!-- Header -->
      <div class="flex items-center justify-between gap-3 p-4 border-b border-border shrink-0">
        <div class="min-w-0">
          <div class="flex items-center gap-3">
            <h2 class="text-xl font-semibold text-text-primary truncate">{solution.solution_name}</h2>
            {#if total > 1}
              <span class="text-xs text-text-muted tabular-nums shrink-0">{currentIndex + 1} of {total}</span>
            {/if}
          </div>
          <div class="flex items-center gap-2 mt-1.5 flex-wrap">
            <div class="flex items-center gap-1">
              <ProgressRing value={compositeScore} size={24} showValue={false} color="auto" animate={false} showTooltip={false} flat={true} />
              <span class="text-sm font-semibold font-display" style:color={scoreColor}>{Math.round(compositeScore * 100)}</span>
            </div>
            <Badge variant={superpower.variant} size="sm">{superpower.label}</Badge>
            {#if solution.project_type}
              <span class="text-xs px-2 py-0.5 rounded-full bg-bg-elevated border border-border text-text-muted">
                {solution.project_type}
              </span>
            {/if}
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <!-- Select / Deselect button -->
          <button
            type="button"
            onclick={handleSelect}
            disabled={disabled}
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
              {isSelected
                ? 'bg-accent/10 text-accent border border-accent/30 hover:bg-accent/15'
                : 'bg-bg-elevated text-text-secondary border border-border hover:border-accent/40 hover:text-accent'
              }
              disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {#if isSelected}
              <CheckCircle class="w-4 h-4" />
              Selected
            {:else}
              <Circle class="w-4 h-4" />
              Select
            {/if}
          </button>
          <!-- Close button -->
          <button
            type="button"
            onclick={onClose}
            aria-label="Close details"
            class="p-1.5 rounded-lg hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
          >
            <X class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Scrollable body -->
      <div class="p-5 overflow-y-auto flex-1">
        <!-- Two-column layout: scores left, text right -->
        <div class="detail-columns">
          <!-- Left: Score ring + bars -->
          <div class="detail-scores">
            <div class="space-y-2">
              {#each scores as score}
                <div>
                  <div class="flex items-center justify-between mb-0.5">
                    <span class="text-xs text-text-muted">{score.label}</span>
                    <span class="text-xs font-mono text-text-muted">
                      {score.value != null ? (score.value * 100).toFixed(0) : "--"}
                    </span>
                  </div>
                  <ProgressBar value={score.value ?? 0} showValue={false} />
                </div>
              {/each}
            </div>
          </div>

          <!-- Right: Text content -->
          <div class="detail-text">
            <!-- Value proposition -->
            {#if solution.value_proposition}
              <p class="text-sm text-text-muted italic leading-relaxed">
                "{solution.value_proposition}"
              </p>
            {/if}

            <!-- Description -->
            <p class="mt-2 text-sm text-text-secondary leading-relaxed">
              {solution.description}
            </p>

            <!-- Quick info row -->
            {#if devTimeParsed}
              <div class="flex flex-wrap items-center gap-2 mt-3">
                <span class="text-xs text-text-muted flex items-center gap-1" title={devTimeParsed.full}>
                  <span>&#9201;</span> {devTimeParsed.short}
                </span>
              </div>
            {/if}

            <!-- Expandable section pills -->
            {#if detailSections.length > 0}
              <div class="flex flex-wrap gap-1.5 mt-4">
                {#each detailSections as section}
                  <button
                    type="button"
                    class="text-xs px-2.5 py-1 rounded-md border transition-colors
                      {expandedSections.has(section.id)
                        ? 'bg-accent/10 border-accent/30 text-accent'
                        : 'bg-bg-elevated border-border text-text-muted hover:border-accent/30 hover:text-text-secondary'}"
                    onclick={() => toggleSection(section.id)}
                  >
                    {section.label}
                    {#if expandedSections.has(section.id)}
                      <ChevronUp class="w-3 h-3 inline ml-0.5" />
                    {:else}
                      <ChevronDown class="w-3 h-3 inline ml-0.5" />
                    {/if}
                  </button>
                {/each}
              </div>

              <!-- Expanded section content -->
              {#each detailSections as section}
                {#if expandedSections.has(section.id)}
                  <div class="mt-3 text-sm border-t border-border pt-3">
                    {#if section.id === 'pricing' && solution.pricing_strategy}
                      <h4 class="mono-label mb-1">Pricing Strategy</h4>
                      <p class="text-text-secondary">{solution.pricing_strategy}</p>
                    {/if}

                    {#if section.id === 'innovation'}
                      <h4 class="mono-label mb-2">Innovation Breakdown</h4>
                      <div class="space-y-2">
                        {#if solution.conventional_approach}
                          <div class="rounded border border-border px-3 py-2">
                            <span class="text-xs font-medium uppercase tracking-wider text-text-muted">Conventional Path</span>
                            <p class="mt-0.5 text-text-secondary">{solution.conventional_approach}</p>
                          </div>
                        {/if}
                        {#if solution.innovation_angle}
                          <div class="rounded border border-accent/30 bg-accent/5 px-3 py-2">
                            <span class="text-xs font-medium uppercase tracking-wider text-accent">What's Different</span>
                            <p class="mt-0.5 text-text-secondary">{solution.innovation_angle}</p>
                          </div>
                        {/if}
                        {#if solution.why_it_works}
                          <div class="rounded border border-border px-3 py-2">
                            <span class="text-xs font-medium uppercase tracking-wider text-text-muted">Why It Works</span>
                            <p class="mt-0.5 text-text-secondary">{solution.why_it_works}</p>
                          </div>
                        {/if}
                      </div>
                    {/if}

                    {#if section.id === 'features' && solution.core_features}
                      <h4 class="mono-label mb-1">Core Features</h4>
                      <ul class="space-y-0.5">
                        {#each solution.core_features as feature}
                          <li class="text-text-secondary flex items-start gap-1.5">
                            <span class="text-accent mt-1 shrink-0">-</span>
                            {feature}
                          </li>
                        {/each}
                      </ul>
                    {/if}

                    {#if section.id === 'painpoints' && solution.pain_points_addressed}
                      <h4 class="mono-label mb-1">Pain Points Addressed</h4>
                      <ul class="space-y-0.5">
                        {#each solution.pain_points_addressed as point}
                          <li class="text-text-secondary flex items-start gap-1.5">
                            <span class="text-accent mt-1 shrink-0">-</span>
                            {point}
                          </li>
                        {/each}
                      </ul>
                    {/if}

                    {#if section.id === 'differentiation' && solution.differentiation_factors}
                      <h4 class="mono-label mb-1">Differentiation</h4>
                      <ul class="space-y-0.5">
                        {#each solution.differentiation_factors as factor}
                          <li class="text-text-secondary flex items-start gap-1.5">
                            <span class="text-accent mt-1 shrink-0">-</span>
                            {factor}
                          </li>
                        {/each}
                      </ul>
                    {/if}

                    {#if section.id === 'personas' && solution.target_personas}
                      <h4 class="mono-label mb-1">Target Personas</h4>
                      <ul class="space-y-0.5">
                        {#each solution.target_personas as persona}
                          <li class="text-text-secondary flex items-start gap-1.5">
                            <span class="text-accent mt-1 shrink-0">-</span>
                            {persona}
                          </li>
                        {/each}
                      </ul>
                    {/if}

                    {#if section.id === 'seo' && solution.programmatic_seo_opportunity}
                      <h4 class="mono-label mb-1">Programmatic SEO Opportunity</h4>
                      <div class="markdown-content markdown-content-compact text-text-secondary text-sm">
                        {@html renderTechnicalContent(solution.programmatic_seo_opportunity)}
                      </div>
                    {/if}

                    {#if section.id === 'cac' && solution.estimated_cac_organic}
                      <h4 class="mono-label mb-1">Estimated CAC</h4>
                      <p class="text-text-secondary">
                        {solution.estimated_cac_organic}{#if solution.estimated_cac_paid} <span class="text-text-muted">(vs {solution.estimated_cac_paid} paid)</span>{/if}
                      </p>
                    {/if}

                    {#if section.id === 'queries' && solution.organic_discovery_queries}
                      <h4 class="mono-label mb-1">Organic Discovery Queries</h4>
                      <div class="flex flex-wrap gap-1.5">
                        {#each solution.organic_discovery_queries as query}
                          <span class="text-xs px-2 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary">
                            {query}
                          </span>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              {/each}
            {/if}
          </div>
        </div>
      </div>
    </div>

    <!-- Nav arrow: Next -->
    {#if total > 1}
      <button
        type="button"
        class="nav-arrow nav-arrow-right"
        onclick={navigateNext}
        aria-label="Next solution"
      >
        <ChevronRight class="w-6 h-6" />
      </button>
    {/if}
  </div>
{/if}

<style>
  .modal-card {
    position: relative;
    z-index: 1;
  }

  .nav-arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  }

  .nav-arrow:hover {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    border-color: var(--color-accent);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.16);
  }

  .nav-arrow-left {
    left: max(0.5rem, calc(50% - 28rem));
  }

  .nav-arrow-right {
    right: max(0.5rem, calc(50% - 28rem));
  }

  /* On smaller screens, position arrows at edge */
  @media (max-width: 900px) {
    .nav-arrow-left {
      left: 0.25rem;
    }
    .nav-arrow-right {
      right: 0.25rem;
    }
  }

  /* Hide arrows on very small screens (use keyboard/swipe instead) */
  @media (max-width: 480px) {
    .nav-arrow {
      display: none;
    }
  }

  .detail-columns {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  @media (min-width: 640px) {
    .detail-columns {
      flex-direction: row;
      gap: 1.5rem;
    }
  }

  .detail-scores {
    flex-shrink: 0;
  }

  @media (min-width: 640px) {
    .detail-scores {
      width: 12rem;
    }
  }

  .detail-text {
    flex: 1;
    min-width: 0;
  }

  .markdown-content-compact :global(h1),
  .markdown-content-compact :global(h2),
  .markdown-content-compact :global(h3),
  .markdown-content-compact :global(h4) {
    margin-top: 0.75rem;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
  }
  .markdown-content-compact :global(p) {
    margin-bottom: 0.5rem;
  }
  .markdown-content-compact :global(ul),
  .markdown-content-compact :global(ol) {
    margin-bottom: 0.5rem;
  }
</style>
