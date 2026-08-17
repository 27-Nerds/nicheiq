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
  import NicheReframeNote from "$lib/components/NicheReframeNote.svelte";
  import GTMPlaybook from "$lib/components/sections/GTMPlaybook.svelte";
  import SEOKeywords from "$lib/components/sections/SEOKeywords.svelte";
  import TechnicalBlueprint from "$lib/components/sections/TechnicalBlueprint.svelte";
  import DataInfrastructure from "$lib/components/sections/DataInfrastructure.svelte";
  import AlternativesSection from "$lib/components/sections/AlternativesSection.svelte";
  import EvidenceAppendix from "$lib/components/sections/EvidenceAppendix.svelte";
  import CoverageNotes from "$lib/components/CoverageNotes.svelte";
  import HelpLink from "$lib/components/ui/HelpLink.svelte";
  import {
    humanizeReportProse,
    leadSentence,
    normalizeSeoScalabilityNarrative,
    renderMarkdown,
  } from "$lib/utils/format";
  import {
    buyerFacingReport,
    buyerFacingSolutionPreview,
  } from "$lib/selection/buyerFacingResearchProse";
  import type { SolutionPreview } from "$lib/types/job";
  import { afterNavigate, replaceState } from "$app/navigation";
  import { localReportDate, utcReportDate } from "$lib/utils/reportDates";
  import { unavailableSectionNotes } from "$lib/utils/unavailableSections";
  import { planVerdictGate } from "$lib/utils/verdictGate";
  import { humanizeTag } from "$lib/utils/ideaTagLabels";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import { tick, type ComponentType, type Snippet } from "svelte";

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

  let {
    report: sourceReport,
    showBackLink = true,
    jobId,
    headerSlot,
    decisionSlot,
  }: Props = $props();

  function safeEvidenceUrl(value: string | null | undefined): string | null {
    if (!value) return null;
    try {
      const url = new URL(value);
      const host = url.hostname.toLowerCase();
      const privateIpv4 = /^(?:10\.|127\.|169\.254\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)/;
      const privateIpv6 = /^(?:\[?::1\]?|\[?f[cd]|\[?fe[89ab])/;
      return url.protocol === "https:"
        && !url.username
        && !url.password
        && host !== "localhost"
        && !host.endsWith(".localhost")
        && !privateIpv4.test(host)
        && !privateIpv6.test(host)
        ? url.href
        : null;
    } catch {
      return null;
    }
  }

  const billingBasisLabel = (value: string): string => ({
    per_lead: "Per lead",
    per_sponsored_listing_month: "Per sponsored listing / month",
    per_paid_upgrade_month: "Per paid upgrade / month",
    affiliate_program: "Affiliate program",
  })[value] ?? value;

  const unitValueSummary = (
    evidence: NonNullable<NonNullable<Report["traffic_monetization"]>["unit_value_evidence"]>,
  ): string | null => {
    if (evidence.value_low == null || evidence.value_high == null) return null;
    const range = evidence.value_low === evidence.value_high
      ? `$${evidence.value_low}`
      : `$${evidence.value_low} - $${evidence.value_high}`;
    return `${range} · ${billingBasisLabel(evidence.billing_basis)}`;
  };
  // The single seam every report view shares. `detail=full` and the
  // Research-quality tab hand raw report fields to the older section components,
  // which never picked up the summary layer's per-call-site humanising — so the
  // page was honest at a glance and reverted to internal names one click deeper.
  // Rewriting once here covers both branches and anything added to either later.
  //
  // `buyerFacingReport` is the second half of that same seam. `humanizeReportProse`
  // rewrites internal field names everywhere; the niche-difficulty verdict and the idea
  // portfolio summary carry a research vocabulary of their own ("corpus", "wedge",
  // "cold-start", "web-verified") that needs sentence-level rewrites, and those two fields
  // reached the paid brief raw through ReportBrief's risk list and the portfolio note
  // below. Normalising both here means a section component cannot forget and a new one
  // cannot regress.
  //
  // `buyerFacingIdeas` is the third. `buyerFacingReport` is field-scoped to the verdict and
  // the portfolio summary, and the IDEA objects hanging off the report carry a vocabulary of
  // their own that only `buyerFacingIdeaProse` knows: `critic_concern` printed "wedge",
  // "mechanism parity", "data_feas" and "cold-start corpus" verbatim on the paid Deep
  // Research report through AlternativesSection's critic panel, and `data_acquisition_notes`
  // did the same through the data badges' tooltips there and in TechnicalBlueprint. Measured
  // over every run under `output/`, 50 of the 210 distinct `alternative_solutions[]
  // .critic_concern` values carry it. Sanitising the ARRAY here rather than the three call
  // sites is the same doctrine `buyerFacingSolutionPreview` follows on the SolutionDetail
  // tree: every current and future consumer of these fields is covered by construction.
  const report = $derived(
    buyerFacingIdeas(buyerFacingReport(humanizeReportProse(sourceReport))),
  );
  let reportShell = $state<HTMLDivElement>();

  /**
   * `AlternativeSolution`, `SolutionDetails` and `SolutionPreview` are three TypeScript
   * declarations of the same pipeline idea object, and only the last one is what the
   * sanitizer is typed against. It reads nothing but the four prose fields all three share
   * and returns its input BY REFERENCE when none of them changed, so the cast is safe in
   * both directions and identity survives it.
   */
  function asBuyerFacingIdea<T extends object>(idea: T): T {
    return buyerFacingSolutionPreview(idea as unknown as SolutionPreview) as unknown as T;
  }

  /** Returns the report untouched when no idea changed, so `$derived` memoisation holds. */
  function buyerFacingIdeas<T extends Report>(source: T): T {
    const alternatives = source.alternative_solutions;
    const details = source.selected_solution_details;
    const nextAlternatives = alternatives?.map(asBuyerFacingIdea);
    const alternativesChanged = !!alternatives
      && !!nextAlternatives
      && nextAlternatives.some((alternative, index) => alternative !== alternatives[index]);
    const nextDetails = details ? asBuyerFacingIdea(details) : details;
    const detailsChanged = !!details && nextDetails !== details;
    if (!alternativesChanged && !detailsChanged) return source;
    return {
      ...source,
      ...(alternativesChanged ? { alternative_solutions: nextAlternatives! } : {}),
      ...(detailsChanged ? { selected_solution_details: nextDetails! } : {}),
    };
  }

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
  // SSR has no reader timezone, so the server emits the UTC label and the local
  // one is swapped in after mount — the initial markup stays byte-identical and
  // the reader ends up on the same calendar day the job page shows them.
  let viewerTimezoneReady = $state(false);
  $effect(() => {
    viewerTimezoneReady = true;
  });
  function readerDate(value: string | null | undefined): string | null {
    return (viewerTimezoneReady ? localReportDate(value) : null) ?? utcReportDate(value);
  }
  const generatedDate = $derived(readerDate(report.generated_at) ?? "Date unavailable");
  // Same treatment as generatedDate; a date-only or non-date string passes through raw.
  const collectionDate = $derived(
    readerDate(report.research_metadata?.collection_date)
      ?? report.research_metadata?.collection_date
      ?? "Not available",
  );
  const reportTitle = $derived(
    solutionDisplayTitle({
      headline: solutionDetails?.headline,
      solution_name: report.selected_solution_name,
    }),
  );
  // The slug-like working name rides as a mono record-line eyebrow only when the
  // headline actually replaced it as the H1.
  const workingName = $derived(
    reportTitle === report.selected_solution_name ? null : report.selected_solution_name,
  );
  const selectedIdeaIdentity = $derived.by(() => {
    const ideaId = solutionDetails.idea_id?.trim();
    const ideaRevision = solutionDetails.idea_revision;
    return ideaId && Number.isInteger(ideaRevision) && Number(ideaRevision) >= 1
      ? { ideaId, ideaRevision: Number(ideaRevision) }
      : null;
  });
  const qualityCaveatCount = $derived(
    new Set(report.data_quality_summary?.quality_caveats ?? []).size,
  );
  const researchQualityLabel = $derived.by(() => {
    const quality = report.data_quality_summary?.overall_data_quality?.trim();
    if (!quality) return "Not graded";
    const label = `${quality.slice(0, 1).toUpperCase()}${quality.slice(1).toLowerCase()}`;
    return qualityCaveatCount
      ? `${label} · ${qualityCaveatCount} ${qualityCaveatCount === 1 ? "caveat" : "caveats"}`
      : label;
  });
  const socialSourceRecordCount = $derived.by<number | null>(() => {
    const dashboardCount = report.executive_dashboard?.key_metrics?.social_evidence_threads;
    if (typeof dashboardCount === "number") return dashboardCount;
    const metadata = report.research_metadata;
    if (
      metadata?.reddit_posts_analyzed === undefined &&
      metadata?.twitter_threads_analyzed === undefined &&
      metadata?.generic_posts_analyzed === undefined
    ) {
      return null;
    }
    return (
      (metadata.reddit_posts_analyzed ?? 0) +
      (metadata.twitter_threads_analyzed ?? 0) +
      (metadata.generic_posts_analyzed ?? 0)
    );
  });
  const ideaPricingHypothesis = $derived(solutionDetails.pricing_strategy?.trim() ?? "");
  const ideaBusinessModel = $derived(humanizeTag(solutionDetails.tags?.monetization));
  const ideaGrowthChannels = $derived(
    (solutionDetails.tags?.growth_channels ?? []).slice(0, 4).map(humanizeTag).filter(Boolean),
  );
  const acquisitionSummary = $derived(
    normalizeSeoScalabilityNarrative(
      report.acquisition_strategy_summary ?? "",
      solutionDetails.seo_scalability_score,
    ),
  );

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
        !!report.estimated_cac_breakdown ||
        !!ideaPricingHypothesis ||
        !!ideaBusinessModel,
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
  // The verdict is computed last and never flowed back into the plan, so a No-Go idea
  // shipped a dated go-to-market with no gate. The gate reframes the view; it never
  // decides anything itself.
  const planGate = $derived(
    planVerdictGate(report.executive_dashboard?.go_no_go_verdict),
  );
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
  const activeTopic = $derived(
    currentView === "evidence"
      ? currentEvidenceTopic
      : currentView === "plan"
        ? currentPlanTopic
        : "",
  );
  // The full identity block — deck, context strip, provenance receipt — answers
  // "what is this report?", which is the Brief's own job. Repeating it above
  // Evidence and Plan pushed every view's content off the first screen and made
  // the three views repaint an identical header, so those views get a one-line
  // identity instead.
  const compactIdentity = $derived(currentView !== "brief");

  // The deck is a one-line answer to "what is this?", so it takes the shortest stored
  // field available. It used to fall through to the whole `executive_summary` — 1,093
  // characters as the page's first paint on the audited run, where `tagline` and
  // `short_description` were both empty and a 230-char `value_proposition` sat unused.
  // The full summary is not dropped: ReportBrief renders it under "What this idea is
  // built around", which is where a passage of that length belongs.
  const deckText = $derived(
    snapshot?.tagline?.trim()
      || solutionDetails?.short_description?.trim()
      || solutionDetails?.value_proposition?.trim()
      || leadSentence(report.executive_summary),
  );

  // Switching views is a query-param navigation: SvelteKit repaints the same
  // header and parks the reader at scrollY 0, so the click produces no visible
  // change. Land the viewport on the incoming view's own content instead. This
  // also carries the anchor-style links ("Review methods & limitations",
  // "Open research appendix"), which target content screens below the fold.
  let viewAnchor = $state<HTMLElement>();
  // Plain `let`, not `$state`: this is a dedupe guard the effect writes on every
  // run, and tracking it would re-enter the effect.
  let lastNavKey: string | null = null;
  $effect(() => {
    const navKey = `${currentView}|${activeTopic}|${isFullDetail}`;
    const anchor = viewAnchor;
    // First render establishes the baseline: arriving at a URL still starts at
    // the top of the report, where the identity block belongs.
    if (lastNavKey === null) {
      lastNavKey = navKey;
      return;
    }
    if (lastNavKey === navKey || !anchor) return;
    lastNavKey = navKey;
    tick().then(() => {
      requestAnimationFrame(() => {
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        anchor.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      });
    });
  });

  $effect(() => {
    currentView;
    currentEvidenceTopic;
    currentPlanTopic;
    if (!reportShell) return;

    requestAnimationFrame(() => {
      for (const nav of reportShell?.querySelectorAll<HTMLElement>(".mobile-view-nav, .topic-nav") ?? []) {
        const active = nav.querySelector<HTMLElement>('[aria-current]');
        if (!active || nav.scrollWidth <= nav.clientWidth) continue;
        const left = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2;
        nav.scrollLeft = Math.max(0, left);
      }
    });
  });
  const coverageNotes = $derived.by(() => [
    ...new Set([
      ...(report.data_quality_summary?.quality_caveats ?? []).map((note) =>
        /^fallback data used in:/i.test(note)
          ? "Fallback data was used for part of this run, so some findings have reduced depth."
          : note,
      ),
      // A degraded dashboard section is stated here rather than silently omitted.
      ...unavailableSectionNotes(report.executive_dashboard?.unavailable_sections),
    ]),
  ]);
  const researchQualityLimited = $derived.by(() => {
    const quality = report.data_quality_summary?.overall_data_quality?.trim().toLowerCase();
    return !quality || quality.includes("low") || coverageNotes.length > 0;
  });
  const researchQualitySummary = $derived.by(() => {
    const quality = report.data_quality_summary?.overall_data_quality?.trim();
    if (!quality) {
      return "This report does not include an overall data-quality grade. Treat ungraded findings as directional.";
    }
    if (quality.toLowerCase().includes("low")) {
      return "Coverage is limited. Use this report to choose what to verify next, not as proof that the market is validated.";
    }
    if (coverageNotes.length) {
      return `Recorded data quality: ${quality}. ${coverageNotes.length} ${coverageNotes.length === 1 ? "caveat requires" : "caveats require"} review before acting on consequential claims.`;
    }
    return `Recorded data quality: ${quality}. No additional quality caveats were retained.`;
  });

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
  // The dated playbook lives in the launch appendix, so this link crosses tabs and
  // moves the underline. Name the destination rather than letting it jump silently.
  const firstMonthDestination = $derived(
    hasDatedPlaybook ? planTopics.find((topic) => topic.id === "launch")?.label : undefined,
  );

  // An unrecognised slug (?topic=quality) used to render the first available topic
  // while the address bar kept the bad value, so the page disagreed with its own
  // URL and the reader could bookmark or share a link that never resolves. Rewrite
  // the URL to the view and topic actually shown.
  //
  // afterNavigate, not $effect, because effects flush inside the hydration render.
  // The rewrite itself waits a microtask on top of that: on the first load
  // SvelteKit runs the afterNavigate callbacks a few statements before it marks
  // the router started, and replaceState throws until it has.
  afterNavigate(() => {
    const requestedViewParam = page.url.searchParams.get("view");
    const requestedTopicParam = page.url.searchParams.get("topic");
    const viewUnknown = requestedViewParam !== null && requestedViewParam !== currentView;
    const topicUnknown = requestedTopicParam !== null && requestedTopicParam !== activeTopic;
    if (!viewUnknown && !topicUnknown) return;
    const canonical = reportHref(
      currentView,
      activeTopic || undefined,
      isFullDetail ? "full" : undefined,
    );
    tick().then(() => replaceState(canonical, page.state));
  });
</script>

<div bind:this={reportShell} class="report-shell">
  <aside class="report-index">
    <nav aria-label="Report views">
      <p class="index-title">Research report</p>
      <ol>
        {#each views as item, index}
          {@const Icon = item.icon}
          <li>
            <a
              href={reportHref(item.id)}
              data-sveltekit-noscroll
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
  </aside>

  <!-- The app/public layouts already provide the page's single main landmark. -->
  <div class="report-main">
    <header class="report-header" class:compact={compactIdentity}>
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

      <div class="report-identity" class:compact={compactIdentity}>
        <p>Deep Research report · {generatedDate}</p>
        {#if workingName}
          <p class="working-name">{workingName}</p>
        {/if}
        <h1>{reportTitle}</h1>
        <!-- Stage-1 reframe disclosure. The report labels itself with the SUBMITTED text
             (`nicheName` reads `niche_context.niche_input`) while every finding under it
             was researched against the wider derived market — the one place a reader is
             most likely to assume the two are the same. Outside the `compactIdentity`
             branch on purpose: it must survive on every report view, not just the brief. -->
        <NicheReframeNote context={report.niche_context} />
        {#if !compactIdentity}
          <div class="report-deck">{deckText}</div>
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
          <div class="research-receipt" aria-label="Research provenance summary">
            <dl>
              <div>
                <dt>Recorded data quality</dt>
                <dd class:limited={researchQualityLimited}>{researchQualityLabel}</dd>
              </div>
              <div>
                <dt>Social source records</dt>
                <dd>{socialSourceRecordCount ?? "Not available"}</dd>
              </div>
              <div>
                <dt>Collected</dt>
                <dd>{collectionDate}</dd>
              </div>
              {#if selectedIdeaIdentity}
                <div>
                  <dt>Selected revision</dt>
                  <dd title={`${selectedIdeaIdentity.ideaId} · revision ${selectedIdeaIdentity.ideaRevision}`}>
                    Revision {selectedIdeaIdentity.ideaRevision}
                  </dd>
                </div>
              {/if}
            </dl>
            <a href={reportHref("evidence", "sources")} data-sveltekit-noscroll>
              Review methods &amp; limitations
            </a>
          </div>
        {/if}
        <nav class="report-help" aria-label="Related help">
          <HelpLink
            href="/help/reading-and-sharing-reports"
            label="Guide to reading and sharing reports"
          />
        </nav>
      </div>

    </header>

    <div class="report-views" bind:this={viewAnchor}>
    <nav class="mobile-view-nav" aria-label="Report views">
      {#each views as item}
        <a
          href={reportHref(item.id)}
          data-sveltekit-noscroll
          class:active={currentView === item.id}
          aria-current={currentView === item.id ? "page" : undefined}
        >
          {item.label}
        </a>
      {/each}
    </nav>

    {#if currentView === "brief"}
      <ReportBrief
        {report}
        {deckText}
        {reportTitle}
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
              data-sveltekit-noscroll
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
              corePainPoint={report.executive_dashboard?.core_pain_point ?? undefined}
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
                <h3 id="monetization-summary-title">
                  {report.traffic_monetization.viability_verdict === "nonviable"
                    ? "Traffic route rejected"
                    : "How this model could earn revenue"}
                </h3>
              </div>
              <dl class="compact-metrics">
                <div>
                  <dt>Model</dt>
                  <dd>{report.traffic_monetization.monetization_model}</dd>
                </div>
                {#if report.traffic_monetization.viability_verdict !== "nonviable" && report.traffic_monetization.estimated_monthly_revenue_range}
                  <div>
                    <dt>Estimated monthly range</dt>
                    <dd>{report.traffic_monetization.estimated_monthly_revenue_range}</dd>
                  </div>
                {/if}
                {#if report.traffic_monetization.viability_verdict}
                  <div>
                    <dt>Route viability</dt>
                    <dd>{report.traffic_monetization.viability_verdict}</dd>
                  </div>
                {/if}
                {#if report.traffic_monetization.viability_verdict !== "nonviable" && report.traffic_monetization.estimated_funnel_value}
                  <div>
                    <dt>Estimated funnel value</dt>
                    <dd>{report.traffic_monetization.estimated_funnel_value}</dd>
                  </div>
                {/if}
              </dl>
              {#if report.traffic_monetization.viability_verdict !== "nonviable" && report.traffic_monetization.qualified_actions}
                <p class="narrative-copy">
                  Qualified actions: {report.traffic_monetization.qualified_actions}
                </p>
              {/if}
              {#if report.traffic_monetization.viability_verdict !== "nonviable" && report.traffic_monetization.conversion_assumptions?.length}
                <ul class="plain-list">
                  {#each report.traffic_monetization.conversion_assumptions as assumption}
                    <li>{assumption}</li>
                  {/each}
                </ul>
              {/if}
              {#if report.traffic_monetization.viability_verdict !== "nonviable" && report.traffic_monetization.unit_value_evidence}
                {@const evidenceUrl = safeEvidenceUrl(report.traffic_monetization.unit_value_evidence.source_url)}
                {@const evidenceValue = unitValueSummary(report.traffic_monetization.unit_value_evidence)}
                {#if report.traffic_monetization.unit_value_evidence.retrieved_quote}
                  <p class="narrative-copy">
                    Verified quote:
                    <span> {report.traffic_monetization.unit_value_evidence.retrieved_quote}</span>
                  </p>
                {/if}
                {#if evidenceValue}<p class="narrative-copy">{evidenceValue}</p>{/if}
                <p class="narrative-copy">
                  Unit value source:
                  {#if evidenceUrl}
                    <a href={evidenceUrl} target="_blank" rel="noopener noreferrer">
                      {report.traffic_monetization.unit_value_evidence.source_name}
                    </a>
                  {:else}
                    <span>{report.traffic_monetization.unit_value_evidence.source_name}</span>
                  {/if}
                </p>
              {/if}
              <p class="narrative-copy">{report.traffic_monetization.monetization_rationale}</p>
            </section>
          {:else if ideaPricingHypothesis || ideaBusinessModel}
            <section class="fallback-section" aria-labelledby="pricing-hypothesis-title">
              <div class="fallback-heading">
                <p>Idea-stage hypothesis</p>
                <h3 id="pricing-hypothesis-title">Pricing direction to validate</h3>
              </div>
              {#if ideaBusinessModel}
                <dl class="compact-metrics">
                  <div>
                    <dt>Proposed model</dt>
                    <dd>{ideaBusinessModel}</dd>
                  </div>
                </dl>
              {/if}
              {#if ideaPricingHypothesis}
                <p class="narrative-copy">{ideaPricingHypothesis}</p>
              {/if}
              <p class="availability-note">
                This direction was carried forward from the selected idea. Structured pricing and
                monetization research was not generated; validate willingness to pay before using
                it as a plan.
              </p>
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
                <dt>Recorded data quality</dt>
                <dd>{report.data_quality_summary?.overall_data_quality ?? "Not graded"}</dd>
              </div>
              <div>
                <dt>Social source records</dt>
                <dd>{socialSourceRecordCount ?? "Not available"}</dd>
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
                <dd>{collectionDate}</dd>
              </div>
            </dl>
            {#if report.idea_portfolio_summary}
              <details class="portfolio-note historical-note">
                <summary>Earlier idea-pool assessment</summary>
                <p class="historical-context">
                  This snapshot was written before the shortlist was selected and before Deep
                  Research. It records the earlier pool-level assessment, not the final verdict for
                  {report.selected_solution_name}. Use the Brief for the current recommendation.
                </p>
                <p>{report.idea_portfolio_summary}</p>
              </details>
            {/if}
            {#if report.market_reality}
              <div class="portfolio-note market-reality-note">
                <strong>Market reality</strong>
                {#if report.market_reality.wallet?.evidence}
                  <p>{report.market_reality.wallet.evidence}</p>
                {/if}
                {#if report.market_reality.incumbents.length}
                  <!-- A third, wider population than either competitor count on the
                       Competition tab: incumbents checked on the web across the whole
                       niche, shown as a capped list. Named and counted so the three
                       numbers read as different scopes rather than as disagreeing
                       answers. "Web-verified" is the pipeline's word, not the buyer's. -->
                  <p class="incumbent-scope">
                    Incumbents checked on the web across the niche:
                    {report.market_reality.incumbents.length > 8
                      ? `first 8 of ${report.market_reality.incumbents.length}`
                      : `all ${report.market_reality.incumbents.length}`}. This is
                    the whole niche, not the direct competitors for the selected idea.
                  </p>
                  <!-- The label a screen reader announces has to match the visible copy
                       above it, which is the comment's own point: "Web-verified" is the
                       pipeline's word, not the buyer's. -->
                  <ul class="named-list" aria-label="Niche incumbents checked on the web">
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
          {#if coverageNotes.length}
            <CoverageNotes notes={coverageNotes} />
          {/if}
          {#if report.evidence_appendix}
            <EvidenceAppendix
              data={report.evidence_appendix}
              selectedPainTitle={report.executive_dashboard?.core_pain_point?.title}
            />
          {/if}
        {/if}
        {/if}
      </div>
    {:else}
      <section class="view-heading" aria-labelledby="plan-view-title">
        <p>{planGate?.eyebrow ?? "Act on the research"}</p>
        <h2 id="plan-view-title">
          {planGate?.heading ?? "Turn the recommendation into an executable plan"}
        </h2>
        <div>
          {#if planGate}
            {planGate.lead}
          {:else if hasDatedPlaybook}
            Start with the dated 30-day playbook, then open product or launch detail when you
            need it.
          {:else}
            Start with the recommended sequence, then open product or launch detail when you
            need it.
          {/if}
        </div>
      </section>

      {#if planGate}
        <aside class="plan-gate {planGate.tone}" aria-labelledby="plan-gate-title">
          <CircleAlert aria-hidden="true" />
          <div>
            <h3 id="plan-gate-title">{planGate.title}</h3>
            <p class="plan-gate-spend">{planGate.spendNote}</p>
            <a href={reportHref("brief")}>See how the verdict was reached</a>
          </div>
        </aside>
      {/if}

      <nav class="topic-nav" aria-label="Plan topics">
          {#each planTopics as topic}
            <a
              href={reportHref("plan", topic.id)}
              data-sveltekit-noscroll
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
            {deckText}
            topic={currentPlanTopic}
            fullDetailHref={currentPlanTopic === "first-30-days"
              ? fullFirstMonthHref
              : reportHref("plan", currentPlanTopic, "full")}
            fullDetailDestination={currentPlanTopic === "first-30-days"
              ? firstMonthDestination
              : undefined}
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
          {:else if acquisitionSummary}
            <section class="fallback-section" aria-labelledby="acquisition-summary-title">
              <div class="fallback-heading">
                <p>Acquisition summary</p>
                <h3 id="acquisition-summary-title">How to reach the first customers</h3>
              </div>
              <div class="legacy-narrative">
                {@html renderMarkdown(acquisitionSummary)}
              </div>
            </section>
          {/if}
          {#if !report.go_to_market_blueprint && ideaGrowthChannels.length}
            <section class="fallback-section" aria-labelledby="channel-hypothesis-title">
              <div class="fallback-heading">
                <p>Idea-stage hypothesis</p>
                <h3 id="channel-hypothesis-title">Channels to test</h3>
              </div>
              <ul class="plain-list">
                {#each ideaGrowthChannels as channel}
                  <li>{channel}</li>
                {/each}
              </ul>
              <p class="availability-note">
                These directions were carried forward from the selected idea. Deep Research did
                not generate a channel plan, so test them before committing budget.
              </p>
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
                    <!-- Aggregate volume across every analyzed keyword, most of
                         which sit outside this idea's intent — category reach,
                         not validated demand for the idea. -->
                    <dt>Category reach (monthly)</dt>
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
    color: var(--color-text-secondary);
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

  .report-header.compact {
    margin-bottom: var(--space-6);
    padding-bottom: var(--space-4);
  }

  .report-header.compact .report-header-top {
    margin-bottom: var(--space-4);
  }

  /* Scroll target for view switches. The margin keeps the incoming view's
     heading off the very top edge of the viewport once it lands. */
  .report-views {
    scroll-margin-top: var(--space-6);
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

  .report-help {
    display: flex;
    margin-top: var(--space-3);
  }

  /* Working-name eyebrow — record-line recipe (DESIGN_SYSTEM §2): the run's slug
     identity sits directly above the headline H1 that replaced it. */
  .report-identity > p.working-name {
    margin: 0 0 var(--space-1-5);
    letter-spacing: 0.07em;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
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

  /* Evidence and Plan keep only the dateline and the title, so the view's own
     heading and its content start above the fold. */
  .report-identity.compact > p {
    margin-bottom: var(--space-2);
  }

  .report-identity.compact h1 {
    max-width: 52ch;
    font-size: var(--text-2xl);
    line-height: 1.2;
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

  .research-receipt {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-4);
    align-items: center;
    margin-top: var(--space-5);
    padding-block: var(--space-4);
    border-block: 1px solid var(--color-border);
  }

  .research-receipt dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
    gap: var(--space-3) var(--space-5);
    margin: 0;
  }

  .research-receipt dt {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .research-receipt dd {
    margin: var(--space-1) 0 0;
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .research-receipt dd.limited {
    color: var(--color-warning-text);
  }

  .research-receipt a {
    display: inline-flex;
    align-items: center;
    min-height: var(--space-8);
    padding-inline: var(--space-2);
    border-radius: var(--radius-md);
    color: var(--color-accent-dark);
    font-size: var(--text-sm);
    font-weight: 700;
    text-underline-offset: 0.2em;
  }

  .research-receipt a:hover {
    background: var(--color-bg-hover);
  }

  .research-receipt a:focus-visible {
    outline: 2px solid var(--color-accent-dark);
    outline-offset: 2px;
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

  .plan-gate {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--space-4);
    align-items: start;
    margin-bottom: var(--space-6);
    padding: var(--space-5) var(--space-6);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-warning-subtle);
  }

  .plan-gate.negative {
    background: var(--color-error-subtle);
  }

  .plan-gate :global(svg) {
    width: var(--space-6);
    height: var(--space-6);
    color: var(--color-warning-text);
  }

  .plan-gate.negative :global(svg) {
    color: var(--color-error-text);
  }

  .plan-gate h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .plan-gate-spend {
    max-width: 72ch;
    margin: var(--space-2) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.6;
  }

  .plan-gate a {
    display: inline-block;
    margin-top: var(--space-3);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
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

  /* Scope caption for the incumbent list — meta, not body copy. */
  .portfolio-note p.incumbent-scope {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
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

  .ruled-out-note summary,
  .historical-note summary {
    min-height: var(--space-8);
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 700;
    cursor: pointer;
  }

  .historical-note .historical-context {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
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
      position: sticky;
      top: 0;
      z-index: 10;
      grid-template-columns: repeat(3, 1fr);
      margin-bottom: var(--space-6);
      border-bottom: 1px solid var(--color-border);
      background: var(--color-bg-base);
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

    /* The sticky mobile view nav supplies the separation here, so the header
       closes flush on every view — including the compact ones. */
    .report-header,
    .report-header.compact {
      margin-bottom: 0;
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

    /* The context strip and the provenance receipt are both restated below — in
       the Brief's own coverage list and on Evidence → Research quality — and
       together they ran the whole first screen, so the narrow Brief opened on
       identity with no finding in view. The methods link stays. */
    .report-meta,
    .research-receipt dl {
      display: none;
    }

    .research-receipt {
      grid-template-columns: 1fr;
      align-items: start;
      margin-top: var(--space-4);
      padding-block: var(--space-3);
    }

    .research-receipt a {
      justify-self: start;
    }

    .view-heading h2 {
      font-size: var(--text-2xl);
    }

    /* A horizontal scroller hid the last topic behind a hairline track — on
       Evidence that is "Research quality", which carries every caveat. Wrap the
       strip instead so nothing depends on discovering a swipe. */
    .topic-nav {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .topic-nav a {
      min-height: var(--space-14);
      padding: var(--space-3);
    }

    .topic-nav a:nth-child(odd) {
      border-right: 1px solid var(--color-border);
    }

    .topic-nav a:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }

    /* An odd final topic takes the full row rather than leaving a torn edge. */
    .topic-nav a:last-child:nth-child(odd) {
      grid-column: 1 / -1;
      border-right: 0;
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
