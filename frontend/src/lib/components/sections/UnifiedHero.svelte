<script lang="ts">
  import {
    CheckCircle,
    AlertTriangle,
    Target,
    TrendingUp,
    TrendingDown,
    Users,
    Search,
    Crosshair,
    Compass,
    Globe,
    Layers,
    Calculator,
    RefreshCw,
    Clock,
    Minus,
    Quote,
    Rocket,
    Shield,
    HelpCircle,
    ArrowDown,
  } from "lucide-svelte";
  import type {
    Report,
    RefinementHighlights,
    SEOCalculationTransparency,
    TrendLongevity,
  } from "$lib/types/report";
  import {
    formatNumber,
    formatScorePercent,
    renderMarkdown,
    stripMarkdown,
  } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import { getTermTooltip } from "$lib/stores/glossary";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";
  import IconListItem from "$lib/components/ui/IconListItem.svelte";
  import { AlertCircle } from "lucide-svelte";

  interface Props {
    report: Report;
    nicheName: string;
    nicheDescription: string;
    funnelStats: {
      scanned: number;
      relevant: number;
      analyzed: number;
      problems: number;
    };
    refinementHighlights?: RefinementHighlights;
    seoCalculationTransparency?: SEOCalculationTransparency;
    trends?: TrendLongevity;
    previewMode?: boolean;
    heroZoneOnly?: boolean;
  }

  let {
    report,
    nicheName,
    nicheDescription,
    funnelStats,
    refinementHighlights,
    seoCalculationTransparency,
    trends,
    previewMode = false,
    heroZoneOnly = false,
  }: Props = $props();

  // Extract data from report
  const dashboard = $derived(report.executive_dashboard);
  const verdict = $derived(dashboard?.go_no_go_verdict);
  const solution = $derived(dashboard?.recommended_solution_snapshot);
  const corePain = $derived(dashboard?.core_pain_point);
  const metrics = $derived(dashboard?.key_metrics);
  const confidenceScore = $derived(dashboard?.confidence_score ?? 0);
  const solutionDetails = $derived(report.selected_solution_details);

  // Match pain_points_addressed to detailed_pain_points for enrichment
  const addressedPainPoint = $derived.by(() => {
    const addressed = solutionDetails?.pain_points_addressed;
    const detailed = report.detailed_pain_points;
    if (addressed?.length && detailed?.length) {
      return detailed.find((dp) => dp.title === addressed[0]) ?? null;
    }
    return null;
  });

  // Primary pain point: prefer addressed, fall back to corePain
  const heroPain = $derived(addressedPainPoint ?? null);
  const heroPainTitle = $derived(heroPain?.title ?? corePain?.title ?? "");
  const heroPainSeverity = $derived(
    heroPain?.severity_score ?? corePain?.severity_score ?? 0,
  );
  const heroPainWTP = $derived(
    heroPain?.willingness_to_pay ?? corePain?.willingness_to_pay_score ?? 0,
  );
  const heroPainOpportunity = $derived(heroPain?.opportunity_level ?? null);
  const heroPainSolutionApproach = $derived(
    heroPain?.solution_approach ?? null,
  );

  // Get attributed quotes from evidence appendix
  const painQuoteSources = $derived.by(() => {
    const title = heroPainTitle;
    const sources = report.evidence_appendix?.pain_point_quote_sources;
    if (title && sources?.length) {
      const match = sources.find((s) => s.pain_point_title === title);
      return match?.quotes_with_sources?.slice(0, 2) ?? [];
    }
    return [];
  });

  // Fallback quotes from representative_quotes (unattributed)
  const fallbackQuotes = $derived.by(() => {
    if (painQuoteSources.length > 0) return [];
    const quotes = heroPain?.representative_quotes ?? [];
    return quotes.slice(0, 2);
  });

  // Pain point analytics
  const painAnalytics = $derived(report.pain_point_analytics);

  // Market signals
  const opportunityScore = $derived(
    report.market_analytics?.overall_opportunity_score ?? 0,
  );
  const trendDirection = $derived(trends?.trend_direction ?? "Unknown");
  const saturationScore = $derived(
    report.competitive_analytics?.market_saturation_score ?? 0,
  );

  let descriptionExpanded = $state(false);

  const scrollToDiagnostics = () => {
    document
      .getElementById("score-diagnostics")
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  // Score improvement percentage for SEO transparency
  const scoreImprovement = $derived.by(() => {
    if (!seoCalculationTransparency) return null;
    const { baseline_seo_score, refined_seo_score } =
      seoCalculationTransparency;
    if (
      baseline_seo_score == null ||
      refined_seo_score == null ||
      baseline_seo_score === 0
    )
      return null;
    return (
      ((refined_seo_score - baseline_seo_score) / baseline_seo_score) *
      100
    ).toFixed(1);
  });

  // Get trend icon
  const getTrendIcon = (direction?: string) => {
    const d = direction?.toLowerCase() || "";
    if (d.includes("grow")) return TrendingUp;
    if (d.includes("declin")) return TrendingDown;
    return Minus;
  };

  // Check for absorbed content
  const hasStrategicInsights = $derived(
    (refinementHighlights?.top_strategic_insights &&
      refinementHighlights.top_strategic_insights.length > 0) ||
      refinementHighlights?.geographic_priority ||
      refinementHighlights?.feature_priority ||
      refinementHighlights?.category_pivot_recommendation ||
      seoCalculationTransparency,
  );

  const hasRiskAssessment = $derived(
    trends?.trend_reversal_risks?.length ||
      trends?.trend_direction ||
      trends?.timing_recommendation,
  );

  // Semantic score color - communicates health at a glance
  const getScoreColor = (
    score: number | null | undefined,
  ): "success" | "warning" | "error" | "muted" => {
    if (score == null) return "muted";
    if (score >= 0.8) return "success"; // Excellent (green)
    if (score >= 0.6) return "warning"; // Moderate (amber)
    return "error"; // Weak (red)
  };

  // Human-readable verdict label
  const getScoreLabel = (score: number | null | undefined): string => {
    if (score == null) return "N/A";
    if (score >= 0.9) return "Exceptional";
    if (score >= 0.8) return "Excellent";
    if (score >= 0.7) return "Strong";
    if (score >= 0.6) return "Moderate";
    if (score >= 0.5) return "Fair";
    return "Needs Work";
  };

  // Legacy alias for backward compat
  const getScoreClass = getScoreColor;

  // Get verdict color class
  const getVerdictClass = (v: string) => {
    if (v === "Go") return "verdict-go";
    if (v === "Conditional") return "verdict-conditional";
    return "verdict-nogo";
  };

  // Saturation helpers
  const getSaturationLabel = (score: number): string => {
    if (score <= 0.3) return "Low";
    if (score <= 0.6) return "Medium";
    return "High";
  };

  const getSaturationClass = (score: number): string => {
    if (score <= 0.3) return "success";
    if (score <= 0.6) return "warning";
    return "error";
  };

  const getTrendClass = (trend: string | null | undefined): string => {
    if (trend?.toLowerCase().includes("grow")) return "success";
    if (trend?.toLowerCase().includes("declin")) return "error";
    return "warning";
  };

  const getRiskClass = (risk: string): string => {
    const r = risk.toLowerCase();
    if (r === "low") return "success";
    if (r === "high") return "error";
    return "warning";
  };

  // Tooltip definitions
  const tooltips = {
    verdict: {
      go: "Strong opportunity with favorable market conditions. Proceed with confidence.",
      conditional:
        "Promising opportunity with some caveats. Review risk factors before proceeding.",
      nogo: "Unfavorable conditions detected. Consider pivoting or choosing an alternative.",
    },
    confidence:
      "Average of market fit, competitive advantage, feasibility, and SEO scores. Directly determines the Go/Conditional/No-Go verdict.",
    opportunity:
      "Overall market opportunity score combining demand signals, growth potential, and monetization viability.",
    trend:
      "Market momentum direction based on search trends, social mentions, and competitive activity.",
    saturation:
      "How crowded the market is. Low = blue ocean, High = intense competition.",
    risk: "Overall risk assessment factoring technical complexity, market uncertainty, and competitive threats.",
    researchDepth:
      "Based on pain point quality — severity scores, willingness-to-pay signals, quote evidence density, and cross-platform validation. Premium = strong evidence across multiple signals. Standard = solid data with some gaps. Basic = minimum viable evidence.",
    pipelineScanned:
      "Reddit discussion URLs found via search. These are the raw results before relevance filtering.",
    pipelineRelevant:
      "Posts kept after filtering out off-topic and low-quality content.",
    pipelineAnalyzed:
      "Posts that underwent deep AI analysis for pain points, sentiment, and market signals.",
    pipelineProblems:
      "Unique pain points extracted. The entire report is built on these — more problems = richer analysis.",
    painSeverity:
      "How much this problem blocks users' workflows or business goals. 80%+ means a critical blocker causing measurable losses. Based on functional impact, not emotional volume.",
    footerSearches:
      "Monthly Google searches for niche keywords — shows how many people are actively looking for solutions. 10K+ indicates solid demand.",
    footerKeywords:
      "Unique keywords analyzed for SEO. More keywords = more pages you can rank for. Check quality in the SEO section.",
    footerCompetitors:
      "Direct competitors in this niche. Fewer = easier entry. Check their profiles in the competitive section.",
  };

  const getVerdictTooltip = (v: string | null): string => {
    if (v === "Go") return tooltips.verdict.go;
    if (v === "Conditional") return tooltips.verdict.conditional;
    return tooltips.verdict.nogo;
  };

  // Context-aware score tooltips
  const GO_THRESHOLD = 0.6;

  const marketFitTooltip = $derived.by(() => {
    const score = metrics?.market_fit_score;
    if (score == null) return "Market demand alignment — no data available";
    const pct = Math.round(score * 100);
    const passes = score >= GO_THRESHOLD;
    return `Market Fit: ${pct}%\nMeasures alignment with validated market demand and pain points.\n${passes ? `Meets Go threshold (\u2265${GO_THRESHOLD * 100}%)` : `Below Go threshold (\u2265${GO_THRESHOLD * 100}%) \u2014 limits verdict to Conditional`}`;
  });

  const techFeasibilityTooltip = $derived.by(() => {
    const score = metrics?.technical_feasibility_score;
    if (score == null) return "Technical feasibility — no data available";
    const pct = Math.round(score * 100);
    const passes = score >= GO_THRESHOLD;
    return `Feasibility: ${pct}%\nTechnical complexity and resource requirements for implementation.\n${passes ? `Meets Go threshold (\u2265${GO_THRESHOLD * 100}%)` : `Below Go threshold (\u2265${GO_THRESHOLD * 100}%) \u2014 limits verdict to Conditional`}`;
  });

  const seoTooltip = $derived.by(() => {
    const score = metrics?.seo_potential_score;
    if (score == null) return "SEO potential — no data available";
    const pct = Math.round(score * 100);
    return `SEO Score: ${pct}%\nOrganic search growth potential based on keyword landscape.`;
  });

  const soloDevTooltip = $derived.by(() => {
    const score = metrics?.solo_dev_feasibility;
    if (score == null) return "Solo dev feasibility — no data available";
    const pct = Math.round(score * 100);
    return `Solo Dev: ${pct}%\nSuitability for a single developer to build and launch.`;
  });

  const compEdgeTooltip = $derived.by(() => {
    const score = metrics?.competitive_advantage_score;
    if (score == null) return "Competitive edge — no data available";
    const pct = Math.round(score * 100);
    return `Comp. Edge: ${pct}%\nCompetitive positioning and differentiation strength.`;
  });

  // Context-aware hero tooltips
  const opportunityScoreTooltip = $derived.by(() => {
    const mf = metrics?.market_fit_score;
    const ca = metrics?.competitive_advantage_score;
    const tf = metrics?.technical_feasibility_score;
    const seo = metrics?.seo_potential_score;
    const avg = confidenceScore;
    const v = verdict?.verdict;

    let parts = [`Opportunity Score: ${Math.round(avg * 100)}%`];
    parts.push(
      `Average of: Market Fit (${mf != null ? Math.round(mf * 100) + "%" : "N/A"}), Comp. Edge (${ca != null ? Math.round(ca * 100) + "%" : "N/A"}), Feasibility (${tf != null ? Math.round(tf * 100) + "%" : "N/A"}), SEO (${seo != null ? Math.round(seo * 100) + "%" : "N/A"})`,
    );
    parts.push("");
    if (v === "Go") {
      parts.push("Verdict: Go \u2014 all thresholds met.");
    } else if (v === "Conditional") {
      const gates: string[] = [];
      if (avg < 0.75) gates.push(`avg ${Math.round(avg * 100)}% < 75%`);
      if (mf != null && mf < 0.6)
        gates.push(`Market Fit ${Math.round(mf * 100)}% < 60%`);
      if (tf != null && tf < 0.6)
        gates.push(`Feasibility ${Math.round(tf * 100)}% < 60%`);
      parts.push(
        `Verdict: Conditional \u2014 ${gates.length > 0 ? gates.join(", ") : "trend/timing factors applied"}.`,
      );
    } else {
      parts.push("Verdict: No-Go \u2014 scores below Conditional thresholds.");
    }
    return parts.join("\n");
  });

  const riskBadgeTooltip = $derived.by(() => {
    const risk = verdict?.risk_level ?? "Unknown";
    const tc = verdict?.trend_context;
    let parts = [`Risk Level: ${risk}`];
    if (risk === "Low")
      parts.push("Strong scores and favorable market trends.");
    else if (risk === "Medium")
      parts.push("Mixed signals \u2014 some score or trend concerns.");
    else
      parts.push(
        "Significant concerns \u2014 validate thoroughly before building.",
      );
    if (tc) parts.push(`\nTrend adjustment: ${tc}`);
    if (verdict?.primary_concern)
      parts.push(`Primary concern: ${verdict.primary_concern}`);
    return parts.join("\n");
  });
</script>

<section id="unified-hero" class="unified-hero">
  <!-- ========== HERO ZONE (Dark Gradient) ========== -->
  <div class="hero-zone" class:hero-zone--standalone={heroZoneOnly} class:hero-zone--preview={previewMode}>
    <div class="hero-split">
      <!-- Left Column: Verdict Box + Risk Badge -->
      <div class="hero-left">
        {#if previewMode}
          <div class="verdict-locked">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <span class="verdict-locked-label">Select a solution to generate</span>
          </div>
        {:else}
          <div
            class="verdict-giant {getVerdictClass(verdict?.verdict ?? 'No-Go')}"
          >
            <span class="verdict-score-label">
              OPPORTUNITY SCORE <Tooltip
                content={opportunityScoreTooltip}
                position="bottom"
              />
            </span>
            <span class="verdict-percentage"
              >{formatScorePercent(confidenceScore)}</span
            >
            <div class="verdict-label-row">
              {#if verdict?.verdict === "Go"}
                <CheckCircle class="verdict-icon-large" />
              {:else if verdict?.verdict === "Conditional"}
                <Shield class="verdict-icon-large" />
              {:else}
                <AlertCircle class="verdict-icon-large" />
              {/if}
              <span class="verdict-label-text"
                >{verdict?.verdict?.toUpperCase() ?? "ANALYZING"}</span
              >
            </div>
            <div class="verdict-risk-badge">
              <Tooltip content={riskBadgeTooltip} position="bottom">
                {#snippet children()}
                  <Badge
                    variant={verdict?.risk_level?.toLowerCase() === "low"
                      ? "success"
                      : verdict?.risk_level?.toLowerCase() === "medium"
                        ? "info"
                        : "muted"}
                    size="sm"
                  >
                    {verdict?.risk_level ?? "Unknown"} Risk
                  </Badge>
                {/snippet}
              </Tooltip>
              {#if dashboard?.research_depth_label}
                <Tooltip content={tooltips.researchDepth} position="bottom">
                  {#snippet children()}
                    <Badge variant="muted" size="sm">
                      {dashboard.research_depth_label}
                    </Badge>
                  {/snippet}
                </Tooltip>
              {/if}
            </div>
            <button class="verdict-breakdown-link" onclick={scrollToDiagnostics}>
              See score breakdown ↓
            </button>
          </div>
        {/if}
      </div>

      <!-- Right Column: Niche Info + Signal Chips -->
      <div class="hero-right">
        <h1 class="niche-title">{nicheName}</h1>
        <div class="niche-description-wrapper">
          <!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
          <p
            class="niche-description"
            class:expanded={descriptionExpanded}
            onclick={() => (descriptionExpanded = !descriptionExpanded)}
            role="button"
            tabindex="0"
            onkeydown={(e) =>
              e.key === "Enter" && (descriptionExpanded = !descriptionExpanded)}
          >
            {nicheDescription}
          </p>
          {#if !descriptionExpanded && nicheDescription?.length > 150}
            <button
              class="expand-btn"
              onclick={() => (descriptionExpanded = true)}
            >
              Show more
            </button>
          {/if}
        </div>

        <!-- Signal Chips (hidden in preview — Phase 2 data only) -->
        {#if !previewMode}
        <div class="signal-chips">
          <Tooltip content={tooltips.opportunity} position="bottom">
            {#snippet children()}
              <div class="signal-chip">
                <span class="signal-value"
                  >{formatScorePercent(opportunityScore)}</span
                >
                <span class="signal-label">Opportunity</span>
              </div>
            {/snippet}
          </Tooltip>

          <Tooltip content={tooltips.trend} position="bottom">
            {#snippet children()}
              <div class="signal-chip">
                <span class="signal-value {getTrendClass(trendDirection)}-text">
                  {#if trendDirection?.toLowerCase().includes("grow")}
                    <TrendingUp size={14} class="signal-icon-inline" />
                  {:else if trendDirection?.toLowerCase().includes("declin")}
                    <TrendingDown size={14} class="signal-icon-inline" />
                  {:else}
                    <Minus size={14} class="signal-icon-inline" />
                  {/if}
                  {trendDirection}
                </span>
                <span class="signal-label">Trend</span>
              </div>
            {/snippet}
          </Tooltip>

          <Tooltip content={tooltips.saturation} position="bottom">
            {#snippet children()}
              <div class="signal-chip">
                <span
                  class="signal-value {getSaturationClass(
                    saturationScore,
                  )}-text"
                >
                  {getSaturationLabel(saturationScore)}
                </span>
                <span class="signal-label">Saturation</span>
              </div>
            {/snippet}
          </Tooltip>

          <Tooltip content={tooltips.risk} position="bottom">
            {#snippet children()}
              <div class="signal-chip">
                <span
                  class="signal-value {getRiskClass(
                    verdict?.risk_level ?? 'Medium',
                  )}-text"
                >
                  {verdict?.risk_level ?? "Unknown"}
                </span>
                <span class="signal-label">Risk</span>
              </div>
            {/snippet}
          </Tooltip>
        </div>
        {/if}
      </div>
    </div>

    <!-- Research Pipeline (Funnel) -->
    <div class="research-pipeline">
      <div class="pipeline-stage">
        <span class="pipeline-num">{funnelStats.scanned}</span>
        <span class="pipeline-label">SCANNED</span>
      </div>
      <div class="pipeline-arrow"></div>
      <div class="pipeline-stage">
        <span class="pipeline-num">{funnelStats.relevant}</span>
        <span class="pipeline-label">RELEVANT</span>
      </div>
      <div class="pipeline-arrow"></div>
      <div class="pipeline-stage">
        <span class="pipeline-num">{funnelStats.analyzed}</span>
        <span class="pipeline-label">EXAMINED</span>
      </div>
      <div class="pipeline-arrow"></div>
      <div class="pipeline-stage highlight">
        <span class="pipeline-num">{funnelStats.problems}</span>
        <span class="pipeline-label">PROBLEMS</span>
      </div>
    </div>
  </div>

  <!-- ========== CONTENT ZONE (Light Background) ========== -->
  {#if !heroZoneOnly}
  <div class="content-zone">
    <!-- Pain/Solution Cards - Overlapping Layout -->
    <div class="cards-container" class:cards-container--preview={previewMode}>
      <!-- Evidence Wall Card -->
      {#if heroPain || corePain}
        <div class="hero-card hero-card--pain">
          <!-- Band 1: Pain Point Identity -->
          <div class="card-header">
            <Target class="card-icon pain" />
            <span class="card-badge"
              >{addressedPainPoint
                ? "PROBLEM ADDRESSED"
                : "CORE PAIN POINT"}</span
            >
          </div>
          <h3 class="pain-title">{heroPainTitle}</h3>

          <div class="pain-stats">
            <div class="pain-stat">
              <span class="pain-stat-value"
                >{formatScorePercent(heroPainSeverity)}</span
              >
              <span class="pain-stat-label">
                Severity <Tooltip
                  content={tooltips.painSeverity}
                  position="top"
                />
              </span>
            </div>
            <div class="pain-stat-divider"></div>
            <div class="pain-stat">
              <span class="pain-stat-value"
                >{formatScorePercent(heroPainWTP)}</span
              >
              <span class="pain-stat-label">
                WTP <Tooltip content={getTermTooltip("WTP")} position="top" />
              </span>
            </div>
            {#if heroPainOpportunity}
              <Badge
                variant={heroPainOpportunity === "high"
                  ? "success"
                  : heroPainOpportunity === "medium"
                    ? "warning"
                    : "muted"}
                size="sm"
              >
                {heroPainOpportunity.toUpperCase()}
              </Badge>
            {:else if corePain?.source_platform}
              <Badge variant="muted" size="sm">{corePain.source_platform}</Badge
              >
            {/if}
          </div>

          <!-- Solution approach callout -->
          {#if heroPainSolutionApproach}
            <div class="solution-approach-callout">
              <Crosshair class="callout-icon" />
              <p class="callout-text">{heroPainSolutionApproach}</p>
            </div>
          {/if}

          <!-- Band 2: Voice of the Customer -->
          {#if painQuoteSources.length > 0}
            <div class="pain-quotes-section">
              {#each painQuoteSources as qs}
                <blockquote class="pain-quote">
                  <Quote class="quote-icon" />
                  <div>
                    <p>{stripMarkdown(qs.quote)}</p>
                    <span class="pain-quote-attribution">
                      {qs.subreddit} &middot; &#9650;{qs.score}
                    </span>
                  </div>
                </blockquote>
              {/each}
            </div>
          {:else if fallbackQuotes.length > 0}
            <div class="pain-quotes-section">
              {#each fallbackQuotes as q}
                <blockquote class="pain-quote">
                  <Quote class="quote-icon" />
                  <p>{stripMarkdown(q)}</p>
                </blockquote>
              {/each}
            </div>
          {:else if corePain?.representative_quote}
            <div class="pain-quotes-section">
              <blockquote class="pain-quote">
                <Quote class="quote-icon" />
                <p>{stripMarkdown(corePain.representative_quote)}</p>
              </blockquote>
            </div>
          {/if}

          <!-- Band 3: Evidence Stats Strip -->
          {#if painAnalytics}
            <div class="pain-evidence-strip">
              <span class="pain-evidence-stat">
                {painAnalytics.total_pain_points} problems
              </span>
              {#if painAnalytics.high_severity_count}
                <span class="pain-evidence-stat pain-evidence-stat--hot">
                  {painAnalytics.high_severity_count} high-severity
                </span>
              {/if}
              {#if heroPain?.source_platforms?.length}
                {#each heroPain.source_platforms.slice(0, 2) as platform}
                  <Badge variant="muted" size="sm">{platform}</Badge>
                {/each}
              {/if}
            </div>
          {/if}

          <a href="#pain-analysis" class="pain-cta">
            See full pain analysis
            <ArrowDown class="cta-arrow" />
          </a>
        </div>
      {/if}

      <!-- Preview gate: separates clear Phase 1 data from blurred Phase 2 -->
      {#if previewMode}
        <div class="preview-gate">
          <span class="preview-gate-label">Unlocks with Deep Research</span>
        </div>
      {/if}

      <!-- Solution Teaser (Enhanced - links to full solution section) -->
      {#if solution}
        <div class="solution-teaser" class:preview-locked={previewMode}>
          <div class="teaser-header">
            <Rocket class="teaser-icon" />
            <span class="teaser-badge">RECOMMENDED SOLUTION</span>
          </div>
          <h3 class="teaser-name" class:preview-blur={previewMode}>{solution.name}</h3>
          <p class="teaser-tagline" class:preview-blur={previewMode}>{solution.tagline}</p>

          <!-- Core value prop -->
          {#if solution.core_value_prop}
            <p class="teaser-value-prop" class:preview-blur={previewMode}>{solution.core_value_prop}</p>
          {/if}

          <!-- Target personas (unique data, not in metrics panel) -->
          {#if solutionDetails?.target_personas?.length}
            <div class="teaser-target" class:preview-blur={previewMode}>
              <Users class="teaser-target-icon" />
              <span class="teaser-target-text"
                >{solutionDetails.target_personas.join(", ")}</span
              >
            </div>
          {/if}

          <!-- Differentiator badges (unique data) -->
          {#if solutionDetails?.differentiation_factors?.length}
            <div class="teaser-badges" class:preview-blur={previewMode}>
              {#each solutionDetails.differentiation_factors.slice(0, 3) as factor}
                <Badge variant="muted" size="sm">{factor}</Badge>
              {/each}
            </div>
          {:else if solution.project_type}
            <!-- Fallback to project type if no differentiators -->
            <div class="teaser-badges" class:preview-blur={previewMode}>
              <Badge variant="muted" size="sm">{solution.project_type}</Badge>
            </div>
          {/if}

          <a href="#solution" class="teaser-cta">
            View Solution Details
            <ArrowDown class="cta-arrow" />
          </a>
        </div>
      {/if}
    </div>

    <!-- Score Diagnostics Panel -->
    <div id="score-diagnostics" class="metrics-panel" class:preview-locked={previewMode}>
      <div class="metrics-panel-header">
        <span class="metrics-panel-title">SCORE DIAGNOSTICS</span>
      </div>

      <div class="metrics-cells">
        <!-- Market Fit -->
        <div class="metric-cell" style="--cell-delay: 0.1s">
          <span class:preview-blur={previewMode}>
            <ProgressRing
              value={metrics?.market_fit_score ?? 0}
              size={52}
              strokeWidth={4}
              color={getScoreColor(metrics?.market_fit_score)}
              showValue={true}
              showTooltip={true}
              flat={true}
              label="Market Fit"
              description={marketFitTooltip}
            />
          </span>
          <span class="metric-label">Market Fit</span>
          <span
            class="metric-verdict {getScoreColor(
              metrics?.market_fit_score,
            )}-text"
            class:preview-blur={previewMode}
          >
            {getScoreLabel(metrics?.market_fit_score)}
          </span>
          {#if metrics?.market_fit_score != null}
            <span
              class="threshold-badge {metrics.market_fit_score >= 0.6
                ? 'passes'
                : 'below'}"
              class:preview-blur={previewMode}
            >
              {metrics.market_fit_score >= 0.6
                ? "Passes Go"
                : "Below Go threshold"}
            </span>
          {/if}
        </div>

        <!-- Feasibility -->
        <div class="metric-cell" style="--cell-delay: 0.15s">
          <span class:preview-blur={previewMode}>
            <ProgressRing
              value={metrics?.technical_feasibility_score ?? 0}
              size={52}
              strokeWidth={4}
              color={getScoreColor(metrics?.technical_feasibility_score)}
              showValue={true}
              showTooltip={true}
              flat={true}
              label="Feasibility"
              description={techFeasibilityTooltip}
            />
          </span>
          <span class="metric-label">Feasibility</span>
          <span
            class="metric-verdict {getScoreColor(
              metrics?.technical_feasibility_score,
            )}-text"
            class:preview-blur={previewMode}
          >
            {getScoreLabel(metrics?.technical_feasibility_score)}
          </span>
          {#if metrics?.technical_feasibility_score != null}
            <span
              class="threshold-badge {metrics.technical_feasibility_score >= 0.6
                ? 'passes'
                : 'below'}"
              class:preview-blur={previewMode}
            >
              {metrics.technical_feasibility_score >= 0.6
                ? "Passes Go"
                : "Below Go threshold"}
            </span>
          {/if}
        </div>

        <!-- SEO Score -->
        <div class="metric-cell" style="--cell-delay: 0.2s">
          <span class:preview-blur={previewMode}>
            <ProgressRing
              value={metrics?.seo_potential_score ?? 0}
              size={52}
              strokeWidth={4}
              color={getScoreColor(metrics?.seo_potential_score)}
              showValue={true}
              showTooltip={true}
              flat={true}
              label="SEO Score"
              description={seoTooltip}
            />
          </span>
          <span class="metric-label">SEO</span>
          <span
            class="metric-verdict {getScoreColor(
              metrics?.seo_potential_score,
            )}-text"
            class:preview-blur={previewMode}
          >
            {getScoreLabel(metrics?.seo_potential_score)}
          </span>
        </div>

        <!-- Solo Dev Feasibility -->
        <div class="metric-cell" style="--cell-delay: 0.25s">
          <span class:preview-blur={previewMode}>
            <ProgressRing
              value={metrics?.solo_dev_feasibility ?? 0}
              size={52}
              strokeWidth={4}
              color={getScoreColor(
                metrics?.solo_dev_feasibility,
              )}
              showValue={true}
              showTooltip={true}
              flat={true}
              label="Solo Dev"
              description={soloDevTooltip}
            />
          </span>
          <span class="metric-label">Solo Dev</span>
          <span
            class="metric-verdict {getScoreColor(
              metrics?.solo_dev_feasibility,
            )}-text"
            class:preview-blur={previewMode}
          >
            {getScoreLabel(
              metrics?.solo_dev_feasibility,
            )}
          </span>
        </div>

        <!-- Competitive Edge -->
        <div class="metric-cell" style="--cell-delay: 0.3s">
          <span class:preview-blur={previewMode}>
            <ProgressRing
              value={metrics?.competitive_advantage_score ?? 0}
              size={52}
              strokeWidth={4}
              color={getScoreColor(metrics?.competitive_advantage_score)}
              showValue={true}
              showTooltip={true}
              flat={true}
              label="Comp. Edge"
              description={compEdgeTooltip}
            />
          </span>
          <span class="metric-label">Comp. Edge</span>
          <span
            class="metric-verdict {getScoreColor(
              metrics?.competitive_advantage_score,
            )}-text"
            class:preview-blur={previewMode}
          >
            {getScoreLabel(metrics?.competitive_advantage_score)}
          </span>
        </div>
      </div>

      <!-- Integrated Footer Stats -->
      <div class="metrics-footer" class:preview-locked={previewMode}>
        <div class="footer-stat">
          <Search class="footer-stat-icon" />
          <span class="footer-stat-value" class:preview-blur={previewMode}
            >{formatNumber(metrics?.total_keyword_search_volume ?? 0)}</span
          >
          <span class="footer-stat-label">
            mo. searches <Tooltip
              content={tooltips.footerSearches}
              position="top"
            />
          </span>
        </div>
        <div class="footer-divider"></div>
        <div class="footer-stat">
          <Target class="footer-stat-icon" />
          <span class="footer-stat-value" class:preview-blur={previewMode}
            >{metrics?.total_keyword_count ?? 0}</span
          >
          <span class="footer-stat-label">
            keywords <Tooltip
              content={tooltips.footerKeywords}
              position="top"
            />
          </span>
        </div>
        <div class="footer-divider"></div>
        <div class="footer-stat">
          <Users class="footer-stat-icon" />
          <span class="footer-stat-value" class:preview-blur={previewMode}
            >{metrics?.primary_competitor_count ?? 0}</span
          >
          <span class="footer-stat-label">
            competitors <Tooltip
              content={tooltips.footerCompetitors}
              position="top"
            />
          </span>
        </div>
      </div>
    </div>

    <!-- Verdict Rationale Zone -->
    {#if verdict && !previewMode}
      <div class="verdict-rationale-zone {getVerdictClass(verdict.verdict)}">
        <div class="rationale-header">
          <div class="rationale-verdict-badge">
            {#if verdict.verdict === "Go"}
              <CheckCircle class="rationale-icon" />
            {:else if verdict.verdict === "Conditional"}
              <Shield class="rationale-icon" />
            {:else}
              <AlertCircle class="rationale-icon" />
            {/if}
            <span class="rationale-verdict-text"
              >{verdict.verdict.toUpperCase()}</span
            >
          </div>
          <div class="rationale-info">
            <span class="rationale-confidence"
              >{formatScorePercent(confidenceScore)} opportunity score</span
            >
            <Badge
              variant={verdict.risk_level.toLowerCase() === "low"
                ? "success"
                : verdict.risk_level.toLowerCase() === "medium"
                  ? "info"
                  : "muted"}
              size="sm"
            >
              {verdict.risk_level} Risk
            </Badge>
          </div>
        </div>
        {#if verdict.trend_context}
          <div class="rationale-adjustment">
            <TrendingDown class="adjustment-icon" />
            <div class="adjustment-content">
              <span class="adjustment-label">MARKET CONTEXT</span>
              <span class="adjustment-text">{verdict.trend_context}</span>
            </div>
          </div>
        {/if}
        {#if verdict.market_viability_context}
          <div class="rationale-adjustment">
            <AlertTriangle class="adjustment-icon" />
            <div class="adjustment-content">
              <span class="adjustment-label">MARKET VIABILITY</span>
              <span class="adjustment-text"
                >{verdict.market_viability_context}</span
              >
            </div>
          </div>
        {/if}
        <p class="rationale-text">{verdict.rationale}</p>
        {#if verdict.primary_concern}
          <div class="rationale-concern">
            <AlertTriangle class="concern-icon" />
            <span>{verdict.primary_concern}</span>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Expandable: Strategic Insights -->
    {#if hasStrategicInsights && !previewMode}
      <ExpandableSection
        title="Strategic Rationale"
        icon={Compass}
        count={refinementHighlights?.top_strategic_insights?.length ?? 0}
        countSuffix="insights"
      >
        <!-- Strategic Insights List -->
        {#if refinementHighlights?.top_strategic_insights && refinementHighlights.top_strategic_insights.length > 0}
          <div class="insights-list">
            {#each refinementHighlights.top_strategic_insights as insight, i}
              <div class="insight-item">
                <span class="insight-num">{i + 1}</span>
                <span class="insight-text">{insight}</span>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Priority Chips -->
        {#if refinementHighlights?.geographic_priority || refinementHighlights?.feature_priority}
          <CardGrid minWidth={200} gap="md">
            {#if refinementHighlights.geographic_priority}
              <InsightCard
                variant="info"
                border="left"
                padding="md"
                hoverable={true}
              >
                {#snippet header()}
                  <div class="priority-header">
                    <Globe class="priority-icon geo" />
                    <span class="priority-label">Geographic Focus</span>
                  </div>
                {/snippet}
                <span class="priority-value"
                  >{refinementHighlights.geographic_priority}</span
                >
              </InsightCard>
            {/if}
            {#if refinementHighlights.feature_priority}
              <InsightCard
                variant="accent"
                border="left"
                padding="md"
                hoverable={true}
              >
                {#snippet header()}
                  <div class="priority-header">
                    <Layers class="priority-icon feature" />
                    <span class="priority-label">Feature Priority</span>
                  </div>
                {/snippet}
                <span class="priority-value"
                  >{refinementHighlights.feature_priority}</span
                >
              </InsightCard>
            {/if}
          </CardGrid>
        {/if}

        <!-- Category Pivot Alert -->
        {#if refinementHighlights?.category_pivot_recommendation}
          <div class="pivot-alert">
            <RefreshCw class="pivot-icon" />
            <div class="pivot-content">
              <span class="pivot-label">Category Pivot Recommended</span>
              <p class="pivot-text">
                {refinementHighlights.category_pivot_recommendation}
              </p>
            </div>
          </div>
        {/if}

        <!-- SEO Transparency -->
        {#if seoCalculationTransparency}
          <div class="seo-transparency">
            <div class="seo-header">
              <Calculator class="seo-calc-icon" />
              <h4 class="seo-title">SEO Score Calculation</h4>
            </div>

            <div class="seo-flow">
              <div class="seo-score baseline">
                <span class="seo-value"
                  >{formatScorePercent(
                    seoCalculationTransparency.baseline_seo_score ?? 0,
                  )}</span
                >
                <span class="seo-label">Baseline</span>
              </div>
              <span class="seo-arrow">→</span>
              <div class="seo-score refined">
                <span class="seo-value"
                  >{formatScorePercent(
                    seoCalculationTransparency.refined_seo_score ?? 0,
                  )}</span
                >
                <span class="seo-label">Refined</span>
              </div>
              {#if scoreImprovement}
                <div
                  class="seo-score change"
                  class:positive={parseFloat(scoreImprovement) >= 0}
                >
                  <span class="seo-value">
                    {parseFloat(scoreImprovement) >= 0
                      ? "+"
                      : ""}{scoreImprovement}%
                  </span>
                  <span class="seo-label">Change</span>
                </div>
              {/if}
            </div>

            <div class="seo-factors">
              <div class="seo-factor">
                <span class="factor-value"
                  >{seoCalculationTransparency.volume_multiplier}x</span
                >
                <span class="factor-label">Volume</span>
              </div>
              <div class="seo-factor">
                <span class="factor-value"
                  >{seoCalculationTransparency.competition_modifier}x</span
                >
                <span class="factor-label">Competition</span>
              </div>
              <div class="seo-factor">
                <span class="factor-value"
                  >{seoCalculationTransparency.tier1_multiplier}x</span
                >
                <span class="factor-label">Tier 1</span>
              </div>
              <div class="seo-factor">
                <span class="factor-value"
                  >{seoCalculationTransparency.estimated_year1_pages}</span
                >
                <span class="factor-label">Est. Pages</span>
              </div>
            </div>

            {#if seoCalculationTransparency.calculation_rationale}
              <p class="seo-rationale">
                {seoCalculationTransparency.calculation_rationale}
              </p>
            {/if}
          </div>
        {/if}
      </ExpandableSection>
    {/if}

    <!-- Expandable: Risk Assessment -->
    {#if hasRiskAssessment && !previewMode}
      <ExpandableSection
        title="Risk Assessment & Timing"
        icon={Shield}
        count={trends?.trend_reversal_risks?.length ?? null}
        countSuffix="risks"
        variant="error"
      >
        <!-- Risk Factors -->
        {#if trends?.trend_reversal_risks && trends.trend_reversal_risks.length > 0}
          <InsightCard
            variant="error"
            border="left"
            padding="md"
            class="risk-card"
          >
            {#snippet header()}
              <h4 class="risk-card-title">Risk Factors</h4>
            {/snippet}
            <div class="risk-items-list">
              {#each trends.trend_reversal_risks as risk}
                <IconListItem icon={AlertCircle} iconVariant="error"
                  >{risk}</IconListItem
                >
              {/each}
            </div>
          </InsightCard>
        {/if}

        <!-- Market Signals Grid -->
        {#if trends}
          <CardGrid minWidth={220} gap="md">
            {#if trends.trend_direction}
              {@const TrendIcon = getTrendIcon(trends.trend_direction)}
              <InsightCard
                variant="default"
                border="left"
                padding="md"
                hoverable={true}
              >
                {#snippet header()}
                  <div class="signal-card-header">
                    <TrendIcon class="signal-card-icon" />
                    <h4 class="signal-card-title">Market Trend</h4>
                  </div>
                {/snippet}
                <div class="signal-rows">
                  <div class="signal-row">
                    <span class="signal-row-label">Direction:</span>
                    <span class="signal-row-value"
                      >{trends.trend_direction}</span
                    >
                  </div>
                  {#if trends.momentum_score !== undefined}
                    <div class="signal-row">
                      <span class="signal-row-label">Momentum:</span>
                      <span class="signal-row-value"
                        >{formatScorePercent(trends.momentum_score)}</span
                      >
                    </div>
                  {/if}
                  {#if trends.longevity_verdict}
                    <div class="signal-row">
                      <span class="signal-row-label">Longevity:</span>
                      <Badge
                        variant={trends.longevity_verdict
                          .toLowerCase()
                          .includes("sustain")
                          ? "success"
                          : trends.longevity_verdict
                                .toLowerCase()
                                .includes("fad")
                            ? "error"
                            : "warning"}
                        size="sm"
                      >
                        {trends.longevity_verdict}
                      </Badge>
                    </div>
                  {/if}
                  {#if trends.market_maturity}
                    <div class="signal-row">
                      <span class="signal-row-label">Maturity:</span>
                      <span class="signal-row-value"
                        >{trends.market_maturity}</span
                      >
                    </div>
                  {/if}
                </div>
              </InsightCard>
            {/if}

            {#if trends.timing_recommendation || trends.longevity_rationale}
              <InsightCard
                variant="default"
                border="left"
                padding="md"
                hoverable={true}
              >
                {#snippet header()}
                  <div class="signal-card-header">
                    <Clock class="signal-card-icon" />
                    <h4 class="signal-card-title">Timing Analysis</h4>
                  </div>
                {/snippet}
                {#if trends.timing_recommendation}
                  <div class="timing-highlight">
                    <p>{trends.timing_recommendation}</p>
                  </div>
                {/if}
                {#if trends.longevity_rationale}
                  <div class="timing-rationale">
                    {@html renderMarkdown(trends.longevity_rationale)}
                  </div>
                {/if}
              </InsightCard>
            {/if}
          </CardGrid>
        {/if}
      </ExpandableSection>
    {/if}
  </div>
  {/if}
</section>

<style>
  /* =========================
	   UNIFIED HERO CONTAINER
	   ========================= */
  .unified-hero {
    margin-bottom: var(--space-6);
  }

  /* =========================
	   HERO ZONE (Dark Gradient)
	   ========================= */
  .hero-zone {
    background: linear-gradient(
      135deg,
      #0f172a 0%,
      #1e293b 40%,
      #431407 80%,
      var(--color-accent) 100%
    );
    padding: var(--space-8) var(--space-5);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    position: relative;
    overflow: hidden;
  }

  .hero-zone--standalone {
    border-radius: var(--radius-lg);
  }

  /* Preview variant — light, inset data readout (escapes the dark-hero slop on job page) */
  .hero-zone--preview {
    background: var(--color-bg-subtle);
    border: none;
  }

  .hero-zone--preview .niche-title {
    color: var(--color-text-primary);
  }
  .hero-zone--preview .niche-description {
    color: var(--color-text-secondary);
  }
  .hero-zone--preview .niche-description:hover {
    color: var(--color-text-primary);
  }
  .hero-zone--preview .expand-btn {
    color: var(--color-accent);
  }
  .hero-zone--preview .expand-btn:hover {
    color: var(--color-accent-dark);
  }

  .hero-zone--preview .pipeline-stage {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
  }
  .hero-zone--preview .pipeline-num {
    color: var(--color-text-primary);
  }
  .hero-zone--preview .pipeline-label {
    color: var(--color-text-muted);
  }

  /* Final stage: emphasize via typography, not peach fill — keeps hexagonal flow consistent */
  .hero-zone--preview .pipeline-stage.highlight {
    background: var(--color-bg-elevated);
  }
  .hero-zone--preview .pipeline-stage.highlight .pipeline-num {
    color: var(--color-accent-dark);
    font-size: var(--text-2xl);
    font-weight: var(--font-extrabold);
  }
  .hero-zone--preview .pipeline-stage.highlight .pipeline-label {
    color: var(--color-accent-dark);
    font-weight: var(--font-semibold);
  }

  .hero-zone--preview .verdict-locked {
    border-color: var(--color-border);
    color: var(--color-text-muted);
  }

  .hero-zone--preview :global(.tooltip-trigger) {
    color: var(--color-text-muted);
    border-color: var(--color-border);
  }
  .hero-zone--preview :global(.tooltip-trigger:hover) {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-hover);
  }

  /* Pain card (in preview mode): larger, darker metrics for contrast on light bg.
     Keep the existing 3px left accent stripe as the single orange container cue —
     no bg tint, no accent border, to avoid stacked-accent slop. */
  .cards-container--preview .pain-stat-value {
    font-size: 1.5rem;
    color: var(--color-accent-dark);
  }

  .cards-container--preview .pain-stat {
    gap: 0.125rem;
  }

  .hero-zone > * {
    position: relative;
    z-index: 1;
  }

  /* Hero Split Layout */
  .hero-split {
    display: grid;
    grid-template-columns: 2fr 3fr;
    gap: var(--space-8);
    margin-bottom: var(--space-6);
  }

  /* Left Column - Verdict */
  .hero-left {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
  }

  .verdict-giant {
    text-align: center;
    padding: var(--space-6) var(--space-5);
    background: rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-lg);
    border: 2px solid rgba(255, 255, 255, 0.1);
  }

  .verdict-giant.verdict-go {
    border-color: var(--color-border-success);
  }

  .verdict-giant.verdict-conditional {
    border-color: rgba(99, 102, 241, 0.4);
  }

  .verdict-giant.verdict-nogo {
    border-color: var(--color-border-error);
  }

  .verdict-score-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: rgba(255, 255, 255, 0.6);
    margin-bottom: var(--space-1);
    display: block;
  }

  .verdict-percentage {
    font-family: var(--font-mono);
    font-size: 4rem;
    font-weight: var(--font-extrabold);
    letter-spacing: var(--tracking-tight);
    line-height: var(--leading-none);
    color: white;
    text-shadow: none;
  }

  .verdict-label-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  :global(.verdict-icon-large) {
    width: var(--space-6);
    height: var(--space-6);
    color: white;
  }

  .verdict-label-text {
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: var(--font-extrabold);
    letter-spacing: var(--tracking-wide);
    color: white;
  }

  /* Verdict colors */
  .verdict-giant.verdict-go .verdict-percentage {
    color: var(--color-success);
    text-shadow: none;
  }
  .verdict-giant.verdict-go :global(.verdict-icon-large) {
    color: var(--color-success);
  }

  .verdict-giant.verdict-conditional .verdict-percentage {
    color: var(--color-info);
    text-shadow: none;
  }
  .verdict-giant.verdict-conditional :global(.verdict-icon-large) {
    color: var(--color-info);
  }

  .verdict-giant.verdict-nogo .verdict-percentage {
    color: var(--color-error);
    text-shadow: none;
  }
  .verdict-giant.verdict-nogo :global(.verdict-icon-large) {
    color: var(--color-error);
  }

  .verdict-risk-badge {
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  /* Right Column - Niche Info */
  .hero-right {
    display: flex;
    flex-direction: column;
    justify-content: center;
  }

  .niche-title {
    font-family: var(--font-display);
    font-size: var(--text-3xl);
    font-weight: var(--font-bold);
    letter-spacing: -0.02em;
    color: white;
    line-height: var(--leading-tight);
    margin-bottom: var(--space-3);
    text-shadow: none;
  }

  .niche-description-wrapper {
    margin-bottom: var(--space-4);
  }

  .niche-description {
    font-size: 0.9375rem;
    color: rgba(255, 255, 255, 0.8);
    line-height: var(--leading-relaxed);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
    margin: 0;
  }

  .niche-description:hover {
    color: rgba(255, 255, 255, 0.95);
  }

  .niche-description.expanded {
    -webkit-line-clamp: unset;
    line-clamp: unset;
    display: block;
  }

  .expand-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.7);
    font-size: var(--text-sm);
    cursor: pointer;
    padding: var(--space-1) 0;
    text-decoration: underline;
    transition: color var(--duration-fast) var(--ease-default);
  }

  .expand-btn:hover {
    color: white;
  }

  /* Signal Chips */
  .signal-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.625rem;
  }

  .signal-chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-2) 0.875rem;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-md);
    min-width: 80px;
    cursor: help;
    transition:
      background var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default);
  }

  .signal-chip:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .signal-value {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-size: 0.9375rem;
    font-weight: var(--font-bold);
    color: white;
  }

  :global(.signal-icon-inline) {
    flex-shrink: 0;
  }

  .signal-label {
    font-size: var(--text-xs);
    color: rgba(255, 255, 255, 0.65);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wider);
    font-weight: var(--font-medium);
  }

  .success-text {
    color: var(--color-success-light) !important;
  }
  .warning-text {
    color: var(--color-warning-light) !important;
  }
  .error-text {
    color: var(--color-error-light) !important;
  }

  /* Research Pipeline */
  .research-pipeline {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
  }

  .pipeline-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-3) var(--space-6);
    background: rgba(255, 255, 255, 0.08);
    clip-path: polygon(
      0 0,
      calc(100% - 12px) 0,
      100% 50%,
      calc(100% - 12px) 100%,
      0 100%,
      12px 50%
    );
    min-width: 90px;
  }

  .pipeline-stage:first-child {
    clip-path: polygon(
      0 0,
      calc(100% - 12px) 0,
      100% 50%,
      calc(100% - 12px) 100%,
      0 100%
    );
    border-radius: var(--radius-md) 0 0 var(--radius-md);
  }

  .pipeline-stage:last-child {
    clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%, 12px 50%);
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
  }

  .pipeline-stage.highlight {
    background: var(--color-accent-glow);
  }

  .pipeline-arrow {
    width: 0;
    height: 0;
  }

  .pipeline-num {
    font-family: var(--font-mono);
    font-size: var(--text-xl);
    font-weight: var(--font-bold);
    color: white;
  }

  .pipeline-label {
    font-size: var(--text-xs);
    color: rgba(255, 255, 255, 0.7);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .pipeline-stage.highlight .pipeline-num {
    color: var(--color-accent);
  }

  /* HelpCircle icons on dark background (hero zone) */
  .hero-zone :global(.tooltip-trigger) {
    color: rgba(255, 255, 255, 0.5);
    border-color: rgba(255, 255, 255, 0.25);
  }

  .hero-zone :global(.tooltip-trigger:hover) {
    color: rgba(255, 255, 255, 0.9);
    border-color: rgba(255, 255, 255, 0.5);
    background: rgba(255, 255, 255, 0.1);
  }

  /* =========================
	   CONTENT ZONE (Light Background)
	   ========================= */
  .content-zone {
    background: var(--color-bg-base);
    padding: var(--space-6) 0 var(--space-8);
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  }

  /* Cards Container - Overlapping Layout */
  .cards-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
    position: relative;
  }

  .cards-container--preview {
    grid-template-columns: 1fr;
  }

  /* Card Header Pattern */
  .card-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: 0.625rem;
  }

  :global(.card-icon) {
    width: var(--space-4);
    height: var(--space-4);
  }

  :global(.card-icon.pain) {
    color: var(--color-accent);
  }

  :global(.card-icon.solution) {
    color: var(--color-accent);
  }

  .card-badge {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: var(--font-bold);
    letter-spacing: 0.1em;
    color: var(--color-accent);
  }

  /* Unified Hero Card Base */
  .hero-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    padding-left: calc(var(--space-5) + 2px);
    position: relative;
    box-shadow: var(--shadow-md);
    overflow: hidden;
  }

  /* Left accent bar (pseudo-element) */
  .hero-card::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  }

  /* Pain variant - orange accent */
  .hero-card--pain::before {
    background: var(--color-accent);
  }

  .pain-title {
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: var(--font-semibold);
    color: var(--color-text-primary);
    line-height: var(--leading-snug);
    margin-bottom: var(--space-3);
  }

  .pain-stats {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-bottom: 0.875rem;
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--color-border);
  }

  .pain-stat {
    display: flex;
    flex-direction: column;
  }

  .pain-stat-value {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: var(--font-bold);
    color: var(--color-accent);
  }

  .pain-stat-label {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .pain-stat-divider {
    width: 1px;
    height: 24px;
    background: var(--color-border-emphasis);
  }

  .pain-quote {
    position: relative;
    padding-left: var(--space-6);
    font-style: italic;
    color: var(--color-text-muted);
    font-size: 0.8125rem;
    line-height: var(--leading-relaxed);
    margin: 0;
  }

  :global(.quote-icon) {
    position: absolute;
    left: 0;
    top: 0;
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-accent);
    opacity: 0.4;
  }

  /* Solution approach callout */
  .solution-approach-callout {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--color-accent-subtle);
    border-radius: var(--radius-md);
    margin-bottom: 0.875rem;
  }

  :global(.callout-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .callout-text {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    line-height: var(--leading-relaxed);
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Quotes section with top border separator */
  .pain-quotes-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding-top: 0.875rem;
    border-top: 1px solid var(--color-border);
    margin-bottom: 0.875rem;
  }

  .pain-quote-attribution {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-style: normal;
    color: var(--color-text-muted);
    margin-top: var(--space-1);
    opacity: 0.8;
  }

  .pain-quote p {
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Evidence stats strip */
  .pain-evidence-strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding-top: 0.875rem;
    border-top: 1px solid var(--color-border);
    margin-bottom: 0.875rem;
  }

  .pain-evidence-stat {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: var(--font-semibold);
    color: var(--color-text-muted);
    padding: var(--space-1) var(--space-2);
    background: var(--color-bg-hover);
    border-radius: var(--radius-sm);
    letter-spacing: 0.02em;
  }

  .pain-evidence-stat--hot {
    color: var(--color-error);
    background: var(--color-error-subtle);
  }

  /* Pain CTA link */
  .pain-cta {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-display);
    font-size: var(--text-sm);
    font-weight: var(--font-semibold);
    color: var(--color-accent);
    text-decoration: none;
    padding: var(--space-2) var(--space-3);
    background: var(--color-accent-subtle);
    border-radius: var(--radius-md);
    transition: background-color 0.2s ease, color 0.2s ease;
  }

  .pain-cta:hover {
    background: var(--color-accent);
    color: white;
  }

  /* =========================
	   SOLUTION TEASER (in content zone)
	   ========================= */
  .solution-teaser {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-success);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    padding-left: calc(var(--space-5) + 2px);
    position: relative;
    box-shadow: var(--shadow-md);
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .solution-teaser:hover {
    border-color: var(--color-success);
    background: var(--color-bg-hover);
  }

  .teaser-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: 0.625rem;
  }

  :global(.teaser-icon) {
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-success);
  }

  .teaser-badge {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: var(--font-bold);
    letter-spacing: 0.1em;
    color: var(--color-success);
  }

  .teaser-name {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: var(--font-bold);
    color: var(--color-accent);
    margin-bottom: var(--space-1);
    line-height: var(--leading-snug);
  }

  .teaser-tagline {
    font-style: italic;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    margin-bottom: 0.875rem;
    line-height: var(--leading-relaxed);
  }

  .teaser-cta {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-family: var(--font-display);
    font-size: var(--text-sm);
    font-weight: var(--font-semibold);
    color: var(--color-accent);
    text-decoration: none;
    padding: var(--space-2) var(--space-3);
    background: var(--color-accent-subtle);
    border-radius: var(--radius-md);
    transition: background-color 0.2s ease, color 0.2s ease;
  }

  .teaser-cta:hover {
    background: var(--color-accent);
    color: white;
  }

  :global(.cta-arrow) {
    width: var(--space-4);
    height: var(--space-4);
    transition: transform 0.2s ease;
  }

  /* Value proposition - explains WHY this solution */
  .teaser-value-prop {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: var(--leading-relaxed);
    margin-bottom: 0.875rem;
    padding-bottom: 0.875rem;
    border-bottom: 1px solid var(--color-border);
  }

  /* Target audience row */
  .teaser-target {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    margin-bottom: 0.875rem;
    padding-bottom: 0.875rem;
    border-bottom: 1px solid var(--color-border);
  }

  :global(.teaser-target-icon) {
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-text-muted);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .teaser-target-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: var(--leading-relaxed);
  }

  /* Differentiator badges */
  .teaser-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
    margin-bottom: 0.875rem;
  }

  /* =========================
	   METRICS PANEL - Diagnostic Instrument Panel
	   ========================= */
  .metrics-panel {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: none;
    overflow: hidden;
    margin-bottom: var(--space-6);
  }

  .metrics-panel-header {
    padding: 0.625rem var(--space-4);
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-hover);
  }

  .metrics-panel-title {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: var(--font-bold);
    letter-spacing: 0.12em;
    color: var(--color-text-muted);
    text-transform: uppercase;
  }

  .metrics-cells {
    display: flex;
    justify-content: stretch;
  }

  .metric-cell {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-5) var(--space-2);
    position: relative;
    transition: background 0.2s ease;
    /* Staggered entrance animation */
    opacity: 0;
    transform: translateY(8px);
    animation: metric-cell-enter 0.4s ease-out forwards;
    animation-delay: var(--cell-delay, 0s);
  }

  .metric-cell:hover {
    background: var(--color-bg-hover);
  }

  /* Internal dividers between cells */
  .metric-cell:not(:last-child)::after {
    content: "";
    position: absolute;
    right: 0;
    top: 20%;
    height: 60%;
    width: 1px;
    background: var(--color-border-emphasis);
  }

  @keyframes metric-cell-enter {
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .metric-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: var(--font-semibold);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-muted);
    margin-top: 0.375rem;
    text-align: center;
  }

  .metric-verdict {
    font-family: var(--font-display);
    font-size: 0.6875rem;
    font-weight: var(--font-semibold);
    margin-top: var(--space-1);
    text-align: center;
  }

  /* Semantic verdict colors */
  .metric-verdict.success-text {
    color: var(--color-success);
  }
  .metric-verdict.warning-text {
    color: var(--color-warning);
  }
  .metric-verdict.error-text {
    color: var(--color-error);
  }
  .metric-verdict.muted-text {
    color: var(--color-text-muted);
  }

  .threshold-badge {
    font-family: var(--font-mono);
    font-size: 0.5rem;
    font-weight: var(--font-semibold);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-top: 0.125rem;
    text-align: center;
  }

  .threshold-badge.passes {
    color: var(--color-success);
    opacity: 0.7;
  }

  .threshold-badge.below {
    color: var(--color-error);
    opacity: 0.85;
  }

  /* Integrated Footer Stats */
  .metrics-footer {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--space-6);
    padding: 0.875rem 1.25rem;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }

  .footer-stat {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.footer-stat-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .footer-stat-value {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: var(--font-semibold);
    color: var(--color-text-primary);
  }

  .footer-stat-label {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .footer-divider {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: var(--color-border-emphasis);
  }

  /* =========================
	   VERDICT RATIONALE ZONE
	   ========================= */
  .verdict-rationale-zone {
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-4);
    position: relative;
  }

  .verdict-rationale-zone.verdict-go {
    background: var(--color-success-subtle);
    border: 1px solid var(--color-border-success);
  }

  .verdict-rationale-zone.verdict-conditional {
    background: var(--color-secondary-subtle);
    border: 1px solid rgba(99, 102, 241, 0.2);
  }

  .verdict-rationale-zone.verdict-nogo {
    background: var(--color-error-subtle);
    border: 1px solid var(--color-border-error);
  }

  .rationale-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: 0.625rem;
  }

  .rationale-verdict-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0.875rem;
    border-radius: var(--radius-sm);
    font-family: var(--font-display);
    font-size: var(--text-md);
    font-weight: var(--font-extrabold);
  }

  .verdict-go .rationale-verdict-badge {
    background: var(--color-success);
    color: white;
  }

  .verdict-conditional .rationale-verdict-badge {
    background: var(--color-info);
    color: white;
  }

  .verdict-nogo .rationale-verdict-badge {
    background: var(--color-error);
    color: white;
  }

  :global(.rationale-icon) {
    width: 1.125rem;
    height: 1.125rem;
  }

  .rationale-verdict-text {
    letter-spacing: 0.02em;
  }

  .rationale-info {
    display: flex;
    align-items: center;
    gap: 0.625rem;
  }

  .rationale-confidence {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .rationale-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: var(--leading-relaxed);
    margin-bottom: 0.625rem;
  }

  .rationale-concern {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--color-warning-subtle);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  :global(.concern-icon) {
    width: var(--text-sm);
    height: var(--text-sm);
    color: var(--color-warning);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  /* Score breakdown link in verdict box */
  .verdict-breakdown-link {
    margin-top: var(--space-3);
    background: none;
    border: none;
    padding: 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: rgba(255, 255, 255, 0.5);
    text-decoration: underline;
    text-underline-offset: 2px;
    cursor: pointer;
    transition: color 0.15s ease;
  }

  .verdict-breakdown-link:hover {
    color: rgba(255, 255, 255, 1);
  }

  /* Rationale adjustment blocks (trend/viability context) */
  .rationale-adjustment {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--color-warning-subtle);
    border-left: 3px solid var(--color-warning);
    border-radius: var(--radius-sm);
    margin-bottom: var(--space-2);
  }

  :global(.adjustment-icon) {
    width: var(--text-sm);
    height: var(--text-sm);
    color: var(--color-warning);
    flex-shrink: 0;
    margin-top: 0.125rem;
  }

  .adjustment-content {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .adjustment-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-warning);
  }

  .adjustment-text {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    line-height: var(--leading-relaxed);
  }

  /* Insights List */
  .insights-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .insight-item {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.625rem;
    background: var(--color-bg-hover);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .insight-num {
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--space-5);
    height: var(--space-5);
    background: var(--color-accent-subtle);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: var(--font-bold);
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .insight-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: var(--leading-normal);
  }

  /* Priority Cards - using CardGrid + InsightCard */
  .priority-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.priority-icon) {
    width: var(--space-4);
    height: var(--space-4);
  }

  :global(.priority-icon.geo) {
    color: var(--color-secondary);
  }

  :global(.priority-icon.feature) {
    color: var(--color-accent);
  }

  .priority-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    color: var(--color-text-muted);
  }

  .priority-value {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: var(--font-semibold);
    color: var(--color-text-primary);
  }

  /* Pivot Alert */
  .pivot-alert {
    display: flex;
    align-items: flex-start;
    gap: 0.625rem;
    padding: 0.875rem;
    background: var(--color-warning-subtle);
    border: 1px solid var(--color-border-warning);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
  }

  :global(.pivot-icon) {
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-warning);
    flex-shrink: 0;
  }

  .pivot-content {
    display: flex;
    flex-direction: column;
  }

  .pivot-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    color: var(--color-warning);
    margin-bottom: 0.125rem;
  }

  .pivot-text {
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    line-height: var(--leading-normal);
    margin: 0;
  }

  /* SEO Transparency */
  .seo-transparency {
    background: var(--color-bg-hover);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 0.875rem;
  }

  .seo-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: 0.875rem;
  }

  :global(.seo-calc-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
  }

  .seo-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: var(--font-semibold);
    color: var(--color-text-primary);
    margin: 0;
  }

  .seo-flow {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    margin-bottom: 0.875rem;
  }

  .seo-score {
    text-align: center;
  }

  .seo-score .seo-value {
    display: block;
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: var(--font-bold);
  }

  .seo-score.baseline .seo-value {
    color: var(--color-text-muted);
  }

  .seo-score.refined .seo-value {
    color: var(--color-accent);
  }

  .seo-score.change.positive .seo-value {
    color: var(--color-success);
  }

  .seo-arrow {
    font-size: var(--text-md);
    color: var(--color-text-muted);
  }

  .seo-score .seo-label {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  .seo-factors {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-2);
    margin-bottom: 0.625rem;
  }

  .seo-factor {
    text-align: center;
    padding: var(--space-2);
    background: var(--color-bg-elevated);
    border-radius: var(--radius-sm);
  }

  .factor-value {
    display: block;
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: var(--font-semibold);
    color: var(--color-text-primary);
  }

  .factor-label {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
  }

  .seo-rationale {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    padding: 0.625rem;
    background: var(--color-bg-elevated);
    border-radius: var(--radius-sm);
    margin: 0;
  }

  /* Risk Section - using InsightCard + IconListItem */
  :global(.risk-card) {
    margin-bottom: var(--space-4);
  }

  .risk-card-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: var(--font-semibold);
    color: var(--color-error);
    margin: 0;
  }

  .risk-items-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  /* Signal Cards - using CardGrid + InsightCard */
  .signal-card-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  :global(.signal-card-icon) {
    width: var(--space-4);
    height: var(--space-4);
    color: var(--color-accent);
  }

  .signal-card-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: var(--font-semibold);
    color: var(--color-text-primary);
    margin: 0;
  }

  .signal-rows {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .signal-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: var(--text-sm);
  }

  .signal-row-label {
    color: var(--color-text-muted);
  }

  .signal-row-value {
    color: var(--color-text-primary);
    font-weight: var(--font-medium);
  }

  .timing-highlight {
    padding: 0.625rem;
    background: var(--color-accent-subtle);
    border-radius: var(--radius-sm);
    margin-bottom: 0.625rem;
  }

  .timing-highlight p {
    font-size: 0.8125rem;
    font-weight: var(--font-medium);
    color: var(--color-text-primary);
    margin: 0;
  }

  .timing-rationale {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    line-height: var(--leading-relaxed);
  }

  /* =========================
	   RESPONSIVE ADJUSTMENTS
	   ========================= */
  @media (max-width: 900px) {
    .hero-split {
      grid-template-columns: 1fr;
      gap: var(--space-6);
    }

    .hero-left {
      order: 1;
    }

    .hero-right {
      order: 0;
    }
  }

  @media (max-width: 768px) {
    .hero-zone {
      padding: var(--space-6);
    }

    .content-zone {
      padding: var(--space-5);
    }

    .verdict-percentage {
      font-size: var(--text-6xl);
    }

    .niche-title {
      font-size: 1.375rem;
    }

    .cards-container {
      grid-template-columns: 1fr;
    }

    .research-pipeline {
      flex-wrap: wrap;
      gap: var(--space-2);
    }

    .pipeline-stage {
      clip-path: none;
      border-radius: var(--radius-md);
      min-width: auto;
      flex: 1;
    }

    .pipeline-stage:first-child,
    .pipeline-stage:last-child {
      clip-path: none;
      border-radius: var(--radius-md);
    }

    /* Metrics panel: 2 rows on tablet */
    .metrics-cells {
      flex-wrap: wrap;
    }

    .metric-cell {
      flex: 1 1 33.33%;
      min-width: 0;
    }

    /* Remove dividers in wrapped layout */
    .metric-cell:nth-child(3)::after {
      display: none;
    }

    .metrics-footer {
      flex-wrap: wrap;
      gap: var(--space-4);
    }

    .rationale-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .seo-flow {
      flex-wrap: wrap;
    }

    .seo-factors {
      grid-template-columns: repeat(2, 1fr);
    }

    /* Teaser responsive */
    .teaser-value-prop,
    .teaser-target-text {
      font-size: var(--text-sm);
    }

    .teaser-badges {
      gap: var(--space-1);
    }
  }

  @media (max-width: 480px) {
    .verdict-percentage {
      font-size: var(--text-5xl);
    }

    .signal-chips {
      justify-content: center;
    }

    .signal-chip {
      min-width: 70px;
      padding: var(--space-1) 0.625rem;
    }

    /* Metrics panel: 2 columns on mobile */
    .metric-cell {
      flex: 1 1 50%;
      padding: 1rem 0.375rem;
    }

    /* Hide dividers except between columns */
    .metric-cell::after {
      display: none;
    }

    .metric-cell:nth-child(odd):not(:last-child)::after {
      display: block;
    }

    .metric-label {
      font-size: 0.5rem;
    }

    .metric-verdict {
      font-size: var(--text-xs);
    }

    .metrics-footer {
      gap: var(--space-3);
      padding: var(--space-3) var(--space-4);
    }

    .footer-stat-value {
      font-size: var(--text-base);
    }

    .footer-stat-label {
      font-size: 0.6875rem;
    }

    .footer-divider {
      width: 3px;
      height: 3px;
    }
  }

  /* ── Preview mode ── */
  .preview-locked {
    user-select: none;
    pointer-events: none;
  }

  .preview-blur {
    filter: blur(5px);
    opacity: 0.5;
  }

  .verdict-locked {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    width: 100%;
    min-height: 200px;
    border: 1px dashed rgba(255, 255, 255, 0.15);
    border-radius: var(--radius-lg, 0.75rem);
    color: rgba(255, 255, 255, 0.4);
  }

  .verdict-locked-label {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    letter-spacing: 0.03em;
  }

  .preview-gate {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 1.5rem 0;
  }

  .preview-gate::before,
  .preview-gate::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }

  .preview-gate-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
</style>
