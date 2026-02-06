<script lang="ts">
  import { fade } from "svelte/transition";
  import {
    Target,
    MessageSquare,
    TrendingUp,
    ChevronDown,
    ChevronUp,
    AlertTriangle,
    DollarSign,
    ArrowRight,
    CheckCircle,
    Sparkles,
    Users,
  } from "lucide-svelte";
  import type {
    DetailedPainPoint,
    PainPointAnalytics,
    SolutionDetails,
  } from "$lib/types/report";
  import {
    formatScorePercent,
    getOpportunityClass,
    getScoreClass,
    getScoreBarClass,
  } from "$lib/utils/format";
  import {
    getOpportunityVariant,
    getPlatformVariant,
  } from "$lib/utils/variantHelpers";
  import Badge from "$lib/components/ui/Badge.svelte";
  import MetricCard from "$lib/components/ui/MetricCard.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import PainPointMatrix from "$lib/components/charts/PainPointMatrix.svelte";
  import FilterGroup from "$lib/components/ui/FilterGroup.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import QuoteBlock from "$lib/components/ui/QuoteBlock.svelte";
  import MetaItem from "$lib/components/ui/MetaItem.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";

  interface Props {
    painPoints: DetailedPainPoint[];
    analytics: PainPointAnalytics;
    solution: SolutionDetails;
    topPainPointsSummary?: string[];
  }

  let { painPoints, analytics, solution, topPainPointsSummary }: Props =
    $props();

  // Tab state
  let activeTab: "journey" | "analysis" = $state("journey");

  // Expanded quotes state for analysis tab
  let expandedQuotes: Record<number, boolean> = $state({});

  // Filter state for analysis tab
  let selectedOpportunity = $state("");
  let selectedPlatform = $state("");

  // Get top 5 pain points for journey view
  const topPainPoints = $derived(
    [...painPoints]
      .sort((a, b) => b.severity_score - a.severity_score)
      .slice(0, 5),
  );

  const avgWtp = $derived(
    topPainPoints.length > 0
      ? topPainPoints.reduce((sum, p) => sum + p.willingness_to_pay, 0) /
          topPainPoints.length
      : 0,
  );

  function toggleQuotes(index: number) {
    expandedQuotes[index] = !expandedQuotes[index];
  }

  // Filter options for analysis tab
  const opportunityOptions = $derived([
    {
      value: "high",
      label: "High",
      count: painPoints.filter((p) => p.opportunity_level === "high").length,
    },
    {
      value: "medium",
      label: "Medium",
      count: painPoints.filter((p) => p.opportunity_level === "medium").length,
    },
    {
      value: "low",
      label: "Low",
      count: painPoints.filter((p) => p.opportunity_level === "low").length,
    },
  ]);

  const platforms = $derived([
    ...new Set(painPoints.flatMap((p) => p.source_platforms || [])),
  ]);
  const platformOptions = $derived(
    platforms.map((p) => ({ value: p, label: p })),
  );

  // Filtered pain points for analysis tab
  const filteredPainPoints = $derived(
    painPoints.filter((p) => {
      if (selectedOpportunity && p.opportunity_level !== selectedOpportunity)
        return false;
      if (selectedPlatform && !p.source_platforms?.includes(selectedPlatform))
        return false;
      return true;
    }),
  );
</script>

<Section
  id="pain-analysis"
  class="report-section"
  icon={Target}
  title="Pain Point Analysis"
  subtitle="User frustrations and monetization signals"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Tab Navigation -->
  <div class="tab-navigation mb-6" role="tablist">
    <button
      class="tab-button {activeTab === 'journey' ? 'tab-active' : ''}"
      onclick={() => (activeTab = "journey")}
      onkeydown={(e) => e.key === "Enter" && (activeTab = "journey")}
      role="tab"
      aria-selected={activeTab === "journey"}
      tabindex={activeTab === "journey" ? 0 : -1}
    >
      <TrendingUp class="w-4 h-4" />
      <span>Journey View</span>
    </button>
    <button
      class="tab-button {activeTab === 'analysis' ? 'tab-active' : ''}"
      onclick={() => (activeTab = "analysis")}
      onkeydown={(e) => e.key === "Enter" && (activeTab = "analysis")}
      role="tab"
      aria-selected={activeTab === "analysis"}
      tabindex={activeTab === "analysis" ? 0 : -1}
    >
      <Target class="w-4 h-4" />
      <span>Full Analysis</span>
    </button>
  </div>

  <!-- Analytics Overview (shown in both tabs) -->
  <AnimateOnScroll animation="fade-up">
    <div class="analytics-grid mb-8">
      <div class="analytics-card analytics-card-featured">
        <div class="analytics-value text-accent">
          {analytics.total_pain_points}
        </div>
        <div class="analytics-label">Total Pain Points</div>
      </div>
      <div class="analytics-card">
        <div class="analytics-value text-accent">
          {analytics.high_severity_count ??
            (analytics as any).high_priority_count ??
            0}
        </div>
        <div class="analytics-label">High Severity</div>
      </div>
      <div
        class="analytics-card {analytics.quadrant_distribution
          .high_severity_high_wtp === 0
          ? 'analytics-card-error'
          : analytics.quadrant_distribution.high_severity_high_wtp <= 2
            ? 'analytics-card-warning'
            : 'analytics-card-highlight'}"
      >
        <div
          class="analytics-value {analytics.quadrant_distribution
            .high_severity_high_wtp === 0
            ? 'text-error'
            : analytics.quadrant_distribution.high_severity_high_wtp <= 2
              ? 'text-warning'
              : 'text-success'}"
        >
          {analytics.quadrant_distribution.high_severity_high_wtp}
        </div>
        <div class="analytics-label inline-flex items-center gap-1">
          High Sev + High WTP <Tooltip
            content={getTermTooltip("WTP")}
            position="top"
          />
        </div>
        <div
          class="analytics-sublabel {analytics.quadrant_distribution
            .high_severity_high_wtp === 0
            ? 'sublabel-error'
            : analytics.quadrant_distribution.high_severity_high_wtp <= 2
              ? 'sublabel-warning'
              : ''}"
        >
          Best Opportunities
        </div>
      </div>
      <div class="analytics-card">
        <div class="analytics-value text-warning">
          {analytics.quadrant_distribution.high_severity_low_wtp}
        </div>
        <div class="analytics-label inline-flex items-center gap-1">
          High Sev + Low WTP <Tooltip
            content={getTermTooltip("WTP")}
            position="top"
          />
        </div>
      </div>
    </div>
  </AnimateOnScroll>

  <!-- JOURNEY TAB -->
  {#if activeTab === "journey"}
    <div transition:fade={{ duration: 200 }}>
      <!-- Intro Narrative -->
      <AnimateOnScroll animation="fade-up">
        <div class="journey-intro">
          <div class="journey-intro-icon">
            <Sparkles class="w-5 h-5 text-accent" />
          </div>
          <p class="journey-intro-text">
            Through extensive research across social platforms, we identified
            key pain points that users experience daily. Here's how <strong
              >{solution.solution_name || "Solution"}</strong
            >
            directly addresses these challenges.
          </p>
        </div>
      </AnimateOnScroll>

      <!-- Pain Points Flow -->
      <div class="pain-solution-flow">
        {#each topPainPoints as painPoint, i}
          <AnimateOnScroll animation="fade-up" delay={i * 100}>
            <div class="flow-row">
              <!-- Pain Point Card -->
              <div
                class="pain-card-enhanced {painPoint.severity_score >= 0.7
                  ? 'pain-card-severity-high'
                  : painPoint.severity_score >= 0.5
                    ? 'pain-card-severity-medium'
                    : ''}"
              >
                <div class="pain-header-enhanced">
                  <div class="pain-severity-ring">
                    <ProgressRing
                      value={painPoint.severity_score}
                      size={48}
                      strokeWidth={4}
                      color="error"
                      showValue={false}
                    />
                    <AlertTriangle class="w-4 h-4 absolute text-error" />
                  </div>
                  <div class="pain-meta">
                    <span class="pain-severity-value"
                      >{formatScorePercent(painPoint.severity_score)}</span
                    >
                    <span class="pain-severity-label">Severity</span>
                  </div>
                </div>
                <h4 class="pain-title">{painPoint.title}</h4>
                <p class="pain-description">{painPoint.description}</p>

                {#if painPoint.representative_quotes && painPoint.representative_quotes.length > 0}
                  <QuoteBlock
                    text={painPoint.representative_quotes[0]}
                    variant="card"
                    class="mb-4"
                  />
                {/if}

                {#if painPoint.source_platforms && painPoint.source_platforms.length > 0}
                  <div class="pain-platforms">
                    {#each painPoint.source_platforms.slice(0, 2) as platform}
                      <Badge variant={getPlatformVariant(platform)} size="sm"
                        >{platform}</Badge
                      >
                    {/each}
                    {#if painPoint.mention_count > 0}
                      <span class="mention-count"
                        >{painPoint.mention_count} mentions</span
                      >
                    {/if}
                  </div>
                {/if}

                {#if painPoint.affected_segments && painPoint.affected_segments.length > 0}
                  <div class="pain-segments">
                    <Users class="w-3 h-3 text-secondary shrink-0" />
                    {#each painPoint.affected_segments.slice(0, 3) as segment}
                      <Badge variant="info" size="sm">{segment}</Badge>
                    {/each}
                  </div>
                {/if}
              </div>

              <!-- Flow Connector -->
              <div class="flow-connector-wrapper">
                <div class="flow-line"></div>
                <div class="flow-arrow-circle">
                  <ArrowRight class="w-5 h-5 text-accent" />
                </div>
                <div class="flow-line"></div>
              </div>

              <!-- Solution Card -->
              <div class="solution-card-enhanced">
                <div class="solution-header">
                  <CheckCircle class="w-4 h-4 text-success" />
                  <span class="solution-label">How We Solve It</span>
                </div>
                {#if painPoint.solution_approach}
                  <!-- New: LLM-generated specific mapping -->
                  <p class="solution-text">{painPoint.solution_approach}</p>
                {:else if solution.core_features && solution.core_features[i]}
                  <!-- Fallback: Old index-based mapping for legacy reports -->
                  <p class="solution-text">{solution.core_features[i]}</p>
                {:else if solution.core_features && solution.core_features[i]}
                  <p class="solution-text">{solution.core_features[i]}</p>
                {:else}
                  <!-- Final fallback: Generic value proposition -->
                  <p class="solution-text solution-generic">
                    {solution.value_proposition || solution.description}
                  </p>
                {/if}
              </div>
            </div>
          </AnimateOnScroll>
        {/each}
      </div>

      <!-- Willingness to Pay Insight -->
      {#if topPainPoints.some((p) => p.willingness_to_pay > 0.5)}
        <AnimateOnScroll animation="fade-up" delay={600}>
          <div class="wtp-insight">
            <div class="wtp-header">
              <TrendingUp class="w-5 h-5 text-success" />
              <h4>Monetization Signal</h4>
            </div>
            <p class="wtp-text">
              {topPainPoints.filter((p) => p.willingness_to_pay > 0.5).length} of
              {topPainPoints.length} top pain points show high willingness-to-pay
              indicators, suggesting strong market demand for a paid solution.
            </p>
            <div class="wtp-scores">
              {#each topPainPoints
                .filter((p) => p.willingness_to_pay > 0.5)
                .slice(0, 3) as point}
                <div class="wtp-item">
                  <span class="wtp-name"
                    >{point.title.slice(0, 30)}{point.title.length > 30
                      ? "..."
                      : ""}</span
                  >
                  <span class="wtp-value"
                    >{formatScorePercent(point.willingness_to_pay)} WTP</span
                  >
                </div>
              {/each}
            </div>
          </div>
        </AnimateOnScroll>
      {/if}

      <!-- Summary Stats -->
      <AnimateOnScroll animation="fade-up" delay={700}>
        <div class="journey-stats">
          <div class="stat-item">
            <span class="stat-value">{painPoints.length}</span>
            <span class="stat-label">Pain Points Identified</span>
          </div>
          <div class="stat-item">
            <span class="stat-value"
              >{painPoints.filter((p) => p.severity_score >= 0.7).length}</span
            >
            <span class="stat-label">High Severity Issues</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{solution.core_features?.length || 0}</span
            >
            <span class="stat-label">Solution Features</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">
              {formatScorePercent(avgWtp)}
            </span>
            <span class="stat-label inline-flex items-center gap-1">
              Avg. WTP Score <Tooltip
                content={getTermTooltip("WTP")}
                position="top"
              />
            </span>
          </div>
        </div>
      </AnimateOnScroll>
    </div>
  {/if}

  <!-- ANALYSIS TAB -->
  {#if activeTab === "analysis"}
    <div transition:fade={{ duration: 200 }}>
      <!-- Pain Point Matrix Chart -->
      {#if painPoints.length > 0}
        <AnimateOnScroll animation="fade-up" delay={100}>
          <div class="mb-8">
            <PainPointMatrix {painPoints} />
          </div>
        </AnimateOnScroll>
      {/if}

      <!-- Filters -->
      {#if painPoints.length > 0}
        <AnimateOnScroll animation="fade-up" delay={150}>
          <div class="filters-row mb-6">
            <FilterGroup
              label="Opportunity"
              options={opportunityOptions}
              bind:selected={selectedOpportunity}
              showCounts={true}
            />
            {#if platformOptions.length > 0}
              <FilterGroup
                label="Platform"
                options={platformOptions}
                bind:selected={selectedPlatform}
              />
            {/if}
          </div>
        </AnimateOnScroll>
      {/if}

      <!-- Pain Points List -->
      <div class="pain-points-list">
        {#each filteredPainPoints as point, index}
          <AnimateOnScroll animation="fade-up" delay={index * 100}>
            <div
              class="pain-point-card-enhanced {point.opportunity_level ===
              'high'
                ? 'opportunity-high'
                : point.opportunity_level === 'medium'
                  ? 'opportunity-medium'
                  : ''}"
            >
              <!-- Header -->
              <div class="pain-point-header">
                <div class="pain-point-rank">#{index + 1}</div>
                <div class="pain-point-info">
                  <h3 class="pain-point-title">{point.title}</h3>
                  <div class="pain-point-badges">
                    <span
                      class="opportunity-badge opportunity-badge-{point.opportunity_level}"
                    >
                      {point.opportunity_level} opportunity
                    </span>
                    {#if point.source_platforms && point.source_platforms.length > 0}
                      {#each point.source_platforms.slice(0, 2) as platform}
                        <Badge variant="muted" size="sm">{platform}</Badge>
                      {/each}
                    {/if}
                  </div>
                </div>
                <!-- Score Rings -->
                <div class="pain-point-scores">
                  <div class="score-ring-item">
                    <ProgressRing
                      value={point.severity_score}
                      size={56}
                      strokeWidth={4}
                      color="auto"
                      showValue={true}
                      animate={true}
                    />
                    <span class="score-ring-label">Severity</span>
                  </div>
                  <div class="score-ring-item">
                    <ProgressRing
                      value={point.willingness_to_pay}
                      size={56}
                      strokeWidth={4}
                      color="auto"
                      showValue={true}
                      animate={true}
                    />
                    <span class="score-ring-label">WTP</span>
                  </div>
                </div>
              </div>

              <p class="pain-point-description">{point.description}</p>

              <!-- Metrics Row -->
              <div class="insight-card__meta">
                <MetaItem
                  icon={AlertTriangle}
                  value={formatScorePercent(point.severity_score)}
                  label="Severity"
                  iconClass="w-4 h-4 text-error"
                />
                <MetaItem
                  icon={DollarSign}
                  value={formatScorePercent(point.willingness_to_pay)}
                  label="WTP"
                  iconClass="w-4 h-4 text-success"
                />
                <MetaItem
                  icon={MessageSquare}
                  value={point.mention_count}
                  label="Mentions"
                  iconClass="w-4 h-4 text-accent"
                />
              </div>

              <!-- Categories -->
              {#if point.categories && point.categories.length > 0}
                <div class="pain-point-categories">
                  {#each point.categories as category}
                    <span class="category-tag">{category}</span>
                  {/each}
                </div>
              {/if}

              <!-- Affected Segments -->
              {#if point.affected_segments && point.affected_segments.length > 0}
                <div class="pain-segments">
                  <Users class="w-3.5 h-3.5 text-secondary shrink-0 mt-0.5" />
                  {#each point.affected_segments as segment}
                    <Badge variant="info" size="sm">{segment}</Badge>
                  {/each}
                </div>
              {/if}

              <!-- Representative Quotes -->
              {#if point.representative_quotes && point.representative_quotes.length > 0}
                <div class="quotes-section">
                  <button
                    class="quotes-toggle"
                    onclick={() => toggleQuotes(index)}
                  >
                    <MessageSquare class="w-4 h-4" />
                    <span
                      >{expandedQuotes[index] ? "Hide" : "Show"}
                      {point.representative_quotes.length} quotes</span
                    >
                    {#if expandedQuotes[index]}
                      <ChevronUp class="w-4 h-4" />
                    {:else}
                      <ChevronDown class="w-4 h-4" />
                    {/if}
                  </button>

                  {#if expandedQuotes[index]}
                    <div class="quotes-list">
                      {#each point.representative_quotes as quote, qi}
                        <QuoteBlock
                          text={quote}
                          variant="enhanced"
                          class="quote-animated"
                          style="animation-delay: {qi * 50}ms"
                        />
                      {/each}
                    </div>
                  {/if}
                </div>
              {/if}

              <!-- Source Post IDs (deduplicated, empty strings filtered) -->
              {#if point.source_post_ids?.length}
                {@const uniqueSourceIds = [
                  ...new Set(point.source_post_ids.filter((id) => id)),
                ]}
                {#if uniqueSourceIds.length > 0}
                  <div class="source-ids">
                    <span class="source-label">Sources:</span>
                    {#each uniqueSourceIds.slice(0, 5) as postId}
                      <span class="source-id">{postId}</span>
                    {/each}
                    {#if uniqueSourceIds.length > 5}
                      <span class="source-more"
                        >+{uniqueSourceIds.length - 5} more</span
                      >
                    {/if}
                  </div>
                {/if}
              {/if}
            </div>
          </AnimateOnScroll>
        {/each}
      </div>
    </div>
  {/if}
</Section>

<style>
  /* Tab Navigation */
  .tab-navigation {
    display: flex;
    gap: 0.5rem;
    padding: 0.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    width: fit-content;
  }

  .tab-button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.625rem 1rem;
    background: transparent;
    border: none;
    border-radius: 0.5rem;
    color: var(--color-text-muted);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .tab-button:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-hover);
  }

  .tab-button.tab-active {
    color: var(--color-accent);
    background: rgba(229, 90, 40, 0.1);
  }

  /* Analytics Grid */
  .analytics-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
  }

  @media (min-width: 768px) {
    .analytics-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .analytics-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.25rem;
    text-align: center;
    transition: all 0.3s ease;
  }

  .analytics-card:hover {
    border-color: var(--color-border-hover);
    transform: translateY(-2px);
  }

  .analytics-card-featured {
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.08) 0%,
      transparent 60%
    );
    border-color: rgba(229, 90, 40, 0.3);
  }

  .analytics-card-highlight {
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.08) 0%,
      transparent 60%
    );
    border-color: rgba(229, 90, 40, 0.3);
  }

  .analytics-card-error {
    background: linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.08) 0%,
      transparent 60%
    );
    border-color: rgba(239, 68, 68, 0.3);
  }

  .analytics-card-warning {
    background: linear-gradient(
      135deg,
      rgba(245, 158, 11, 0.08) 0%,
      transparent 60%
    );
    border-color: rgba(245, 158, 11, 0.3);
  }

  .analytics-value {
    font-family: var(--font-display);
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 0.25rem;
  }

  .analytics-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }

  .analytics-sublabel {
    font-size: 0.6875rem;
    color: var(--color-success);
    margin-top: 0.25rem;
  }

  .analytics-sublabel.sublabel-error {
    color: var(--color-error);
  }

  .analytics-sublabel.sublabel-warning {
    color: var(--color-warning);
  }

  /* Journey Tab Styles */
  .journey-intro {
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.08) 0%,
      transparent 60%
    );
    border: 1px solid rgba(229, 90, 40, 0.2);
    border-radius: 1rem;
    padding: 1.5rem;
    margin-bottom: 2rem;
  }

  .journey-intro-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: rgba(229, 90, 40, 0.1);
    border: 1px solid rgba(229, 90, 40, 0.3);
    border-radius: 0.5rem;
    margin-bottom: 1rem;
  }

  .journey-intro-text {
    font-size: 1.0625rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
  }

  .journey-intro-text strong {
    color: var(--color-accent);
  }

  .pain-solution-flow {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }

  .flow-row {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 1rem;
    align-items: center;
  }

  .pain-card-enhanced {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.25rem;
    transition: all 0.3s ease;
  }

  .pain-card-enhanced:hover {
    border-color: rgba(239, 68, 68, 0.3);
    box-shadow: 0 4px 20px rgba(239, 68, 68, 0.1);
  }

  .pain-card-severity-high {
    border-left: 3px solid var(--color-error);
    background: linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.05) 0%,
      transparent 50%
    );
  }

  .pain-card-severity-medium {
    border-left: 3px solid var(--color-warning);
    background: linear-gradient(
      135deg,
      rgba(245, 158, 11, 0.05) 0%,
      transparent 50%
    );
  }

  .pain-header-enhanced {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .pain-severity-ring {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .pain-meta {
    display: flex;
    flex-direction: column;
  }

  .pain-severity-value {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-error);
    line-height: 1;
  }

  .pain-severity-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    margin-top: 0.125rem;
  }

  .pain-title {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.5rem;
  }

  .pain-description {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin-bottom: 0.75rem;
  }

  .pain-platforms {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .mention-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .flow-connector-wrapper {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 0 0.5rem;
  }

  .flow-line {
    flex: 1;
    height: 2px;
    background: linear-gradient(
      90deg,
      var(--color-border),
      var(--color-accent)
    );
  }

  .flow-arrow-circle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: var(--color-bg-elevated);
    border: 2px solid var(--color-accent);
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 12px rgba(229, 90, 40, 0.3);
  }

  .solution-card-enhanced {
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.08) 0%,
      transparent 60%
    );
    border: 1px solid rgba(229, 90, 40, 0.2);
    border-left: 3px solid var(--color-success);
    border-radius: 0.75rem;
    padding: 1.25rem;
    transition: all 0.3s ease;
  }

  .solution-card-enhanced:hover {
    border-color: rgba(229, 90, 40, 0.4);
    box-shadow: 0 4px 20px rgba(229, 90, 40, 0.1);
  }

  .solution-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .solution-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-success);
    font-weight: 600;
  }

  .solution-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
  }

  .solution-generic {
    font-style: italic;
    color: var(--color-text-muted);
  }

  .wtp-insight {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-success);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 2rem;
  }

  .wtp-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .wtp-header h4 {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .wtp-text {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin-bottom: 1rem;
  }

  .wtp-scores {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .wtp-item {
    display: flex;
    flex-direction: column;
    background: var(--color-bg-elevated);
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
  }

  .wtp-name {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .wtp-value {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-success);
  }

  .journey-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.25rem;
    text-align: center;
  }

  .stat-value {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-accent);
  }

  .stat-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    margin-top: 0.25rem;
  }

  /* Analysis Tab Styles */
  .filters-row {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5rem;
    padding: 1rem 1.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
  }

  .pain-points-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .pain-point-card-enhanced {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    transition: all 0.3s ease;
  }

  .pain-point-card-enhanced:hover {
    border-color: var(--color-border-hover);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  }

  .pain-point-card-enhanced.opportunity-high {
    border-left: 3px solid var(--color-success);
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.03) 0%,
      transparent 30%
    );
  }

  .pain-point-card-enhanced.opportunity-medium {
    border-left: 3px solid var(--color-warning);
    background: linear-gradient(
      135deg,
      rgba(245, 158, 11, 0.03) 0%,
      transparent 30%
    );
  }

  .pain-point-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .pain-point-rank {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 700;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .pain-point-info {
    flex: 1;
    min-width: 0;
  }

  .pain-point-title {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.5rem;
  }

  .pain-point-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .opportunity-badge {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.25rem 0.625rem;
    border-radius: 9999px;
  }

  .opportunity-badge-high {
    background: rgba(229, 90, 40, 0.15);
    color: var(--color-success);
    border: 1px solid rgba(229, 90, 40, 0.3);
  }

  .opportunity-badge-medium {
    background: rgba(245, 158, 11, 0.15);
    color: var(--color-warning);
    border: 1px solid rgba(245, 158, 11, 0.3);
  }

  .opportunity-badge-low {
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
  }

  .pain-point-scores {
    display: flex;
    gap: 1rem;
    flex-shrink: 0;
  }

  .score-ring-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .score-ring-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }

  .pain-point-description {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
    margin-bottom: 1rem;
  }

  .pain-point-categories {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .pain-segments {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.375rem;
    margin-bottom: 0.75rem;
  }

  .category-tag {
    font-size: 0.6875rem;
    padding: 0.25rem 0.625rem;
    border-radius: 0.25rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .quotes-section {
    border-top: 1px solid var(--color-border);
    padding-top: 1rem;
    margin-top: 0.5rem;
  }

  .quotes-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: none;
    border: none;
    padding: 0.5rem 0;
    color: var(--color-text-muted);
    font-size: 0.875rem;
    cursor: pointer;
    transition: color 0.2s ease;
  }

  .quotes-toggle:hover {
    color: var(--color-accent);
  }

  .quotes-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  /* Quote animation support */
  :global(.quote-animated) {
    opacity: 0;
    animation: fadeInUp 0.3s ease forwards;
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .source-ids {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }

  .source-label {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .source-id {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-elevated);
    border-radius: 0.25rem;
    color: var(--color-text-muted);
  }

  .source-more {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Mobile Responsiveness */
  @media (max-width: 768px) {
    .flow-row {
      grid-template-columns: 1fr;
      gap: 0.75rem;
    }

    .flow-connector-wrapper {
      flex-direction: column;
      padding: 0.5rem 0;
    }

    .flow-line {
      width: 2px;
      height: 1.5rem;
      background: linear-gradient(
        180deg,
        var(--color-border),
        var(--color-accent)
      );
    }

    .pain-point-header {
      flex-direction: column;
    }

    .pain-point-scores {
      width: 100%;
      justify-content: flex-start;
      margin-top: 0.5rem;
    }
  }
</style>
