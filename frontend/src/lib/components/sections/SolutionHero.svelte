<script lang="ts">
  import {
    Rocket,
    Trophy,
    Puzzle,
    Workflow,
    Target,
    Layers,
    CheckCircle,
    Clock,
    Globe,
    DollarSign,
    Users,
    Search,
    FileText,
    Wallet,
    TrendingUp,
    BarChart3,
    Hash,
    Cpu,
    Settings,
    Code,
    User,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type {
    SolutionDetails,
    ExecutiveDashboard,
    BudgetEstimate,
    PricingStrategy,
  } from "$lib/types/report";
  import {
    renderMarkdown,
    parseRationaleMetrics,
    formatScorePercent,
  } from "$lib/utils/format";
  import { formatPricingSummary } from "$lib/utils/pricing";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import CheckListItem from "$lib/components/ui/CheckListItem.svelte";
  import SectionLabel from "$lib/components/ui/SectionLabel.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import { solutionDisplayTitle, originalityMetric } from "$lib/utils/solution-utils";

  interface Props {
    solution: SolutionDetails;
    dashboard: ExecutiveDashboard;
    selectionRationale: string;
    budgetEstimate?: BudgetEstimate | string | null;
    pricingStrategy?: PricingStrategy | null;
  }

  let {
    solution,
    dashboard,
    selectionRationale,
    budgetEstimate,
    pricingStrategy,
  }: Props = $props();

  const solutionName = $derived(solutionDisplayTitle({ ...solution, solution_name: solution.solution_name || "Solution" }) || "Solution");
  const hasHeadline = $derived(!!solution.headline?.trim());
  const origMetric = $derived(originalityMetric(solution));
  const snapshot = $derived(dashboard.recommended_solution_snapshot);
  const verdict = $derived(dashboard.go_no_go_verdict);

  // Parse metrics from rationale text
  const parsedRationale = $derived(parseRationaleMetrics(selectionRationale));

  // Extract just the duration part from dev time (e.g., "6-8 weeks" from "6-8 weeks for MVP...")
  const extractDevTimeDuration = (
    devTime: string,
  ): { short: string; full: string } => {
    const match = devTime.match(/^[\d\-\+]+\s*(?:weeks?|months?|days?)/i);
    if (match) {
      return { short: match[0], full: devTime };
    }
    // Fallback: if text is short enough, show it all
    if (devTime.length <= 20) {
      return { short: devTime, full: devTime };
    }
    // Otherwise truncate
    return { short: devTime.slice(0, 17) + "...", full: devTime };
  };

  // Format budget range for display (e.g., "$500-$2K")
  const formatBudgetRange = (
    budget: BudgetEstimate | string | null | undefined,
  ): string | null => {
    if (!budget || typeof budget === "string") return null;
    const formatK = (n: number) =>
      n >= 1000 ? `$${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}K` : `$${n}`;
    return `${formatK(budget.monthly_budget_min)}-${formatK(budget.monthly_budget_max)}`;
  };

  const budgetDisplay = $derived(formatBudgetRange(budgetEstimate));

  // Use structured pricing object when available (fixes Freemium-Lite display for existing reports)
  const businessModelText = $derived(
    pricingStrategy
      ? formatPricingSummary(pricingStrategy)
      : solution.pricing_strategy,
  );

  // Get semantic variant for Selection Rationale metrics based on value
  const getMetricCardVariant = (metric: {
    label: string;
    value: string;
  }): "default" | "success" | "warning" | "accent" => {
    const label = metric.label.toLowerCase();
    const value = metric.value;

    // Score-based metrics (e.g., "8.5/10" or "0.85")
    if (label.includes("score") || label.includes("fit")) {
      const numMatch = value.match(/(\d+\.?\d*)/);
      if (numMatch) {
        const num = parseFloat(numMatch[1]);
        if (num >= 8 || (num >= 0.8 && num <= 1)) return "success";
        if (num >= 6 || (num >= 0.6 && num < 0.8)) return "accent";
        return "warning";
      }
    }

    // Percentage-based metrics
    if (value.includes("%")) {
      const numMatch = value.match(/(\d+)/);
      if (numMatch) {
        const num = parseInt(numMatch[1]);
        if (num >= 70) return "success";
        if (num >= 40) return "accent";
        return "warning";
      }
    }

    return "accent";
  };

  // Get icon component for metric based on label pattern
  const getMetricIcon = (label: string): typeof Globe => {
    const lowerLabel = label.toLowerCase();
    if (lowerLabel.includes("seo")) return Globe;
    if (lowerLabel.includes("search")) return Search;
    if (lowerLabel.includes("tech") || lowerLabel.includes("feasibility"))
      return Cpu;
    if (lowerLabel.includes("settings") || lowerLabel.includes("config"))
      return Settings;
    if (lowerLabel.includes("dev") || lowerLabel.includes("solo")) return Code;
    if (lowerLabel.includes("user") || lowerLabel.includes("audience"))
      return User;
    if (lowerLabel.includes("market") || lowerLabel.includes("fit"))
      return Target;
    if (lowerLabel.includes("growth") || lowerLabel.includes("trend"))
      return TrendingUp;
    return BarChart3;
  };

  // Extract numeric value (0-100) for progress bar from metric value
  const extractProgressValue = (value: string): number => {
    // Try to extract percentage directly
    const percentMatch = value.match(/(\d+(?:\.\d+)?)\s*%/);
    if (percentMatch) return Math.min(100, parseFloat(percentMatch[1]));

    // Try to extract X/10 format
    const tenScaleMatch = value.match(/(\d+(?:\.\d+)?)\s*\/\s*10/);
    if (tenScaleMatch) return Math.min(100, parseFloat(tenScaleMatch[1]) * 10);

    // Try to extract decimal (0.0-1.0)
    const decimalMatch = value.match(/^0\.(\d+)$/);
    if (decimalMatch)
      return Math.min(100, parseFloat("0." + decimalMatch[1]) * 100);

    // Try to extract any number and assume it's out of 10 if <= 10
    const numMatch = value.match(/(\d+(?:\.\d+)?)/);
    if (numMatch) {
      const num = parseFloat(numMatch[1]);
      if (num <= 10) return num * 10;
      if (num <= 100) return num;
    }

    return 75; // Default fallback
  };

  // Get progress bar color based on variant
  const getProgressColor = (
    variant: "default" | "success" | "warning" | "accent",
  ): string => {
    switch (variant) {
      case "success":
        return "var(--color-success)";
      case "warning":
        return "var(--color-warning)";
      case "accent":
        return "var(--color-accent)";
      default:
        return "var(--color-text-muted)";
    }
  };
</script>

<Section
  id="solution"
  class="report-section"
  icon={SECTION_MAP['solution'].icon}
  title="Recommended Solution"
  subtitle="AI-validated product opportunity"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Solution Hero Card -->
  <div class="solution-hero-card">
    <div class="hero-top">
      <div class="hero-badges">
        {#if snapshot.project_type}
          <Badge variant="default">{snapshot.project_type}</Badge>
        {/if}
      </div>
      <div class="hero-icon">
        <Rocket class="hero-icon-svg" />
      </div>
    </div>

    <h3 class="hero-title">{solutionName}</h3>

    {#if hasHeadline}
      <p class="hero-codename">{solution.solution_name}</p>
    {/if}

    {#if snapshot.tagline}
      <p class="hero-tagline">{snapshot.tagline}</p>
    {:else if solution.short_description}
      <p class="hero-tagline">{solution.short_description}</p>
    {/if}

    <!-- Value Proposition -->
    <InsightCard variant="accent" border="left" padding="md">
      <p class="value-text">
        {solution.value_proposition ||
          snapshot.core_value_prop ||
          solution.description}
      </p>
    </InsightCard>
  </div>

  <!-- Launch Parameters Strip -->
  {#if solution.estimated_development_time || solution.estimated_indexable_pages || solution.estimated_cac_organic || budgetDisplay}
    <div class="launch-params">
      <div class="launch-params-header">
        <span class="launch-params-label">LAUNCH PARAMETERS</span>
        <div class="launch-params-line"></div>
      </div>
      <CardGrid minWidth={140} gap="md" class="launch-params-grid">
        {#if solution.estimated_development_time}
          {@const devTime = extractDevTimeDuration(
            solution.estimated_development_time,
          )}
          <div class="param-card param-time" style="--param-delay: 0s">
            <div class="param-icon-wrap">
              <Clock class="param-icon" />
            </div>
            <div class="param-data">
              <span class="param-value">{devTime.short}</span>
              <span class="param-label">
                Time to MVP
                {#if devTime.short !== devTime.full}
                  <Tooltip content={devTime.full} position="top" />
                {/if}
              </span>
            </div>
          </div>
        {/if}

        {#if solution.estimated_indexable_pages}
          <div class="param-card param-scale" style="--param-delay: 0.08s">
            <div class="param-icon-wrap">
              <Globe class="param-icon" />
            </div>
            <div class="param-data">
              <span class="param-value"
                >{solution.estimated_indexable_pages}</span
              >
              <span class="param-label">SEO Pages Y1</span>
            </div>
          </div>
        {/if}

        {#if solution.estimated_cac_organic}
          <div class="param-card param-cost" style="--param-delay: 0.16s">
            <div class="param-icon-wrap">
              <DollarSign class="param-icon" />
            </div>
            <div class="param-data">
              <span class="param-value">
                {solution.estimated_cac_organic}
                {#if solution.estimated_cac_paid}
                  <span class="cac-vs-paid"
                    >vs {solution.estimated_cac_paid} paid</span
                  >
                {/if}
              </span>
              <span class="param-label">
                Organic CAC
                <Tooltip content={getTermTooltip("CAC")} position="top" />
              </span>
            </div>
          </div>
        {/if}

        {#if budgetDisplay}
          <div class="param-card param-budget" style="--param-delay: 0.24s">
            <div class="param-icon-wrap">
              <Wallet class="param-icon" />
            </div>
            <div class="param-data">
              <span class="param-value">{budgetDisplay}</span>
              <span class="param-label">
                Monthly Budget
                <Tooltip
                  content="Estimated monthly marketing budget to achieve growth targets"
                  position="top"
                />
              </span>
            </div>
          </div>
        {/if}
      </CardGrid>
    </div>
  {/if}

  <!-- How It Works -->
  {#if solution.description && solution.description !== solution.value_proposition}
    <InsightCard variant="accent" border="left" padding="md" class="how-it-works-card">
      {#snippet header()}
        <div class="how-it-works-header">
          <Workflow class="how-it-works-icon" />
          <span class="how-it-works-title">HOW IT WORKS</span>
        </div>
      {/snippet}
      <p class="how-it-works-content">{solution.description}</p>
    </InsightCard>
  {/if}

  <!-- Distinctiveness score card -->
  {#if origMetric.value != null}
    <InsightCard
      variant="warning"
      border="left"
      padding="md"
      class="innovation-card"
    >
      {#snippet header()}
        <div class="innovation-header">
          <div class="innovation-label">
            <Puzzle class="innovation-icon" />
            <span>{origMetric.label?.toUpperCase()}</span>
          </div>
          <div class="innovation-score">
            <span class="score-value">{formatScorePercent(origMetric.value)}</span>
          </div>
        </div>
      {/snippet}
      {#if solution.conventional_approach || solution.innovation_angle || solution.why_it_works}
        <div class="innovation-breakdown">
          {#if solution.conventional_approach}
            <div class="innovation-facet">
              <span class="facet-label">Conventional Path</span>
              <p class="facet-text">{solution.conventional_approach}</p>
            </div>
          {/if}
          {#if solution.innovation_angle}
            <div class="innovation-facet facet-highlight">
              <span class="facet-label">What's Different</span>
              <p class="facet-text">{solution.innovation_angle}</p>
            </div>
          {/if}
          {#if solution.why_it_works}
            <div class="innovation-facet">
              <span class="facet-label">Why It Works</span>
              <p class="facet-text">{solution.why_it_works}</p>
            </div>
          {/if}
        </div>
      {/if}
    </InsightCard>
  {/if}

  <!-- Discovery Queries -->
  {#if solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0}
    <InsightCard
      variant="info"
      border="left"
      padding="md"
      class="discovery-card"
    >
      {#snippet header()}
        <div class="discovery-header">
          <Search class="discovery-icon" />
          <span class="discovery-title">HOW USERS FIND YOU</span>
        </div>
      {/snippet}
      <div class="discovery-queries">
        {#each solution.organic_discovery_queries.slice(0, 8) as query}
          <span class="query-chip">{query}</span>
        {/each}
      </div>
    </InsightCard>
  {/if}

  <!-- Target Personas -->
  {#if solution.target_personas && solution.target_personas.length > 0}
    <div class="personas-section">
      <SubsectionHeader
        title="Target Audience"
        icon={Users}
        count={solution.target_personas.length}
        variant="info"
      />
      <CardGrid minWidth={220} gap="md">
        {#each solution.target_personas as persona, i}
          <InsightCard
            variant={i === 0 ? "accent" : "default"}
            border="left"
            hoverable={true}
            padding="md"
          >
            {#snippet header()}
              <div class="persona-header">
                <span class="persona-num" class:primary={i === 0}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <SectionLabel
                  text={i === 0 ? "Primary" : "Secondary"}
                  variant={i === 0 ? "accent" : "muted"}
                />
              </div>
            {/snippet}
            <span class="persona-text">{persona}</span>
          </InsightCard>
        {/each}
      </CardGrid>
    </div>
  {/if}

  <!-- Business Model -->
  {#if businessModelText}
    <InsightCard
      variant="success"
      border="left"
      padding="md"
      class="business-model-card"
    >
      {#snippet header()}
        <div class="business-model-header">
          <DollarSign class="business-model-icon" />
          <span class="business-model-title">Business Model</span>
        </div>
      {/snippet}
      <p class="business-model-text">{businessModelText}</p>
    </InsightCard>
  {/if}

  <!-- Competitive Advantages - Always Visible -->
  {#if solution.differentiation_factors && solution.differentiation_factors.length > 0}
    <div class="advantages-card">
      <div class="advantages-header">
        <Trophy class="advantages-icon" />
        <span class="advantages-title">Competitive Advantages</span>
        <Badge variant="success" size="sm"
          >{solution.differentiation_factors.length}</Badge
        >
      </div>
      <CardGrid minWidth={240} gap="sm">
        {#each solution.differentiation_factors as factor}
          <div class="advantage-item">
            <CheckCircle class="check-icon" />
            <span class="advantage-text">{factor}</span>
          </div>
        {/each}
      </CardGrid>
    </div>
  {/if}


  <!-- Core Features -->
  {#if solution.core_features && solution.core_features.length > 0}
    <div class="core-features-section">
      <ExpandableSection
        title="Core Features"
        icon={Layers}
        count={solution.core_features.length}
        defaultOpen={false}
        variant="muted"
      >
        <InsightCard variant="muted" border="left" padding="md">
          <ul class="feature-list">
            {#each solution.core_features as feature}
              <CheckListItem color="accent">{feature}</CheckListItem>
            {/each}
          </ul>
        </InsightCard>
      </ExpandableSection>
    </div>
  {/if}

  <!-- SEO Content Engine -->
  {#if solution.content_generation_model}
    <div class="seo-engine-section">
      <ExpandableSection
        title="SEO Content Engine"
        icon={Globe}
        defaultOpen={false}
        variant="muted"
      >
        <InsightCard variant="muted" border="left" padding="md">
          <div class="seo-engine-content">
            {@html renderMarkdown(solution.content_generation_model)}
          </div>
        </InsightCard>
      </ExpandableSection>
    </div>
  {/if}

  <!-- Selection Rationale -->
  {#if selectionRationale}
    <ExpandableSection
      title="Selection Rationale"
      icon={Target}
      count={parsedRationale.metrics.length > 0
        ? parsedRationale.metrics.length
        : null}
      countSuffix="metrics"
    >
      <!-- Extracted Metrics as InsightCard Grid -->
      {#if parsedRationale.metrics.length > 0}
        <div class="rationale-metrics-section">
          <div class="rationale-metrics-label">
            <BarChart3 class="rationale-metrics-icon" />
            <SectionLabel text="Key Metrics" variant="accent" />
          </div>
          <CardGrid minWidth={140} gap="md">
            {#each parsedRationale.metrics as metric}
              {@const MetricIcon = getMetricIcon(metric.label)}
              {@const cardVariant = getMetricCardVariant(metric)}
              {@const progressValue = extractProgressValue(metric.value)}
              <InsightCard
                variant={cardVariant}
                border="left"
                padding="sm"
                hoverable={true}
              >
                {#snippet meta()}
                  <div class="rationale-metric-label">
                    <MetricIcon class="rationale-metric-icon" />
                    <span class="rationale-metric-name">{metric.label}</span>
                  </div>
                {/snippet}
                <span class="rationale-metric-value">{metric.value}</span>
                <div class="metric-progress">
                  <div
                    class="metric-progress-fill"
                    style="width: {progressValue}%; background: {getProgressColor(
                      cardVariant,
                    )};"
                  ></div>
                </div>
              </InsightCard>
            {/each}
          </CardGrid>
        </div>
      {/if}
      <!-- Narrative -->
      <div class="rationale-text">
        {@html renderMarkdown(
          parsedRationale.highlightedText || selectionRationale,
        )}
      </div>
    </ExpandableSection>
  {/if}
</Section>

<style>
  /* =========================
	   SOLUTION HERO CARD
	   ========================= */
  .solution-hero-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.875rem;
    padding: var(--space-6);
    margin-bottom: var(--space-4);
  }

  .hero-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-4);
  }

  .hero-badges {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .hero-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
  }

  :global(.hero-icon-svg) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent-dark);
  }

  .hero-title {
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 4vw, 2rem);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: var(--color-text-primary);
    margin-bottom: 0.375rem;
  }

  .hero-codename {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-muted);
    margin-top: var(--space-1);
  }

  .hero-tagline {
    font-size: 0.9375rem;
    color: var(--color-text-muted);
    font-style: italic;
    margin-bottom: var(--space-4);
    line-height: 1.5;
    max-width: 70ch;
  }

  /* Value Block - using InsightCard */
  .value-text {
    font-size: var(--text-base);
    color: var(--color-text-muted);
    line-height: 1.6;
    margin: 0;
    max-width: 70ch;
  }

  /* =========================
	   LAUNCH PARAMETERS STRIP
	   ========================= */
  .launch-params {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-4) var(--space-5) var(--space-5);
    margin-bottom: var(--space-4);
    position: relative;
    overflow: hidden;
  }

  .launch-params-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
    position: relative;
    z-index: 1;
  }

  .launch-params-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: var(--color-text-muted);
    text-transform: uppercase;
    white-space: nowrap;
  }

  .launch-params-line {
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }

  :global(.launch-params-grid) {
    position: relative;
    z-index: 1;
  }

  .param-card {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    padding: 0.875rem 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    position: relative;
    overflow: hidden;
    /* Staggered entrance animation */
    opacity: 0;
    transform: translateY(6px);
    animation: param-enter 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    animation-delay: var(--param-delay, 0s);
  }

  @keyframes param-enter {
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Semantic color variants */
  .param-time {
    --param-color: var(--color-warning);
    --param-bg: rgba(245, 158, 11, 0.08);
  }
  .param-scale {
    --param-color: var(--color-info);
    --param-bg: rgba(59, 130, 246, 0.08);
  }
  .param-cost {
    --param-color: var(--color-success);
    --param-bg: rgba(34, 197, 94, 0.08);
  }
  .param-budget {
    --param-color: var(--viz-cat-4);
    --param-bg: rgba(139, 92, 246, 0.08);
  }

  .param-card:hover {
    border-color: var(--param-color, var(--color-accent));
  }

  .param-icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.25rem;
    height: 2.25rem;
    background: var(--param-bg, var(--color-accent-subtle));
    border-radius: var(--radius-md);
    flex-shrink: 0;
    transition:
      transform 0.25s ease,
      background 0.25s ease;
  }

  .param-card:hover .param-icon-wrap {
    transform: scale(1.05);
    background: var(--param-color, var(--color-accent));
  }

  :global(.param-icon) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--param-color, var(--color-accent));
    transition: color 0.25s ease;
  }

  .param-card:hover :global(.param-icon) {
    color: var(--color-text-on-accent);
  }

  .param-data {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }

  .param-value {
    font-family: var(--font-display);
    font-size: 1.0625rem;
    font-weight: 800;
    color: var(--color-text-primary);
    line-height: 1.1;
    letter-spacing: -0.01em;
  }

  .param-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  /* =========================
	   ADVANTAGES CARD
	   ========================= */
  .advantages-card {
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
    border-radius: var(--radius-lg);
    padding: 1.125rem;
    margin-bottom: var(--space-3);
  }

  .advantages-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: 0.875rem;
  }

  :global(.advantages-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-success);
  }

  .advantages-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-success);
  }

  .advantage-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: 0.625rem;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(34, 197, 94, 0.1);
    border-left: 2px solid transparent;
    border-radius: 0.375rem;
    transition: background-color 0.15s ease, border-left-color 0.15s ease, transform 0.15s ease;
  }

  .advantage-item:hover {
    background: var(--color-success-subtle);
    border-left-color: var(--color-success);
    transform: scale(1.01);
  }

  :global(.check-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-success);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .advantage-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.45;
  }

  /* =========================
	   TARGET AUDIENCE (Personas)
	   ========================= */
  .persona-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .persona-num {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    color: var(--color-text-muted);
    background: var(--color-bg-subtle);
    padding: 0.25rem 0.375rem;
    border-radius: var(--radius-sm);
  }

  .persona-num.primary {
    color: var(--color-accent-dark);
    background: var(--color-accent-glow);
  }

  /* =========================
	   HOW IT WORKS
	   ========================= */
  :global(.how-it-works-card) {
    margin-bottom: var(--space-3);
  }

  .how-it-works-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.how-it-works-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent-dark);
  }

  .how-it-works-title {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: var(--color-accent-dark);
    text-transform: uppercase;
  }

  .how-it-works-content {
    font-size: 0.8125rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
    margin: 0;
    max-width: 70ch;
  }

  /* =========================
	   FEATURE LIST
	   ========================= */
  .feature-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  /* =========================
	   SEO CONTENT ENGINE
	   ========================= */
  .seo-engine-content {
    font-size: 0.8125rem;
    line-height: 1.65;
    color: var(--color-text-secondary);
  }

  .seo-engine-content :global(p) {
    margin-bottom: 0.625rem;
  }

  .seo-engine-content :global(p:last-child) {
    margin-bottom: 0;
  }

  /* =========================
	   SELECTION RATIONALE
	   ========================= */
  .rationale-metrics-section {
    margin-bottom: var(--space-5);
  }

  .rationale-metrics-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  :global(.rationale-metrics-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent-dark);
  }

  .rationale-metric-label {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  :global(.rationale-metric-icon) {
    width: 0.75rem;
    height: 0.75rem;
    color: var(--color-text-muted);
  }

  .rationale-metric-name {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .rationale-metric-value {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  /* Progress bar for metrics */
  .metric-progress {
    width: 100%;
    height: 4px;
    background: var(--color-bg-subtle);
    border-radius: 2px;
    margin-top: var(--space-2);
    overflow: hidden;
  }

  .metric-progress-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .rationale-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.65;
  }

  .rationale-text :global(p) {
    margin-bottom: 0.625rem;
  }

  .rationale-text :global(p:last-child) {
    margin-bottom: 0;
  }

  /* =========================
	   SECTION WRAPPERS
	   ========================= */
  .core-features-section,
  .seo-engine-section {
    margin-bottom: var(--space-6);
  }

  /* =========================
	   TARGET PERSONAS SECTION
	   ========================= */
  .personas-section {
    margin-bottom: var(--space-4);
  }

  .persona-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* =========================
	   BUSINESS MODEL - using InsightCard
	   ========================= */
  :global(.business-model-card) {
    margin-bottom: var(--space-3);
  }

  .business-model-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  :global(.business-model-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-success);
  }

  .business-model-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-success);
    white-space: nowrap;
  }

  .business-model-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.55;
    margin: 0;
  }

  /* =========================
	   CAC VS PAID COMPARISON
	   ========================= */
  .cac-vs-paid {
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-muted);
    margin-left: var(--space-1);
  }

  /* =========================
	   INNOVATION SCORE - using InsightCard
	   ========================= */
  :global(.innovation-card) {
    margin-bottom: var(--space-3);
  }

  .innovation-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
  }

  .innovation-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.innovation-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-warning);
  }

  .innovation-label span {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: var(--color-warning);
    text-transform: uppercase;
  }

  .innovation-score {
    display: flex;
    align-items: baseline;
    gap: 0.125rem;
  }

  .innovation-score .score-value {
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 800;
    color: var(--color-warning);
    line-height: 1;
  }

  .innovation-breakdown {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-top: var(--space-1);
  }

  .innovation-facet {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .innovation-facet.facet-highlight {
    background: transparent;
    border-left: 2px solid var(--color-warning);
    padding: var(--space-2) var(--space-3);
    border-radius: 0 0.375rem 0.375rem 0;
  }

  .facet-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--color-text-muted);
    text-transform: uppercase;
  }

  .facet-highlight .facet-label {
    color: var(--color-warning);
  }

  .facet-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.55;
    margin: 0;
  }

  .facet-highlight .facet-text {
    color: inherit;
  }

  /* =========================
	   DISCOVERY QUERIES - using InsightCard
	   ========================= */
  :global(.discovery-card) {
    margin-bottom: var(--space-3);
  }

  .discovery-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.discovery-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-secondary);
  }

  .discovery-title {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: var(--color-secondary);
    text-transform: uppercase;
  }

  .discovery-queries {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .query-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.75rem;
    background: var(--color-secondary-subtle);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 100px;
    font-size: var(--text-sm);
    color: var(--color-secondary-dark);
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .query-chip:hover {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
  }

  /* =========================
	   RESPONSIVE
	   ========================= */
  @media (max-width: 768px) {
    .param-card {
      padding: 0.75rem 1rem;
    }

    .query-chip {
      padding: 0.3125rem 0.625rem;
      font-size: 0.6875rem;
    }
  }

  @media (max-width: 480px) {
    .hero-title {
      font-size: 1.375rem;
    }

    .launch-params {
      padding: 0.875rem 1rem 1rem;
    }

    .param-icon-wrap {
      width: 2rem;
      height: 2rem;
    }

    :global(.param-icon) {
      width: 1rem;
      height: 1rem;
    }

    .param-value {
      font-size: 0.9375rem;
    }

    .innovation-score .score-value {
      font-size: 1.25rem;
    }

    .cac-vs-paid {
      display: block;
      margin-left: 0;
      margin-top: 0.125rem;
    }
  }
</style>
