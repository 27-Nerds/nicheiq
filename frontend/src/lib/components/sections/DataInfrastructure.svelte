<script lang="ts">
  import {
    Server,
    DollarSign,
    AlertTriangle,
    CheckCircle,
    ExternalLink,
    Shield,
    Zap,
    RotateCcw,
    Layers,
    TrendingUp,
    Clock,
    Activity,
    Cpu,
    Globe,
    ChevronRight,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type {
    DataSourceResearchFull,
    DataRoadmapPhase,
    DataSourceProvider,
    EvaluatedDataSource,
  } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import AnimateOnScroll from "$lib/components/ui/AnimateOnScroll.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";

  interface Props {
    data: DataSourceResearchFull;
  }

  let { data }: Props = $props();

  // Parse cost tiers from estimated_monthly_cost string
  const costTiers = $derived.by(() => {
    if (!data.estimated_monthly_cost) return null;

    const text = data.estimated_monthly_cost;
    const tiers: {
      label: string;
      users: string;
      cost: string;
      details?: string;
    }[] = [];

    // Try to parse "MVP (1k users): $X-Y/month" pattern
    const mvpMatch = text.match(/MVP[^:]*:\s*(\$[\d,]+-[\d,]+\/month)/i);
    const growthMatch = text.match(/Growth[^:]*:\s*(\$[\d,]+-[\d,]+\/month)/i);
    const scaleMatch = text.match(/Scale[^:]*:\s*(\$[\d,]+-[\d,]+\/month)/i);

    if (mvpMatch) {
      tiers.push({
        label: "MVP",
        users: "1K users",
        cost: mvpMatch[1].replace("/month", ""),
      });
    }
    if (growthMatch) {
      const growthDetails = text
        .match(/Growth[^;]+/i)?.[0]
        ?.replace(/Growth[^:]*:\s*\$[\d,]+-[\d,]+\/month\s*/i, "")
        .trim();
      tiers.push({
        label: "Growth",
        users: "10K users",
        cost: growthMatch[1].replace("/month", ""),
        details: growthDetails?.replace(/^\(|\)$/g, ""),
      });
    }
    if (scaleMatch) {
      const scaleDetails = text
        .match(/Scale[^.]+/i)?.[0]
        ?.replace(/Scale[^:]*:\s*\$[\d,]+-[\d,]+\+?\/month\s*/i, "")
        .trim();
      tiers.push({
        label: "Scale",
        users: "100K users",
        cost: scaleMatch[1].replace("/month", ""),
        details: scaleDetails?.replace(/^\(|\)$/g, ""),
      });
    }

    return tiers.length > 0 ? tiers : null;
  });

  // Extract unit economics note
  const unitEconomicsNote = $derived.by(() => {
    if (!data.estimated_monthly_cost) return null;
    const match = data.estimated_monthly_cost.match(
      /Target unit economics:[^.]+\./i,
    );
    return match ? match[0] : null;
  });

  // Count metrics for hero strip
  const sourceCount = $derived(
    (data.primary_data_sources?.length || 0) +
      (data.fallback_sources?.length || 0),
  );
  const phaseCount = $derived(data.implementation_phases?.length || 0);
  const riskCount = $derived(data.data_quality_risks?.length || 0);
  const partnershipCount = $derived(data.data_partnerships_needed?.length || 0);

  // Access model badge variant
  const getAccessBadgeVariant = (accessModel: string) => {
    const model = accessModel?.toLowerCase() || "";
    if (model === "free") return "success";
    if (model === "freemium") return "accent";
    if (model === "paid") return "warning";
    if (model.includes("partner") || model.includes("restricted"))
      return "error";
    return "muted";
  };

  // Phase colors for timeline
  const getPhaseColor = (phaseName: string) => {
    const name = phaseName?.toLowerCase() || "";
    if (name === "mvp")
      return {
        bg: "var(--color-success-subtle)",
        border: "var(--color-success)",
        text: "var(--color-success)",
      };
    if (name === "growth")
      return {
        bg: "var(--color-info-subtle)",
        border: "var(--color-info)",
        text: "var(--color-info)",
      };
    if (name === "scale")
      return {
        bg: "rgba(168, 85, 247, 0.15)",
        border: "#a855f7",
        text: "#a855f7",
      };
    return {
      bg: "var(--color-bg-surface)",
      border: "var(--color-border)",
      text: "var(--color-text-muted)",
    };
  };

  // Priority badge variant
  const getPriorityVariant = (priority: string) => {
    const p = priority?.toUpperCase() || "";
    if (p === "HIGH") return "success";
    if (p === "MEDIUM") return "warning";
    if (p === "LOW") return "muted";
    return "muted";
  };

  // Quality metric score to percentage
  const getQualityPercent = (value: string | undefined) => {
    if (!value) return 0;
    const lower = value.toLowerCase();
    if (
      lower === "high" ||
      lower === "low" ||
      lower === "free" ||
      lower === "daily" ||
      lower === "real-time"
    )
      return 90;
    if (lower === "medium" || lower === "weekly") return 60;
    if (lower.includes("%")) {
      const num = parseInt(value);
      return isNaN(num) ? 50 : num;
    }
    return 50;
  };
</script>

<Section
  id="data-infrastructure"
  class="report-section"
  icon={SECTION_MAP['data-infrastructure'].icon}
  title="Data Infrastructure Roadmap"
  subtitle="Data sources, integrations, and implementation phases"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Hero Strip with Key Metrics -->
  <HeroStrip>
    {#snippet primary()}
      <HeroPrimary
        icon={Cpu}
        label="Data Sources"
        sublabel={String(sourceCount)}
        color="success"
      />
    {/snippet}
    <HeroMetric
      value={phaseCount}
      label="Phases"
      icon={Layers}
      color="accent"
    />
    {#if partnershipCount > 0}
      <HeroMetric
        value={partnershipCount}
        label="Partnerships"
        icon={Globe}
        color="warning"
      />
    {/if}
    {#if riskCount > 0}
      <HeroMetric
        value={riskCount}
        label="Risks"
        icon={AlertTriangle}
        color="error"
      />
    {/if}
  </HeroStrip>

  <!-- Cost Tiers - Visual Breakdown -->
  {#if costTiers && costTiers.length > 0}
    <AnimateOnScroll animation="fade-up">
      <div class="cost-tiers-section">
        <div class="cost-tiers-header">
          <DollarSign class="cost-tiers-icon" />
          <span class="cost-tiers-title">Infrastructure Cost Scaling</span>
        </div>
        <div class="cost-tiers-grid">
          {#each costTiers as tier, i}
            {@const isLast = i === costTiers.length - 1}
            <div
              class="cost-tier-card cost-tier-card--{tier.label.toLowerCase()}"
            >
              <div class="cost-tier-header">
                <span class="cost-tier-badge">{tier.label}</span>
                <span class="cost-tier-users">{tier.users}</span>
              </div>
              <div class="cost-tier-amount">{tier.cost}</div>
              <div class="cost-tier-period">per month</div>
              {#if tier.details}
                <div class="cost-tier-details">{tier.details}</div>
              {/if}
              {#if !isLast}
                <div class="cost-tier-arrow">
                  <ChevronRight />
                </div>
              {/if}
            </div>
          {/each}
        </div>
        {#if unitEconomicsNote}
          <div class="unit-economics-note">
            <TrendingUp class="unit-economics-icon" />
            <span>{unitEconomicsNote}</span>
          </div>
        {/if}
      </div>
    </AnimateOnScroll>
  {:else if data.estimated_monthly_cost}
    <!-- Fallback for unparseable cost format -->
    <AnimateOnScroll animation="fade-up">
      <div class="cost-fallback-card">
        <DollarSign class="cost-fallback-icon" />
        <div class="cost-fallback-content">
          <span class="cost-fallback-label">Estimated Monthly Cost</span>
          <div class="cost-fallback-text">
            {@html renderMarkdown(data.estimated_monthly_cost)}
          </div>
        </div>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- Implementation Phases - Timeline -->
  {#if data.implementation_phases && data.implementation_phases.length > 0}
    <AnimateOnScroll animation="fade-up">
      <div class="timeline-section">
        <div class="timeline-header">
          <Clock class="timeline-header-icon" />
          <h3 class="timeline-title">Implementation Timeline</h3>
        </div>
        <div class="timeline-track">
          {#each data.implementation_phases as phase, i}
            {@const colors = getPhaseColor(phase.phase_name)}
            {@const isLast = i === data.implementation_phases.length - 1}
            <div
              class="timeline-phase"
              style="--phase-color: {colors.border}; --phase-bg: {colors.bg}"
            >
              <!-- Timeline connector -->
              <div class="timeline-connector">
                <div class="timeline-node"></div>
                {#if !isLast}
                  <div class="timeline-line"></div>
                {/if}
              </div>

              <!-- Phase card -->
              <div class="phase-card">
                <div class="phase-card-header">
                  <div class="phase-badge-group">
                    <span class="phase-number">Phase {phase.phase_number}</span>
                    <span class="phase-name" style="color: {colors.text}"
                      >{phase.phase_name}</span
                    >
                  </div>
                  <div class="phase-meta">
                    <span class="phase-timeline">{phase.timeline}</span>
                    <span class="phase-cost"
                      >{phase.estimated_monthly_cost}</span
                    >
                  </div>
                </div>

                <p class="phase-goal">{phase.goal}</p>

                <!-- Data Sources -->
                {#if phase.data_sources && phase.data_sources.length > 0}
                  <div class="phase-sources">
                    <span class="phase-section-label">
                      <Server class="phase-section-icon" />
                      Sources
                    </span>
                    <div class="phase-source-tags">
                      {#each phase.data_sources as source}
                        <span class="source-tag">{source}</span>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Milestones -->
                {#if phase.key_milestones && phase.key_milestones.length > 0}
                  <div class="phase-milestones">
                    <span class="phase-section-label">
                      <CheckCircle class="phase-section-icon" />
                      Milestones
                    </span>
                    <ul class="milestone-list">
                      {#each phase.key_milestones as milestone}
                        <li class="milestone-item">{milestone}</li>
                      {/each}
                    </ul>
                  </div>
                {/if}

                <!-- Fallbacks (collapsed by default) -->
                {#if phase.fallback_strategies && phase.fallback_strategies.length > 0}
                  <details class="phase-fallbacks">
                    <summary class="fallbacks-summary">
                      <RotateCcw class="fallbacks-icon" />
                      <span
                        >{phase.fallback_strategies.length} fallback strategies</span
                      >
                    </summary>
                    <ul class="fallback-list">
                      {#each phase.fallback_strategies as fallback}
                        <li class="fallback-item">{fallback}</li>
                      {/each}
                    </ul>
                  </details>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    </AnimateOnScroll>
  {/if}

  <!-- Expandable Sections -->
  <div class="expandable-sections">
    <!-- Primary Data Sources -->
    {#if data.primary_data_sources && data.primary_data_sources.length > 0}
      <ExpandableSection
        title="Primary Data Sources"
        icon={Server}
        count={data.primary_data_sources.length}
        countSuffix="sources"
        variant="success"
      >
        <div class="sources-grid">
          {#each data.primary_data_sources as source}
            <div class="source-card">
              <div class="source-card-header">
                <div class="source-info">
                  <h4 class="source-name">{source.provider}</h4>
                  {#if source.url}
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="source-link"
                    >
                      <ExternalLink class="source-link-icon" />
                      API Docs
                    </a>
                  {/if}
                </div>
                <Badge
                  variant={getAccessBadgeVariant(source.access_model)}
                  size="sm"
                >
                  {source.access_model}
                </Badge>
              </div>

              <div class="source-metrics">
                {#if source.cost_estimate}
                  <div class="source-metric">
                    <DollarSign class="source-metric-icon" />
                    <span>{source.cost_estimate}</span>
                  </div>
                {/if}
                {#if source.update_frequency}
                  <div class="source-metric">
                    <Activity class="source-metric-icon" />
                    <span>{source.update_frequency}</span>
                  </div>
                {/if}
                {#if source.integration_effort}
                  <div class="source-metric">
                    <Cpu class="source-metric-icon" />
                    <span>{source.integration_effort}</span>
                  </div>
                {/if}
              </div>

              {#if source.coverage}
                <div class="source-coverage">
                  <span class="coverage-label">Coverage</span>
                  <span class="coverage-value">{source.coverage}</span>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Evaluated Sources with Quality Matrix -->
    {#if data.source_evaluation?.evaluated_sources && data.source_evaluation.evaluated_sources.length > 0}
      <ExpandableSection
        title="Source Quality Analysis"
        icon={Shield}
        count={data.source_evaluation.evaluated_sources.length}
        countSuffix="evaluated"
        variant="accent"
      >
        <div class="evaluated-sources-list">
          {#each data.source_evaluation.evaluated_sources as source}
            <div class="evaluated-card">
              <div class="evaluated-header">
                <div class="evaluated-info">
                  <h4 class="evaluated-name">{source.provider}</h4>
                  <p class="evaluated-rationale">{source.priority_rationale}</p>
                </div>
                <Badge variant={getPriorityVariant(source.priority)} size="sm">
                  {source.priority}
                </Badge>
              </div>

              <!-- Quality Metrics as Visual Bars -->
              {#if source.quality_metrics}
                <div class="quality-matrix">
                  <div class="quality-row">
                    <span class="quality-label">Freshness</span>
                    <div class="quality-bar-wrap">
                      <div
                        class="quality-bar"
                        style="--bar-fill: {getQualityPercent(
                          source.quality_metrics.freshness,
                        )}%"
                      ></div>
                    </div>
                    <span class="quality-value"
                      >{source.quality_metrics.freshness ?? "N/A"}</span
                    >
                  </div>
                  <div class="quality-row">
                    <span class="quality-label">Coverage</span>
                    <div class="quality-bar-wrap">
                      <div
                        class="quality-bar"
                        style="--bar-fill: {getQualityPercent(
                          source.quality_metrics.coverage_score,
                        )}%"
                      ></div>
                    </div>
                    <span class="quality-value"
                      >{source.quality_metrics.coverage_score ?? "N/A"}</span
                    >
                  </div>
                  <div class="quality-row">
                    <span class="quality-label">Integration</span>
                    <div class="quality-bar-wrap">
                      <div
                        class="quality-bar quality-bar--inverse"
                        style="--bar-fill: {100 -
                          getQualityPercent(
                            source.quality_metrics.integration_complexity,
                          )}%"
                      ></div>
                    </div>
                    <span class="quality-value"
                      >{source.quality_metrics.integration_complexity ??
                        "N/A"}</span
                    >
                  </div>
                  <div class="quality-row">
                    <span class="quality-label">Cost</span>
                    <div class="quality-bar-wrap">
                      <div
                        class="quality-bar"
                        style="--bar-fill: {getQualityPercent(
                          source.quality_metrics.cost_viability,
                        )}%"
                      ></div>
                    </div>
                    <span class="quality-value"
                      >{source.quality_metrics.cost_viability ?? "N/A"}</span
                    >
                  </div>
                </div>
              {/if}

              <!-- Cost estimates -->
              <div class="evaluated-costs">
                {#if source.mvp_cost_estimate}
                  <span class="cost-tag cost-tag--mvp"
                    >MVP: {source.mvp_cost_estimate}</span
                  >
                {/if}
                {#if source.scale_cost_estimate}
                  <span class="cost-tag cost-tag--scale"
                    >Scale: {source.scale_cost_estimate}</span
                  >
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Fallback Sources -->
    {#if data.fallback_sources && data.fallback_sources.length > 0}
      <ExpandableSection
        title="Fallback Sources"
        icon={RotateCcw}
        count={data.fallback_sources.length}
        countSuffix="backups"
        variant="warning"
      >
        <div class="fallback-sources-grid">
          {#each data.fallback_sources as source}
            <div class="fallback-source-card">
              <div class="fallback-source-header">
                <span class="fallback-source-name">{source.provider}</span>
                <Badge
                  variant={getAccessBadgeVariant(source.access_model)}
                  size="sm"
                >
                  {source.access_model}
                </Badge>
              </div>
              {#if source.cost_estimate}
                <span class="fallback-source-cost">{source.cost_estimate}</span>
              {/if}
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Data Quality Risks -->
    {#if data.data_quality_risks && data.data_quality_risks.length > 0}
      <ExpandableSection
        title="Data Quality Risks"
        icon={AlertTriangle}
        count={data.data_quality_risks.length}
        countSuffix="risks"
        variant="error"
      >
        <div class="risks-list">
          {#each data.data_quality_risks as risk}
            <div class="risk-item">
              <AlertTriangle class="risk-icon" />
              <span class="risk-text">{risk}</span>
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Risk Mitigation -->
    {#if data.source_evaluation?.risk_mitigation_strategies && data.source_evaluation.risk_mitigation_strategies.length > 0}
      <ExpandableSection
        title="Risk Mitigation"
        icon={Shield}
        count={data.source_evaluation.risk_mitigation_strategies.length}
        countSuffix="strategies"
        variant="success"
      >
        <div class="mitigation-list">
          {#each data.source_evaluation.risk_mitigation_strategies as strategy}
            <div class="mitigation-item">
              <CheckCircle class="mitigation-icon" />
              <span class="mitigation-text">{strategy}</span>
            </div>
          {/each}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Implementation Strategy Narrative -->
    {#if data.implementation_roadmap}
      <ExpandableSection
        title="Implementation Strategy"
        icon={Layers}
        variant="default"
      >
        <div class="narrative-content">
          {@html renderMarkdown(data.implementation_roadmap)}
        </div>
      </ExpandableSection>
    {/if}

    <!-- Competitive Data Insights -->
    {#if data.competitive_data_insights}
      <ExpandableSection
        title="Competitive Data Insights"
        icon={Activity}
        variant="accent"
      >
        <div class="narrative-content">
          {@html renderMarkdown(data.competitive_data_insights)}
        </div>
      </ExpandableSection>
    {/if}

    <!-- SEO-Aligned Priorities -->
    {#if data.seo_aligned_priorities}
      <ExpandableSection
        title="SEO-Aligned Data Priorities"
        icon={TrendingUp}
        variant="success"
      >
        <div class="narrative-content narrative-content--highlight">
          {@html renderMarkdown(data.seo_aligned_priorities)}
        </div>
      </ExpandableSection>
    {/if}
  </div>

  <!-- Recommended Stack Footer -->
  {#if data.source_evaluation?.recommended_stack && data.source_evaluation.recommended_stack.length > 0}
    <div class="recommended-stack">
      <span class="recommended-stack-label">Recommended Stack</span>
      <div class="recommended-stack-tags">
        {#each data.source_evaluation.recommended_stack as item}
          <Badge variant="accent" size="sm">{item}</Badge>
        {/each}
      </div>
    </div>
  {/if}
</Section>

<style>
  /* Cost Tiers Section */
  .cost-tiers-section {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .cost-tiers-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }

  :global(.cost-tiers-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent);
  }

  .cost-tiers-title {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .cost-tiers-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0;
    position: relative;
  }

  .cost-tier-card {
    position: relative;
    padding: 1.25rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .cost-tier-card:first-child {
    border-radius: 0.5rem 0 0 0.5rem;
  }

  .cost-tier-card:last-child {
    border-radius: 0 0.5rem 0.5rem 0;
  }

  .cost-tier-card:not(:last-child) {
    border-right: none;
  }

  .cost-tier-card--mvp {
    background: var(--color-success-subtle);
    border-color: var(--color-border-success);
  }

  .cost-tier-card--growth {
    background: var(--color-info-subtle);
    border-color: var(--color-border-info);
  }

  .cost-tier-card--scale {
    background: rgba(168, 85, 247, 0.06);
    border-color: rgba(168, 85, 247, 0.3);
  }

  .cost-tier-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    margin-bottom: 0.75rem;
  }

  .cost-tier-badge {
    font-family: var(--font-display);
    font-size: 0.875rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .cost-tier-card--mvp .cost-tier-badge {
    color: var(--color-success);
  }
  .cost-tier-card--growth .cost-tier-badge {
    color: var(--color-info);
  }
  .cost-tier-card--scale .cost-tier-badge {
    color: #a855f7;
  }

  .cost-tier-users {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .cost-tier-amount {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--color-text-primary);
    line-height: 1.1;
  }

  .cost-tier-period {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }

  .cost-tier-details {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
    max-width: 180px;
  }

  .cost-tier-arrow {
    position: absolute;
    right: -12px;
    top: 50%;
    transform: translateY(-50%);
    width: 24px;
    height: 24px;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2;
  }

  :global(.cost-tier-arrow svg) {
    width: 14px;
    height: 14px;
    color: var(--color-text-muted);
  }

  .unit-economics-note {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
    border-radius: 0.5rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  :global(.unit-economics-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-success);
    flex-shrink: 0;
  }

  /* Cost Fallback */
  .cost-fallback-card {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 1.25rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    margin-bottom: 1.5rem;
  }

  :global(.cost-fallback-icon) {
    width: 1.5rem;
    height: 1.5rem;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .cost-fallback-content {
    flex: 1;
  }

  .cost-fallback-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }

  .cost-fallback-text {
    font-size: 0.9375rem;
    color: var(--color-text-primary);
    line-height: 1.6;
  }

  /* Timeline Section */
  .timeline-section {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .timeline-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  :global(.timeline-header-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent);
  }

  .timeline-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .timeline-track {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .timeline-phase {
    display: flex;
    gap: 1.25rem;
  }

  .timeline-connector {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 24px;
    flex-shrink: 0;
  }

  .timeline-node {
    width: 16px;
    height: 16px;
    background: var(--phase-bg);
    border: 3px solid var(--phase-color);
    border-radius: 50%;
    flex-shrink: 0;
  }

  .timeline-line {
    flex: 1;
    width: 2px;
    background: var(--color-border);
    min-height: 40px;
  }

  .phase-card {
    flex: 1;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--phase-color);
    border-radius: 0.5rem;
    padding: 1.25rem;
    margin-bottom: 1rem;
  }

  .phase-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }

  .phase-badge-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .phase-number {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .phase-name {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 700;
  }

  .phase-meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.125rem;
  }

  .phase-timeline {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .phase-cost {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .phase-goal {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0 0 1rem;
  }

  .phase-sources,
  .phase-milestones {
    margin-bottom: 0.75rem;
  }

  .phase-section-label {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }

  :global(.phase-section-icon) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .phase-source-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .source-tag {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
    color: var(--color-text-secondary);
  }

  .milestone-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.375rem;
  }

  .milestone-item {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    padding-left: 1rem;
    position: relative;
  }

  .milestone-item::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.5em;
    width: 4px;
    height: 4px;
    background: var(--phase-color);
    border-radius: 50%;
  }

  .phase-fallbacks {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
  }

  .fallbacks-summary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    cursor: pointer;
    list-style: none;
  }

  .fallbacks-summary::-webkit-details-marker {
    display: none;
  }

  :global(.fallbacks-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: #eab308;
  }

  .fallback-list {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 0;
    display: grid;
    gap: 0.25rem;
  }

  .fallback-item {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    padding-left: 1.25rem;
    position: relative;
  }

  .fallback-item::before {
    content: "↳";
    position: absolute;
    left: 0;
    color: var(--color-text-muted);
  }

  /* Expandable Sections */
  .expandable-sections {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  /* Sources Grid */
  .sources-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
  }

  .source-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1rem;
  }

  .source-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .source-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .source-name {
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
    font-size: 0.9375rem;
  }

  .source-link {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--color-accent);
    text-decoration: none;
  }

  .source-link:hover {
    text-decoration: underline;
  }

  :global(.source-link-icon) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .source-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .source-metric {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  :global(.source-metric-icon) {
    width: 0.75rem;
    height: 0.75rem;
    color: var(--color-text-muted);
  }

  .source-coverage {
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .coverage-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .coverage-value {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  /* Evaluated Sources */
  .evaluated-sources-list {
    display: grid;
    gap: 1rem;
  }

  .evaluated-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    padding: 1.25rem;
  }

  .evaluated-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .evaluated-info {
    flex: 1;
  }

  .evaluated-name {
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 0.25rem;
  }

  .evaluated-rationale {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
    margin: 0;
  }

  /* Quality Matrix */
  .quality-matrix {
    display: grid;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .quality-row {
    display: grid;
    grid-template-columns: 80px 1fr 60px;
    align-items: center;
    gap: 0.75rem;
  }

  .quality-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .quality-bar-wrap {
    height: 6px;
    background: var(--color-bg-elevated);
    border-radius: 3px;
    overflow: hidden;
  }

  .quality-bar {
    height: 100%;
    width: var(--bar-fill, 50%);
    background: var(--color-success);
    border-radius: 3px;
    transition: width 0.5s ease;
  }

  .quality-bar--inverse {
    background: var(--color-success);
  }

  .quality-value {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    text-align: right;
  }

  .evaluated-costs {
    display: flex;
    gap: 0.5rem;
  }

  .cost-tag {
    font-size: 0.6875rem;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
  }

  .cost-tag--mvp {
    background: var(--color-success-subtle);
    color: var(--color-success);
  }

  .cost-tag--scale {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
  }

  /* Fallback Sources Grid */
  .fallback-sources-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.75rem;
  }

  .fallback-source-card {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-left: 3px solid #eab308;
    border-radius: 0.5rem;
    padding: 0.875rem 1rem;
  }

  .fallback-source-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .fallback-source-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .fallback-source-cost {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin-top: 0.25rem;
    display: block;
  }

  /* Risks List */
  .risks-list {
    display: grid;
    gap: 0.5rem;
  }

  .risk-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--color-error-subtle);
    border: 1px solid var(--color-border-error);
    border-radius: 0.5rem;
  }

  :global(.risk-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-error);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .risk-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  /* Mitigation List */
  .mitigation-list {
    display: grid;
    gap: 0.5rem;
  }

  .mitigation-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
    border-radius: 0.5rem;
  }

  :global(.mitigation-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-success);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .mitigation-text {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
  }

  /* Narrative Content */
  .narrative-content {
    font-size: 0.9375rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .narrative-content--highlight {
    padding: 1rem;
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
    border-radius: 0.5rem;
  }

  /* Recommended Stack */
  .recommended-stack {
    margin-top: 1.5rem;
    padding-top: 1.25rem;
    border-top: 1px solid var(--color-border);
  }

  .recommended-stack-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.75rem;
  }

  .recommended-stack-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .cost-tiers-grid {
      grid-template-columns: 1fr;
      gap: 0.75rem;
    }

    .cost-tier-card {
      border-radius: 0.5rem !important;
      border: 1px solid var(--color-border) !important;
    }

    .cost-tier-arrow {
      display: none;
    }

    .phase-card-header {
      flex-direction: column;
      gap: 0.5rem;
    }

    .phase-meta {
      align-items: flex-start;
    }

    .sources-grid {
      grid-template-columns: 1fr;
    }

    .quality-row {
      grid-template-columns: 60px 1fr 50px;
    }
  }
</style>
