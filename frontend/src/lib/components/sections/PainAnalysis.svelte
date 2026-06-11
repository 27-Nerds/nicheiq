<script lang="ts">
  import { fade } from "svelte/transition";
  import {
    MessageSquare,
    TrendingUp,
    ChevronDown,
    ChevronUp,
    AlertTriangle,
    DollarSign,
    ArrowRight,
    CheckCircle,
    Lock,
    Compass,
    Users,
    Flame,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
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
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";
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
    previewMode?: boolean;
    onUnlockClick?: () => void;
  }

  let { painPoints, analytics, solution, topPainPointsSummary, previewMode = false, onUnlockClick }: Props =
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

  const bestOppsColor = $derived.by(() => {
    const count = analytics.quadrant_distribution.high_severity_high_wtp;
    if (count === 0) return "error" as const;
    if (count <= 2) return "warning" as const;
    return "success" as const;
  });

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
  icon={SECTION_MAP['pain-analysis'].icon}
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
      <Flame class="w-4 h-4" />
      <span>Full Analysis</span>
    </button>
  </div>

  <!-- Analytics Overview (shown in both tabs) -->
  <div class="mb-8">
    <HeroStrip>
      {#snippet primary()}
        <HeroPrimary
          icon={AlertTriangle}
          label="Pain Points"
          sublabel={String(analytics.total_pain_points)}
          color="accent"
        />
      {/snippet}

      <HeroMetric
        value={analytics.high_severity_count ?? (analytics as any).high_priority_count ?? 0}
        label="High Severity"
        icon={Flame}
        color="error"
      />

      <HeroMetric
        value={analytics.quadrant_distribution.high_severity_high_wtp}
        label="Best Opportunities"
        color={bestOppsColor}
      />

      <HeroMetric
        value={analytics.quadrant_distribution.high_severity_low_wtp}
        label="High Sev / Low WTP"
        color="warning"
        icon={AlertTriangle}
      />
    </HeroStrip>
  </div>

  <!-- JOURNEY TAB -->
  {#if activeTab === "journey"}
    <div transition:fade={{ duration: 200 }}>
      <!-- Intro Narrative -->
      <div class="journey-intro">
        <div class="journey-intro-icon">
          <Compass class="w-5 h-5 text-accent" />
        </div>
        <p class="journey-intro-text">
          {#if previewMode}
            Through extensive research across social platforms, we identified
            key pain points that users experience daily. Run <strong>Deep Research</strong>
            to see how a solution directly addresses each challenge.
          {:else}
            Through extensive research across social platforms, we identified
            key pain points that users experience daily. Here's how <strong
              >{solution.solution_name || "Solution"}</strong
            >
            directly addresses these challenges.
          {/if}
        </p>
      </div>

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
                        >{painPoint.mention_count} {painPoint.mention_count === 1 ? 'mention' : 'mentions'}</span
                      >
                    {/if}
                  </div>
                {/if}

                {#if painPoint.affected_segments && painPoint.affected_segments.length > 0}
                  <div class="pain-segments">
                    <Users class="w-3 h-3 text-secondary shrink-0 mt-0.5" />
                    <div class="pain-segments__tags">
                      {#each painPoint.affected_segments.slice(0, 3) as segment}
                        <Badge variant="info" size="sm">{segment}</Badge>
                      {/each}
                    </div>
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
              <div class="solution-card-enhanced" class:solution-card-locked={previewMode}>
                <div class="solution-header">
                  {#if previewMode}
                    <Lock class="w-4 h-4 text-muted" />
                    <span class="solution-label solution-label-locked">How We Solve It</span>
                  {:else}
                    <CheckCircle class="w-4 h-4 text-success" />
                    <span class="solution-label">How We Solve It</span>
                  {/if}
                </div>
                {#if previewMode}
                  <div class="solution-skeleton">
                    <div class="solution-skeleton-line"></div>
                    <div class="solution-skeleton-line"></div>
                    <div class="solution-skeleton-line"></div>
                    <div class="solution-skeleton-line"></div>
                    <div class="solution-skeleton-line"></div>
                    <div class="solution-lock-chip">
                      <Lock class="w-2.5 h-2.5" />
                      <span>Deep Research</span>
                    </div>
                  </div>
                {:else if painPoint.solution_approach}
                  <p class="solution-text">{painPoint.solution_approach}</p>
                {:else if solution.core_features && solution.core_features[i]}
                  <p class="solution-text">{solution.core_features[i]}</p>
                {:else}
                  <p class="solution-text solution-generic">
                    {solution.value_proposition || solution.description}
                  </p>
                {/if}
              </div>
            </div>
          </AnimateOnScroll>
        {/each}
      </div>

      {#if previewMode && onUnlockClick}
        <div class="unlock-link-wrapper">
          <button class="unlock-link" onclick={onUnlockClick}>
            See how each problem maps to a solution — unlock Deep Research
          </button>
        </div>
      {/if}

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
          {#if !previewMode}
            <div class="stat-item">
              <span class="stat-value">{solution.core_features?.length || 0}</span
              >
              <span class="stat-label">Solution Features</span>
            </div>
          {/if}
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
        <AnimateOnScroll animation="fade-in" delay={100}>
          <div class="mb-8">
            <PainPointMatrix {painPoints} />
          </div>
        </AnimateOnScroll>
      {/if}

      <!-- Filters -->
      {#if painPoints.length > 0}
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
      {/if}

      <!-- Pain Points List -->
      <div class="pain-points-list">
        {#each filteredPainPoints as point, index}
          <AnimateOnScroll animation="fade-in" delay={index * 100}>
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
                  <div class="pain-segments__tags">
                    {#each point.affected_segments as segment}
                      <Badge variant="info" size="sm">{segment}</Badge>
                    {/each}
                  </div>
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
    gap: var(--space-2);
    padding: var(--space-1);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    width: fit-content;
  }

  .tab-button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0.625rem 1rem;
    background: transparent;
    border: none;
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    font-size: var(--text-base);
    font-weight: 500;
    cursor: pointer;
    transition: color 0.2s ease, background-color 0.2s ease;
  }

  .tab-button:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-hover);
  }

  .tab-button.tab-active {
    color: var(--color-accent);
    background: var(--color-accent-subtle);
  }

  /* Journey Tab Styles */
  .journey-intro {
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-xl);
    padding: var(--space-6);
    margin-bottom: var(--space-8);
  }

  .journey-intro-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
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
    gap: var(--space-6);
    margin-bottom: var(--space-8);
  }

  .flow-row {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: var(--space-4);
    align-items: center;
  }

  .pain-card-enhanced {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    transition: border-color 0.3s ease;
  }

  .pain-card-enhanced:hover {
    border-color: var(--color-border-emphasis);
  }

  .pain-card-severity-high {
    border-left: 3px solid var(--color-severity-critical);
    background: var(--color-bg-surface);
  }

  .pain-card-severity-medium {
    border-left: 3px solid var(--color-severity-medium);
    background: var(--color-bg-surface);
  }

  .pain-header-enhanced {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
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
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-severity-critical);
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }

  .pain-severity-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    margin-top: 0.125rem;
  }

  .pain-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: var(--space-2);
  }

  .pain-description {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin-bottom: var(--space-3);
  }

  .pain-platforms {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .mention-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
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
    background: var(--color-accent);
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
  }

  .solution-card-enhanced {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-success);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    transition: border-color 0.3s ease;
  }

  .solution-card-enhanced:hover {
    border-color: var(--color-border-emphasis);
  }

  .solution-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
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

  /* Locked solution card (preview mode) */
  .solution-card-locked {
    border-left-color: var(--color-border);
  }

  .solution-label-locked {
    color: var(--color-text-muted);
  }

  .solution-skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    position: relative;
  }

  .solution-skeleton-line {
    height: 0.875rem;
    border-radius: 4px;
    background: var(--color-bg-hover);
    filter: blur(3px);
  }

  .solution-skeleton-line:nth-child(1) { width: 90%; }
  .solution-skeleton-line:nth-child(2) { width: 75%; }
  .solution-skeleton-line:nth-child(3) { width: 55%; }
  .solution-skeleton-line:nth-child(4) { width: 85%; }
  .solution-skeleton-line:nth-child(5) { width: 40%; }

  .solution-lock-chip {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: 2px 10px;
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 2rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .unlock-link-wrapper {
    text-align: center;
    padding: var(--space-6) 0 var(--space-2);
  }

  .unlock-link {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--color-accent);
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    transition: background-color 0.15s ease;
  }

  .unlock-link:hover {
    background: rgba(234, 88, 12, 0.06);
  }

  .wtp-insight {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    margin-bottom: var(--space-8);
  }

  .wtp-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
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
    margin-bottom: var(--space-4);
  }

  .wtp-scores {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
  }

  .wtp-item {
    display: flex;
    flex-direction: column;
    background: var(--color-bg-elevated);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
  }

  .wtp-name {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .wtp-value {
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-success);
    font-variant-numeric: tabular-nums;
  }

  .journey-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: var(--space-4);
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    text-align: center;
  }

  .stat-value {
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-accent);
    font-variant-numeric: tabular-nums;
  }

  .stat-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    margin-top: var(--space-1);
  }

  /* Analysis Tab Styles */
  .filters-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-6);
    padding: var(--space-4) var(--space-5);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .pain-points-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .pain-point-card-enhanced {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    transition: border-color 0.3s ease;
  }

  .pain-point-card-enhanced:hover {
    border-color: var(--color-border-hover);
  }

  .pain-point-card-enhanced.opportunity-high {
    border-left: 3px solid var(--color-opportunity);
    background: var(--color-bg-surface);
  }

  .pain-point-card-enhanced.opportunity-medium {
    border-left: 3px solid var(--color-severity-medium);
    background: var(--color-bg-surface);
  }

  .pain-point-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-4);
    margin-bottom: var(--space-4);
  }

  .pain-point-rank {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
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
    margin-bottom: var(--space-2);
  }

  .pain-point-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .opportunity-badge {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.25rem 0.625rem;
    border-radius: var(--radius-full);
  }

  .opportunity-badge-high {
    background: var(--color-opportunity-bg);
    color: var(--color-opportunity);
    border: 1px solid var(--color-border-success);
  }

  .opportunity-badge-medium {
    background: var(--color-severity-medium-bg);
    color: var(--color-severity-medium);
    border: 1px solid var(--color-border-warning);
  }

  .opportunity-badge-low {
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
  }

  .pain-point-scores {
    display: flex;
    gap: var(--space-4);
    flex-shrink: 0;
  }

  .score-ring-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
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
    margin-bottom: var(--space-4);
  }

  .pain-point-categories {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .pain-segments {
    display: flex;
    align-items: flex-start;
    gap: 0.375rem;
    margin-top: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .pain-segments__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .category-tag {
    font-size: 0.6875rem;
    padding: 0.25rem 0.625rem;
    border-radius: var(--radius-sm);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .quotes-section {
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-4);
    margin-top: var(--space-2);
  }

  .quotes-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    background: none;
    border: none;
    padding: 0.5rem 0;
    color: var(--color-text-muted);
    font-size: var(--text-base);
    cursor: pointer;
    transition: color 0.2s ease;
  }

  .quotes-toggle:hover {
    color: var(--color-accent);
  }

  .quotes-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-top: var(--space-4);
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
    gap: var(--space-2);
    margin-top: var(--space-3);
  }

  .source-label {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .source-id {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-elevated);
    border-radius: var(--radius-sm);
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
      background: var(--color-accent);
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
