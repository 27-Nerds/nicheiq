<script lang="ts">
	import type { Report } from '$lib/types/report';
	import { ArrowLeft, AlertTriangle } from 'lucide-svelte';

	// Decision Gateway (Go/No-Go)
	import ExecutiveSummary from '$lib/components/sections/ExecutiveSummary.svelte';
	import SolutionHero from '$lib/components/sections/SolutionHero.svelte';

	// Customer & Problem (Who & Why)
	import AudienceSection from '$lib/components/sections/AudienceSection.svelte';
	import PainAnalysis from '$lib/components/sections/PainAnalysis.svelte';
	import ContentInsights from '$lib/components/sections/ContentInsights.svelte';

	// Market Viability (Is It Worth It?)
	import MarketSizing from '$lib/components/sections/MarketSizing.svelte';
	import MonetizationStrategy from '$lib/components/sections/MonetizationStrategy.svelte';
	import Competitors from '$lib/components/sections/Competitors.svelte';
	import TrendSection from '$lib/components/sections/TrendSection.svelte';

	// Build Specification (How)
	import TechnicalBlueprint from '$lib/components/sections/TechnicalBlueprint.svelte';
	import SEOKeywords from '$lib/components/sections/SEOKeywords.svelte';

	// Execution (Launch)
	import GTMPlaybook from '$lib/components/sections/GTMPlaybook.svelte';
	import DataInfrastructure from '$lib/components/sections/DataInfrastructure.svelte';

	// Reference (Appendix)
	import AlternativesSection from '$lib/components/sections/AlternativesSection.svelte';
	import EvidenceAppendix from '$lib/components/sections/EvidenceAppendix.svelte';
	import ResearchMetadata from '$lib/components/sections/ResearchMetadata.svelte';

	// UI components
	import SectionNav from '$lib/components/ui/SectionNav.svelte';

	// Header Summary
	import HeaderSummary from '$lib/components/sections/HeaderSummary.svelte';

	interface Props {
		data: {
			report: Report;
			jobId: string;
		};
	}

	let { data }: Props = $props();
	const report = $derived(data.report);
	const jobId = $derived(data.jobId);

	// Get solution details with fallback
	const solutionDetails = $derived(report?.selected_solution_details || {
		name: report?.selected_solution_name,
		description: report?.executive_summary || '',
		solution_name: report?.selected_solution_name
	});
</script>

<svelte:head>
	{#if report}
		<title>{report.selected_solution_name} - NicheIQ Report</title>
		<meta name="description" content={report.executive_summary?.slice(0, 160)} />
	{:else}
		<title>Report Not Found - NicheIQ</title>
	{/if}
</svelte:head>

{#if !report}
	<div class="min-h-screen flex items-center justify-center">
		<div class="text-center">
			<h1 class="text-2xl font-bold text-text-primary mb-4">Report Not Found</h1>
			<p class="text-text-secondary mb-6">The requested report could not be loaded.</p>
			<a href="/jobs/{jobId}" class="btn-primary">Back to Job Status</a>
		</div>
	</div>
{:else}
	<div class="report-layout">
		<!-- Section Navigation Overlay -->
		<SectionNav {report} />

		<!-- Main Content -->
		<main class="report-content">
			<!-- Back to Job Link -->
			<a href="/jobs/{jobId}" class="back-link">
				<ArrowLeft class="w-4 h-4" />
				<span>Back to Job Status</span>
			</a>

			<!-- Header Summary -->
			<HeaderSummary
				niche={report.niche}
				nicheContext={report.niche_context}
				researchMetadata={report.research_metadata}
				painPointAnalytics={report.pain_point_analytics}
				detailedPainPointsCount={report.detailed_pain_points?.length ?? 0}
				solutionName={report.selected_solution_name}
				solutionDescription={report.selected_solution_details?.description}
				severityScore={report.executive_dashboard?.core_pain_point?.severity_score}
				wtpScore={report.executive_dashboard?.core_pain_point?.willingness_to_pay_score}
				marketFitScore={report.selected_solution_details?.market_fit_score}
				feasibilityScore={report.selected_solution_details?.technical_feasibility_score}
				soloDevScore={report.selected_solution_details?.solo_dev_feasibility}
			/>

			<!-- DECISION GATEWAY (Go/No-Go) -->
			{#if report.executive_dashboard}
				<ExecutiveSummary
					data={report.executive_dashboard}
					executiveSummary={report.executive_summary}
					refinementHighlights={report.refinement_highlights}
					seoCalculationTransparency={report.seo_calculation_transparency}
					trends={report.trend_longevity}
				/>
			{:else}
				<section class="report-section">
					<div class="warning-banner">
						<AlertTriangle class="w-5 h-5 text-warning" />
						<div>
							<h3 class="font-semibold text-text-primary">Executive Summary Unavailable</h3>
							<p class="text-sm text-text-secondary">
								The executive dashboard could not be generated for this report.
								Some data may be missing from earlier pipeline stages.
							</p>
						</div>
					</div>
				</section>
			{/if}

			{#if report.executive_dashboard}
				<SolutionHero
					solution={solutionDetails}
					dashboard={report.executive_dashboard}
					selectionRationale={report.selection_rationale || ''}
					scores={report.selection_criteria_scores}
				/>
			{/if}

			<!-- CUSTOMER & PROBLEM (Who & Why) -->
			{#if report.audience_mapping}
				<AudienceSection data={report.audience_mapping} />
			{/if}

			{#if report.detailed_pain_points && report.detailed_pain_points.length > 0}
				<PainAnalysis
					painPoints={report.detailed_pain_points}
					analytics={report.pain_point_analytics}
					solution={solutionDetails}
				/>
			{/if}

			{#if report.content_categorization || report.overall_competitive_insights}
				<ContentInsights
					contentCategorization={report.content_categorization}
					overallCompetitiveInsights={report.overall_competitive_insights}
				/>
			{/if}

			<!-- MARKET VIABILITY (Is It Worth It?) -->
			<MarketSizing data={report.market_sizing} />

			{#if report.pricing_strategy || report.traffic_monetization}
				<MonetizationStrategy
					pricingData={report.pricing_strategy}
					trafficData={report.traffic_monetization}
				/>
			{/if}

			{#if report.competitive_analytics}
				<Competitors
					profiles={report.competitor_profiles || []}
					analysis={report.competitive_analysis}
					analytics={report.competitive_analytics}
					landscapeMatrix={report.competitive_landscape_matrix}
				/>
			{/if}

			{#if report.trend_longevity}
				<TrendSection data={report.trend_longevity} />
			{/if}

			<!-- BUILD SPECIFICATION (How) -->
			{#if solutionDetails}
				<TechnicalBlueprint
					solution={solutionDetails}
					implementationOverview={report.solution_implementation_overview}
					mvpScope={report.mvp_scope_definition}
					userJourney={report.solution_user_journey}
					dataInfrastructureRoadmap={report.data_infrastructure_roadmap}
				/>
			{/if}

			{#if report.seo_strategy_report}
				<SEOKeywords
					strategy={report.seo_strategy_report}
					analytics={report.seo_analytics}
				/>
			{/if}

			<!-- EXECUTION (Launch) -->
			{#if report.go_to_market_blueprint}
				<GTMPlaybook
					gtmData={report.go_to_market_blueprint}
					nextSteps={report.next_steps}
				/>
			{/if}

			{#if report.data_source_research_full}
				<DataInfrastructure data={report.data_source_research_full} />
			{/if}

			<!-- REFERENCE (Appendix) -->
			{#if report.alternative_solutions && report.alternative_solutions.length > 0}
				<AlternativesSection data={report.alternative_solutions} />
			{/if}

			{#if report.evidence_appendix}
				<EvidenceAppendix data={report.evidence_appendix} />
			{/if}

			{#if report.research_metadata}
				<ResearchMetadata
					metadata={report.research_metadata}
					overallConfidence={report.executive_dashboard?.confidence_score}
				/>
			{/if}
		</main>
	</div>
{/if}

<style>
	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		margin-bottom: 1rem;
		color: var(--color-text-secondary);
		font-size: 0.875rem;
		border-radius: 0.375rem;
		transition: all 0.15s ease;
	}

	.back-link:hover {
		color: var(--color-text-primary);
		background: var(--color-bg-elevated);
	}

	.niche-context-bar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		margin-bottom: 2rem;
	}

	.niche-label {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-text-muted);
	}

	.niche-value {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
	}

	.warning-banner {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 1.25rem;
		background: var(--color-warning-bg, rgba(234, 179, 8, 0.1));
		border: 1px solid var(--color-warning, #eab308);
		border-radius: 0.5rem;
	}
</style>
