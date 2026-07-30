<script lang="ts">
  import { page } from "$app/state";
  import { ArrowLeft, CircleAlert, FileText, FlaskConical, ListChecks } from "lucide-svelte";
  import type { Report, SolutionDetails } from "$lib/types/report";
  import ReportBrief from "$lib/components/report/ReportBrief.svelte";
  import ReportEvidenceSummary from "$lib/components/report/ReportEvidenceSummary.svelte";
  import ReportPlanSummary from "$lib/components/report/ReportPlanSummary.svelte";
  import PainAnalysis from "$lib/components/sections/PainAnalysis.svelte";
  import MarketSizing from "$lib/components/sections/MarketSizing.svelte";
  import MonetizationStrategy from "$lib/components/sections/MonetizationStrategy.svelte";
  import TrendSection from "$lib/components/sections/TrendSection.svelte";
  import Competitors from "$lib/components/sections/Competitors.svelte";
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";
  import ContentInsights from "$lib/components/sections/ContentInsights.svelte";
  import SolutionHero from "$lib/components/sections/SolutionHero.svelte";
  import GTMPlaybook from "$lib/components/sections/GTMPlaybook.svelte";
  import SEOKeywords from "$lib/components/sections/SEOKeywords.svelte";
  import TechnicalBlueprint from "$lib/components/sections/TechnicalBlueprint.svelte";
  import DataInfrastructure from "$lib/components/sections/DataInfrastructure.svelte";
  import AlternativesSection from "$lib/components/sections/AlternativesSection.svelte";
  import EvidenceAppendix from "$lib/components/sections/EvidenceAppendix.svelte";
  import CoverageNotes from "$lib/components/CoverageNotes.svelte";
  import { renderMarkdown } from "$lib/utils/format";
  import type { ComponentType, Snippet } from "svelte";

  type ReportView = "brief" | "evidence" | "plan";
  type EvidenceTopicId = "demand" | "market" | "competition" | "sources";
  type PlanTopicId = "first-30-days" | "product" | "launch";
  type Topic<T extends string> = {
    id: T;
    label: string;
    description: string;
    available: boolean;
  };

  interface Props {
    report: Report;
    showBackLink?: boolean;
    showShareButton?: boolean;
    jobId?: string;
    headerSlot?: Snippet;
    decisionSlot?: Snippet;
  }

  let { report, showBackLink = true, jobId, headerSlot, decisionSlot }: Props = $props();

  const solutionDetails = $derived<SolutionDetails>(
    report.selected_solution_details ?? {
      description: report.executive_summary || "",
      solution_name: report.selected_solution_name,
      headline: report.selected_solution_name,
      short_description: report.executive_summary || "",
    },
  );
  const snapshot = $derived(report.executive_dashboard?.recommended_solution_snapshot);
  const nicheName = $derived(
    report.niche_context?.niche_input ?? report.niche?.slice(0, 80) ?? "Research report",
  );
  const generatedDate = $derived.by(() => {
    if (!report.generated_at) return "Date unavailable";
    const date = new Date(report.generated_at);
    if (Number.isNaN(date.getTime())) return "Date unavailable";
    return new Intl.DateTimeFormat("en", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(date);
  });

  const evidenceTopics = $derived.by<Topic<EvidenceTopicId>[]>(() => [
    {
      id: "demand",
      label: "Demand",
      description: "Problems and buyers",
      available:
        (report.detailed_pain_points?.length ?? 0) > 0 ||
        !!report.pain_point_analytics ||
        !!report.pain_points_summary ||
        !!report.audience_mapping,
    },
    {
      id: "market",
      label: "Market",
      description: "Size, pricing, and timing",
      available:
        !!report.market_sizing ||
        !!report.pricing_strategy ||
        !!report.traffic_monetization ||
        !!report.trend_longevity ||
        !!report.market_validation ||
        !!report.estimated_cac_breakdown,
    },
    {
      id: "competition",
      label: "Competition",
      description: "Alternatives and positioning",
      available:
        !!report.competitive_analytics ||
        !!report.competitive_analysis ||
        (report.competitor_profiles?.length ?? 0) > 0 ||
        !!report.competitive_landscape_matrix ||
        !!report.competitive_summary ||
        !!report.content_categorization ||
        !!report.overall_competitive_insights ||
        (report.alternative_solutions?.length ?? 0) > 0 ||
        (report.recommended_solutions?.length ?? 0) > 0 ||
        !!report.solutions_summary,
    },
    {
      id: "sources",
      label: "Research quality",
      description: "Coverage, limits, and provenance",
      available: true,
    },
  ]);

  const hasDatedPlaybook = $derived(Boolean(report.go_to_market_blueprint?.first_30_days_playbook));
  const planTopics = $derived.by<Topic<PlanTopicId>[]>(() => [
    {
      id: "first-30-days",
      label: hasDatedPlaybook ? "First 30 days" : "Recommended sequence",
      description: hasDatedPlaybook ? "A dated action plan" : "What to do first",
      available:
        (report.next_steps?.length ?? 0) > 0 ||
        !!report.go_to_market_blueprint?.first_30_days_playbook,
    },
    {
      id: "product",
      label: "Product & build",
      description: "Scope, system, and data",
      available:
        !!report.selected_solution_details ||
        !!report.solution_implementation_overview ||
        !!report.mvp_scope_definition ||
        !!report.solution_user_journey ||
        !!report.site_structure ||
        !!report.user_flows ||
        !!report.data_source_research_full ||
        !!report.data_infrastructure_roadmap ||
        !!report.data_sourcing_recommendations,
    },
    {
      id: "launch",
      label: "Launch & growth",
      description: "GTM and organic acquisition",
      available:
        !!report.go_to_market_blueprint ||
        !!report.acquisition_strategy_summary ||
        !!report.seo_strategy_report ||
        !!report.seo_analytics ||
        (report.keyword_clusters?.length ?? 0) > 0 ||
        !!report.content_strategy_preview,
    },
  ]);
  const hasTechnicalDetail = $derived(
    !!solutionDetails.technical_approach ||
      !!solutionDetails.estimated_development_time ||
      !!solutionDetails.data_sources?.length ||
      !!report.solution_implementation_overview ||
      !!report.mvp_scope_definition ||
      !!report.solution_user_journey ||
      !!report.data_infrastructure_roadmap ||
      !!report.site_structure ||
      !!report.user_flows,
  );

  const requestedView = $derived(page.url.searchParams.get("view"));
  const currentView = $derived<ReportView>(
    requestedView === "evidence" || requestedView === "plan" ? requestedView : "brief",
  );
  const requestedTopic = $derived(page.url.searchParams.get("topic"));
  const isFullDetail = $derived(page.url.searchParams.get("detail") === "full");
  const availableEvidenceTopics = $derived(evidenceTopics.filter((topic) => topic.available));
  const availablePlanTopics = $derived(planTopics.filter((topic) => topic.available));
  const currentEvidenceTopic = $derived<EvidenceTopicId>(
    evidenceTopics.some((topic) => topic.id === requestedTopic)
      ? (requestedTopic as EvidenceTopicId)
      : (availableEvidenceTopics[0]?.id ?? "sources"),
  );
  const currentEvidenceTopicInfo = $derived(
    evidenceTopics.find((topic) => topic.id === currentEvidenceTopic),
  );
  const currentPlanTopic = $derived<PlanTopicId>(
    planTopics.some((topic) => topic.id === requestedTopic)
      ? (requestedTopic as PlanTopicId)
      : (availablePlanTopics[0]?.id ?? "first-30-days"),
  );
  const currentPlanTopicInfo = $derived(planTopics.find((topic) => topic.id === currentPlanTopic));
  const researchQualityLimited = $derived.by(() => {
    const quality = report.data_quality_summary?.overall_data_quality?.trim().toLowerCase();
    return !quality || quality.includes("low");
  });
  const researchQualitySummary = $derived.by(() => {
    const quality = report.data_quality_summary?.overall_data_quality?.trim();
    if (!quality) {
      return "This report does not include an overall data-quality grade. Treat ungraded findings as directional.";
    }
    if (quality.toLowerCase().includes("low")) {
      return "Coverage is limited. Use this report to choose what to verify next, not as proof that the market is validated.";
    }
    return `${quality} data quality was recorded for this run. Review the limitations below before acting on consequential claims.`;
  });
  const coverageNotes = $derived(
    (report.data_quality_summary?.quality_caveats ?? []).map((note) =>
      /^fallback data used in:/i.test(note)
        ? "Fallback data was used for part of this run, so some findings have reduced depth."
        : note,
    ),
  );

  const views: Array<{
    id: ReportView;
    label: string;
    description: string;
    icon: ComponentType;
  }> = [
    { id: "brief", label: "Brief", description: "Understand the recommendation", icon: FileText },
    { id: "evidence", label: "Evidence", description: "Verify the case", icon: FlaskConical },
    { id: "plan", label: "Plan", description: "Decide what to do next", icon: ListChecks },
  ];

  function reportHref(view: ReportView, topic?: string, detail?: "full"): string {
    const url = new URL(page.url);
    url.searchParams.set("view", view);
    if (topic) url.searchParams.set("topic", topic);
    else url.searchParams.delete("topic");
    if (detail) url.searchParams.set("detail", detail);
    else url.searchParams.delete("detail");
    url.hash = "";
    return `${url.pathname}${url.search}`;
  }
  const fullFirstMonthHref = $derived(
    hasDatedPlaybook
      ? `${reportHref("plan", "launch", "full")}#first-30-days-playbook`
      : undefined,
  );
</script>

<div class="report-shell">
  <aside class="report-index">
    <nav aria-label="Report views">
      <p class="index-title">Research report</p>
      <ol>
        {#each views as item, index}
          {@const Icon = item.icon}
          <li>
            <a
              href={reportHref(item.id)}
              class:active={currentView === item.id}
              aria-current={currentView === item.id ? "page" : undefined}
            >
              <span class="index-number">0{index + 1}</span>
              <Icon aria-hidden="true" />
              <span>
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
            </a>
          </li>
        {/each}
      </ol>
    </nav>
    <div class="index-context">
      <span>Selected opportunity</span>
      <strong>{report.selected_solution_name}</strong>
      <small>Generated {generatedDate}</small>
    </div>
  </aside>

  <!-- The app/public layouts already provide the page's single main landmark. -->
  <div class="report-main">
    <header class="report-header">
      <div class="report-header-top">
        {#if showBackLink && jobId}
          <a href="/jobs/{jobId}" class="back-link">
            <ArrowLeft aria-hidden="true" />
            <span>Back to job</span>
          </a>
        {:else}
          <span class="public-label">Deep Research report</span>
        {/if}
        {#if headerSlot}
          {@render headerSlot()}
        {/if}
      </div>

      <div class="report-identity">
        <p>Deep Research report · {generatedDate}</p>
        <h1>{report.selected_solution_name}</h1>
        <div class="report-deck">
          {snapshot?.tagline ??
            solutionDetails?.headline ??
            solutionDetails?.short_description ??
            report.executive_summary}
        </div>
        <div class="report-meta" aria-label="Report context">
          <span>{nicheName}</span>
          {#if report.executive_dashboard?.research_depth_label}
            <span>{report.executive_dashboard.research_depth_label}</span>
          {/if}
          {#if report.seeded_from_catalog}
            <span>Catalog-seeded research</span>
          {/if}
          {#if report.user_adjusted}
            <span>User-adjusted research</span>
          {/if}
        </div>
      </div>

      <nav class="mobile-view-nav" aria-label="Report views">
        {#each views as item}
          <a
            href={reportHref(item.id)}
            class:active={currentView === item.id}
            aria-current={currentView === item.id ? "page" : undefined}
          >
            {item.label}
          </a>
        {/each}
      </nav>
    </header>

    {#if currentView === "brief"}
      <ReportBrief
        {report}
        evidenceHref={reportHref("evidence", availableEvidenceTopics[0]?.id)}
        planHref={reportHref("plan", availablePlanTopics[0]?.id)}
        {decisionSlot}
      />
    {:else if currentView === "evidence"}
      <section class="view-heading" aria-labelledby="evidence-view-title">
        <p>Verify the case</p>
        <h2 id="evidence-view-title">Trace each conclusion to its evidence</h2>
        <div>
          Findings are grouped by the questions a founder needs to answer. Missing research stays
          visible as unavailable rather than becoming a zero.
        </div>
      </section>

      <nav class="topic-nav" aria-label="Evidence topics">
          {#each evidenceTopics as topic}
            <a
              href={reportHref("evidence", topic.id)}
              class:active={currentEvidenceTopic === topic.id}
              class:unavailable={!topic.available}
              aria-current={currentEvidenceTopic === topic.id ? "location" : undefined}
            >
              <strong>{topic.label}</strong>
              <span>{topic.description}</span>
              {#if !topic.available}<small>Unavailable</small>{/if}
            </a>
          {/each}
      </nav>

      <div class="view-content" class:full-detail={isFullDetail}>
        {#if !currentEvidenceTopicInfo?.available}
          <section class="topic-unavailable" aria-labelledby="evidence-topic-unavailable-title">
            <CircleAlert aria-hidden="true" />
            <div>
              <h3 id="evidence-topic-unavailable-title">
                {currentEvidenceTopicInfo?.label ?? "This evidence topic"} is unavailable
              </h3>
              <p>
                This report did not retain enough structured research to summarize this topic.
                Nothing has been substituted from another section.
              </p>
            </div>
          </section>
        {:else if currentEvidenceTopic !== "sources" && !isFullDetail}
          <ReportEvidenceSummary
            {report}
            topic={currentEvidenceTopic}
            fullDetailHref={reportHref("evidence", currentEvidenceTopic, "full")}
          />
        {:else}
          {#if isFullDetail && currentEvidenceTopic !== "sources"}
            <div class="detail-mode">
              <div>
                <span>Research appendix</span>
                <strong>Showing detailed generated artifacts for this topic</strong>
              </div>
              <a href={reportHref("evidence", currentEvidenceTopic)}>Back to summary</a>
            </div>
          {/if}
        {#if currentEvidenceTopic === "demand"}
          {#if report.detailed_pain_points?.length && report.pain_point_analytics}
            <PainAnalysis
              painPoints={report.detailed_pain_points}
              analytics={report.pain_point_analytics}
              solution={solutionDetails}
            />
          {:else if report.detailed_pain_points?.length}
            <section class="fallback-section" aria-labelledby="captured-problems-title">
              <div class="fallback-heading">
                <p>Captured problems</p>
                <h3 id="captured-problems-title">What customers repeatedly struggle with</h3>
              </div>
              <ol class="finding-list">
                {#each report.detailed_pain_points.slice(0, 6) as painPoint, index}
                  <li>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <strong>{painPoint.title}</strong>
                      <p>{painPoint.description}</p>
                    </div>
                  </li>
                {/each}
              </ol>
              <p class="availability-note">
                This report captured the customer problems, but it does not include the later
                aggregate pain analysis.
              </p>
            </section>
          {:else if report.pain_points_summary}
            <section class="fallback-section" aria-labelledby="pain-summary-title">
              <div class="fallback-heading">
                <p>Problem summary</p>
                <h3 id="pain-summary-title">What the available research found</h3>
              </div>
              <div class="legacy-narrative">
                {@html renderMarkdown(report.pain_points_summary)}
              </div>
              <p class="availability-note">
                This is a summary from an earlier report format. Individual evidence records are
                not available.
              </p>
            </section>
          {:else if report.pain_point_analytics}
            <section class="fallback-section" aria-labelledby="pain-metrics-title">
              <div class="fallback-heading">
                <p>Problem evidence</p>
                <h3 id="pain-metrics-title">What the aggregate analysis retained</h3>
              </div>
              <dl class="compact-metrics">
                <div>
                  <dt>Problems analyzed</dt>
                  <dd>{report.pain_point_analytics.total_pain_points}</dd>
                </div>
                <div>
                  <dt>High-opportunity problems</dt>
                  <dd>
                    {report.pain_point_analytics.high_opportunity_count ??
                      report.pain_point_analytics.high_severity_count ??
                      "Not available"}
                  </dd>
                </div>
              </dl>
              <p class="availability-note">
                The detailed problem records are not available in this report.
              </p>
            </section>
          {/if}
          {#if report.audience_mapping}
            <AudienceSection
              data={report.audience_mapping}
              targetAudience={report.niche_context?.user_target_audience ?? null}
            />
          {:else if solutionDetails.target_personas?.length}
            <section class="fallback-section" aria-labelledby="buyer-summary-title">
              <div class="fallback-heading">
                <p>Intended buyers</p>
                <h3 id="buyer-summary-title">Who the product was designed for</h3>
              </div>
              <ul class="plain-list">
                {#each solutionDetails.target_personas as persona}
                  <li>{persona}</li>
                {/each}
              </ul>
              <p class="availability-note">
                A full audience map was not generated for this report.
              </p>
            </section>
          {/if}
        {:else if currentEvidenceTopic === "market"}
          {#if report.market_sizing}
            <MarketSizing data={report.market_sizing} />
          {/if}
          {#if report.pricing_strategy}
            <MonetizationStrategy
              pricingData={report.pricing_strategy}
              trafficData={report.traffic_monetization}
              cacBreakdown={report.estimated_cac_breakdown}
            />
          {:else if report.traffic_monetization}
            <section class="fallback-section" aria-labelledby="monetization-summary-title">
              <div class="fallback-heading">
                <p>Monetization</p>
                <h3 id="monetization-summary-title">How this model could earn revenue</h3>
              </div>
              <dl class="compact-metrics">
                <div>
                  <dt>Model</dt>
                  <dd>{report.traffic_monetization.monetization_model}</dd>
                </div>
                <div>
                  <dt>Estimated monthly range</dt>
                  <dd>{report.traffic_monetization.estimated_monthly_revenue_range}</dd>
                </div>
              </dl>
              <p class="narrative-copy">{report.traffic_monetization.monetization_rationale}</p>
            </section>
          {/if}
          {#if report.trend_longevity}
            <TrendSection data={report.trend_longevity} />
          {/if}
          {#if report.market_validation && !report.market_sizing}
            <section class="fallback-section" aria-labelledby="market-validation-title">
              <div class="fallback-heading">
                <p>Available market read</p>
                <h3 id="market-validation-title">How the opportunity was assessed</h3>
              </div>
              <div class="legacy-narrative">
                {@html renderMarkdown(report.market_validation)}
              </div>
              <p class="availability-note">
                This report predates the structured market-sizing model.
              </p>
            </section>
          {/if}
          {#if report.estimated_cac_breakdown && !report.pricing_strategy}
            <section class="fallback-section" aria-labelledby="cac-breakdown-title">
              <div class="fallback-heading">
                <p>Acquisition economics</p>
                <h3 id="cac-breakdown-title">Estimated customer-acquisition cost</h3>
              </div>
              <div class="legacy-narrative">
                {@html renderMarkdown(report.estimated_cac_breakdown)}
              </div>
            </section>
          {/if}
        {:else if currentEvidenceTopic === "competition"}
          {#if report.competitive_analytics && report.competitive_analysis}
            <Competitors
              profiles={report.competitor_profiles || []}
              analysis={report.competitive_analysis}
              analytics={report.competitive_analytics}
              landscapeMatrix={report.competitive_landscape_matrix}
              summary={report.competitive_summary}
              selectedSolutionName={report.selected_solution_name}
            />
          {:else if
            report.competitive_summary ||
            report.competitive_analysis ||
            report.competitor_profiles?.length ||
            report.competitive_analytics}
            <section class="fallback-section" aria-labelledby="competition-summary-title">
              <div class="fallback-heading">
                <p>Competitive read</p>
                <h3 id="competition-summary-title">What the available research says</h3>
              </div>
              {#if report.competitive_summary}
                <div class="legacy-narrative">
                  {@html renderMarkdown(report.competitive_summary)}
                </div>
              {:else if report.competitive_analysis?.strategic_recommendations}
                <div class="legacy-narrative">
                  {@html renderMarkdown(report.competitive_analysis.strategic_recommendations)}
                </div>
              {/if}
              {#if report.competitor_profiles?.length}
                <ul class="named-list" aria-label="Competitors reviewed">
                  {#each report.competitor_profiles.slice(0, 8) as competitor}
                    <li>
                      <strong>{competitor.name}</strong>
                      <span>{competitor.competitor_type}</span>
                    </li>
                  {/each}
                </ul>
              {/if}
              {#if report.competitive_analytics}
                <dl class="compact-metrics">
                  <div>
                    <dt>Competitors reviewed</dt>
                    <dd>{report.competitive_analytics.competitor_count}</dd>
                  </div>
                  <div>
                    <dt>Market gaps identified</dt>
                    <dd>{report.competitive_analytics.market_gaps_identified}</dd>
                  </div>
                  <div>
                    <dt>Differentiation read</dt>
                    <dd>{report.competitive_analytics.differentiation_strength}</dd>
                  </div>
                </dl>
              {/if}
              <p class="availability-note">
                This report does not include the full competitive analytics layer.
              </p>
            </section>
          {/if}
          {#if report.content_categorization || report.overall_competitive_insights}
            <ContentInsights
              contentCategorization={report.content_categorization}
              overallCompetitiveInsights={report.overall_competitive_insights}
            />
          {/if}
          {#if report.alternative_solutions?.length}
            <AlternativesSection data={report.alternative_solutions} />
          {:else if report.recommended_solutions?.length || report.solutions_summary}
            <section class="fallback-section" aria-labelledby="alternatives-summary-title">
              <div class="fallback-heading">
                <p>Other paths considered</p>
                <h3 id="alternatives-summary-title">Alternative solution directions</h3>
              </div>
              {#if report.recommended_solutions?.length}
                <ul class="plain-list">
                  {#each report.recommended_solutions as alternative}
                    <li>{alternative}</li>
                  {/each}
                </ul>
              {:else}
                <div class="legacy-narrative">
                  {@html renderMarkdown(report.solutions_summary)}
                </div>
              {/if}
            </section>
          {/if}
        {:else}
          <section class="methods-summary" aria-labelledby="methods-title">
            <div>
              <p>Research transparency</p>
              <h3 id="methods-title">Coverage, provenance, and limitations</h3>
            </div>
            <p class="quality-interpretation" class:caution={researchQualityLimited}>
              {researchQualitySummary}
            </p>
            <dl>
              <div>
                <dt>Overall data quality</dt>
                <dd>{report.data_quality_summary?.overall_data_quality ?? "Not graded"}</dd>
              </div>
              <div>
                <dt>Social evidence</dt>
                <dd>
                  {report.executive_dashboard?.key_metrics?.social_evidence_threads ??
                    report.evidence_appendix?.top_reddit_threads?.length ??
                    "Not available"}
                </dd>
              </div>
              <div>
                <dt>Generated</dt>
                <dd>{generatedDate}</dd>
              </div>
              <div>
                <dt>Social source quality</dt>
                <dd>{report.data_quality_summary?.social_content_quality_tier ?? "Not graded"}</dd>
              </div>
              <div>
                <dt>Problem-evidence quality</dt>
                <dd>{report.data_quality_summary?.pain_point_quality_tier ?? "Not graded"}</dd>
              </div>
              <div>
                <dt>Collection date</dt>
                <dd>{report.research_metadata?.collection_date ?? "Not available"}</dd>
              </div>
            </dl>
            {#if report.idea_portfolio_summary}
              <div class="portfolio-note">
                <strong>Idea-pool read</strong>
                <p>{report.idea_portfolio_summary}</p>
              </div>
            {/if}
            {#if report.market_reality}
              <div class="portfolio-note market-reality-note">
                <strong>Market reality</strong>
                {#if report.market_reality.wallet?.evidence}
                  <p>{report.market_reality.wallet.evidence}</p>
                {/if}
                {#if report.market_reality.incumbents.length}
                  <ul class="named-list" aria-label="Verified incumbents">
                    {#each report.market_reality.incumbents.slice(0, 8) as incumbent}
                      <li>
                        <strong>{incumbent.name}</strong>
                        <span>{incumbent.pricing ?? incumbent.focus ?? "Pricing not recorded"}</span>
                      </li>
                    {/each}
                  </ul>
                {/if}
              </div>
            {/if}
            {#if report.research_metadata?.fallback_stages?.length}
              <div class="portfolio-note">
                <strong>Reduced-depth stages</strong>
                <p>
                  {report.research_metadata.fallback_stages.length}
                  {report.research_metadata.fallback_stages.length === 1 ? "stage used" : "stages used"}
                  fallback data. The limitations below identify what this affects.
                </p>
              </div>
            {/if}
            {#if
              report.data_quality_summary?.examined_ruled_out?.length ||
              report.examined_ruled_out?.length}
              <details class="portfolio-note ruled-out-note">
                <summary>
                  {(report.data_quality_summary?.examined_ruled_out ??
                    report.examined_ruled_out ??
                    []).length}
                  weaker
                  {(report.data_quality_summary?.examined_ruled_out ??
                    report.examined_ruled_out ??
                    []).length === 1
                    ? "direction"
                    : "directions"}
                  examined and ruled out
                </summary>
                <ul class="ruled-out-list">
                  {#each
                    (report.data_quality_summary?.examined_ruled_out ??
                      report.examined_ruled_out ??
                      []) as finding}
                    <li>
                      <strong>{finding.idea_name ?? finding.pain_title}</strong>
                      <span>{finding.reason}</span>
                    </li>
                  {/each}
                </ul>
              </details>
            {/if}
            {#if report.seeded_from_catalog || report.user_adjusted}
              <div class="portfolio-note">
                <strong>How this run was shaped</strong>
                {#if report.seeded_from_catalog}
                  <p>
                    This report began from a catalog entry, so its community evidence may be
                    lighter than a fresh Discovery run.
                  </p>
                {/if}
                {#if report.user_adjusted}
                  <p>
                    You changed this run at a research checkpoint before it continued.
                    {report.user_adjustments?.join(" ")}
                  </p>
                {/if}
              </div>
            {/if}
          </section>
          {#if report.evidence_appendix}
            <EvidenceAppendix data={report.evidence_appendix} />
          {/if}
          {#if coverageNotes.length}
            <CoverageNotes notes={coverageNotes} />
          {/if}
        {/if}
        {/if}
      </div>
    {:else}
      <section class="view-heading" aria-labelledby="plan-view-title">
        <p>Act on the research</p>
        <h2 id="plan-view-title">Turn the recommendation into an executable plan</h2>
        <div>
          {hasDatedPlaybook
            ? "Start with the dated 30-day playbook, then open product or launch detail when you need it."
            : "Start with the recommended sequence, then open product or launch detail when you need it."}
        </div>
      </section>

      <nav class="topic-nav" aria-label="Plan topics">
          {#each planTopics as topic}
            <a
              href={reportHref("plan", topic.id)}
              class:active={currentPlanTopic === topic.id}
              class:unavailable={!topic.available}
              aria-current={currentPlanTopic === topic.id ? "location" : undefined}
            >
              <strong>{topic.label}</strong>
              <span>{topic.description}</span>
              {#if !topic.available}<small>Unavailable</small>{/if}
            </a>
          {/each}
      </nav>

      <div class="view-content" class:full-detail={isFullDetail}>
        {#if !currentPlanTopicInfo?.available}
          <section class="topic-unavailable" aria-labelledby="plan-topic-unavailable-title">
            <CircleAlert aria-hidden="true" />
            <div>
              <h3 id="plan-topic-unavailable-title">
                {currentPlanTopicInfo?.label ?? "This plan topic"} is unavailable
              </h3>
              <p>
                This report did not retain enough structured output to build this part of the
                plan. Nothing has been inferred from another topic.
              </p>
            </div>
          </section>
        {:else if !isFullDetail}
          <ReportPlanSummary
            {report}
            topic={currentPlanTopic}
            fullDetailHref={currentPlanTopic === "first-30-days"
              ? fullFirstMonthHref
              : reportHref("plan", currentPlanTopic, "full")}
          />
        {:else}
          <div class="detail-mode">
            <div>
              <span>Implementation appendix</span>
              <strong>Showing detailed generated output for this topic</strong>
            </div>
            <a href={reportHref("plan", currentPlanTopic)}>Back to summary</a>
          </div>
        {#if currentPlanTopic === "first-30-days"}
          <section class="first-steps" aria-labelledby="first-steps-title">
            <div class="first-steps-head">
              <p>Recommended sequence</p>
              <h3 id="first-steps-title">What to do first</h3>
            </div>
            {#if report.go_to_market_blueprint?.first_30_days_playbook}
              {@const playbook = report.go_to_market_blueprint.first_30_days_playbook}
              <ol>
                {#each [
                  ...playbook.week_1_actions,
                  ...playbook.week_2_actions,
                  ...playbook.week_3_actions,
                  ...playbook.week_4_actions,
                ].slice(0, 6) as step, index}
                  <li>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <p>{step}</p>
                  </li>
                {/each}
              </ol>
            {:else if report.next_steps?.length}
              <ol>
                {#each report.next_steps.slice(0, 6) as step, index}
                  <li>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <p>{step}</p>
                  </li>
                {/each}
              </ol>
            {:else}
              <div class="inline-empty">
                <CircleAlert aria-hidden="true" />
                <p>A first-month sequence was not generated for this report.</p>
              </div>
            {/if}
          </section>
        {:else if currentPlanTopic === "product"}
          {#if report.executive_dashboard}
            <SolutionHero
              solution={solutionDetails}
              dashboard={report.executive_dashboard}
              selectionRationale={report.selection_rationale || ""}
              budgetEstimate={report.go_to_market_blueprint?.budget_estimate}
              pricingStrategy={report.pricing_strategy}
            />
          {/if}
          {#if hasTechnicalDetail}
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
          {:else if report.data_sourcing_recommendations}
            <section class="fallback-section" aria-labelledby="data-recommendations-title">
              <div class="fallback-heading">
                <p>Data plan</p>
                <h3 id="data-recommendations-title">Available sourcing recommendations</h3>
              </div>
              <div class="legacy-narrative">
                {@html renderMarkdown(report.data_sourcing_recommendations)}
              </div>
              <p class="availability-note">
                Detailed source-by-source research was not generated for this report.
              </p>
            </section>
          {/if}
        {:else}
          {#if report.go_to_market_blueprint}
            <GTMPlaybook
              gtmData={report.go_to_market_blueprint}
              nextSteps={report.next_steps}
            />
          {:else if report.acquisition_strategy_summary}
            <section class="fallback-section" aria-labelledby="acquisition-summary-title">
              <div class="fallback-heading">
                <p>Acquisition summary</p>
                <h3 id="acquisition-summary-title">How to reach the first customers</h3>
              </div>
              <div class="legacy-narrative">
                {@html renderMarkdown(report.acquisition_strategy_summary)}
              </div>
            </section>
          {/if}
          {#if report.seo_strategy_report && report.seo_analytics}
            <SEOKeywords
              strategy={report.seo_strategy_report}
              analytics={report.seo_analytics}
            />
          {:else if
            report.content_strategy_preview ||
            report.seo_strategy_report ||
            report.seo_analytics}
            <section class="fallback-section" aria-labelledby="growth-summary-title">
              <div class="fallback-heading">
                <p>Organic growth</p>
                <h3 id="growth-summary-title">Available search and content direction</h3>
              </div>
              {#if report.content_strategy_preview}
                <div class="legacy-narrative">
                  {@html renderMarkdown(report.content_strategy_preview)}
                </div>
              {:else if report.seo_strategy_report?.content_strategy}
                <div class="legacy-narrative">
                  {@html renderMarkdown(report.seo_strategy_report.content_strategy)}
                </div>
              {/if}
              {#if report.seo_analytics}
                <dl class="compact-metrics">
                  <div>
                    <dt>Keywords analyzed</dt>
                    <dd>{report.seo_analytics.total_keywords}</dd>
                  </div>
                  <div>
                    <dt>Monthly search volume</dt>
                    <dd>{report.seo_analytics.total_search_volume.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>High-volume keywords</dt>
                    <dd>{report.seo_analytics.high_volume_keywords}</dd>
                  </div>
                </dl>
              {/if}
              <p class="availability-note">
                This report does not include the full SEO analytics layer.
              </p>
            </section>
          {/if}
        {/if}
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .report-shell {
    width: min(100%, 86rem);
    min-height: 100vh;
    margin: 0 auto;
    padding: var(--space-8) var(--space-6) var(--space-16);
    display: grid;
    grid-template-columns: 14rem minmax(0, 1fr);
    gap: var(--space-10);
    align-items: start;
  }

  .report-index {
    position: sticky;
    top: var(--space-8);
    display: grid;
    gap: var(--space-8);
    padding-top: var(--space-2);
  }

  .index-title,
  .public-label {
    margin: 0 0 var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .report-index ol {
    display: grid;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .report-index a {
    position: relative;
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr);
    align-items: start;
    gap: var(--space-2);
    min-height: var(--space-12);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    text-decoration: none;
    transition:
      color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default);
  }

  .report-index a::before {
    content: "";
    position: absolute;
    inset: var(--space-2) auto var(--space-2) 0;
    width: 2px;
    border-radius: var(--radius-full);
    background: transparent;
  }

  .report-index a:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-hover);
  }

  .report-index a.active {
    color: var(--color-text-primary);
    background: var(--color-bg-surface);
  }

  .report-index a.active::before {
    background: var(--color-accent);
  }

  .report-index :global(svg) {
    width: var(--space-4);
    height: var(--space-4);
    margin-top: var(--space-1);
    color: var(--color-text-muted);
  }

  .index-number {
    margin-top: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  .report-index strong,
  .report-index small {
    display: block;
  }

  .report-index strong {
    font-size: var(--text-base);
    font-weight: 700;
  }

  .report-index small {
    margin-top: var(--space-1);
    font-size: var(--text-sm);
    line-height: 1.4;
    color: var(--color-text-muted);
  }

  .index-context {
    display: grid;
    gap: var(--space-2);
    padding-top: var(--space-5);
    border-top: 1px solid var(--color-border);
  }

  .index-context span {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .index-context strong {
    font-size: var(--text-sm);
    line-height: 1.45;
    color: var(--color-text-primary);
  }

  .index-context small {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .report-main {
    width: 100%;
    min-width: 0;
    padding: 0;
  }

  .report-header {
    margin-bottom: var(--space-8);
    padding-bottom: var(--space-6);
    border-bottom: 1px solid var(--color-border);
  }

  .report-header-top {
    min-height: var(--space-10);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    min-height: var(--space-8);
    padding: 0 var(--space-2);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    font-weight: 600;
    text-decoration: none;
    transition:
      color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default);
  }

  .back-link :global(svg) {
    width: var(--space-4);
    height: var(--space-4);
  }

  .back-link:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-hover);
  }

  .report-identity > p {
    margin: 0 0 var(--space-3);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .report-identity h1 {
    max-width: 24ch;
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--text-4xl);
    font-weight: 700;
    line-height: 1.08;
    letter-spacing: -0.02em;
    color: var(--color-text-primary);
    text-wrap: balance;
  }

  .report-deck {
    max-width: 72ch;
    margin-top: var(--space-3);
    color: var(--color-text-secondary);
    font-size: var(--text-md);
    line-height: 1.55;
  }

  .report-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-4);
    margin-top: var(--space-4);
  }

  .report-meta span {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .report-meta span + span::before {
    content: "·";
    margin-right: var(--space-4);
    color: var(--color-border-emphasis);
  }

  .mobile-view-nav {
    display: none;
  }

  .view-heading {
    display: grid;
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .view-heading > p,
  .first-steps-head > p,
  .methods-summary > div:first-child > p {
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .view-heading h2 {
    max-width: 30ch;
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--text-3xl);
    font-weight: 700;
    line-height: 1.15;
    color: var(--color-text-primary);
    text-wrap: balance;
  }

  .view-heading > div {
    max-width: 70ch;
    color: var(--color-text-secondary);
    font-size: var(--text-md);
    line-height: 1.6;
  }

  .topic-nav {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    margin-bottom: var(--space-8);
    border-block: 1px solid var(--color-border);
  }

  .topic-nav a {
    position: relative;
    display: grid;
    gap: var(--space-1);
    min-height: var(--space-16);
    padding: var(--space-4);
    color: var(--color-text-secondary);
    text-decoration: none;
    transition:
      color var(--duration-fast) var(--ease-default),
      background-color var(--duration-fast) var(--ease-default);
  }

  .topic-nav a::after {
    content: "";
    position: absolute;
    inset: auto 0 0;
    height: 2px;
    background: transparent;
  }

  .topic-nav a:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-surface);
  }

  .topic-nav a.active {
    color: var(--color-text-primary);
    background: var(--color-bg-elevated);
  }

  .topic-nav a.active::after {
    background: var(--color-accent);
  }

  .topic-nav a.unavailable:not(.active) {
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
  }

  .topic-nav strong {
    font-size: var(--text-base);
    font-weight: 700;
  }

  .topic-nav span {
    font-size: var(--text-sm);
    line-height: 1.4;
    color: var(--color-text-muted);
  }

  .topic-nav small {
    justify-self: start;
    margin-top: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-warning-text);
  }

  .view-content {
    display: grid;
    gap: var(--space-10);
  }

  .topic-unavailable {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--space-4);
    align-items: start;
    padding: var(--space-6);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-warning-subtle);
  }

  .topic-unavailable :global(svg) {
    width: var(--space-6);
    height: var(--space-6);
    color: var(--color-warning-text);
  }

  .topic-unavailable h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .topic-unavailable p {
    max-width: 64ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .view-content :global(.report-section) {
    padding-bottom: var(--space-10);
    background: transparent;
  }

  .view-content :global(.report-section:last-child) {
    padding-bottom: 0;
  }

  .view-content :global(.markdown-content p),
  .view-content :global(.markdown-content li) {
    max-width: 72ch;
  }

  .methods-summary,
  .first-steps,
  .fallback-section {
    display: grid;
    gap: var(--space-6);
    padding: var(--space-6);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .methods-summary h3,
  .first-steps h3,
  .fallback-section h3 {
    margin: var(--space-2) 0 0;
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .methods-summary dl {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: 0;
    border-block: 1px solid var(--color-border);
  }

  .methods-summary dl div {
    padding: var(--space-4);
  }

  .methods-summary dl div + div {
    border-left: 1px solid var(--color-border);
  }

  .methods-summary dt {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .methods-summary dd {
    margin: var(--space-2) 0 0;
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .quality-interpretation {
    max-width: 76ch;
    margin: 0;
    padding: var(--space-4);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .quality-interpretation.caution {
    background: var(--color-warning-subtle);
    color: var(--color-warning-text);
  }

  .portfolio-note {
    padding-top: var(--space-5);
    border-top: 1px solid var(--color-border);
  }

  .portfolio-note strong {
    font-size: var(--text-base);
    color: var(--color-text-primary);
  }

  .portfolio-note p {
    max-width: 76ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .fallback-heading > p {
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .finding-list,
  .plain-list,
  .named-list,
  .ruled-out-list {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .finding-list {
    display: grid;
  }

  .finding-list li {
    display: grid;
    grid-template-columns: var(--space-10) minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-5) 0;
    border-top: 1px solid var(--color-border);
  }

  .finding-list li > span {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-text-muted);
  }

  .finding-list strong {
    color: var(--color-text-primary);
    font-size: var(--text-base);
  }

  .finding-list p {
    max-width: 72ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .plain-list {
    display: grid;
    gap: var(--space-3);
  }

  .plain-list li {
    position: relative;
    padding-left: var(--space-5);
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.55;
  }

  .plain-list li::before {
    content: "";
    position: absolute;
    top: 0.65em;
    left: 0;
    width: var(--space-1);
    height: var(--space-1);
    border-radius: var(--radius-full);
    background: var(--color-text-muted);
  }

  .named-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2) var(--space-6);
    margin-top: var(--space-4);
  }

  .named-list li {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) 0;
    border-top: 1px solid var(--color-border);
  }

  .named-list strong,
  .named-list span {
    font-size: var(--text-sm);
  }

  .named-list strong {
    color: var(--color-text-primary);
  }

  .named-list span {
    color: var(--color-text-muted);
    text-align: right;
  }

  .legacy-narrative {
    max-width: 76ch;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.65;
  }

  .legacy-narrative :global(:first-child) {
    margin-top: 0;
  }

  .legacy-narrative :global(:last-child) {
    margin-bottom: 0;
  }

  .availability-note {
    margin: 0;
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.55;
  }

  .compact-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
    margin: 0;
    border-block: 1px solid var(--color-border);
  }

  .compact-metrics div {
    padding: var(--space-4);
  }

  .compact-metrics dt {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  .compact-metrics dd {
    margin: var(--space-2) 0 0;
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 700;
  }

  .narrative-copy {
    max-width: 76ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.65;
  }

  .ruled-out-note summary {
    min-height: var(--space-8);
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 700;
    cursor: pointer;
  }

  .ruled-out-list {
    display: grid;
    gap: var(--space-3);
    margin-top: var(--space-4);
  }

  .ruled-out-list li {
    display: grid;
    gap: var(--space-1);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border);
  }

  .ruled-out-list strong {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }

  .ruled-out-list span {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  .first-steps ol {
    display: grid;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .first-steps li {
    display: grid;
    grid-template-columns: var(--space-10) minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-5) 0;
    border-top: 1px solid var(--color-border);
  }

  .first-steps li > span {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-text-muted);
  }

  .first-steps li p {
    max-width: 74ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .inline-empty {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding-top: var(--space-5);
    border-top: 1px solid var(--color-border);
    color: var(--color-text-secondary);
  }

  .inline-empty :global(svg) {
    width: var(--space-5);
    height: var(--space-5);
    flex: 0 0 auto;
  }

  .inline-empty p {
    margin: 0;
  }

  .detail-mode {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-5);
    margin-bottom: var(--space-6);
    padding: var(--space-4) var(--space-5);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }

  .detail-mode span,
  .detail-mode strong {
    display: block;
  }

  .detail-mode span {
    margin-bottom: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .detail-mode strong {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }

  .detail-mode a {
    min-height: var(--space-8);
    display: inline-flex;
    align-items: center;
    padding: 0 var(--space-3);
    border-radius: var(--radius-md);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
    transition: background-color var(--duration-fast) var(--ease-default);
  }

  .detail-mode a:hover {
    background: var(--color-bg-hover);
  }

  .detail-mode a:active {
    background: var(--color-bg-active);
  }

  /* Final reports are documents first. Explicit full-detail views must remain
     complete in print and browser captures even before every section intersects. */
  .full-detail :global(.animate-fade-up),
  .full-detail :global(.animate-fade-in-triggered),
  .full-detail :global(.animate-scale-in),
  .full-detail :global(.animate-slide-left),
  .full-detail :global(.animate-slide-right) {
    opacity: 1;
    transform: none;
    transition: none;
  }

  @media (max-width: 72rem) {
    .report-shell {
      grid-template-columns: 1fr;
      gap: var(--space-6);
      padding-top: var(--space-6);
    }

    .report-index {
      display: none;
    }

    .mobile-view-nav {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      margin-top: var(--space-8);
      border-bottom: 1px solid var(--color-border);
    }

    .mobile-view-nav a {
      position: relative;
      min-height: var(--space-12);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--color-text-secondary);
      font-size: var(--text-base);
      font-weight: 700;
      text-decoration: none;
    }

    .mobile-view-nav a::after {
      content: "";
      position: absolute;
      inset: auto 0 0;
      height: 2px;
      background: transparent;
    }

    .mobile-view-nav a.active {
      color: var(--color-text-primary);
    }

    .mobile-view-nav a.active::after {
      background: var(--color-accent);
    }

    .report-header {
      padding-bottom: 0;
    }
  }

  @media (max-width: 42rem) {
    .report-shell {
      padding: var(--space-4) var(--space-4) var(--space-12);
    }

    .report-header-top {
      align-items: flex-start;
      flex-direction: column;
      margin-bottom: var(--space-6);
    }

    .detail-mode {
      align-items: stretch;
      flex-direction: column;
    }

    .detail-mode a {
      justify-content: center;
    }

    .report-identity h1 {
      font-size: var(--text-3xl);
    }

    .report-deck {
      font-size: var(--text-md);
    }

    .report-meta {
      display: grid;
      gap: var(--space-2);
    }

    .report-meta span + span::before {
      content: none;
    }

    .view-heading h2 {
      font-size: var(--text-2xl);
    }

    .topic-nav {
      display: flex;
      overflow-x: auto;
      scroll-snap-type: x mandatory;
    }

    .topic-nav a {
      flex: 0 0 11rem;
      scroll-snap-align: start;
    }

    .methods-summary,
    .first-steps,
    .fallback-section {
      padding: var(--space-5);
    }

    .methods-summary dl {
      grid-template-columns: 1fr;
    }

    .methods-summary dl div + div {
      border-top: 1px solid var(--color-border);
      border-left: 0;
    }

    .named-list {
      grid-template-columns: 1fr;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .report-index a,
    .back-link,
    .topic-nav a {
      transition: none;
    }
  }

  @media print {
    .report-index,
    .report-header-top,
    .mobile-view-nav,
    .topic-nav {
      display: none;
    }

    .report-shell {
      display: block;
      width: auto;
      padding: 0;
    }

    .report-header {
      margin-bottom: var(--space-8);
    }
  }
</style>
