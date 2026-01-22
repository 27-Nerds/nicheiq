<script lang="ts">
  import {
    Sparkles,
    Zap,
    Target,
    Layers,
    CheckCircle,
    Clock,
    Globe,
    Rocket,
    DollarSign,
    Users,
    Lightbulb,
    Search,
    FileText,
    Crosshair,
  } from "lucide-svelte";
  import type {
    SolutionDetails,
    ExecutiveDashboard,
    SelectionCriteriaScore,
  } from "$lib/types/report";
  import { renderMarkdown, parseRationaleMetrics } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import SectionHeader from "$lib/components/ui/SectionHeader.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import InsightCard from "$lib/components/ui/InsightCard.svelte";

  interface Props {
    solution: SolutionDetails;
    dashboard: ExecutiveDashboard;
    selectionRationale: string;
    scores?: SelectionCriteriaScore[];
  }

  let { solution, dashboard, selectionRationale, scores }: Props = $props();

  const solutionName = $derived(solution.solution_name || "Solution");
  const snapshot = $derived(dashboard.recommended_solution_snapshot);
  const verdict = $derived(dashboard.go_no_go_verdict);

  // Parse metrics from rationale text
  const parsedRationale = $derived(parseRationaleMetrics(selectionRationale));

  // Get verdict styling
  const getVerdictBadge = (v: string) => {
    if (v === "Go") return { variant: "success" as const, text: "GO" };
    if (v === "No-Go") return { variant: "error" as const, text: "NO-GO" };
    return { variant: "warning" as const, text: v.toUpperCase() };
  };
  const vBadge = $derived(getVerdictBadge(verdict.verdict));

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
</script>

<section id="solution" class="report-section">
  <SectionHeader
    icon={Rocket}
    title="Recommended Solution"
    subtitle="AI-validated product opportunity"
  />

  <!-- Solution Hero Card -->
  <div class="solution-hero-card">
    <div class="hero-top">
      <div class="hero-badges">
        {#if snapshot.project_type}
          <Badge variant="default">{snapshot.project_type}</Badge>
        {/if}
        <Badge variant={vBadge.variant}>{vBadge.text}</Badge>
      </div>
      <div class="hero-sparkle">
        <Sparkles class="sparkle-icon" />
      </div>
    </div>

    <h3 class="hero-title">{solutionName}</h3>

    {#if snapshot.tagline}
      <p class="hero-tagline">{snapshot.tagline}</p>
    {/if}

    <!-- Value Proposition -->
    <div class="value-block">
      <p class="value-text">
        {solution.value_proposition ||
          snapshot.core_value_prop ||
          solution.description}
      </p>
    </div>
  </div>

  <!-- Launch Parameters Strip -->
  {#if solution.estimated_development_time || solution.estimated_indexable_pages || solution.estimated_cac_organic}
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
            <div class="param-glow"></div>
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
            <div class="param-glow"></div>
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
                  <span class="cac-vs-paid">vs {solution.estimated_cac_paid} paid</span>
                {/if}
              </span>
              <span class="param-label">
                Organic CAC
                <Tooltip content={getTermTooltip("CAC")} position="top" />
              </span>
            </div>
            <div class="param-glow"></div>
          </div>
        {/if}
      </CardGrid>
    </div>
  {/if}

  <!-- Innovation Score Card -->
  {#if solution.novelty_score != null}
    <div class="innovation-card">
      <div class="innovation-header">
        <div class="innovation-label">
          <Lightbulb class="innovation-icon" />
          <span>INNOVATION</span>
        </div>
        <div class="innovation-score">
          <span class="score-value">{solution.novelty_score.toFixed(1)}</span>
          <span class="score-max">/10</span>
        </div>
      </div>
      {#if solution.novelty_justification}
        <p class="innovation-text">{solution.novelty_justification}</p>
      {/if}
    </div>
  {/if}

  <!-- Discovery Queries -->
  {#if solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0}
    <div class="discovery-card">
      <div class="discovery-header">
        <Search class="discovery-icon" />
        <span class="discovery-title">HOW USERS FIND YOU</span>
      </div>
      <div class="discovery-queries">
        {#each solution.organic_discovery_queries.slice(0, 8) as query}
          <span class="query-chip">{query}</span>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Pain Points Addressed -->
  {#if solution.pain_points_addressed && solution.pain_points_addressed.length > 0}
    <div class="pain-points-card">
      <div class="pain-points-header">
        <Crosshair class="pain-points-icon" />
        <span class="pain-points-title">PROBLEMS SOLVED</span>
        <Badge variant="muted" size="sm">{solution.pain_points_addressed.length}</Badge>
      </div>
      <ul class="pain-points-list">
        {#each solution.pain_points_addressed.slice(0, 4) as point}
          <li class="pain-point-item">{point}</li>
        {/each}
      </ul>
    </div>
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
          <div class="persona-card" style="--persona-delay: {i * 0.05}s">
            <span class="persona-text">{persona}</span>
          </div>
        {/each}
      </CardGrid>
    </div>
  {/if}

  <!-- Business Model -->
  {#if solution.pricing_strategy}
    <div class="business-model-strip">
      <div class="business-model-label">
        <DollarSign class="business-model-icon" />
        <span>Business Model</span>
      </div>
      <p class="business-model-text">{solution.pricing_strategy}</p>
    </div>
  {/if}

  <!-- Competitive Advantages - Always Visible -->
  {#if solution.differentiation_factors && solution.differentiation_factors.length > 0}
    <div class="advantages-card">
      <div class="advantages-header">
        <Zap class="advantages-icon" />
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

  <!-- Expandable: How It Works -->
  {#if solution.description && solution.description !== solution.value_proposition}
    <ExpandableSection
      title="How It Works"
      icon={FileText}
      variant="default"
    >
      <p class="how-it-works-text">{solution.description}</p>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Core Features -->
  {#if solution.core_features && solution.core_features.length > 0}
    <ExpandableSection
      title="Core Features"
      icon={Layers}
      count={solution.core_features.length}
      variant="accent"
    >
      <CardGrid minWidth={260} gap="md">
        {#each solution.core_features as feature, i}
          <InsightCard
            variant={i < 2 ? "accent" : "default"}
            border={i < 2 ? "left" : "all"}
            hoverable={true}
            padding="sm"
          >
            {#snippet header()}
              <span class="feature-num" class:primary={i < 2}>
                {String(i + 1).padStart(2, "0")}
              </span>
            {/snippet}
            <span class="feature-text">{feature}</span>
          </InsightCard>
        {/each}
      </CardGrid>
    </ExpandableSection>
  {/if}

  <!-- Expandable: SEO Content Engine -->
  {#if solution.content_generation_model}
    <ExpandableSection
      title="SEO Content Engine"
      icon={Globe}
      variant="accent"
    >
      <p class="seo-content-text">{solution.content_generation_model}</p>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Why This Solution -->
  {#if selectionRationale}
    <ExpandableSection
      title="Selection Rationale"
      icon={Target}
      count={parsedRationale.metrics.length > 0 ? parsedRationale.metrics.length : null}
      countSuffix="metrics"
      variant="accent"
    >
      <!-- Extracted Metrics -->
      {#if parsedRationale.metrics.length > 0}
        <div class="rationale-metrics">
          {#each parsedRationale.metrics as metric}
            <div class="metric-chip">
              <span class="metric-value">{metric.value}</span>
              <span class="metric-label">{metric.label}</span>
            </div>
          {/each}
        </div>
      {/if}
      <!-- Narrative -->
      <div class="rationale-text">
        {@html renderMarkdown(parsedRationale.highlightedText || selectionRationale)}
      </div>
    </ExpandableSection>
  {/if}
</section>

<style>
  /* =========================
	   SOLUTION HERO CARD
	   ========================= */
  .solution-hero-card {
    background: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 0.875rem;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    transition: box-shadow 0.2s ease;
  }

  .solution-hero-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  }

  .hero-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .hero-badges {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .hero-sparkle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.15) 0%,
      rgba(229, 90, 40, 0.06) 100%
    );
    border: 1px solid rgba(229, 90, 40, 0.3);
    border-radius: 0.5rem;
    box-shadow: 0 0 12px rgba(229, 90, 40, 0.15);
  }

  :global(.sparkle-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: #e55a28;
    filter: drop-shadow(0 0 2px rgba(229, 90, 40, 0.4));
  }

  .hero-title {
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 4vw, 2rem);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: #18181b;
    margin-bottom: 0.375rem;
  }

  .hero-tagline {
    font-size: 0.9375rem;
    color: #71717a;
    font-style: italic;
    margin-bottom: 1rem;
    line-height: 1.5;
  }

  /* Value Block */
  .value-block {
    background: linear-gradient(
      135deg,
      rgba(229, 90, 40, 0.05) 0%,
      transparent 50%
    );
    border: 1px solid rgba(229, 90, 40, 0.12);
    border-left: 3px solid #e55a28;
    border-radius: 0.5rem;
    padding: 0.875rem 1rem;
  }

  .value-text {
    font-size: 0.875rem;
    color: #71717a;
    line-height: 1.6;
    margin: 0;
  }

  /* =========================
	   LAUNCH PARAMETERS STRIP
	   ========================= */
  .launch-params {
    background: linear-gradient(180deg, #fafafa 0%, #f4f4f5 100%);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem 1.25rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
  }

  /* Subtle grid pattern overlay */
  .launch-params::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image: linear-gradient(rgba(0, 0, 0, 0.02) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 0, 0, 0.02) 1px, transparent 1px);
    background-size: 20px 20px;
    pointer-events: none;
    opacity: 0.5;
  }

  .launch-params-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    position: relative;
    z-index: 1;
  }

  .launch-params-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #a1a1aa;
    text-transform: uppercase;
    white-space: nowrap;
  }

  .launch-params-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(
      90deg,
      rgba(0, 0, 0, 0.08) 0%,
      transparent 100%
    );
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
    background: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 0.625rem;
    position: relative;
    overflow: hidden;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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

  .param-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  }

  .param-card:hover .param-glow {
    opacity: 1;
  }

  /* Semantic color variants */
  .param-time {
    --param-color: #f59e0b;
    --param-bg: rgba(245, 158, 11, 0.08);
  }
  .param-scale {
    --param-color: #3b82f6;
    --param-bg: rgba(59, 130, 246, 0.08);
  }
  .param-cost {
    --param-color: #22c55e;
    --param-bg: rgba(34, 197, 94, 0.08);
  }

  .param-card:hover {
    border-color: var(--param-color, #e55a28);
  }

  .param-icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.25rem;
    height: 2.25rem;
    background: var(--param-bg, rgba(229, 90, 40, 0.08));
    border-radius: 0.5rem;
    flex-shrink: 0;
    transition:
      transform 0.25s ease,
      background 0.25s ease;
  }

  .param-card:hover .param-icon-wrap {
    transform: scale(1.05);
    background: var(--param-color, #e55a28);
  }

  :global(.param-icon) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--param-color, #e55a28);
    transition: color 0.25s ease;
  }

  .param-card:hover :global(.param-icon) {
    color: #ffffff;
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
    color: #18181b;
    line-height: 1.1;
    letter-spacing: -0.01em;
  }

  .param-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 500;
    color: #71717a;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  /* Accent glow on hover */
  .param-glow {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(
      90deg,
      transparent,
      var(--param-color, #e55a28),
      transparent
    );
    opacity: 0;
    transition: opacity 0.25s ease;
  }

  /* =========================
	   ADVANTAGES CARD
	   ========================= */
  .advantages-card {
    background: linear-gradient(
      135deg,
      rgba(34, 197, 94, 0.05) 0%,
      transparent 50%
    );
    border: 1px solid rgba(34, 197, 94, 0.15);
    border-radius: 0.75rem;
    padding: 1.125rem;
    margin-bottom: 0.75rem;
  }

  .advantages-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.875rem;
  }

  :global(.advantages-icon) {
    width: 1rem;
    height: 1rem;
    color: #22c55e;
  }

  .advantages-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: #22c55e;
  }

  .advantage-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.625rem;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(34, 197, 94, 0.1);
    border-left: 2px solid transparent;
    border-radius: 0.375rem;
    transition: all 0.15s ease;
  }

  .advantage-item:hover {
    background: rgba(34, 197, 94, 0.08);
    border-left-color: #22c55e;
    transform: scale(1.01);
  }

  :global(.check-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: #22c55e;
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .advantage-text {
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.45;
  }

  /* =========================
	   FEATURES (inside ExpandableSection)
	   ========================= */
  .feature-num {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    color: var(--color-text-muted);
    background: rgba(0, 0, 0, 0.06);
    padding: 0.25rem 0.375rem;
    border-radius: 0.25rem;
    transition: all 0.15s ease;
  }

  .feature-num.primary {
    color: var(--color-accent);
    background: rgba(229, 90, 40, 0.12);
  }

  .feature-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* Rationale */
  .rationale-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.875rem;
    padding-bottom: 0.875rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }

  .metric-chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 0.375rem;
    min-width: 65px;
  }

  .metric-chip .metric-value {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 700;
    color: #e55a28;
  }

  .metric-chip .metric-label {
    font-size: 0.5rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #a1a1aa;
  }

  .rationale-text {
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.65;
  }

  .rationale-text :global(p) {
    margin-bottom: 0.625rem;
  }

  .rationale-text :global(p:last-child) {
    margin-bottom: 0;
  }

  /* =========================
	   TARGET PERSONAS SECTION
	   ========================= */
  .personas-section {
    margin-bottom: 1rem;
  }

  .persona-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    padding: 0.875rem 1rem;
    transition: all 0.15s ease;
    /* Staggered entrance animation */
    opacity: 0;
    transform: translateY(6px);
    animation: persona-enter 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    animation-delay: var(--persona-delay, 0s);
  }

  @keyframes persona-enter {
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .persona-card:hover {
    border-color: rgba(99, 102, 241, 0.3);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }

  .persona-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  /* =========================
	   BUSINESS MODEL STRIP
	   ========================= */
  .business-model-strip {
    display: flex;
    align-items: flex-start;
    gap: 0.875rem;
    padding: 0.875rem 1rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-success);
    border-radius: 0.625rem;
    margin-bottom: 0.75rem;
  }

  .business-model-label {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    flex-shrink: 0;
  }

  :global(.business-model-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-success);
  }

  .business-model-label span {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
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
    color: #a1a1aa;
    margin-left: 0.25rem;
  }

  /* =========================
	   INNOVATION SCORE CARD
	   ========================= */
  .innovation-card {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.06) 0%, transparent 60%);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
  }

  .innovation-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }

  .innovation-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  :global(.innovation-icon) {
    width: 1rem;
    height: 1rem;
    color: #f59e0b;
  }

  .innovation-label span {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #f59e0b;
    text-transform: uppercase;
  }

  .innovation-score {
    display: flex;
    align-items: baseline;
    gap: 0.125rem;
  }

  .innovation-score .score-value {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 800;
    color: #f59e0b;
    line-height: 1;
  }

  .innovation-score .score-max {
    font-size: 0.8125rem;
    font-weight: 500;
    color: #a1a1aa;
  }

  .innovation-text {
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.55;
    margin: 0;
    font-style: italic;
  }

  /* =========================
	   DISCOVERY QUERIES
	   ========================= */
  .discovery-card {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, transparent 60%);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
  }

  .discovery-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  :global(.discovery-icon) {
    width: 1rem;
    height: 1rem;
    color: #6366f1;
  }

  .discovery-title {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #6366f1;
    text-transform: uppercase;
  }

  .discovery-queries {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .query-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.75rem;
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 100px;
    font-size: 0.75rem;
    color: #4f46e5;
    transition: all 0.15s ease;
  }

  .query-chip:hover {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
  }

  /* =========================
	   PAIN POINTS ADDRESSED
	   ========================= */
  .pain-points-card {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.04) 0%, transparent 60%);
    border: 1px solid rgba(239, 68, 68, 0.15);
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
  }

  .pain-points-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.625rem;
  }

  :global(.pain-points-icon) {
    width: 1rem;
    height: 1rem;
    color: #ef4444;
  }

  .pain-points-title {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: #ef4444;
    text-transform: uppercase;
  }

  .pain-points-list {
    margin: 0;
    padding-left: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .pain-point-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.45;
    padding-left: 1rem;
    position: relative;
  }

  .pain-point-item::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.5rem;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #ef4444;
  }

  /* =========================
	   HOW IT WORKS TEXT
	   ========================= */
  .how-it-works-text {
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.65;
    margin: 0;
  }

  /* =========================
	   SEO CONTENT ENGINE TEXT
	   ========================= */
  .seo-content-text {
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.65;
    margin: 0;
  }

  /* =========================
	   RESPONSIVE
	   ========================= */
  @media (max-width: 768px) {
    .param-card {
      padding: 0.75rem 1rem;
    }

    .business-model-strip {
      flex-direction: column;
      gap: 0.5rem;
    }

    .innovation-card,
    .discovery-card,
    .pain-points-card {
      padding: 0.875rem 1rem;
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

    .persona-card {
      padding: 0.75rem 0.875rem;
    }

    .business-model-strip {
      padding: 0.75rem 0.875rem;
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
