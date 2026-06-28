<script lang="ts">
  import type { Report } from "$lib/types/report";
  import { ArrowLeft, AlertTriangle, Info } from "lucide-svelte";

  // PHASE 1: DECISION (Go/No-Go verdict)
  import UnifiedHero from "$lib/components/sections/UnifiedHero.svelte";
  import NicheRealityCheck from "$lib/components/sections/NicheRealityCheck.svelte";
  import SolutionHero from "$lib/components/sections/SolutionHero.svelte";

  // PHASE 2: VALIDATE (Is the opportunity real?)
  import PainAnalysis from "$lib/components/sections/PainAnalysis.svelte";
  import MarketSizing from "$lib/components/sections/MarketSizing.svelte";
  import MonetizationStrategy from "$lib/components/sections/MonetizationStrategy.svelte";
  import TrendSection from "$lib/components/sections/TrendSection.svelte";
  import Competitors from "$lib/components/sections/Competitors.svelte";

  // PHASE 3: EXECUTE (How to launch & build)
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";
  import ContentInsights from "$lib/components/sections/ContentInsights.svelte";
  import GTMPlaybook from "$lib/components/sections/GTMPlaybook.svelte";
  import SEOKeywords from "$lib/components/sections/SEOKeywords.svelte";
  import TechnicalBlueprint from "$lib/components/sections/TechnicalBlueprint.svelte";
  import DataInfrastructure from "$lib/components/sections/DataInfrastructure.svelte";

  // PHASE 4: REFERENCE (Appendix)
  import AlternativesSection from "$lib/components/sections/AlternativesSection.svelte";
  import EvidenceAppendix from "$lib/components/sections/EvidenceAppendix.svelte";
  import CoverageNotes from "$lib/components/CoverageNotes.svelte";

  // UI components
  import SectionNav from "$lib/components/ui/SectionNav.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";

  interface Props {
    report: Report;
    showBackLink?: boolean;
    showShareButton?: boolean;
    jobId?: string;
    headerSlot?: import("svelte").Snippet;
  }

  let { report, showBackLink = true, jobId, headerSlot }: Props = $props();

  // Get solution details with fallback
  const solutionDetails = $derived(
    report?.selected_solution_details || {
      name: report?.selected_solution_name,
      description: report?.executive_summary || "",
      solution_name: report?.selected_solution_name,
    },
  );

  // Filtering pipeline stats for UnifiedHero
  const funnelStats = $derived({
    scanned:
      (report?.research_metadata?.filtering_stats as Record<string, number>)
        ?.total_urls_searched || 0,
    relevant:
      (report?.research_metadata?.filtering_stats as Record<string, number>)
        ?.total_urls_relevant || 0,
    analyzed: (report?.research_metadata?.reddit_posts_analyzed ?? 0) +
              (report?.research_metadata?.twitter_threads_analyzed ?? 0) +
              (report?.research_metadata?.generic_posts_analyzed ?? 0) || 0,
    problems:
      report?.pain_point_analytics?.total_pain_points ||
      report?.detailed_pain_points?.length ||
      0,
  });

  // Niche display values
  const nicheName = $derived(
    report?.niche_context?.niche_input ??
      report?.niche?.slice(0, 60) ??
      "Unknown Niche",
  );
  const nicheDescription = $derived(
    report?.niche_context?.niche_description ?? report?.niche ?? "",
  );
</script>

<div class="report-layout">
  <!-- Section Navigation Overlay -->
  <SectionNav {report} />

  <!-- Main Content -->
  <main class="report-content">
    <!-- Header area: back link + optional slot for share button -->
    {#if showBackLink || headerSlot}
      <div class="report-header-bar">
        {#if showBackLink && jobId}
          <a href="/jobs/{jobId}" class="back-link">
            <ArrowLeft class="w-4 h-4" />
            <span>Back to Job Status</span>
          </a>
        {:else}
          <div></div>
        {/if}
        {#if headerSlot}
          {@render headerSlot()}
        {/if}
      </div>
    {/if}

    <!-- AI Disclaimer Banner -->
    <div class="mb-4 p-4 rounded-lg border border-border bg-bg-elevated">
      <div class="flex items-start gap-3">
        <Info class="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
        <p class="text-sm text-text-secondary">
          We're always improving report quality, but at the end of the day, AI
          is AI — it does a solid job, though it can occasionally get things
          wrong. Use this as your research starting point, not your final
          answer.
        </p>
      </div>
    </div>

    <!-- Seeded-from-catalog transparency badge -->
    {#if report.seeded_from_catalog}
      <div class="mb-4 p-3 rounded-lg border border-border bg-bg-base flex items-start gap-3">
        <Info class="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
        <p class="text-sm text-text-secondary">
          <span class="font-medium text-text-primary">Seeded from the catalog.</span>
          This report was generated from a catalog entry without a fresh community scrape, so
          live quotes and the evidence appendix are lighter than a full discovery run.
        </p>
      </div>
    {/if}

    <!-- Unified Hero Section (merged header + executive summary) -->
    {#if report.executive_dashboard}
      <UnifiedHero
        {report}
        {nicheName}
        {nicheDescription}
        {funnelStats}
        refinementHighlights={report.refinement_highlights}
        seoCalculationTransparency={report.seo_calculation_transparency}
        trends={report.trend_longevity}
      />
    {:else}
      <section class="report-section">
        <EmptyState
          icon={AlertTriangle}
          title="Executive Summary Unavailable"
          description="The executive dashboard could not be generated for this report. Some data may be missing from earlier pipeline stages."
          variant="warning"
        />
      </section>
    {/if}

    <!-- Research Reality Check — candid software-fit verdict (framing anchor) -->
    {#if report.niche_difficulty_verdict}
      <section class="report-section">
        <NicheRealityCheck verdict={report.niche_difficulty_verdict} context="report" />
      </section>
    {/if}

    <!-- PHASE 1: DECISION (Solution details) -->
    <div class="phase-section phase-decision">
      <SectionDivider num={1} label="Decision" />

      {#if report.executive_dashboard}
        <SolutionHero
          solution={solutionDetails}
          dashboard={report.executive_dashboard}
          selectionRationale={report.selection_rationale || ""}
          budgetEstimate={report.go_to_market_blueprint?.budget_estimate}
          pricingStrategy={report.pricing_strategy}
        />
      {/if}
    </div>

    <!-- PHASE 2: VALIDATE (Is the opportunity real?) -->
    <div class="phase-section phase-validate">
      <SectionDivider num={2} label="Validate" />
      {#if report.detailed_pain_points && report.detailed_pain_points.length > 0 && report.pain_point_analytics}
        <PainAnalysis
          painPoints={report.detailed_pain_points}
          analytics={report.pain_point_analytics}
          solution={solutionDetails}
        />
      {/if}

      {#if report.market_sizing}
        <MarketSizing data={report.market_sizing} />
      {/if}

      {#if report.pricing_strategy}
        <MonetizationStrategy
          pricingData={report.pricing_strategy}
          trafficData={report.traffic_monetization}
          cacBreakdown={report.estimated_cac_breakdown}
        />
      {/if}

      {#if report.trend_longevity}
        <TrendSection data={report.trend_longevity} />
      {/if}

      {#if report.competitive_analytics && report.competitive_analysis}
        <Competitors
          profiles={report.competitor_profiles || []}
          analysis={report.competitive_analysis}
          analytics={report.competitive_analytics}
          landscapeMatrix={report.competitive_landscape_matrix}
          summary={report.competitive_summary}
          selectedSolutionName={report.selected_solution_name}
        />
      {/if}
    </div>

    <!-- PHASE 3: EXECUTE (How to launch & build) -->
    <div class="phase-section phase-execute">
      <SectionDivider num={3} label="Execute" />
      {#if report.audience_mapping}
        <AudienceSection
          data={report.audience_mapping}
          targetAudience={report.niche_context?.user_target_audience ?? null}
        />
      {/if}

      {#if report.content_categorization || report.overall_competitive_insights}
        <ContentInsights
          contentCategorization={report.content_categorization}
          overallCompetitiveInsights={report.overall_competitive_insights}
        />
      {/if}

      {#if report.go_to_market_blueprint}
        <GTMPlaybook
          gtmData={report.go_to_market_blueprint}
          nextSteps={report.next_steps}
        />
      {/if}

      {#if report.seo_strategy_report && report.seo_analytics}
        <SEOKeywords
          strategy={report.seo_strategy_report}
          analytics={report.seo_analytics}
        />
      {/if}

      {#if solutionDetails}
        <TechnicalBlueprint
          solution={solutionDetails}
          implementationOverview={report.solution_implementation_overview}
          mvpScope={report.mvp_scope_definition}
          userJourney={report.solution_user_journey}
          dataInfrastructureRoadmap={report.data_infrastructure_roadmap}
          siteStructure={report.site_structure}
          userFlows={report.user_flows}
        />
      {/if}

      {#if report.data_source_research_full}
        <DataInfrastructure data={report.data_source_research_full} />
      {/if}
    </div>

    <!-- PHASE 4: REFERENCE (Appendix) -->
    <div class="phase-section phase-reference">
      <SectionDivider num={4} label="Reference" />
      {#if report.alternative_solutions && report.alternative_solutions.length > 0}
        <AlternativesSection data={report.alternative_solutions} />
      {/if}

      {#if report.evidence_appendix}
        <EvidenceAppendix data={report.evidence_appendix} />
      {/if}

      {#if report.data_quality_summary?.quality_caveats?.length}
        <section class="report-section">
          <CoverageNotes notes={report.data_quality_summary.quality_caveats} />
        </section>
      {/if}
    </div>
  </main>
</div>

<style>
  /* =========================
	   GLOBAL SECTION STYLES
	   ========================= */
  :global(.report-section) {
    background: var(--color-bg-base);
  }

  /* =========================
	   HEADER BAR
	   ========================= */
  .report-header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
    gap: 1rem;
  }

  /* =========================
	   BACK LINK
	   ========================= */
  .back-link {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    border-radius: 0.375rem;
    transition: color 0.15s ease, background-color 0.15s ease;
  }

  .back-link:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-elevated);
  }

  /* Phase Section Styling — numbered SectionDivider in normal flow (Phase 5).
     The divider supplies its own top padding, so phase-section no longer needs
     the extra top space the old absolute pill required. */
  .phase-section {
    margin-bottom: 1rem;
  }

  /* Phase wayfinding: large neutral numeral acts as the landmark — size,
     not color, carries the hierarchy. */
  .phase-section :global(.section-divider) {
    padding-top: var(--space-16);
  }

  .phase-section :global(.section-divider .num) {
    font-family: var(--font-display);
    font-size: var(--text-4xl);
    font-weight: 800;
    line-height: 1;
    color: var(--color-text-primary);
  }

  .phase-section :global(.section-divider .dot) {
    display: none;
  }

  /* Editorial measure for long-form analysis prose inside report sections.
     Targets p/li only so markdown tables stay full-width. */
  .report-content :global(.markdown-content p),
  .report-content :global(.markdown-content li) {
    max-width: 70ch;
  }

  @media (max-width: 768px) {
    .phase-section {
      margin-bottom: 0.75rem;
    }
  }
</style>
