<script lang="ts">
  import {
    TrendingUp,
    TrendingDown,
    Minus,
    Clock,
    AlertTriangle,
    Calendar,
    ChevronRight,
    BarChart3,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { TrendLongevity } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";
  import StatPill from "$lib/components/ui/StatPill.svelte";
  import IconListItem from "$lib/components/ui/IconListItem.svelte";

  interface Props {
    data: TrendLongevity;
  }

  let { data }: Props = $props();

  // Determine trend icon and color
  const trendConfig = $derived.by(() => {
    const direction = data.trend_direction?.toLowerCase() || "";
    if (direction.includes("grow")) {
      return {
        icon: TrendingUp,
        color: "var(--color-success)",
        label: "Growing",
      };
    } else if (direction.includes("declin")) {
      return {
        icon: TrendingDown,
        color: "var(--color-error)",
        label: "Declining",
      };
    }
    return { icon: Minus, color: "var(--color-warning)", label: "Stable" };
  });

  // Determine verdict badge variant
  const verdictConfig = $derived.by(() => {
    const verdict = data.longevity_verdict?.toLowerCase() || "";
    if (verdict.includes("sustain"))
      return {
        variant: "success" as const,
        color: "var(--color-success)",
        label: "SUSTAINABLE",
      };
    if (verdict.includes("risky") || verdict.includes("fad"))
      return {
        variant: "error" as const,
        color: "var(--color-error)",
        label: "RISKY",
      };
    return {
      variant: "warning" as const,
      color: "var(--color-warning)",
      label: "MODERATE",
    };
  });

  // Momentum score percentage
  const momentumPercent = $derived(
    data.momentum_score !== undefined
      ? Math.round(data.momentum_score * 100)
      : null,
  );

  // HeroMetric color deriveds
  const trendMetricColor = $derived.by(() => {
    const d = data.trend_direction?.toLowerCase() || "";
    if (d.includes("grow")) return "success" as const;
    if (d.includes("declin")) return "error" as const;
    return "warning" as const;
  });

  const confidenceColor = $derived.by(() => {
    if (data.trend_confidence === "High") return "success" as const;
    if (data.trend_confidence === "Medium") return "warning" as const;
    return "error" as const;
  });

  const verdictColor = $derived.by(() => {
    const v = data.longevity_verdict?.toLowerCase() || "";
    if (v.includes("sustain")) return "success" as const;
    if (v.includes("risky") || v.includes("fad")) return "error" as const;
    return "warning" as const;
  });
</script>

<Section
  id="trends"
  class="report-section"
  icon={SECTION_MAP['trends'].icon}
  title="Market Trends & Longevity"
  subtitle="Trend analysis and market timing"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Hero Strip -->
  <HeroStrip>
    {#snippet primary()}
      {#if momentumPercent !== null}
        <HeroPrimary
          value={momentumPercent / 100}
          label="Momentum"
          sublabel={momentumPercent >= 70
            ? "Strong"
            : momentumPercent >= 40
              ? "Moderate"
              : "Weak"}
          color={momentumPercent >= 70
            ? "success"
            : momentumPercent >= 40
              ? "warning"
              : "error"}
        />
      {/if}
    {/snippet}

    {#if data.trend_direction}
      <HeroMetric value={data.trend_direction} label="Direction" icon={trendConfig.icon} color={trendMetricColor} />
    {/if}
    {#if data.trend_confidence}
      <HeroMetric value={data.trend_confidence} label="Confidence" color={confidenceColor} />
    {/if}
    {#if data.longevity_verdict}
      <HeroMetric value={data.longevity_verdict} label="Longevity" color={verdictColor} />
    {/if}
    {#if data.timing_recommendation}
      <HeroMetric value={data.timing_recommendation} label="Timing" icon={Clock} color="accent" />
    {/if}
  </HeroStrip>

  <!-- Stats Strip -->
  <div class="stats-strip">
    {#if data.keyword_volume_trend}
      <StatPill label="Keyword Volume" value={data.keyword_volume_trend} />
    {/if}
    {#if data.discussion_frequency_trend}
      <StatPill label="Discussions" value={data.discussion_frequency_trend} />
    {/if}
    {#if data.new_entrants_trend}
      <StatPill label="New Entrants" value={data.new_entrants_trend} />
    {/if}
    {#if data.market_maturity}
      <StatPill label="Maturity" value={data.market_maturity} />
    {/if}
    {#if data.discussion_recency}
      <StatPill label="Discussion Recency" value={data.discussion_recency} />
    {/if}
    {#if data.competitive_activity_level}
      <StatPill label="Competition" value={data.competitive_activity_level} />
    {/if}
    {#if data.volume_growth_rate}
      <StatPill label="Volume Growth" value={data.volume_growth_rate} />
    {/if}
    {#if data.trend_duration}
      <StatPill label="Trend Duration" value={data.trend_duration} />
    {/if}
  </div>

  <!-- Seasonality Card (Always Visible if present) -->
  {#if data.seasonal_pattern || data.peak_periods}
    <div class="seasonality-card">
      <div class="seasonality-header">
        <Calendar class="seasonality-icon" />
        <span class="seasonality-title">Seasonality</span>
      </div>
      {#if data.seasonal_pattern}
        <p class="seasonality-text">{data.seasonal_pattern}</p>
      {/if}
      {#if data.peak_periods}
        <div class="peak-periods">
          <span class="periods-label">Peak Periods:</span>
          <Badge variant="muted" size="sm">{data.peak_periods}</Badge>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Expandable: Longevity Analysis -->
  {#if data.longevity_rationale}
    <ExpandableSection title="Longevity Analysis" icon={BarChart3}>
      <div class="analysis-content">
        {@html renderMarkdown(data.longevity_rationale)}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Growth Indicators -->
  {#if data.community_growth_indicators && data.community_growth_indicators.length > 0}
    <ExpandableSection
      title="Growth Indicators"
      icon={TrendingUp}
      count={data.community_growth_indicators.length}
      variant="success"
    >
      <div class="item-list">
        {#each data.community_growth_indicators as indicator}
          <IconListItem icon={ChevronRight} iconVariant="success"
            >{indicator}</IconListItem
          >
        {/each}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Risk Factors -->
  {#if data.trend_reversal_risks && data.trend_reversal_risks.length > 0}
    <ExpandableSection
      title="Risk Factors"
      icon={AlertTriangle}
      count={data.trend_reversal_risks.length}
      variant="error"
    >
      <div class="item-list">
        {#each data.trend_reversal_risks as risk}
          <IconListItem icon={AlertTriangle} iconVariant="error"
            >{risk}</IconListItem
          >
        {/each}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Metadata Footer -->
  {#if data.data_sources_analyzed || data.analysis_timeframe}
    <div class="metadata-footer">
      {#if data.data_sources_analyzed}
        <span class="metadata-item">
          <span class="metadata-label">Sources:</span>
          {data.data_sources_analyzed}
        </span>
      {/if}
      {#if data.analysis_timeframe}
        <span class="metadata-item">
          <span class="metadata-label">Timeframe:</span>
          {data.analysis_timeframe}
        </span>
      {/if}
    </div>
  {/if}
</Section>

<style>
  /* Stats Strip */
  .stats-strip {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-6);
    margin-bottom: var(--space-4);
  }

  /* Seasonality Card */
  .seasonality-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-4);
  }

  .seasonality-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .seasonality-header :global(.seasonality-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent-dark);
  }

  .seasonality-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .seasonality-text {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0 0 var(--space-3);
  }

  .peak-periods {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .periods-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  /* Analysis Content */
  .analysis-content {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.7;
  }

  .analysis-content :global(p) {
    margin: 0 0 var(--space-3);
  }

  .analysis-content :global(p:last-child) {
    margin-bottom: 0;
  }

  /* Item List - using IconListItem component */
  .item-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  /* Metadata Footer */
  .metadata-footer {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .metadata-item {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .metadata-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-right: var(--space-1);
  }

  /* Responsive */
  @media (max-width: 480px) {
    .stats-strip {
      flex-direction: column;
    }
  }
</style>
