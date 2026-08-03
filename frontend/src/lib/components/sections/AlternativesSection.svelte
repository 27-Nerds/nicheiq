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
  import { renderMarkdown, formatScorePercent, humanizeInternalJargon } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import ProgressBar from "$lib/components/ui/ProgressBar.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";
  import { solutionDisplayTitle, originalityScore, originalityMetric } from "$lib/utils/solution-utils";
  import { normalizeDataAccess } from "$lib/utils/ideaTagLabels";
  import {
    adversarialReviewFinding,
    directIncumbentParity,
    noDirectIncumbentFound,
    PREMISE_UNPROVEN_CODA,
  } from "$lib/utils/adversarialReview";

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

  // Data-access model → human label + risk-palette variant (severity ramp, never accent).
  const ACCESS_LABELS: Record<string, string> = {
    public: "Public API",
    freemium: "Freemium API",
    paywalled: "Paid Data",
    unofficial: "Scraping / Unofficial",
    restricted: "Access Restricted",
    blocked: "Blocked",
    unverified: "Unverified",
  };
  // Empty label = value outside the closed vocabulary; the badge is omitted.
  function accessLabel(m: string | undefined): string {
    const k = normalizeDataAccess(m);
    return k ? ACCESS_LABELS[k] : "";
  }
  function accessVariant(m: string | undefined): "success" | "warning" | "error" | "muted" {
    const k = normalizeDataAccess(m);
    if (k === "public" || k === "freemium") return "success";
    if (k === "paywalled" || k === "unofficial") return "warning";
    if (k === "restricted" || k === "blocked") return "error";
    return "muted";
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
      {@const directParity = directIncumbentParity(solution)}
      {@const noIncumbentFound = noDirectIncumbentFound(solution)}
      {@const adversarial = adversarialReviewFinding(solution)}
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
              {#if solution.idea_tier === "bundle"}
                <Badge variant="accent" size="sm">Bundle product</Badge>
              {:else if solution.idea_tier === "salvaged"}
                <Badge variant="info" size="sm">Rescued concept</Badge>
              {:else if solution.idea_tier === "merged"}
                <Badge variant="muted" size="sm">Merged</Badge>
              {/if}
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
              {#if accessLabel(solution.data_access_model)}
                <Badge
                  variant={accessVariant(solution.data_access_model)}
                  size="sm"
                  title={solution.data_acquisition_notes || undefined}
                >
                  Data: {accessLabel(solution.data_access_model)}
                </Badge>
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
          {#if solution.market_fit_score || solution.technical_feasibility_score || originalityScore(solution) != null || solution.competitive_advantage_score}
            <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
              {#if solution.market_fit_score != null}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">
                    <Tooltip content={SCORE_DEFINITIONS.market_fit} position="top" class="cursor-help">
                      {#snippet children()}<span>Market Fit</span>{/snippet}
                    </Tooltip>
                  </div>
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
                  <div class="text-xs text-text-muted mb-1">
                    <Tooltip content={SCORE_DEFINITIONS.technical_feasibility} position="top" class="cursor-help">
                      {#snippet children()}<span>Technical</span>{/snippet}
                    </Tooltip>
                  </div>
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
                  <div class="text-xs text-text-muted mb-1">
                    <Tooltip content={SCORE_DEFINITIONS.competitive_advantage} position="top" class="cursor-help">
                      {#snippet children()}<span>Competitive</span>{/snippet}
                    </Tooltip>
                  </div>
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
                  <div class="text-xs text-text-muted mb-1">
                    <Tooltip content={SCORE_DEFINITIONS.seo} position="top" class="cursor-help">
                      {#snippet children()}<span>SEO Potential</span>{/snippet}
                    </Tooltip>
                  </div>
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
              {#if originalityMetric(solution).value != null}
                {@const orig = originalityMetric(solution)}
                <div class="text-center">
                  <div class="text-xs text-text-muted mb-1">
                    <Tooltip content={SCORE_DEFINITIONS.originality} position="top" class="cursor-help">
                      {#snippet children()}<span>{orig.label}</span>{/snippet}
                    </Tooltip>
                  </div>
                  <ProgressBar
                    value={(orig.value ?? 0) * 100}
                    max={100}
                    showValue={false}
                  />
                  <div class="text-sm font-medium text-text-primary mt-1">
                    {formatScorePercent(orig.value)}
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
                  <Users class="w-4 h-4 text-text-muted" />
                  <span class="text-sm font-medium text-text-primary"
                    >Top Competitors</span
                  >
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each solution.top_competitors as competitor}
                    <span
                      class="text-xs px-2 py-0.5 rounded border border-border text-text-secondary"
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

          <!-- Honest brief: community evidence + the critic's bear case -->
          {#if solution.demand_quotes?.length}
            <div class="mt-4 border-t border-border pt-4">
              <div class="text-xs text-text-muted mb-2">
                What the community says
              </div>
              <div class="space-y-2">
                {#each solution.demand_quotes.slice(0, 3) as quote}
                  <blockquote
                    class="text-sm text-text-secondary italic border-l-2 border-border pl-3"
                  >
                    "{quote}"
                  </blockquote>
                {/each}
              </div>
            </div>
          {/if}
          {#if solution.critic_concern}
            <div class="mt-4 p-3 rounded border border-border">
              <div class="text-xs text-text-muted font-medium mb-1">
                Independent critic's take
              </div>
              <p class="text-sm text-text-secondary">
                {humanizeInternalJargon(solution.critic_concern)}
              </p>
            </div>
          {/if}
          {#if adversarial}
            <div
              class="mt-4 p-3 rounded border {adversarial.severity === 'weakened'
                ? 'border-warning/30 bg-warning/5'
                : 'border-error/30 bg-error/5'}"
            >
              <div
                class="text-xs font-medium mb-1 {adversarial.severity === 'weakened'
                  ? 'text-warning'
                  : 'text-error'}"
              >
                {adversarial.label}
              </div>
              {#each adversarial.details as detail}
                <p class="text-sm text-text-secondary">{detail}</p>
              {/each}
              {#if adversarial.severity === "weakened"}
                <p class="text-sm text-text-muted mt-1">
                  This candidate remains available — review these concerns before committing to it.
                </p>
              {:else}
                <p class="text-sm text-text-muted mt-1">{PREMISE_UNPROVEN_CODA}</p>
              {/if}
            </div>
          {/if}
          {#if directParity || noIncumbentFound}
            <div class="mt-4 p-3 rounded border border-border">
              <div class="text-xs text-text-muted font-medium mb-1">
                Incumbent check (web-verified)
              </div>
              <p class="text-sm text-text-secondary">
                {noIncumbentFound
                  ? "No incumbent found shipping this idea's core mechanism."
                  : directParity}
              </p>
            </div>
          {/if}
          {#if solution.adjacent_market_parity}
            <div class="mt-4 p-3 rounded border border-border">
              <div class="text-xs text-text-muted font-medium mb-1">
                Adjacent market check (audience-independent, web-verified)
              </div>
              <p class="text-sm text-text-secondary">
                {solution.adjacent_market_parity} — this product monetizes the same
                mechanism/data in its own market, so it shapes both the competition and where
                the money actually is.
              </p>
            </div>
          {/if}
          {#if solution.source_segment_payability_class}
            <div class="mt-4 p-3 rounded border border-border">
              <div class="text-xs text-text-muted font-medium mb-1">Who pays</div>
              <p class="text-sm text-text-secondary">
                {#if solution.source_segment_payability_class === "corporate-budget"}
                  Buyers with organizational budget authority — direct paid pricing is viable.
                {:else if solution.source_segment_payability_class === "smb-budget"}
                  Small-business operators paying from business revenue — price-aware but used to
                  paying for tools that earn their keep.
                {:else if solution.source_segment_payability_class === "prosumer-wallet"}
                  Prosumers paying out of pocket — expect low price ceilings and churn-prone
                  subscriptions; validate willingness-to-pay before committing.
                {:else if solution.source_segment_payability_class === "personal-wallet"}
                  Individuals spending personal money episodically — a historically
                  low-willingness-to-pay buyer; favor one-time pricing or free-tool distribution.
                {:else}
                  Mixed buyer types — pick the segment with budget authority and price for it.
                {/if}
              </p>
            </div>
          {/if}

          <!-- Pivot Trigger -->
          {#if solution.pivot_trigger}
            <div class="mt-4 p-3 rounded border border-border">
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
