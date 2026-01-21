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
		Zap,
		Lightbulb,
		Globe,
		Layers,
		Calculator,
		RefreshCw,
		ShieldAlert,
		Clock,
		Minus,
		Quote,
		ChevronDown,
		Sparkles,
		BarChart3,
		Shield
	} from 'lucide-svelte';
	import type { ExecutiveDashboard, RefinementHighlights, SEOCalculationTransparency, TrendLongevity } from '$lib/types/report';
	import { formatNumber, formatPercent, renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import ExpandableSection from '$lib/components/ui/ExpandableSection.svelte';
	import HeroStat from '$lib/components/ui/HeroStat.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';

	interface Props {
		data: ExecutiveDashboard;
		executiveSummary: string;
		refinementHighlights?: RefinementHighlights;
		seoCalculationTransparency?: SEOCalculationTransparency;
		trends?: TrendLongevity;
	}

	let { data, executiveSummary, refinementHighlights, seoCalculationTransparency, trends }: Props = $props();

	const verdict = $derived(data.go_no_go_verdict);
	const solution = $derived(data.recommended_solution_snapshot);
	const corePain = $derived(data.core_pain_point);
	const metrics = $derived(data.key_metrics);

	// Expandable sections state
	let showStrategicInsights = $state(false);
	let showRiskAssessment = $state(false);

	// Score improvement percentage for SEO transparency
	const scoreImprovement = $derived.by(() => {
		if (!seoCalculationTransparency) return null;
		const { baseline_seo_score, refined_seo_score } = seoCalculationTransparency;
		if (baseline_seo_score === 0) return null;
		return ((refined_seo_score - baseline_seo_score) / baseline_seo_score * 100).toFixed(1);
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
		(refinementHighlights?.top_strategic_insights && refinementHighlights.top_strategic_insights.length > 0) ||
		refinementHighlights?.geographic_priority ||
		refinementHighlights?.feature_priority ||
		refinementHighlights?.category_pivot_recommendation ||
		seoCalculationTransparency
	);

	const hasRiskAssessment = $derived(
		trends?.risk_factors?.length ||
		trends?.trend_direction ||
		trends?.timing_recommendation
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
</script>

<section id="executive" class="executive-section">
	<SectionHeader
		icon={BarChart3}
		title="Executive Summary"
		subtitle="Key metrics and strategic insights at a glance"
	/>

	<!-- Hero Metrics Strip - Most important numbers -->
	<div class="hero-metrics">
		<div class="hero-metric primary">
			<Search class="hero-metric-icon" />
			<div class="hero-metric-body">
				<span class="hero-metric-value">{formatNumber(metrics.total_keyword_search_volume)}</span>
				<span class="hero-metric-label">Monthly Search Volume</span>
			</div>
		</div>

		<div class="hero-scores">
			<div class="hero-score" class:strong={getScoreClass(metrics.market_fit_score) === 'success'}>
				<ProgressRing
					value={metrics.market_fit_score ?? 0}
					size={44}
					strokeWidth={3}
					color={getScoreClass(metrics.market_fit_score)}
					showValue={true}
				/>
				<span class="hero-score-label">Market Fit</span>
			</div>

			<div class="hero-score" class:strong={getScoreClass(metrics.technical_feasibility_score) === 'success'}>
				<ProgressRing
					value={metrics.technical_feasibility_score ?? 0}
					size={44}
					strokeWidth={3}
					color={getScoreClass(metrics.technical_feasibility_score)}
					showValue={true}
				/>
				<span class="hero-score-label">Feasibility</span>
			</div>

			<div class="hero-score" class:strong={getScoreClass(metrics.competitive_advantage_score) === 'success'}>
				<ProgressRing
					value={metrics.competitive_advantage_score ?? 0}
					size={44}
					strokeWidth={3}
					color={getScoreClass(metrics.competitive_advantage_score)}
					showValue={true}
				/>
				<span class="hero-score-label">Comp. Edge</span>
			</div>

			<div class="hero-score" class:strong={getScoreClass(metrics.seo_potential_score) === 'success'}>
				<ProgressRing
					value={metrics.seo_potential_score ?? 0}
					size={44}
					strokeWidth={3}
					color={getScoreClass(metrics.seo_potential_score)}
					showValue={true}
				/>
				<span class="hero-score-label">SEO Score</span>
			</div>
		</div>
	</div>

	<!-- Quick Stats Pills -->
	<div class="quick-stats">
		<div class="quick-stat">
			<Search class="quick-stat-icon" />
			<span class="quick-stat-value">{metrics.total_keyword_count}</span>
			<span class="quick-stat-label">Keywords</span>
		</div>
		<div class="quick-stat">
			<Users class="quick-stat-icon" />
			<span class="quick-stat-value">{metrics.primary_competitor_count}</span>
			<span class="quick-stat-label">Competitors</span>
		</div>
		<div class="quick-stat priority">
			<Target class="quick-stat-icon" />
			<span class="quick-stat-value">{metrics.high_priority_pain_points}</span>
			<span class="quick-stat-label">High Priority Pains</span>
		</div>
	</div>

	<!-- Two Column Layout: Pain + Solution -->
	<div class="content-grid">
		<!-- Core Pain Point Card -->
		<div class="pain-card">
			<div class="card-header">
				<Target class="card-header-icon pain" />
				<span class="card-badge pain">CORE PAIN POINT</span>
			</div>
			<h3 class="pain-title">{corePain.title}</h3>

			<div class="pain-stats">
				<div class="pain-stat">
					<span class="pain-stat-value">{formatPercent(corePain.severity_score)}</span>
					<span class="pain-stat-label">Severity</span>
				</div>
				<div class="pain-stat">
					<span class="pain-stat-value">{formatPercent(corePain.willingness_to_pay_score)}</span>
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

		<!-- Solution Snapshot Card -->
		<div class="solution-card">
			<div class="card-header">
				<Sparkles class="card-header-icon solution" />
				<span class="card-badge solution">RECOMMENDED SOLUTION</span>
			</div>
			<h3 class="solution-name">{solution.name}</h3>
			<p class="solution-tagline">{solution.tagline}</p>
			<div class="solution-meta">
				<Badge variant="default">{solution.project_type}</Badge>
			</div>
			<p class="solution-value">{solution.core_value_prop}</p>
		</div>
	</div>

	<!-- Verdict & Risk Banner -->
	<div class="verdict-banner {getVerdictClass(verdict.verdict)}">
		<div class="verdict-main">
			<div class="verdict-badge">
				{#if verdict.verdict === 'Go'}
					<CheckCircle class="verdict-icon" />
				{:else if verdict.verdict === 'Conditional'}
					<AlertTriangle class="verdict-icon" />
				{:else}
					<XCircle class="verdict-icon" />
				{/if}
				<span class="verdict-text">{verdict.verdict.toUpperCase()}</span>
			</div>
			<div class="verdict-info">
				<span class="verdict-confidence">{formatPercent(data.confidence_score)} confidence</span>
				<Badge variant={verdict.risk_level === 'Low' ? 'success' : verdict.risk_level === 'High' ? 'error' : 'warning'} size="sm">
					{verdict.risk_level} Risk
				</Badge>
			</div>
		</div>
		<p class="verdict-rationale">{verdict.rationale}</p>
		{#if verdict.primary_concern}
			<div class="verdict-concern">
				<AlertTriangle class="concern-icon" />
				<span>{verdict.primary_concern}</span>
			</div>
		{/if}
	</div>

	<!-- Analysis Summary -->
	<div class="summary-card">
		<h3 class="summary-title">Analysis Summary</h3>
		<div class="summary-content">
			{@html renderMarkdown(executiveSummary)}
		</div>
	</div>

	<!-- Expandable: Strategic Insights -->
	{#if hasStrategicInsights}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => showStrategicInsights = !showStrategicInsights}>
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
								<Calculator class="seo-icon" />
								<h4 class="seo-title">SEO Score Calculation</h4>
							</div>

							<div class="seo-flow">
								<div class="seo-score baseline">
									<span class="seo-value">{(seoCalculationTransparency.baseline_seo_score * 100).toFixed(0)}%</span>
									<span class="seo-label">Baseline</span>
								</div>
								<span class="seo-arrow">→</span>
								<div class="seo-score refined">
									<span class="seo-value">{(seoCalculationTransparency.refined_seo_score * 100).toFixed(0)}%</span>
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
									<span class="factor-value">{seoCalculationTransparency.volume_multiplier}x</span>
									<span class="factor-label">Volume</span>
								</div>
								<div class="seo-factor">
									<span class="factor-value">{seoCalculationTransparency.competition_modifier}x</span>
									<span class="factor-label">Competition</span>
								</div>
								<div class="seo-factor">
									<span class="factor-value">{seoCalculationTransparency.tier1_multiplier}x</span>
									<span class="factor-label">Tier 1</span>
								</div>
								<div class="seo-factor">
									<span class="factor-value">{seoCalculationTransparency.estimated_year1_pages}</span>
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
			<button class="expandable-header" onclick={() => showRiskAssessment = !showRiskAssessment}>
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
									<TrendIcon class="signal-icon" />
									<h4 class="signal-title">Market Trend</h4>
									<div class="signal-rows">
										<div class="signal-row">
											<span class="signal-label">Direction:</span>
											<span class="signal-value">{trends.trend_direction}</span>
										</div>
										{#if trends.momentum_score !== undefined}
											<div class="signal-row">
												<span class="signal-label">Momentum:</span>
												<span class="signal-value">{Math.round(trends.momentum_score * 100)}%</span>
											</div>
										{/if}
										{#if trends.longevity_verdict}
											<div class="signal-row">
												<span class="signal-label">Longevity:</span>
												<Badge variant={trends.longevity_verdict.includes('Sustain') ? 'success' : trends.longevity_verdict.includes('Fad') ? 'error' : 'warning'} size="sm">
													{trends.longevity_verdict}
												</Badge>
											</div>
										{/if}
										{#if trends.market_maturity}
											<div class="signal-row">
												<span class="signal-label">Maturity:</span>
												<span class="signal-value">{trends.market_maturity}</span>
											</div>
										{/if}
									</div>
								</div>
							{/if}

							{#if trends.timing_recommendation || trends.longevity_rationale}
								<div class="signal-card">
									<Clock class="signal-icon" />
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
</section>

<style>
	/* =========================
	   SECTION CONTAINER
	   ========================= */
	.executive-section {
		padding: 1.5rem;
		background: var(--color-bg-base);
	}

	/* =========================
	   SECTION HEADER
	   ========================= */
	.section-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}

	.header-icon-wrap {
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

	.header-text {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.section-title {
		font-family: var(--font-display);
		font-size: 1.375rem;
		font-weight: 800;
		color: #18181B;
		margin: 0;
	}

	.section-subtitle {
		font-size: 0.8125rem;
		color: #A1A1AA;
		margin: 0;
	}

	/* =========================
	   HERO METRICS STRIP
	   ========================= */
	.hero-metrics {
		display: flex;
		align-items: stretch;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.hero-metric.primary {
		flex: 0 0 auto;
		display: flex;
		align-items: center;
		gap: 0.875rem;
		padding: 1.125rem 1.5rem;
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.1) 0%, rgba(229, 90, 40, 0.03) 100%);
		border: 1px solid rgba(229, 90, 40, 0.25);
		border-radius: 0.75rem;
	}

	:global(.hero-metric-icon) {
		width: 2rem;
		height: 2rem;
		color: #E55A28;
	}

	.hero-metric-body {
		display: flex;
		flex-direction: column;
	}

	.hero-metric-value {
		font-family: var(--font-display);
		font-size: 1.75rem;
		font-weight: 800;
		color: #E55A28;
		line-height: 1.1;
	}

	.hero-metric-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.hero-scores {
		flex: 1;
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.625rem;
	}

	.hero-score {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.375rem;
		padding: 0.875rem 0.5rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.625rem;
		transition: all 0.15s ease;
	}

	.hero-score:hover {
		border-color: rgba(0, 0, 0, 0.15);
	}

	.hero-score.strong {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.06) 0%, transparent 60%);
		border-color: rgba(34, 197, 94, 0.2);
	}

	.hero-score-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 500;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		text-align: center;
	}

	/* =========================
	   QUICK STATS PILLS
	   ========================= */
	.quick-stats {
		display: flex;
		gap: 0.625rem;
		margin-bottom: 1.25rem;
		flex-wrap: wrap;
	}

	.quick-stat {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.875rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 9999px;
	}

	.quick-stat.priority {
		border-color: rgba(239, 68, 68, 0.25);
		background: rgba(239, 68, 68, 0.04);
	}

	.quick-stat.priority :global(.quick-stat-icon) {
		color: #EF4444;
	}

	:global(.quick-stat-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #A1A1AA;
	}

	.quick-stat-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 700;
		color: #18181B;
	}

	.quick-stat-label {
		font-size: 0.75rem;
		color: #71717A;
	}

	/* =========================
	   CONTENT GRID (Pain + Solution)
	   ========================= */
	.content-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	/* Card Header Pattern */
	.card-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.625rem;
	}

	:global(.card-header-icon) {
		width: 1rem;
		height: 1rem;
	}

	:global(.card-header-icon.pain) {
		color: #E55A28;
	}

	:global(.card-header-icon.solution) {
		color: #E55A28;
	}

	.card-badge {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 700;
		letter-spacing: 0.1em;
	}

	.card-badge.pain {
		color: #E55A28;
	}

	.card-badge.solution {
		color: #E55A28;
	}

	/* Pain Card */
	.pain-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-left: 3px solid #E55A28;
		border-radius: 0.75rem;
		padding: 1.125rem;
	}

	.pain-title {
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 600;
		color: #18181B;
		line-height: 1.35;
		margin-bottom: 0.75rem;
	}

	.pain-stats {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.875rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid rgba(0, 0, 0, 0.06);
	}

	.pain-stat {
		display: flex;
		flex-direction: column;
	}

	.pain-stat-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 700;
		color: #E55A28;
	}

	.pain-stat-label {
		font-size: 0.625rem;
		color: #A1A1AA;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.pain-quote {
		position: relative;
		padding-left: 1.5rem;
		font-style: italic;
		color: #71717A;
		font-size: 0.8125rem;
		line-height: 1.55;
		margin: 0;
	}

	:global(.quote-icon) {
		position: absolute;
		left: 0;
		top: 0;
		width: 1rem;
		height: 1rem;
		color: #E55A28;
		opacity: 0.4;
	}

	/* Solution Card */
	.solution-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		padding: 1.125rem;
	}

	.solution-name {
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: 700;
		color: #E55A28;
		margin-bottom: 0.25rem;
	}

	.solution-tagline {
		font-style: italic;
		color: #71717A;
		font-size: 0.875rem;
		margin-bottom: 0.625rem;
	}

	.solution-meta {
		margin-bottom: 0.625rem;
	}

	.solution-value {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.55;
		margin: 0;
	}

	/* =========================
	   VERDICT BANNER
	   ========================= */
	.verdict-banner {
		border-radius: 0.75rem;
		padding: 1.125rem;
		margin-bottom: 1rem;
	}

	.verdict-banner.verdict-go {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.08) 0%, rgba(34, 197, 94, 0.02) 100%);
		border: 1px solid rgba(34, 197, 94, 0.3);
	}

	.verdict-banner.verdict-conditional {
		background: linear-gradient(135deg, rgba(234, 179, 8, 0.08) 0%, rgba(234, 179, 8, 0.02) 100%);
		border: 1px solid rgba(234, 179, 8, 0.3);
	}

	.verdict-banner.verdict-nogo {
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.02) 100%);
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.verdict-main {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin-bottom: 0.625rem;
	}

	.verdict-badge {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.875rem;
		border-radius: 0.375rem;
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 800;
	}

	.verdict-go .verdict-badge {
		background: #22C55E;
		color: white;
	}

	.verdict-conditional .verdict-badge {
		background: #EAB308;
		color: white;
	}

	.verdict-nogo .verdict-badge {
		background: #EF4444;
		color: white;
	}

	:global(.verdict-icon) {
		width: 1.125rem;
		height: 1.125rem;
	}

	.verdict-info {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	.verdict-confidence {
		font-size: 0.8125rem;
		color: #71717A;
	}

	.verdict-rationale {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.55;
		margin-bottom: 0.625rem;
	}

	.verdict-concern {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: rgba(234, 179, 8, 0.1);
		border-radius: 0.375rem;
		font-size: 0.75rem;
		color: #71717A;
	}

	:global(.concern-icon) {
		width: 0.75rem;
		height: 0.75rem;
		color: #EAB308;
		flex-shrink: 0;
		margin-top: 0.125rem;
	}

	/* =========================
	   SUMMARY CARD
	   ========================= */
	.summary-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		padding: 1.125rem;
		margin-bottom: 1rem;
	}

	.summary-title {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
		margin-bottom: 0.625rem;
	}

	.summary-content {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.65;
	}

	.summary-content :global(p) {
		margin-bottom: 0.625rem;
	}

	.summary-content :global(p:last-child) {
		margin-bottom: 0;
	}

	/* =========================
	   EXPANDABLE SECTIONS
	   ========================= */
	.expandable-section {
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		overflow: hidden;
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.875rem 1rem;
		background: #FFFFFF;
		border: none;
		cursor: pointer;
		transition: background-color 0.15s;
	}

	.expandable-header:hover {
		background: rgba(0, 0, 0, 0.02);
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	:global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: #E55A28;
	}

	:global(.expandable-icon.risk) {
		color: #EF4444;
	}

	.expandable-title span {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
	}

	:global(.chevron-icon) {
		width: 1rem;
		height: 1rem;
		color: #A1A1AA;
		transition: transform 0.2s;
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 1rem 1rem;
		background: #FFFFFF;
	}

	/* Insights List */
	.insights-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.insight-item {
		display: flex;
		align-items: flex-start;
		gap: 0.625rem;
		padding: 0.625rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.5rem;
	}

	.insight-num {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		background: rgba(229, 90, 40, 0.1);
		border-radius: 50%;
		font-size: 0.625rem;
		font-weight: 700;
		color: #E55A28;
		flex-shrink: 0;
	}

	.insight-text {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.5;
	}

	/* Priority Grid */
	.priority-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.625rem;
		margin-bottom: 1rem;
	}

	.priority-chip {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.875rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.5rem;
	}

	.priority-chip.geo :global(.priority-icon) {
		color: #3B82F6;
	}

	.priority-chip.feature :global(.priority-icon) {
		color: #8B5CF6;
	}

	:global(.priority-icon) {
		width: 1.25rem;
		height: 1.25rem;
	}

	.priority-content {
		display: flex;
		flex-direction: column;
	}

	.priority-label {
		font-size: 0.625rem;
		color: #A1A1AA;
	}

	.priority-value {
		font-family: var(--font-display);
		font-size: 0.875rem;
		font-weight: 600;
		color: #18181B;
	}

	/* Pivot Alert */
	.pivot-alert {
		display: flex;
		align-items: flex-start;
		gap: 0.625rem;
		padding: 0.875rem;
		background: rgba(234, 179, 8, 0.06);
		border: 1px solid rgba(234, 179, 8, 0.25);
		border-radius: 0.5rem;
		margin-bottom: 1rem;
	}

	:global(.pivot-icon) {
		width: 1rem;
		height: 1rem;
		color: #EAB308;
		flex-shrink: 0;
	}

	.pivot-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #EAB308;
		margin-bottom: 0.125rem;
	}

	.pivot-text {
		font-size: 0.8125rem;
		color: #18181B;
		line-height: 1.5;
		margin: 0;
	}

	/* SEO Transparency */
	.seo-transparency {
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.5rem;
		padding: 0.875rem;
	}

	.seo-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.875rem;
	}

	:global(.seo-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #E55A28;
	}

	.seo-title {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #18181B;
		margin: 0;
	}

	.seo-flow {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		margin-bottom: 0.875rem;
	}

	.seo-score {
		text-align: center;
	}

	.seo-score .seo-value {
		display: block;
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
	}

	.seo-score.baseline .seo-value {
		color: #A1A1AA;
	}

	.seo-score.refined .seo-value {
		color: #E55A28;
	}

	.seo-score.change.positive .seo-value {
		color: #22C55E;
	}

	.seo-arrow {
		font-size: 1rem;
		color: #A1A1AA;
	}

	.seo-score .seo-label {
		font-size: 0.5625rem;
		color: #A1A1AA;
	}

	.seo-factors {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.5rem;
		margin-bottom: 0.625rem;
	}

	.seo-factor {
		text-align: center;
		padding: 0.5rem;
		background: #FFFFFF;
		border-radius: 0.375rem;
	}

	.factor-value {
		display: block;
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
	}

	.factor-label {
		font-size: 0.5625rem;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.seo-rationale {
		font-size: 0.75rem;
		color: #71717A;
		padding: 0.625rem;
		background: #FFFFFF;
		border-radius: 0.375rem;
		margin: 0;
	}

	/* Risk Section */
	.risk-list {
		background: rgba(239, 68, 68, 0.04);
		border: 1px solid rgba(239, 68, 68, 0.15);
		border-radius: 0.5rem;
		padding: 0.875rem;
		margin-bottom: 1rem;
	}

	.risk-list-title {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #EF4444;
		margin-bottom: 0.625rem;
	}

	.risk-items {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.risk-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.75rem;
		color: #71717A;
		line-height: 1.5;
	}

	.risk-bullet {
		color: #EF4444;
		font-weight: 700;
	}

	.signals-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.625rem;
	}

	.signal-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.5rem;
		padding: 0.875rem;
	}

	:global(.signal-icon) {
		width: 1rem;
		height: 1rem;
		color: #E55A28;
		margin-bottom: 0.5rem;
	}

	.signal-title {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #18181B;
		margin-bottom: 0.625rem;
	}

	.signal-rows {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.signal-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.75rem;
	}

	.signal-label {
		color: #A1A1AA;
	}

	.signal-value {
		color: #18181B;
		font-weight: 500;
	}

	.timing-highlight {
		padding: 0.625rem;
		background: rgba(229, 90, 40, 0.06);
		border-radius: 0.375rem;
		margin-bottom: 0.625rem;
	}

	.timing-highlight p {
		font-size: 0.8125rem;
		font-weight: 500;
		color: #18181B;
		margin: 0;
	}

	.timing-rationale {
		font-size: 0.75rem;
		color: #71717A;
		line-height: 1.55;
	}

	/* =========================
	   RESPONSIVE ADJUSTMENTS
	   ========================= */
	@media (max-width: 900px) {
		.hero-scores {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 768px) {
		.executive-section {
			padding: 1rem;
		}

		.hero-metrics {
			flex-direction: column;
		}

		.hero-metric.primary {
			justify-content: center;
		}

		.content-grid {
			grid-template-columns: 1fr;
		}

		.quick-stats {
			justify-content: center;
		}

		.verdict-main {
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
		.hero-scores {
			grid-template-columns: 1fr 1fr;
		}

		.quick-stat {
			padding: 0.375rem 0.625rem;
		}

		.quick-stat-label {
			font-size: 0.6875rem;
		}
	}
</style>
