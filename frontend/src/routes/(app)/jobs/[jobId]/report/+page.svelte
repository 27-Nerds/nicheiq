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
	import EmptyState from '$lib/components/ui/EmptyState.svelte';

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
		<EmptyState
			icon={AlertTriangle}
			title="Report Not Found"
			description="The requested report could not be loaded. It may have been deleted or you may not have permission to view it."
		>
			<a href="/jobs/{jobId}" class="btn-primary">Back to Job Status</a>
		</EmptyState>
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

			<!-- PHASE 1: DECISION GATEWAY (Go/No-Go) -->
			<div class="phase-section phase-decision">
				<div class="phase-label">Decision Gateway</div>
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
						<EmptyState
							icon={AlertTriangle}
							title="Executive Summary Unavailable"
							description="The executive dashboard could not be generated for this report. Some data may be missing from earlier pipeline stages."
							variant="warning"
						/>
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
			</div>

			<!-- PHASE 2: CUSTOMER & PROBLEM (Who & Why) -->
			<div class="phase-section phase-customer">
				<div class="phase-label">Customer & Problem</div>
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
			</div>

			<!-- PHASE 3: MARKET VIABILITY (Is It Worth It?) -->
			<div class="phase-section phase-market">
				<div class="phase-label">Market Viability</div>
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
						summary={report.competitive_summary}
					/>
				{/if}

				{#if report.trend_longevity}
					<TrendSection data={report.trend_longevity} />
				{/if}
			</div>

			<!-- PHASE 4: BUILD & EXECUTE -->
			<div class="phase-section phase-build">
				<div class="phase-label">Build & Execute</div>
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

				{#if report.go_to_market_blueprint}
					<GTMPlaybook
						gtmData={report.go_to_market_blueprint}
						nextSteps={report.next_steps}
					/>
				{/if}

				{#if report.data_source_research_full}
					<DataInfrastructure data={report.data_source_research_full} />
				{/if}
			</div>

			<!-- PHASE 5: REFERENCE (Appendix) -->
			<div class="phase-section phase-reference">
				<div class="phase-label">Reference</div>
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
			</div>
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

	/* Phase Section Styling */
	.phase-section {
		position: relative;
		padding: 2rem 0;
		margin-bottom: 1rem;
		border-radius: 1rem;
		background: var(--phase-tint, transparent);
	}

	.phase-section::before {
		content: '';
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 4px;
		border-radius: 2px;
		background: var(--phase-accent, var(--color-border));
	}

	.phase-label {
		position: absolute;
		top: 0;
		left: 1rem;
		transform: translateY(-50%);
		padding: 0.25rem 0.75rem;
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--phase-text, var(--color-text-muted));
		background: var(--phase-label-bg, var(--color-bg-base));
		border: 1px solid var(--phase-accent, var(--color-border));
		border-radius: 2rem;
	}

	/* Phase-specific colors */
	.phase-decision {
		--phase-tint: rgba(229, 90, 40, 0.02);
		--phase-accent: var(--color-accent);
		--phase-text: var(--color-accent);
		--phase-label-bg: rgba(229, 90, 40, 0.08);
	}

	.phase-customer {
		--phase-tint: rgba(99, 102, 241, 0.02);
		--phase-accent: var(--color-secondary);
		--phase-text: var(--color-secondary);
		--phase-label-bg: rgba(99, 102, 241, 0.08);
	}

	.phase-market {
		--phase-tint: rgba(34, 197, 94, 0.02);
		--phase-accent: var(--color-success);
		--phase-text: var(--color-success-dark);
		--phase-label-bg: rgba(34, 197, 94, 0.08);
	}

	.phase-build {
		--phase-tint: rgba(139, 92, 246, 0.02);
		--phase-accent: #8B5CF6;
		--phase-text: #7C3AED;
		--phase-label-bg: rgba(139, 92, 246, 0.08);
	}

	.phase-reference {
		--phase-tint: rgba(100, 116, 139, 0.02);
		--phase-accent: var(--color-text-muted);
		--phase-text: var(--color-text-muted);
		--phase-label-bg: rgba(100, 116, 139, 0.08);
	}

	@media (max-width: 768px) {
		.phase-section {
			padding: 1.5rem 0;
		}

		.phase-section::before {
			width: 3px;
		}

		.phase-label {
			font-size: 0.5625rem;
			padding: 0.1875rem 0.5rem;
		}
	}
</style>
