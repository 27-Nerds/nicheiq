<script lang="ts">
	import type { Report } from '$lib/types/report';
	import {
		ArrowLeft,
		AlertTriangle,
		CheckCircle,
		XCircle,
		TrendingUp,
		TrendingDown,
		Minus,
		Target,
		DollarSign,
		Wrench,
		User
	} from 'lucide-svelte';
	import Badge from '$lib/components/ui/Badge.svelte';

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

	// Filtering pipeline stats
	const urlsScanned = $derived(
		(report?.research_metadata?.filtering_stats as Record<string, number>)?.reddit_urls_searched || 0
	);

	const urlsRelevant = $derived(
		(report?.research_metadata?.filtering_stats as Record<string, number>)?.reddit_urls_relevant || 0
	);

	const postsAnalyzed = $derived(
		report?.research_metadata?.reddit_posts_analyzed || 0
	);

	const commentsAnalyzed = $derived(
		report?.research_metadata?.reddit_comments_analyzed || 0
	);

	// Get pain point count
	const painPointCount = $derived(
		report?.pain_point_analytics?.total_pain_points ||
		report?.detailed_pain_points?.length || 0
	);

	// Verdict and Confidence
	const verdict = $derived(report?.executive_dashboard?.go_no_go_verdict?.verdict ?? null);
	const confidenceScore = $derived(report?.executive_dashboard?.confidence_score ?? 0);
	const riskLevel = $derived(report?.executive_dashboard?.go_no_go_verdict?.risk_level ?? 'Unknown');

	// Market Opportunity
	const opportunityScore = $derived(report?.market_analytics?.overall_opportunity_score ?? 0);

	// Trend Data
	const trendDirection = $derived(report?.trend_longevity?.trend_direction ?? 'Unknown');

	// Competitive Data
	const saturationScore = $derived(report?.competitive_analytics?.market_saturation_score ?? 0);

	// Solution scores
	const severityScore = $derived(report?.executive_dashboard?.core_pain_point?.severity_score ?? 0);
	const wtpScore = $derived(report?.executive_dashboard?.core_pain_point?.willingness_to_pay_score ?? 0);
	const marketFitScore = $derived(report?.selected_solution_details?.market_fit_score ?? 0);
	const feasibilityScore = $derived(report?.selected_solution_details?.technical_feasibility_score ?? 0);
	const soloDevScore = $derived(report?.selected_solution_details?.solo_dev_feasibility ?? 0);

	// Niche display values
	const nicheName = $derived(report?.niche_context?.niche_input ?? report?.niche?.slice(0, 60) ?? 'Unknown Niche');
	const nicheDescription = $derived(report?.niche_context?.niche_description ?? report?.niche ?? '');

	// Helper Functions
	function formatPercent(value: number): string {
		return `${Math.round(value * 100)}%`;
	}

	function getScoreClass(score: number): 'success' | 'warning' | 'error' {
		if (score >= 0.7) return 'success';
		if (score >= 0.4) return 'warning';
		return 'error';
	}

	function getVerdictClass(v: string | null): string {
		if (v === 'Go') return 'verdict-go';
		if (v === 'Conditional') return 'verdict-conditional';
		return 'verdict-nogo';
	}

	function getSaturationLabel(score: number): string {
		if (score <= 0.3) return 'Low';
		if (score <= 0.6) return 'Medium';
		return 'High';
	}

	function getSaturationClass(score: number): 'success' | 'warning' | 'error' {
		if (score <= 0.3) return 'success';
		if (score <= 0.6) return 'warning';
		return 'error';
	}

	function getRiskVariant(risk: string): 'success' | 'warning' | 'error' {
		if (risk === 'Low') return 'success';
		if (risk === 'High') return 'error';
		return 'warning';
	}
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
					<!-- Verdict Badge -->
					<div class="hero-main">
						<div class="verdict-badge {getVerdictClass(verdict)}">
							{#if verdict === 'Go'}
								<CheckCircle class="verdict-icon" size={20} />
							{:else if verdict === 'Conditional'}
								<AlertTriangle class="verdict-icon" size={20} />
							{:else}
								<XCircle class="verdict-icon" size={20} />
							{/if}
							<span class="verdict-text">{verdict?.toUpperCase() ?? 'ANALYZING'}</span>
							<span class="verdict-confidence">{formatPercent(confidenceScore)}</span>
						</div>
					</div>
					<!-- Niche Name + Description -->
					<div class="hero-niche-container">
						<h1 class="hero-niche">{nicheName}</h1>
						<p class="hero-description">{nicheDescription}</p>
					</div>

					<!-- Quick Signals -->
					<div class="hero-signals">
						<div class="signal-chip">
							<span class="signal-value">{formatPercent(opportunityScore)}</span>
							<span class="signal-label">Opportunity</span>
						</div>
						<div class="signal-chip trend">
							{#if trendDirection?.toLowerCase().includes('grow')}
								<TrendingUp size={16} class="trend-icon trend-up" />
							{:else if trendDirection?.toLowerCase().includes('declin')}
								<TrendingDown size={16} class="trend-icon trend-down" />
							{:else}
								<Minus size={16} class="trend-icon trend-stable" />
							{/if}
							<span class="signal-value">{trendDirection}</span>
						</div>
						<div class="signal-chip">
							<span class="signal-value {getSaturationClass(saturationScore)}-text">{getSaturationLabel(saturationScore)}</span>
							<span class="signal-label">Saturation</span>
						</div>
						<Badge variant={getRiskVariant(riskLevel)} size="sm">{riskLevel} Risk</Badge>
					</div>
				</div>

				<div class="header-content">
					<!-- Compact Research Stats -->
					<div class="research-stats-compact">
						<div class="stat-item">
							<span class="stat-num">{urlsScanned}</span>
							<span class="stat-label">Scanned</span>
						</div>
						<span class="stat-divider">→</span>
						<div class="stat-item">
							<span class="stat-num">{urlsRelevant}</span>
							<span class="stat-label">Relevant</span>
						</div>
						<span class="stat-divider">→</span>
						<div class="stat-item">
							<span class="stat-num">{postsAnalyzed}</span>
							<span class="stat-label">Analyzed</span>
						</div>
						<span class="stat-divider">→</span>
						<div class="stat-item highlight">
							<span class="stat-num">{painPointCount}</span>
							<span class="stat-label">Problems</span>
						</div>
					</div>

					<!-- Solution Card -->
					<div class="solution-card">
						<div class="solution-badge">SOLUTION</div>
						<h2 class="solution-name">{report.selected_solution_name}</h2>
						<p class="solution-description">
							{report.selected_solution_details?.description || report.executive_summary?.slice(0, 300)}
						</p>

						<!-- Color-Coded Metrics -->
						<div class="metrics-grid">
							{#if severityScore}
								<div class="metric-badge {getScoreClass(severityScore)}">
									<AlertTriangle size={14} />
									<div class="metric-content">
										<span class="metric-value">{formatPercent(severityScore)}</span>
										<span class="metric-label">Severity</span>
									</div>
								</div>
							{/if}
							{#if wtpScore}
								<div class="metric-badge {getScoreClass(wtpScore)}">
									<DollarSign size={14} />
									<div class="metric-content">
										<span class="metric-value">{formatPercent(wtpScore)}</span>
										<span class="metric-label">WTP</span>
									</div>
								</div>
							{/if}
							{#if marketFitScore}
								<div class="metric-badge {getScoreClass(marketFitScore)}">
									<Target size={14} />
									<div class="metric-content">
										<span class="metric-value">{formatPercent(marketFitScore)}</span>
										<span class="metric-label">Market Fit</span>
									</div>
								</div>
							{/if}
							{#if feasibilityScore}
								<div class="metric-badge {getScoreClass(feasibilityScore)}">
									<Wrench size={14} />
									<div class="metric-content">
										<span class="metric-value">{formatPercent(feasibilityScore)}</span>
										<span class="metric-label">Feasibility</span>
									</div>
								</div>
							{/if}
							{#if soloDevScore}
								<div class="metric-badge {getScoreClass(soloDevScore)}">
									<User size={14} />
									<div class="metric-content">
										<span class="metric-value">{formatPercent(soloDevScore)}</span>
										<span class="metric-label">Solo Dev</span>
									</div>
								</div>
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

	/* Hero Redesign - Premium Gradient with Texture */
	.header-hero {
		background:
			linear-gradient(
				135deg,
				#1e293b 0%,
				#334155 25%,
				#78350f 60%,
				#E55A28 100%
			);
		padding: 1.5rem 2rem;
		border-radius: 1rem 1rem 0 0;
		position: relative;
		overflow: hidden;
	}

	/* Subtle noise texture overlay */
	.header-hero::before {
		content: '';
		position: absolute;
		inset: 0;
		background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
		opacity: 0.03;
		pointer-events: none;
	}

	/* Ensure content is above texture */
	.header-hero > * {
		position: relative;
		z-index: 1;
	}

	.hero-main {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.75rem;
	}

	.verdict-badge {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.625rem 1.25rem;
		border-radius: 0.75rem;
		background: rgba(255, 255, 255, 0.12);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border: 1px solid rgba(255, 255, 255, 0.2);
		box-shadow:
			0 4px 16px rgba(0, 0, 0, 0.15),
			inset 0 1px 0 rgba(255, 255, 255, 0.1);
		transition: transform 0.2s ease, box-shadow 0.2s ease;
	}

	.verdict-badge:hover {
		transform: translateY(-1px);
	}

	/* Verdict-specific glows */
	.verdict-badge.verdict-go {
		border-color: rgba(34, 197, 94, 0.5);
		box-shadow:
			0 4px 16px rgba(0, 0, 0, 0.15),
			0 0 20px rgba(34, 197, 94, 0.25),
			inset 0 1px 0 rgba(255, 255, 255, 0.1);
	}

	.verdict-badge.verdict-conditional {
		border-color: rgba(245, 158, 11, 0.5);
		box-shadow:
			0 4px 16px rgba(0, 0, 0, 0.15),
			0 0 20px rgba(245, 158, 11, 0.25),
			inset 0 1px 0 rgba(255, 255, 255, 0.1);
	}

	.verdict-badge.verdict-nogo {
		border-color: rgba(239, 68, 68, 0.5);
		box-shadow:
			0 4px 16px rgba(0, 0, 0, 0.15),
			0 0 20px rgba(239, 68, 68, 0.25),
			inset 0 1px 0 rgba(255, 255, 255, 0.1);
	}

	:global(.verdict-badge .verdict-icon) { color: white; }

	.verdict-text {
		font-size: 0.9375rem;
		font-weight: 800;
		color: white;
		letter-spacing: 0.05em;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
	}

	.verdict-confidence {
		font-size: 0.8125rem;
		color: rgba(255, 255, 255, 0.9);
		font-weight: 700;
		padding-left: 0.5rem;
		border-left: 1px solid rgba(255, 255, 255, 0.2);
	}

	.hero-niche-container {
		margin-bottom: 1rem;
	}

	.hero-niche {
		font-size: 1.625rem;
		font-weight: 700;
		color: white;
		line-height: 1.25;
		margin-bottom: 0.5rem;
		text-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
	}

	.hero-description {
		font-size: 0.875rem;
		color: rgba(255, 255, 255, 0.8);
		line-height: 1.6;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
	}

	/* Hero Signals */
	.hero-signals {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.signal-chip {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 0.5rem 0.875rem;
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 0.5rem;
		min-width: 70px;
		transition: background 0.15s ease, border-color 0.15s ease;
	}

	.signal-chip:hover {
		background: rgba(255, 255, 255, 0.12);
		border-color: rgba(255, 255, 255, 0.2);
	}

	.signal-chip.trend {
		flex-direction: row;
		gap: 0.375rem;
	}

	.signal-value {
		font-size: 0.9375rem;
		font-weight: 700;
		color: white;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
	}

	.signal-label {
		font-size: 0.5625rem;
		color: rgba(255, 255, 255, 0.65);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-weight: 500;
	}

	:global(.trend-icon) { color: white; }
	:global(.trend-up) { color: var(--color-success-light, #86efac); }
	:global(.trend-down) { color: var(--color-error-light, #fca5a5); }
	:global(.trend-stable) { color: var(--color-warning-light, #fde047); }

	.success-text { color: var(--color-success-light, #86efac) !important; }
	.warning-text { color: var(--color-warning-light, #fde047) !important; }
	.error-text { color: var(--color-error-light, #fca5a5) !important; }

	/* Badge styling in hero context */
	.hero-signals :global(.badge) {
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid rgba(255, 255, 255, 0.15);
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
	}

	.hero-signals :global(.badge-success) {
		background: rgba(34, 197, 94, 0.2);
		color: #86efac;
		border-color: rgba(34, 197, 94, 0.3);
	}

	.hero-signals :global(.badge-warning) {
		background: rgba(245, 158, 11, 0.2);
		color: #fde047;
		border-color: rgba(245, 158, 11, 0.3);
	}

	.hero-signals :global(.badge-error) {
		background: rgba(239, 68, 68, 0.2);
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.3);
	}

	/* Header Content */
	.header-content {
		background: var(--color-bg-elevated);
		padding: 1.5rem 2rem;
		border-radius: 0 0 1rem 1rem;
		border: 1px solid var(--color-border);
		border-top: none;
	}

	/* Compact Research Stats */
	.research-stats-compact {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 1rem;
	}

	.stat-item {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.stat-num {
		font-size: 1.125rem;
		font-weight: 700;
		color: var(--color-text-primary);
	}

	.stat-label {
		font-size: 0.625rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
	}

	.stat-item.highlight .stat-num {
		color: var(--color-accent);
	}

	.stat-divider {
		color: var(--color-text-muted);
		font-size: 0.75rem;
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

	/* Color-Coded Metric Badges */
	.metrics-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.metric-badge {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid;
		transition: transform 0.15s ease;
	}

	.metric-badge:hover {
		transform: translateY(-1px);
	}

	.metric-badge.success {
		background: var(--color-success-subtle, rgba(34, 197, 94, 0.1));
		border-color: var(--color-success);
		color: var(--color-success-dark, #166534);
	}

	.metric-badge.warning {
		background: var(--color-warning-subtle, rgba(234, 179, 8, 0.1));
		border-color: var(--color-warning);
		color: var(--color-warning-dark, #a16207);
	}

	.metric-badge.error {
		background: var(--color-error-subtle, rgba(239, 68, 68, 0.1));
		border-color: var(--color-error);
		color: var(--color-error-dark, #991b1b);
	}

	.metric-content {
		display: flex;
		flex-direction: column;
	}

	.metric-value {
		font-size: 0.875rem;
		font-weight: 700;
	}

	.metric-badge .metric-label {
		font-size: 0.5625rem;
		color: inherit;
		opacity: 0.8;
		text-transform: uppercase;
	}

	/* Mobile Responsive */
	@media (max-width: 768px) {
		.header-hero {
			padding: 1.25rem;
			background:
				linear-gradient(
					160deg,
					#1e293b 0%,
					#334155 30%,
					#78350f 70%,
					#E55A28 100%
				);
		}

		.hero-main {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.75rem;
		}

		.verdict-badge {
			padding: 0.5rem 1rem;
		}

		.verdict-text {
			font-size: 0.875rem;
		}

		.hero-niche { font-size: 1.375rem; }

		.hero-description {
			font-size: 0.8125rem;
			-webkit-line-clamp: 3;
		}

		.hero-signals { gap: 0.5rem; }

		.signal-chip {
			padding: 0.375rem 0.625rem;
			min-width: 60px;
		}

		.header-content {
			padding: 1.25rem;
		}

		.research-stats-compact { flex-wrap: wrap; gap: 0.5rem; }

		.solution-name {
			font-size: 1.35rem;
		}

		.metrics-grid { gap: 0.375rem; }

		.metric-badge {
			padding: 0.375rem 0.5rem;
			gap: 0.375rem;
		}
	}
</style>
