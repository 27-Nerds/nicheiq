<script lang="ts">
  import {
    Target,
    Layers,
    Clock,
    DollarSign,
    Users,
    TrendingUp,
    Code,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { AlternativeSolution } from "$lib/types/report";
  import { renderMarkdown, formatScorePercent } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import ProgressBar from "$lib/components/ui/ProgressBar.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface Props {
    data: AlternativeSolution[];
  }

  let { data }: Props = $props();

  // Determine competitive intensity color
  function getIntensityColor(intensity: string | undefined): string {
    if (!intensity) return "text-text-muted";
    const lower = intensity.toLowerCase();
    if (lower === "low") return "text-success";
    if (lower === "high") return "text-error";
    return "text-warning";
  }
</script>

<Section
  id="alternatives"
  class="report-section"
  icon={SECTION_MAP['alternatives'].icon}
  title="Alternative Solutions"
  subtitle="{data.length} options analyzed as pivot considerations"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <p class="text-text-secondary mb-8">
    These alternative solutions were evaluated during the ideation process. Each
    offers a different approach with unique trade-offs.
  </p>

  <div class="space-y-6">
    {#each data as solution, index}
      <AnimateOnScroll animation="fade-in" delay={index * 100}>
        <div
          class="card hover:border-border-emphasis transition-colors"
        >
          <!-- Header -->
          <div class="flex flex-wrap items-start justify-between gap-4 mb-4">
            <div>
              <h3 class="text-xl font-semibold text-text-primary">
                {solutionDisplayTitle(solution)}
              </h3>
              {#if solution.headline?.trim()}
                <p class="text-text-muted text-xs uppercase tracking-wider">{solution.solution_name}</p>
              {/if}
              {#if solution.short_description || solution.value_proposition}
                <p class="text-text-secondary text-sm mt-1">
                  {solution.short_description || solution.value_proposition}
                </p>
              {/if}
            </div>
            <div class="flex flex-wrap gap-2">
              {#if solution.solo_dev_feasibility != null}
                {@const feasibility = solution.solo_dev_feasibility}
                {#if Number.isFinite(feasibility)}
                  <Badge
                    variant={feasibility >= 0.7
                      ? "success"
                      : feasibility >= 0.4
                        ? "warning"
                        : "error"}
                    size="sm"
                  >
                    Solo Dev: {formatScorePercent(feasibility, 0, "-")}
                  </Badge>
                {/if}
              {/if}
              {#if solution.competitive_intensity}
                <Badge variant="muted" size="sm">
                  <span
                    class={getIntensityColor(solution.competitive_intensity)}
                  >
                    Competition: {solution.competitive_intensity}
                  </span>
                </Badge>
              {/if}
            </div>
          </div>

          <!-- Scores Grid -->
          {#if solution.market_fit_score || solution.technical_feasibility_score || solution.novelty_score || solution.competitive_advantage_score}
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
              {#if solution.market_fit_score != null}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">Market Fit</div>
                  <ProgressBar
                    value={(solution.market_fit_score ?? 0) * 100}
                    max={100}
                    showValue={false}
                  />
                  <div class="text-sm font-medium text-text-primary mt-1">
                    {formatScorePercent(solution.market_fit_score)}
                  </div>
                </div>
              {/if}
              {#if solution.technical_feasibility_score != null}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">Technical</div>
                  <ProgressBar
                    value={(solution.technical_feasibility_score ?? 0) * 100}
                    max={100}
                    showValue={false}
                  />
                  <div class="text-sm font-medium text-text-primary mt-1">
                    {formatScorePercent(solution.technical_feasibility_score)}
                  </div>
                </div>
              {/if}
              {#if solution.competitive_advantage_score != null}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">Competitive</div>
                  <ProgressBar
                    value={(solution.competitive_advantage_score ?? 0) * 100}
                    max={100}
                    showValue={false}
                  />
                  <div class="text-sm font-medium text-text-primary mt-1">
                    {formatScorePercent(solution.competitive_advantage_score)}
                  </div>
                </div>
              {/if}
              {#if solution.seo_growth_potential_score != null}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">SEO Potential</div>
                  <ProgressBar
                    value={(solution.seo_growth_potential_score ?? 0) * 100}
                    max={100}
                    showValue={false}
                  />
                  <div class="text-sm font-medium text-text-primary mt-1">
                    {formatScorePercent(solution.seo_growth_potential_score)}
                  </div>
                </div>
              {/if}
              {#if solution.novelty_score !== undefined}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">Novelty</div>
                  <ProgressBar
                    value={solution.novelty_score * 100}
                    max={100}
                    showValue={false}
                  />
                  <div class="text-sm font-medium text-text-primary mt-1">
                    {formatScorePercent(solution.novelty_score)}
                  </div>
                </div>
              {/if}
            </div>
          {/if}

          <!-- Summary/Description -->
          {#if solution.summary}
            <div class="markdown-content narrative text-sm mb-4">
              {@html renderMarkdown(solution.summary)}
            </div>
          {:else if solution.description}
            <p class="text-text-secondary text-sm mb-4">
              {solution.description}
            </p>
          {/if}

          <!-- Technical Approach -->
          {#if solution.technical_approach}
            <div class="card-surface mb-4">
              <div class="flex items-center gap-2 mb-2">
                <Code class="w-4 h-4 text-accent" />
                <span class="text-sm font-medium text-text-primary"
                  >Technical Approach</span
                >
              </div>
              <p class="text-sm text-text-secondary leading-relaxed">
                {solution.technical_approach}
              </p>
            </div>
          {/if}

          <!-- Details Grid -->
          <div class="grid md:grid-cols-2 gap-4 mb-4">
            <!-- Core Features -->
            {#if solution.core_features && solution.core_features.length > 0}
              <div class="card-surface">
                <div class="flex items-center gap-2 mb-2">
                  <Layers class="w-4 h-4 text-accent" />
                  <span class="text-sm font-medium text-text-primary"
                    >Core Features</span
                  >
                </div>
                <ul class="space-y-1">
                  {#each solution.core_features.slice(0, 5) as feature}
                    <li
                      class="text-sm text-text-secondary leading-relaxed flex items-start gap-1"
                    >
                      <span class="text-accent">•</span>
                      {feature}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}

            <!-- Target Personas -->
            {#if solution.target_personas && solution.target_personas.length > 0}
              <div class="card-surface">
                <div class="flex items-center gap-2 mb-2">
                  <Users class="w-4 h-4 text-accent" />
                  <span class="text-sm font-medium text-text-primary"
                    >Target Users</span
                  >
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each solution.target_personas as persona}
                    <span
                      class="text-xs px-2 py-0.5 rounded bg-bg-surface border border-border text-text-muted"
                      >{persona}</span
                    >
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Competitors -->
            {#if solution.top_competitors && solution.top_competitors.length > 0}
              <div class="card-surface">
                <div class="flex items-center gap-2 mb-2">
                  <Users class="w-4 h-4 text-warning" />
                  <span class="text-sm font-medium text-text-primary"
                    >Top Competitors</span
                  >
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each solution.top_competitors as competitor}
                    <span
                      class="text-xs px-2 py-0.5 rounded bg-warning/10 border border-warning/30 text-warning"
                      >{competitor}</span
                    >
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Market Gaps -->
            {#if solution.market_gaps && solution.market_gaps.length > 0}
              <div class="card-surface">
                <div class="flex items-center gap-2 mb-2">
                  <Target class="w-4 h-4 text-success" />
                  <span class="text-sm font-medium text-text-primary"
                    >Market Gaps Addressed</span
                  >
                </div>
                <ul class="space-y-1">
                  {#each solution.market_gaps as gap}
                    <li
                      class="text-sm text-text-secondary leading-relaxed flex items-start gap-1"
                    >
                      <span class="text-success">+</span>
                      {gap}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
          </div>

          <!-- Economic Indicators -->
          {#if solution.estimated_development_time || solution.estimated_cac_organic || solution.pricing_model}
            <div
              class="flex flex-wrap gap-4 text-sm border-t border-border pt-4 mb-4"
            >
              {#if solution.estimated_development_time}
                <div class="flex items-center gap-2">
                  <Clock class="w-4 h-4 text-text-muted" />
                  <span class="text-text-muted">Dev Time:</span>
                  <span class="text-text-primary"
                    >{solution.estimated_development_time}</span
                  >
                </div>
              {/if}
              {#if solution.estimated_cac_organic}
                <div class="flex items-center gap-2">
                  <DollarSign class="w-4 h-4 text-text-muted" />
                  <span class="text-text-muted inline-flex items-center gap-1">
                    CAC: <Tooltip
                      content={getTermTooltip("CAC")}
                      position="top"
                    />
                  </span>
                  <span class="text-text-primary"
                    >{solution.estimated_cac_organic}</span
                  >
                </div>
              {/if}
              {#if solution.pricing_model}
                <div class="flex items-center gap-2">
                  <TrendingUp class="w-4 h-4 text-text-muted" />
                  <span class="text-text-muted">Pricing:</span>
                  <span class="text-text-primary">{solution.pricing_model}</span
                  >
                </div>
              {/if}
            </div>
          {/if}

          <!-- Key Differentiator & Best Suited For -->
          <div class="grid md:grid-cols-2 gap-4 border-t border-border pt-4">
            {#if solution.key_differentiator}
              <div>
                <div class="text-xs text-text-muted mb-1">
                  Key Differentiator
                </div>
                <p class="text-sm text-accent">{solution.key_differentiator}</p>
              </div>
            {/if}
            {#if solution.best_suited_for}
              <div>
                <div class="text-xs text-text-muted mb-1">Best Suited For</div>
                <p class="text-sm text-text-primary">
                  {solution.best_suited_for}
                </p>
              </div>
            {/if}
          </div>

          <!-- Pivot Trigger -->
          {#if solution.pivot_trigger}
            <div
              class="mt-4 p-3 rounded bg-warning/10 border border-warning/30"
            >
              <div class="text-xs text-warning font-medium mb-1">
                When to Pivot to This Solution
              </div>
              <p class="text-sm text-text-secondary">
                {solution.pivot_trigger}
              </p>
            </div>
          {/if}
        </div>
      </AnimateOnScroll>
    {/each}
  </div>
</Section>
