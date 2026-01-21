<script lang="ts">
	import {
		CheckCircle,
		XCircle,
		AlertTriangle,
		Target,
		TrendingUp,
		TrendingDown,
		Users,
		Search,
		Lightbulb,
		Globe,
		Layers,
		Calculator,
		RefreshCw,
		Clock,
		Minus,
		Quote,
		ChevronDown,
		Sparkles,
		Shield,
		HelpCircle
	} from 'lucide-svelte';
	import type {
		Report,
		RefinementHighlights,
		SEOCalculationTransparency,
		TrendLongevity
	} from '$lib/types/report';
	import { formatNumber, formatPercent, renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';

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
	}

	let {
		report,
		nicheName,
		nicheDescription,
		funnelStats,
		refinementHighlights,
		seoCalculationTransparency,
		trends
	}: Props = $props();

	// Extract data from report
	const dashboard = $derived(report.executive_dashboard);
	const verdict = $derived(dashboard?.go_no_go_verdict);
	const solution = $derived(dashboard?.recommended_solution_snapshot);
	const corePain = $derived(dashboard?.core_pain_point);
	const metrics = $derived(dashboard?.key_metrics);
	const confidenceScore = $derived(dashboard?.confidence_score ?? 0);

	// Market signals
	const opportunityScore = $derived(report.market_analytics?.overall_opportunity_score ?? 0);
	const trendDirection = $derived(trends?.trend_direction ?? 'Unknown');
	const saturationScore = $derived(report.competitive_analytics?.market_saturation_score ?? 0);

	// Expandable sections state
	let showStrategicInsights = $state(false);
	let showRiskAssessment = $state(false);
	let descriptionExpanded = $state(false);

	// Score improvement percentage for SEO transparency
	const scoreImprovement = $derived.by(() => {
		if (!seoCalculationTransparency) return null;
		const { baseline_seo_score, refined_seo_score } = seoCalculationTransparency;
		if (baseline_seo_score === 0) return null;
		return (((refined_seo_score - baseline_seo_score) / baseline_seo_score) * 100).toFixed(1);
	});

	// Get trend icon
	const getTrendIcon = (direction?: string) => {
		const d = direction?.toLowerCase() || '';
		if (d.includes('grow')) return TrendingUp;
		if (d.includes('declin')) return TrendingDown;
		return Minus;
	};

	// Check for absorbed content
	const hasStrategicInsights = $derived(
		(refinementHighlights?.top_strategic_insights &&
			refinementHighlights.top_strategic_insights.length > 0) ||
			refinementHighlights?.geographic_priority ||
			refinementHighlights?.feature_priority ||
			refinementHighlights?.category_pivot_recommendation ||
			seoCalculationTransparency
	);

	const hasRiskAssessment = $derived(
		trends?.risk_factors?.length || trends?.trend_direction || trends?.timing_recommendation
	);

	// Score color helper
	const getScoreClass = (score: number | null | undefined) => {
		if (score == null) return 'muted';
		if (score >= 0.7) return 'success';
		if (score >= 0.5) return 'warning';
		return 'error';
	};

	// Get verdict color class
	const getVerdictClass = (v: string) => {
		if (v === 'Go') return 'verdict-go';
		if (v === 'Conditional') return 'verdict-conditional';
		return 'verdict-nogo';
	};

	// Saturation helpers
	const getSaturationLabel = (score: number): string => {
		if (score <= 0.3) return 'Low';
		if (score <= 0.6) return 'Medium';
		return 'High';
	};

	const getSaturationClass = (score: number): string => {
		if (score <= 0.3) return 'success';
		if (score <= 0.6) return 'warning';
		return 'error';
	};

	const getTrendClass = (trend: string | null | undefined): string => {
		if (trend?.toLowerCase().includes('grow')) return 'success';
		if (trend?.toLowerCase().includes('declin')) return 'error';
		return 'warning';
	};

	const getRiskClass = (risk: string): string => {
		if (risk === 'Low') return 'success';
		if (risk === 'High') return 'error';
		return 'warning';
	};

	// Tooltip definitions
	const tooltips = {
		verdict: {
			go: 'Strong opportunity with favorable market conditions. Proceed with confidence.',
			conditional:
				'Promising opportunity with some caveats. Review risk factors before proceeding.',
			nogo: 'Unfavorable conditions detected. Consider pivoting or choosing an alternative.'
		},
		confidence:
			'How certain the AI is about this verdict, based on data quality and signal strength.',
		opportunity:
			'Overall market opportunity score combining demand signals, growth potential, and monetization viability.',
		trend: 'Market momentum direction based on search trends, social mentions, and competitive activity.',
		saturation: 'How crowded the market is. Low = blue ocean, High = intense competition.',
		risk: 'Overall risk assessment factoring technical complexity, market uncertainty, and competitive threats.'
	};

	const getVerdictTooltip = (v: string | null): string => {
		if (v === 'Go') return tooltips.verdict.go;
		if (v === 'Conditional') return tooltips.verdict.conditional;
		return tooltips.verdict.nogo;
	};
</script>

<section id="unified-hero" class="unified-hero">
	<!-- ========== HERO ZONE (Dark Gradient) ========== -->
	<div class="hero-zone">
		<div class="hero-split">
			<!-- Left Column: Verdict Box + Risk Badge -->
			<div class="hero-left">
				<div class="verdict-giant {getVerdictClass(verdict?.verdict ?? 'No-Go')}">
					<span class="verdict-percentage">{Math.round(confidenceScore * 100)}%</span>
					<div class="verdict-label-row">
						{#if verdict?.verdict === 'Go'}
							<CheckCircle class="verdict-icon-large" />
						{:else if verdict?.verdict === 'Conditional'}
							<AlertTriangle class="verdict-icon-large" />
						{:else}
							<XCircle class="verdict-icon-large" />
						{/if}
						<span class="verdict-label-text">{verdict?.verdict?.toUpperCase() ?? 'ANALYZING'}</span>
					</div>
					<div class="verdict-risk-badge">
						<Badge
							variant={verdict?.risk_level === 'Low'
								? 'success'
								: verdict?.risk_level === 'High'
									? 'error'
									: 'warning'}
							size="sm"
						>
							{verdict?.risk_level ?? 'Unknown'} Risk
						</Badge>
					</div>
				</div>
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
						onkeydown={(e) => e.key === 'Enter' && (descriptionExpanded = !descriptionExpanded)}
					>
						{nicheDescription}
					</p>
					{#if !descriptionExpanded && nicheDescription?.length > 150}
						<button class="expand-btn" onclick={() => (descriptionExpanded = true)}>
							Show more
						</button>
					{/if}
				</div>

				<!-- Signal Chips -->
				<div class="signal-chips">
					<div class="signal-chip" title={tooltips.opportunity}>
						<span class="signal-value">{formatPercent(opportunityScore)}</span>
						<span class="signal-label">Opportunity</span>
					</div>

					<div class="signal-chip" title={tooltips.trend}>
						<span class="signal-value {getTrendClass(trendDirection)}-text">
							{#if trendDirection?.toLowerCase().includes('grow')}
								<TrendingUp size={14} class="signal-icon-inline" />
							{:else if trendDirection?.toLowerCase().includes('declin')}
								<TrendingDown size={14} class="signal-icon-inline" />
							{:else}
								<Minus size={14} class="signal-icon-inline" />
							{/if}
							{trendDirection}
						</span>
						<span class="signal-label">Trend</span>
					</div>

					<div class="signal-chip" title={tooltips.saturation}>
						<span class="signal-value {getSaturationClass(saturationScore)}-text">
							{getSaturationLabel(saturationScore)}
						</span>
						<span class="signal-label">Saturation</span>
					</div>

					<div class="signal-chip" title={tooltips.risk}>
						<span class="signal-value {getRiskClass(verdict?.risk_level ?? 'Medium')}-text">
							{verdict?.risk_level ?? 'Unknown'}
						</span>
						<span class="signal-label">Risk</span>
					</div>
				</div>
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
				<span class="pipeline-label">ANALYZED</span>
			</div>
			<div class="pipeline-arrow"></div>
			<div class="pipeline-stage highlight">
				<span class="pipeline-num">{funnelStats.problems}</span>
				<span class="pipeline-label">PROBLEMS</span>
			</div>
		</div>
	</div>

	<!-- ========== CONTENT ZONE (Light Background) ========== -->
	<div class="content-zone">
		<!-- Pain/Solution Cards - Overlapping Layout -->
		<div class="cards-container">
			<!-- Core Pain Point Card -->
			{#if corePain}
				<div class="hero-card hero-card--pain">
					<div class="card-header">
						<Target class="card-icon pain" />
						<span class="card-badge">CORE PAIN POINT</span>
					</div>
					<h3 class="pain-title">{corePain.title}</h3>

					<div class="pain-stats">
						<div class="pain-stat">
							<span class="pain-stat-value">{formatPercent(corePain.severity_score)}</span>
							<span class="pain-stat-label">Severity</span>
						</div>
						<div class="pain-stat-divider"></div>
						<div class="pain-stat">
							<span class="pain-stat-value"
								>{formatPercent(corePain.willingness_to_pay_score)}</span
							>
							<span class="pain-stat-label">
								WTP <Tooltip content={getTermTooltip('WTP')} position="top" />
							</span>
						</div>
						<Badge variant="muted" size="sm">{corePain.source_platform}</Badge>
					</div>

					<blockquote class="pain-quote">
						<Quote class="quote-icon" />
						<p>{corePain.representative_quote}</p>
					</blockquote>
				</div>
			{/if}

			<!-- Solution Card -->
			{#if solution}
				<div class="hero-card hero-card--solution">
					<div class="card-header">
						<Sparkles class="card-icon solution" />
						<span class="card-badge">RECOMMENDED SOLUTION</span>
					</div>
					<h3 class="solution-name">{solution.name}</h3>
					<p class="solution-tagline">{solution.tagline}</p>
					<div class="solution-meta">
						<Badge variant="default">{solution.project_type}</Badge>
					</div>
					<p class="solution-value">{solution.core_value_prop}</p>
				</div>
			{/if}
		</div>

		<!-- Metrics Grid - 2x2 Progress Rings + Quick Stats -->
		<div class="metrics-section">
			<div class="metrics-rings">
				<div class="metric-ring-item" style="--delay: 0.1s">
					<ProgressRing
						value={metrics?.market_fit_score ?? 0}
						size={68}
						strokeWidth={4}
						color={getScoreClass(metrics?.market_fit_score)}
						showValue={true}
						label="Market Fit"
					/>
					<span class="metric-ring-label">Market Fit</span>
				</div>

				<div class="metric-ring-item" style="--delay: 0.2s">
					<ProgressRing
						value={metrics?.technical_feasibility_score ?? 0}
						size={68}
						strokeWidth={4}
						color={getScoreClass(metrics?.technical_feasibility_score)}
						showValue={true}
						label="Feasibility"
					/>
					<span class="metric-ring-label">Feasibility</span>
				</div>

				<div class="metric-ring-item" style="--delay: 0.3s">
					<ProgressRing
						value={metrics?.competitive_advantage_score ?? 0}
						size={68}
						strokeWidth={4}
						color={getScoreClass(metrics?.competitive_advantage_score)}
						showValue={true}
						label="Comp. Edge"
					/>
					<span class="metric-ring-label">Comp. Edge</span>
				</div>

				<div class="metric-ring-item" style="--delay: 0.4s">
					<ProgressRing
						value={metrics?.seo_potential_score ?? 0}
						size={68}
						strokeWidth={4}
						color={getScoreClass(metrics?.seo_potential_score)}
						showValue={true}
						label="SEO Score"
					/>
					<span class="metric-ring-label">SEO Score</span>
				</div>
			</div>

			<!-- Quick Stats Pills -->
			<div class="quick-stats">
				<div class="quick-stat">
					<Search class="quick-stat-icon" />
					<span class="quick-stat-value">{formatNumber(metrics?.total_keyword_search_volume ?? 0)}</span>
					<span class="quick-stat-label">Search Vol</span>
				</div>
				<div class="quick-stat">
					<Target class="quick-stat-icon" />
					<span class="quick-stat-value">{metrics?.total_keyword_count ?? 0}</span>
					<span class="quick-stat-label">Keywords</span>
				</div>
				<div class="quick-stat">
					<Users class="quick-stat-icon" />
					<span class="quick-stat-value">{metrics?.primary_competitor_count ?? 0}</span>
					<span class="quick-stat-label">Competitors</span>
				</div>
				{#if report.selected_solution_details?.solo_dev_feasibility}
					<div class="quick-stat highlight">
						<span class="quick-stat-value"
							>{formatPercent(report.selected_solution_details.solo_dev_feasibility)}</span
						>
						<span class="quick-stat-label">Solo Dev</span>
					</div>
				{/if}
			</div>
		</div>

		<!-- Verdict Rationale Zone -->
		{#if verdict}
			<div class="verdict-rationale-zone {getVerdictClass(verdict.verdict)}">
				<div class="rationale-header">
					<div class="rationale-verdict-badge">
						{#if verdict.verdict === 'Go'}
							<CheckCircle class="rationale-icon" />
						{:else if verdict.verdict === 'Conditional'}
							<AlertTriangle class="rationale-icon" />
						{:else}
							<XCircle class="rationale-icon" />
						{/if}
						<span class="rationale-verdict-text">{verdict.verdict.toUpperCase()}</span>
					</div>
					<div class="rationale-info">
						<span class="rationale-confidence">{formatPercent(confidenceScore)} confidence</span>
						<Badge
							variant={verdict.risk_level === 'Low'
								? 'success'
								: verdict.risk_level === 'High'
									? 'error'
									: 'warning'}
							size="sm"
						>
							{verdict.risk_level} Risk
						</Badge>
					</div>
				</div>
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
		{#if hasStrategicInsights}
			<div class="expandable-section">
				<button
					class="expandable-header"
					onclick={() => (showStrategicInsights = !showStrategicInsights)}
				>
					<div class="expandable-title">
						<Lightbulb class="expandable-icon" />
						<span>Strategic Rationale</span>
						<Badge variant="muted" size="sm">
							{refinementHighlights?.top_strategic_insights?.length ?? 0} insights
						</Badge>
					</div>
					<ChevronDown class="chevron-icon {showStrategicInsights ? 'expanded' : ''}" />
				</button>

				{#if showStrategicInsights}
					<div class="expandable-content">
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
							<div class="priority-grid">
								{#if refinementHighlights.geographic_priority}
									<div class="priority-chip geo">
										<Globe class="priority-icon" />
										<div class="priority-content">
											<span class="priority-label">Geographic Focus</span>
											<span class="priority-value">{refinementHighlights.geographic_priority}</span>
										</div>
									</div>
								{/if}
								{#if refinementHighlights.feature_priority}
									<div class="priority-chip feature">
										<Layers class="priority-icon" />
										<div class="priority-content">
											<span class="priority-label">Feature Priority</span>
											<span class="priority-value">{refinementHighlights.feature_priority}</span>
										</div>
									</div>
								{/if}
							</div>
						{/if}

						<!-- Category Pivot Alert -->
						{#if refinementHighlights?.category_pivot_recommendation}
							<div class="pivot-alert">
								<RefreshCw class="pivot-icon" />
								<div class="pivot-content">
									<span class="pivot-label">Category Pivot Recommended</span>
									<p class="pivot-text">{refinementHighlights.category_pivot_recommendation}</p>
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
											>{(seoCalculationTransparency.baseline_seo_score * 100).toFixed(0)}%</span
										>
										<span class="seo-label">Baseline</span>
									</div>
									<span class="seo-arrow">→</span>
									<div class="seo-score refined">
										<span class="seo-value"
											>{(seoCalculationTransparency.refined_seo_score * 100).toFixed(0)}%</span
										>
										<span class="seo-label">Refined</span>
									</div>
									{#if scoreImprovement}
										<div class="seo-score change" class:positive={parseFloat(scoreImprovement) >= 0}>
											<span class="seo-value">
												{parseFloat(scoreImprovement) >= 0 ? '+' : ''}{scoreImprovement}%
											</span>
											<span class="seo-label">Change</span>
										</div>
									{/if}
								</div>

								<div class="seo-factors">
									<div class="seo-factor">
										<span class="factor-value">{seoCalculationTransparency.volume_multiplier}x</span
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
										<span class="factor-value">{seoCalculationTransparency.tier1_multiplier}x</span>
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
									<p class="seo-rationale">{seoCalculationTransparency.calculation_rationale}</p>
								{/if}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}

		<!-- Expandable: Risk Assessment -->
		{#if hasRiskAssessment}
			<div class="expandable-section">
				<button
					class="expandable-header"
					onclick={() => (showRiskAssessment = !showRiskAssessment)}
				>
					<div class="expandable-title">
						<Shield class="expandable-icon risk" />
						<span>Risk Assessment & Timing</span>
						{#if trends?.risk_factors?.length}
							<Badge variant="error" size="sm">{trends.risk_factors.length} risks</Badge>
						{/if}
					</div>
					<ChevronDown class="chevron-icon {showRiskAssessment ? 'expanded' : ''}" />
				</button>

				{#if showRiskAssessment}
					<div class="expandable-content">
						<!-- Risk Factors -->
						{#if trends?.risk_factors && trends.risk_factors.length > 0}
							<div class="risk-list">
								<h4 class="risk-list-title">Risk Factors</h4>
								<ul class="risk-items">
									{#each trends.risk_factors as risk}
										<li class="risk-item">
											<span class="risk-bullet">!</span>
											<span>{risk}</span>
										</li>
									{/each}
								</ul>
							</div>
						{/if}

						<!-- Market Signals Grid -->
						{#if trends}
							<div class="signals-grid">
								{#if trends.trend_direction}
									{@const TrendIcon = getTrendIcon(trends.trend_direction)}
									<div class="signal-card">
										<TrendIcon class="signal-card-icon" />
										<h4 class="signal-title">Market Trend</h4>
										<div class="signal-rows">
											<div class="signal-row">
												<span class="signal-row-label">Direction:</span>
												<span class="signal-row-value">{trends.trend_direction}</span>
											</div>
											{#if trends.momentum_score !== undefined}
												<div class="signal-row">
													<span class="signal-row-label">Momentum:</span>
													<span class="signal-row-value"
														>{Math.round(trends.momentum_score * 100)}%</span
													>
												</div>
											{/if}
											{#if trends.longevity_verdict}
												<div class="signal-row">
													<span class="signal-row-label">Longevity:</span>
													<Badge
														variant={trends.longevity_verdict.includes('Sustain')
															? 'success'
															: trends.longevity_verdict.includes('Fad')
																? 'error'
																: 'warning'}
														size="sm"
													>
														{trends.longevity_verdict}
													</Badge>
												</div>
											{/if}
											{#if trends.market_maturity}
												<div class="signal-row">
													<span class="signal-row-label">Maturity:</span>
													<span class="signal-row-value">{trends.market_maturity}</span>
												</div>
											{/if}
										</div>
									</div>
								{/if}

								{#if trends.timing_recommendation || trends.longevity_rationale}
									<div class="signal-card">
										<Clock class="signal-card-icon" />
										<h4 class="signal-title">Timing Analysis</h4>
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
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</section>

<style>
	/* =========================
	   UNIFIED HERO CONTAINER
	   ========================= */
	.unified-hero {
		margin-bottom: var(--space-8);
	}

	/* =========================
	   HERO ZONE (Dark Gradient)
	   ========================= */
	.hero-zone {
		background: linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #431407 80%, var(--color-accent) 100%);
		padding: var(--space-8);
		border-radius: var(--radius-xl) var(--radius-xl) 0 0;
		position: relative;
		overflow: hidden;
	}

	/* Noise texture overlay */
	.hero-zone::before {
		content: '';
		position: absolute;
		inset: 0;
		background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
		opacity: 0.03;
		pointer-events: none;
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
		padding: var(--space-6) var(--space-8);
		background: rgba(255, 255, 255, 0.08);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border-radius: var(--radius-xl);
		border: 2px solid rgba(255, 255, 255, 0.1);
	}

	.verdict-giant.verdict-go {
		border-color: var(--color-border-success);
		box-shadow: 0 0 20px rgba(34, 197, 94, 0.2);
	}

	.verdict-giant.verdict-conditional {
		border-color: var(--color-border-warning);
		box-shadow: 0 0 20px rgba(245, 158, 11, 0.2);
	}

	.verdict-giant.verdict-nogo {
		border-color: var(--color-border-error);
		box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
	}

	.verdict-percentage {
		font-family: var(--font-mono);
		font-size: 4rem;
		font-weight: var(--font-extrabold);
		letter-spacing: var(--tracking-tight);
		line-height: var(--leading-none);
		color: white;
		text-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
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
		text-shadow: 0 4px 20px rgba(34, 197, 94, 0.4);
	}
	.verdict-giant.verdict-go :global(.verdict-icon-large) {
		color: var(--color-success);
	}

	.verdict-giant.verdict-conditional .verdict-percentage {
		color: var(--color-warning);
		text-shadow: 0 4px 20px rgba(245, 158, 11, 0.4);
	}
	.verdict-giant.verdict-conditional :global(.verdict-icon-large) {
		color: var(--color-warning);
	}

	.verdict-giant.verdict-nogo .verdict-percentage {
		color: var(--color-error);
		text-shadow: 0 4px 20px rgba(239, 68, 68, 0.4);
	}
	.verdict-giant.verdict-nogo :global(.verdict-icon-large) {
		color: var(--color-error);
	}

	.verdict-risk-badge {
		margin-top: var(--space-3);
		padding-top: var(--space-3);
		border-top: 1px solid rgba(255, 255, 255, 0.1);
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
		text-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
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
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: var(--radius-md);
		min-width: 80px;
		cursor: help;
		transition: background var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default);
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
		clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%);
		border-radius: var(--radius-md) 0 0 var(--radius-md);
	}

	.pipeline-stage:last-child {
		clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%, 12px 50%);
		border-radius: 0 var(--radius-md) var(--radius-md) 0;
	}

	.pipeline-stage.highlight {
		background: var(--color-accent-glow-strong);
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
	}

	.pipeline-stage.highlight .pipeline-num {
		color: var(--color-accent);
	}

	/* =========================
	   CONTENT ZONE (Light Background)
	   ========================= */
	.content-zone {
		background: var(--color-bg-base);
		padding: var(--space-6) var(--space-8) var(--space-8);
		border-radius: 0 0 var(--radius-xl) var(--radius-xl);
		border: 1px solid var(--color-border);
		border-top: none;
	}

	/* Cards Container - Overlapping Layout */
	.cards-container {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-4);
		margin-bottom: var(--space-6);
		position: relative;
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
		content: '';
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

	/* Solution variant - green accent */
	.hero-card--solution::before {
		background: var(--color-success);
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

	.solution-name {
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: var(--font-bold);
		color: var(--color-accent);
		margin-bottom: var(--space-1);
	}

	.solution-tagline {
		font-style: italic;
		color: var(--color-text-muted);
		font-size: var(--text-base);
		margin-bottom: 0.625rem;
	}

	.solution-meta {
		margin-bottom: 0.625rem;
	}

	.solution-value {
		font-size: 0.8125rem;
		color: var(--color-text-muted);
		line-height: var(--leading-relaxed);
		margin: 0;
	}

	/* =========================
	   METRICS SECTION
	   ========================= */
	.metrics-section {
		margin-bottom: var(--space-6);
	}

	.metrics-rings {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: var(--space-4);
		margin-bottom: var(--space-4);
	}

	.metric-ring-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-4) var(--space-2);
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		opacity: 0;
		transform: scale(0.8);
		animation: metric-reveal 0.5s ease-out forwards;
		animation-delay: var(--delay, 0s);
	}

	@keyframes metric-reveal {
		to {
			opacity: 1;
			transform: scale(1);
		}
	}

	.metric-ring-label {
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		font-weight: var(--font-medium);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		text-align: center;
	}

	/* Quick Stats Pills */
	.quick-stats {
		display: flex;
		justify-content: center;
		gap: 0.625rem;
		flex-wrap: wrap;
	}

	.quick-stat {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) 0.875rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-full);
	}

	.quick-stat.highlight {
		border-color: var(--color-border-accent);
		background: var(--color-accent-subtle);
	}

	:global(.quick-stat-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: var(--color-text-muted);
	}

	.quick-stat-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: var(--font-bold);
		color: var(--color-text-primary);
	}

	.quick-stat.highlight .quick-stat-value {
		color: var(--color-accent);
	}

	.quick-stat-label {
		font-size: var(--text-sm);
		color: var(--color-text-muted);
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
		background: linear-gradient(
			90deg,
			var(--color-success-subtle) 0%,
			transparent 50%,
			var(--color-success-subtle) 100%
		);
		border: 1px solid var(--color-border-success);
	}

	.verdict-rationale-zone.verdict-conditional {
		background: linear-gradient(
			90deg,
			var(--color-warning-subtle) 0%,
			transparent 50%,
			var(--color-warning-subtle) 100%
		);
		border: 1px solid var(--color-border-warning);
	}

	.verdict-rationale-zone.verdict-nogo {
		background: linear-gradient(
			90deg,
			var(--color-error-subtle) 0%,
			transparent 50%,
			var(--color-error-subtle) 100%
		);
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
		background: var(--color-warning);
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

	/* =========================
	   EXPANDABLE SECTIONS
	   ========================= */
	.expandable-section {
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		margin-bottom: var(--space-3);
		overflow: hidden;
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.875rem var(--space-4);
		background: var(--color-bg-elevated);
		border: none;
		cursor: pointer;
		transition: background-color var(--duration-fast);
	}

	.expandable-header:hover {
		background: var(--color-bg-hover);
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	:global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-accent);
	}

	:global(.expandable-icon.risk) {
		color: var(--color-error);
	}

	.expandable-title span {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: var(--font-semibold);
		color: var(--color-text-primary);
	}

	:global(.chevron-icon) {
		width: var(--space-4);
		height: var(--space-4);
		color: var(--color-text-muted);
		transition: transform var(--duration-normal);
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 var(--space-4) var(--space-4);
		background: var(--color-bg-elevated);
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

	/* Priority Grid */
	.priority-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.625rem;
		margin-bottom: var(--space-4);
	}

	.priority-chip {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.875rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
	}

	.priority-chip.geo :global(.priority-icon) {
		color: var(--color-info);
	}

	.priority-chip.feature :global(.priority-icon) {
		color: var(--viz-cat-4);
	}

	:global(.priority-icon) {
		width: var(--space-5);
		height: var(--space-5);
	}

	.priority-content {
		display: flex;
		flex-direction: column;
	}

	.priority-label {
		font-size: var(--text-xs);
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

	/* Risk Section */
	.risk-list {
		background: var(--color-error-subtle);
		border: 1px solid var(--color-border-error);
		border-radius: var(--radius-md);
		padding: 0.875rem;
		margin-bottom: var(--space-4);
	}

	.risk-list-title {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: var(--font-semibold);
		color: var(--color-error);
		margin-bottom: 0.625rem;
	}

	.risk-items {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.risk-item {
		display: flex;
		align-items: flex-start;
		gap: var(--space-2);
		font-size: var(--text-sm);
		color: var(--color-text-muted);
		line-height: var(--leading-normal);
	}

	.risk-bullet {
		color: var(--color-error);
		font-weight: var(--font-bold);
	}

	.signals-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.625rem;
	}

	.signal-card {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		padding: 0.875rem;
	}

	:global(.signal-card-icon) {
		width: var(--space-4);
		height: var(--space-4);
		color: var(--color-accent);
		margin-bottom: var(--space-2);
	}

	.signal-title {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: var(--font-semibold);
		color: var(--color-text-primary);
		margin-bottom: 0.625rem;
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

		.metrics-rings {
			grid-template-columns: repeat(2, 1fr);
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

		.quick-stats {
			justify-content: flex-start;
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

		.metrics-rings {
			grid-template-columns: 1fr 1fr;
			gap: var(--space-3);
		}

		.quick-stat {
			padding: var(--space-1) 0.625rem;
		}

		.quick-stat-label {
			font-size: 0.6875rem;
		}
	}
</style>
