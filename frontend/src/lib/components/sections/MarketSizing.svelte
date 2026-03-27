<script lang="ts">
  import {
    TrendingUp,
    Database,
    CheckCircle,
    AlertTriangle,
    Timer,
    Target,
    Compass,
    BarChart3,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { MarketSizing } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import MarketFunnel from "$lib/components/charts/MarketFunnel.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";
  import StatPill from "$lib/components/ui/StatPill.svelte";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import IconListItem from "$lib/components/ui/IconListItem.svelte";
  import SectionLabel from "$lib/components/ui/SectionLabel.svelte";
  import { Plus, AlertCircle } from "lucide-svelte";

  interface Props {
    data: MarketSizing;
  }

  let { data }: Props = $props();

  // Get viability verdict styling
  const getViabilityConfig = (verdict?: string) => {
    const v = verdict?.toLowerCase() || "";
    if (v === "strong")
      return { color: "var(--color-success)", variant: "success" as const, label: "STRONG" };
    if (v === "moderate")
      return {
        color: "#EAB308",
        variant: "warning" as const,
        label: "MODERATE",
      };
    return { color: "var(--color-error)", variant: "error" as const, label: "WEAK" };
  };

  // Get saturation level styling
  const getSaturationVariant = (
    level?: string,
  ): "success" | "warning" | "error" => {
    const l = level?.toLowerCase() || "";
    if (l === "low") return "success";
    if (l === "medium") return "warning";
    return "error";
  };

  // Get timing styling
  const getTimingVariant = (
    timing?: string,
  ): "success" | "warning" | "error" => {
    const t = timing?.toLowerCase() || "";
    if (t === "early") return "success";
    if (t === "growth") return "warning";
    return "error";
  };

  const viabilityConfig = $derived(
    getViabilityConfig(data.market_viability_verdict),
  );
</script>

<Section
  id="market-sizing"
  class="report-section"
  icon={SECTION_MAP['market-sizing'].icon}
  title="Market Sizing"
  subtitle="TAM/SAM/SOM analysis and growth opportunity"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Hero Strip: Viability Verdict + Key Signals -->
  <HeroStrip>
    {#snippet primary()}
      <HeroPrimary
        icon={CheckCircle}
        label="Market Viability"
        sublabel={viabilityConfig.label}
        color={viabilityConfig.variant}
      />
    {/snippet}
    {#if data.market_growth_rate}
      <HeroMetric
        value={data.market_growth_rate}
        label="Growth Rate"
        icon={TrendingUp}
        color="success"
      />
    {/if}
    {#if data.market_saturation_level}
      <HeroMetric
        value={data.market_saturation_level}
        label="Saturation"
        color={getSaturationVariant(data.market_saturation_level)}
      />
    {/if}
    {#if data.market_timing_assessment}
      <HeroMetric
        value={data.market_timing_assessment}
        label="Timing"
        icon={Timer}
        color={getTimingVariant(data.market_timing_assessment)}
      />
    {/if}
  </HeroStrip>

  <!-- Market Funnel Visualization -->
  <div class="funnel-card">
    <MarketFunnel
      tam={data.total_addressable_market}
      sam={data.serviceable_available_market}
      somY1={data.serviceable_obtainable_market_y1}
      somY3={data.serviceable_obtainable_market_y3}
    />
  </div>

  <!-- Stats Strip -->
  <div class="stats-strip">
    {#if data.keyword_demand_signal}
      <StatPill label="Keyword Demand" value={data.keyword_demand_signal} />
    {/if}
    {#if data.pain_point_frequency}
      <StatPill label="Pain Frequency" value={data.pain_point_frequency} />
    {/if}
    {#if data.competitor_market_presence}
      <StatPill label="Competition" value={data.competitor_market_presence} />
    {/if}
    {#if data.primary_methodology}
      <StatPill label="Method" value={data.primary_methodology} />
    {/if}
  </div>

  <!-- Entry Strategy Card (Always Visible) -->
  {#if data.recommended_entry_strategy}
    <InsightCard
      variant="accent"
      border="left"
      padding="md"
      class="strategy-card"
    >
      {#snippet header()}
        <SectionLabel
          text="Recommended Entry Strategy"
          variant="accent"
          icon={Compass}
        />
      {/snippet}
      <p class="strategy-text">{data.recommended_entry_strategy}</p>
    </InsightCard>
  {/if}

  <!-- Growth Drivers & Risks -->
  {#if (data.growth_drivers && data.growth_drivers.length > 0) || (data.risk_factors && data.risk_factors.length > 0)}
    <div class="drivers-risks-section">
      <SubsectionHeader
        title="Growth Drivers & Risks"
        icon={BarChart3}
        count={(data.growth_drivers?.length || 0) +
          (data.risk_factors?.length || 0)}
      />
      <CardGrid minWidth={240} gap="md">
        {#if data.growth_drivers && data.growth_drivers.length > 0}
          <InsightCard variant="success" border="left" padding="md">
            {#snippet header()}
              <SectionLabel
                text="Growth Drivers"
                variant="success"
                icon={TrendingUp}
              />
            {/snippet}
            <div class="item-list">
              {#each data.growth_drivers as driver}
                <IconListItem icon={Plus} iconVariant="success"
                  >{driver}</IconListItem
                >
              {/each}
            </div>
          </InsightCard>
        {/if}

        {#if data.risk_factors && data.risk_factors.length > 0}
          <InsightCard variant="error" border="left" padding="md">
            {#snippet header()}
              <SectionLabel
                text="Market Risks"
                variant="error"
                icon={AlertCircle}
              />
            {/snippet}
            <div class="item-list">
              {#each data.risk_factors as risk}
                <IconListItem icon={AlertCircle} iconVariant="error"
                  >{risk}</IconListItem
                >
              {/each}
            </div>
          </InsightCard>
        {/if}
      </CardGrid>
    </div>
  {/if}

  <!-- Segment Breakdown -->
  {#if data.segment_sizing && data.segment_sizing.length > 0}
    <div class="segment-breakdown-section">
      <SubsectionHeader
        title="Segment Breakdown"
        icon={Target}
        count={data.segment_sizing.length}
      />
      <div class="segments-grid">
        {#each data.segment_sizing as segment}
          <InsightCard variant="muted" border="left" padding="md">
            {#snippet header()}
              <div class="segment-header">
                <h4 class="segment-name">{segment.segment_name}</h4>
                <Badge
                  variant={segment.confidence_level === "High"
                    ? "success"
                    : "warning"}
                  size="sm"
                >
                  {segment.confidence_level}
                </Badge>
              </div>
            {/snippet}
            <div class="segment-metrics">
              <div class="metric">
                <span class="metric-label">
                  TAM <Tooltip content={getTermTooltip("TAM")} position="top" />
                </span>
                <span class="metric-value">{segment.tam_estimate}</span>
              </div>
              <div class="metric">
                <span class="metric-label">
                  SAM <Tooltip content={getTermTooltip("SAM")} position="top" />
                </span>
                <span class="metric-value">{segment.sam_estimate}</span>
              </div>
              <div class="metric highlight">
                <span class="metric-label">
                  SOM <Tooltip content={getTermTooltip("SOM")} position="top" />
                </span>
                <span class="metric-value accent">{segment.som_estimate}</span>
              </div>
            </div>
            {#if segment.sizing_methodology}
              <p class="segment-method">{segment.sizing_methodology}</p>
            {/if}
          </InsightCard>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Methodology -->
  {#if data.methodology_explanation}
    <div class="methodology-section">
      <ExpandableSection
        title="Methodology"
        icon={Database}
        count={data.data_sources_used?.length}
        variant="muted"
        defaultOpen={false}
      >
        <InsightCard variant="muted" border="left" padding="md">
          <div class="methodology-content">
            {@html renderMarkdown(data.methodology_explanation)}
          </div>
          {#if data.data_sources_used && data.data_sources_used.length > 0}
            <div class="sources-row">
              <span class="sources-label">Data Sources:</span>
              <div class="sources-tags">
                {#each data.data_sources_used as source}
                  <span class="source-tag">{source}</span>
                {/each}
              </div>
            </div>
          {/if}
        </InsightCard>
      </ExpandableSection>
    </div>
  {/if}

  <!-- Viability Rationale -->
  {#if data.viability_rationale}
    <div class="viability-rationale-section">
      <ExpandableSection
        title="Viability Rationale"
        icon={CheckCircle}
        variant="success"
        defaultOpen={false}
      >
        <InsightCard variant="success" border="left" padding="md">
          <div class="rationale-content">
            {@html renderMarkdown(data.viability_rationale)}
          </div>
        </InsightCard>
      </ExpandableSection>
    </div>
  {/if}
</Section>

<style>
  /* =========================
	   FUNNEL CARD
	   ========================= */
  .funnel-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-4);
  }

  /* =========================
	   STATS STRIP
	   ========================= */
  .stats-strip {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  /* =========================
	   STRATEGY CARD - using InsightCard
	   ========================= */
  :global(.strategy-card) {
    margin-bottom: var(--space-3);
  }

  .strategy-text {
    font-size: var(--text-base);
    color: var(--color-text-primary);
    line-height: 1.6;
    margin: 0;
  }

  /* Drivers & Risks - using IconListItem */
  .item-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  /* Segments Grid */
  .segments-grid {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .segment-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.625rem;
  }

  .segment-name {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .segment-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.875rem;
    margin-bottom: var(--space-2);
  }

  .metric {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .metric.highlight {
    padding: 0.375rem 0.5rem;
    background: var(--color-accent-subtle);
    border-radius: 0.375rem;
  }

  .metric-label {
    font-family: var(--font-mono);
    font-size: 0.5rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
  }

  .metric-value {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .metric-value.accent {
    color: var(--color-accent);
  }

  .segment-method {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    line-height: 1.45;
    margin: 0;
  }

  /* Methodology Content */
  .methodology-content {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.65;
    margin-bottom: 0.875rem;
  }

  .methodology-content :global(p) {
    margin-bottom: var(--space-2);
  }

  .methodology-content :global(p:last-child) {
    margin-bottom: 0;
  }

  .sources-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding-top: 0.875rem;
    border-top: 1px solid var(--color-border);
  }

  .sources-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .sources-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .source-tag {
    font-size: 0.6875rem;
    padding: var(--space-1) var(--space-2);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
  }

  /* Rationale Content */
  .rationale-content {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.65;
  }

  .rationale-content :global(p) {
    margin-bottom: var(--space-2);
  }

  .rationale-content :global(p:last-child) {
    margin-bottom: 0;
  }

  /* =========================
	   SECTION WRAPPERS
	   ========================= */
  .drivers-risks-section,
  .segment-breakdown-section,
  .methodology-section,
  .viability-rationale-section {
    margin-bottom: var(--space-6);
  }

  /* =========================
	   RESPONSIVE
	   ========================= */
  @media (max-width: 768px) {
    .segment-metrics {
      flex-direction: column;
      gap: 0.5rem;
    }
  }

  @media (max-width: 480px) {
    .funnel-card {
      padding: 1rem;
    }
  }
</style>
