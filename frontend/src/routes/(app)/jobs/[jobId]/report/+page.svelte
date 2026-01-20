<script lang="ts">
	import type { Report } from '$lib/types/report';
	import { ArrowLeft, AlertTriangle } from 'lucide-svelte';

	// PHASE 1: DECISION (Go/No-Go verdict)
	import ExecutiveSummary from '$lib/components/sections/ExecutiveSummary.svelte';
	import SolutionHero from '$lib/components/sections/SolutionHero.svelte';

	// PHASE 2: VALIDATE (Is the opportunity real?)
	import PainAnalysis from '$lib/components/sections/PainAnalysis.svelte';
	import MarketSizing from '$lib/components/sections/MarketSizing.svelte';
	import MonetizationStrategy from '$lib/components/sections/MonetizationStrategy.svelte';
	import TrendSection from '$lib/components/sections/TrendSection.svelte';
	import Competitors from '$lib/components/sections/Competitors.svelte';

	// PHASE 3: EXECUTE (How to launch & build)
	import AudienceSection from '$lib/components/sections/AudienceSection.svelte';
	import ContentInsights from '$lib/components/sections/ContentInsights.svelte';
	import GTMPlaybook from '$lib/components/sections/GTMPlaybook.svelte';
	import SEOKeywords from '$lib/components/sections/SEOKeywords.svelte';
	import TechnicalBlueprint from '$lib/components/sections/TechnicalBlueprint.svelte';
	import DataInfrastructure from '$lib/components/sections/DataInfrastructure.svelte';

	// PHASE 4: REFERENCE (Appendix)
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

	// Get severity label (HIGH/MEDIUM/LOW)
	function getSeverityLabel(score: number | undefined): string {
		if (!score) return '';
		if (score >= 0.7) return 'HIGH';
		if (score >= 0.4) return 'MEDIUM';
		return 'LOW';
	}

	// Calculate total discussions analyzed
	const totalDiscussions = $derived(
		(report?.research_metadata?.reddit_posts_analyzed || 0) +
		(report?.research_metadata?.twitter_threads_analyzed || 0)
	);

	// Get pain point count
	const painPointCount = $derived(
		report?.pain_point_analytics?.total_pain_points ||
		report?.detailed_pain_points?.length || 0
	);
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

			<!-- Report Header -->
			<header class="report-header">
				<div class="header-hero">
					<h1 class="header-headline">WE DELIVER LAUNCH-READY<br/>BUSINESS SOLUTION.</h1>
				</div>

				<div class="header-content">
					<!-- Niche & Research Stats -->
					<div class="research-summary">
						<p class="niche-label">Researched Niche</p>
						<p class="niche-name">{report.niche}</p>
						<p class="research-stats">
							We analyzed {totalDiscussions} real discussions from Reddit{#if report.research_metadata?.twitter_threads_analyzed}, Twitter,{/if} and online communities and identified {painPointCount} mentions of specific problems.
						</p>
					</div>

					<!-- Solution Card -->
					<div class="solution-card">
						<div class="solution-badge">SOLUTION</div>
						<h2 class="solution-name">{report.selected_solution_name}</h2>
						<p class="solution-description">
							{report.selected_solution_details?.description || report.executive_summary?.slice(0, 300)}
						</p>

						<!-- Metrics Badges -->
						<div class="metrics-grid">
							{#if report.executive_dashboard?.core_pain_point?.severity_score}
								<span class="metric-badge">
									SEVERITY: {(report.executive_dashboard.core_pain_point.severity_score).toFixed(2)} ({getSeverityLabel(report.executive_dashboard.core_pain_point.severity_score)})
								</span>
							{/if}
							{#if report.executive_dashboard?.core_pain_point?.willingness_to_pay_score}
								<span class="metric-badge">
									WTP: {(report.executive_dashboard.core_pain_point.willingness_to_pay_score).toFixed(2)} {getSeverityLabel(report.executive_dashboard.core_pain_point.willingness_to_pay_score)}
								</span>
							{/if}
							{#if report.selected_solution_details?.market_fit_score}
								<span class="metric-badge">
									MARKET FIT: {Math.round(report.selected_solution_details.market_fit_score * 100)}%
								</span>
							{/if}
							{#if report.selected_solution_details?.technical_feasibility_score}
								<span class="metric-badge">
									FEASIBILITY: {Math.round(report.selected_solution_details.technical_feasibility_score * 100)}%
								</span>
							{/if}
							{#if report.selected_solution_details?.solo_dev_feasibility}
								<span class="metric-badge">
									SOLO DEV: {Math.round(report.selected_solution_details.solo_dev_feasibility * 100)}%
								</span>
							{/if}
						</div>
					</div>
				</div>
			</header>

			<!-- PHASE 1: DECISION (Go/No-Go verdict) -->
			<div class="phase-section phase-decision">
				<div class="phase-label">Decision</div>
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

			<!-- PHASE 2: VALIDATE (Is the opportunity real?) -->
			<div class="phase-section phase-validate">
				<div class="phase-label">Validate</div>
				{#if report.detailed_pain_points && report.detailed_pain_points.length > 0}
					<PainAnalysis
						painPoints={report.detailed_pain_points}
						analytics={report.pain_point_analytics}
						solution={solutionDetails}
					/>
				{/if}

				<MarketSizing data={report.market_sizing} />

				{#if report.pricing_strategy || report.traffic_monetization}
					<MonetizationStrategy
						pricingData={report.pricing_strategy}
						trafficData={report.traffic_monetization}
					/>
				{/if}

				{#if report.trend_longevity}
					<TrendSection data={report.trend_longevity} />
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
			</div>

			<!-- PHASE 3: EXECUTE (How to launch & build) -->
			<div class="phase-section phase-execute">
				<div class="phase-label">Execute</div>
				{#if report.audience_mapping}
					<AudienceSection data={report.audience_mapping} />
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

				{#if report.seo_strategy_report}
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
					/>
				{/if}

				{#if report.data_source_research_full}
					<DataInfrastructure data={report.data_source_research_full} />
				{/if}
			</div>

			<!-- PHASE 4: REFERENCE (Appendix) -->
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

	.phase-validate {
		--phase-tint: rgba(34, 197, 94, 0.02);
		--phase-accent: var(--color-success);
		--phase-text: var(--color-success-dark);
		--phase-label-bg: rgba(34, 197, 94, 0.08);
	}

	.phase-execute {
		--phase-tint: rgba(99, 102, 241, 0.02);
		--phase-accent: var(--color-secondary);
		--phase-text: var(--color-secondary);
		--phase-label-bg: rgba(99, 102, 241, 0.08);
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

		.phase-label {
			font-size: 0.5625rem;
			padding: 0.1875rem 0.5rem;
		}
	}

	/* Report Header */
	.report-header {
		margin-bottom: 2rem;
	}

	.header-hero {
		background: var(--color-accent);
		padding: 3rem 2rem;
		border-radius: 1rem 1rem 0 0;
	}

	.header-headline {
		font-size: 2.5rem;
		font-weight: 800;
		color: white;
		line-height: 1.1;
		text-transform: uppercase;
	}

	.header-content {
		background: var(--color-bg-elevated);
		padding: 2rem;
		border-radius: 0 0 1rem 1rem;
		border: 1px solid var(--color-border);
		border-top: none;
	}

	.research-summary {
		margin-bottom: 1.5rem;
		padding-bottom: 1.5rem;
		border-bottom: 1px solid var(--color-border);
	}

	.niche-label {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-bottom: 0.25rem;
	}

	.niche-name {
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 0.75rem;
	}

	.research-stats {
		font-size: 0.9rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}

	/* Solution Card */
	.solution-card {
		background: white;
		padding: 1.5rem;
		border-radius: 0.75rem;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
	}

	.solution-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-success);
		margin-bottom: 0.5rem;
	}

	.solution-badge::before {
		content: '\2705';
	}

	.solution-name {
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--color-success);
		margin-bottom: 0.75rem;
	}

	.solution-description {
		font-size: 0.95rem;
		color: var(--color-text-secondary);
		line-height: 1.6;
		margin-bottom: 1.25rem;
	}

	.metrics-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.metric-badge {
		display: inline-block;
		padding: 0.625rem 1rem;
		background: var(--color-bg-dark, #1a1a1a);
		color: white;
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		border-radius: 0.375rem;
	}

	/* Mobile responsive for header */
	@media (max-width: 768px) {
		.header-hero {
			padding: 2rem 1.25rem;
		}

		.header-headline {
			font-size: 1.75rem;
		}

		.header-content {
			padding: 1.25rem;
		}

		.solution-name {
			font-size: 1.35rem;
		}

		.metrics-grid {
			gap: 0.375rem;
		}

		.metric-badge {
			padding: 0.5rem 0.75rem;
			font-size: 0.7rem;
		}
	}
</style>
