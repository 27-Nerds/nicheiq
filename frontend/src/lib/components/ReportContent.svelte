<script lang="ts">
	import type { Report } from '$lib/types/report';
	import {
		ArrowLeft,
		AlertTriangle,
		Info
	} from 'lucide-svelte';

	// PHASE 1: DECISION (Go/No-Go verdict)
	import UnifiedHero from '$lib/components/sections/UnifiedHero.svelte';
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

	// UI components
	import SectionNav from '$lib/components/ui/SectionNav.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';

	interface Props {
		report: Report;
		showBackLink?: boolean;
		showShareButton?: boolean;
		jobId?: string;
		headerSlot?: import('svelte').Snippet;
	}

	let {
		report,
		showBackLink = true,
		jobId,
		headerSlot,
	}: Props = $props();

	// Get solution details with fallback
	const solutionDetails = $derived(report?.selected_solution_details || {
		name: report?.selected_solution_name,
		description: report?.executive_summary || '',
		solution_name: report?.selected_solution_name
	});

	// Filtering pipeline stats for UnifiedHero
	const funnelStats = $derived({
		scanned: (report?.research_metadata?.filtering_stats as Record<string, number>)?.reddit_urls_searched || 0,
		relevant: (report?.research_metadata?.filtering_stats as Record<string, number>)?.reddit_urls_relevant || 0,
		analyzed: report?.research_metadata?.reddit_posts_analyzed || 0,
		problems: report?.pain_point_analytics?.total_pain_points || report?.detailed_pain_points?.length || 0
	});

	// Niche display values
	const nicheName = $derived(report?.niche_context?.niche_input ?? report?.niche?.slice(0, 60) ?? 'Unknown Niche');
	const nicheDescription = $derived(report?.niche_context?.niche_description ?? report?.niche ?? '');
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
		<div class="mb-4 p-4 rounded-lg bg-gradient-to-r from-secondary/5 via-accent/5 to-secondary/5 border border-secondary/10">
			<div class="flex items-start gap-3">
				<div class="p-2 rounded-lg bg-secondary/10 shrink-0">
					<Info class="w-4 h-4 text-secondary" />
				</div>
				<p class="text-sm text-text-secondary">
					We're always improving report quality, but at the end of the day, AI is AI — it does a solid job, though it can occasionally get things wrong. Use this as your research starting point, not your final answer.
				</p>
			</div>
		</div>

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

		<!-- PHASE 1: DECISION (Solution details) -->
		<div class="phase-section phase-decision">
			<div class="phase-label">Decision</div>

			{#if report.executive_dashboard}
				<SolutionHero
					solution={solutionDetails}
					dashboard={report.executive_dashboard}
					selectionRationale={report.selection_rationale || ''}
					scores={report.selection_criteria_scores}
					budgetEstimate={report.go_to_market_blueprint?.budget_estimate}
				/>
			{/if}
		</div>

		<!-- PHASE 2: VALIDATE (Is the opportunity real?) -->
		<div class="phase-section phase-validate">
			<div class="phase-label">Validate</div>
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
			<div class="phase-label">Reference</div>
			{#if report.alternative_solutions && report.alternative_solutions.length > 0}
				<AlternativesSection data={report.alternative_solutions} />
			{/if}

			{#if report.evidence_appendix}
				<EvidenceAppendix data={report.evidence_appendix} />
			{/if}
		</div>
	</main>
</div>

<style>
	/* =========================
	   GLOBAL SECTION STYLES
	   ========================= */
	:global(.report-section) {
		padding: 1.5rem;
		background: var(--color-bg-base);
	}

	@media (max-width: 768px) {
		:global(.report-section) {
			padding: 1rem;
		}
	}

	/* =========================
	   GLOBAL HEADER STYLES
	   ========================= */
	:global(.section-header) {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}

	:global(.header-icon-wrap) {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		background: rgba(229, 90, 40, 0.1);
		border-radius: 0.5rem;
	}

	:global(.header-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: #E55A28;
	}

	:global(.header-text) {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	:global(.section-title) {
		font-family: var(--font-display);
		font-size: 1.375rem;
		font-weight: 800;
		color: #18181B;
		margin: 0;
	}

	:global(.section-subtitle) {
		font-size: 0.8125rem;
		color: #A1A1AA;
		margin: 0;
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
</style>
