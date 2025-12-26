<script lang="ts">
	import {
		CheckCircle,
		XCircle,
		AlertTriangle,
		Target,
		TrendingUp,
		TrendingDown,
		Users,
		BarChart3,
		Search,
		Zap,
		Shield,
		LineChart,
		Lightbulb,
		Globe,
		Layers,
		Calculator,
		RefreshCw,
		ShieldAlert,
		Clock,
		Timer,
		Minus
	} from 'lucide-svelte';
	import type { ExecutiveDashboard, RefinementHighlights, SEOCalculationTransparency, TrendLongevity } from '$lib/types/report';
	import { formatNumber, formatPercent, formatScore, getVerdictClass, getRiskClass, getScoreClass, getScoreBarClass, renderMarkdown } from '$lib/utils/format';
	import MetricCard from '$lib/components/ui/MetricCard.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		data: ExecutiveDashboard;
		executiveSummary: string;
		// Absorbed from VerdictRationale
		refinementHighlights?: RefinementHighlights;
		seoCalculationTransparency?: SEOCalculationTransparency;
		// Absorbed from RiskTiming
		trends?: TrendLongevity;
	}

	let { data, executiveSummary, refinementHighlights, seoCalculationTransparency, trends }: Props = $props();

	const verdict = $derived(data.go_no_go_verdict);
	const solution = $derived(data.recommended_solution_snapshot);
	const corePain = $derived(data.core_pain_point);
	const metrics = $derived(data.key_metrics);

	// Calculate score improvement percentage for SEO transparency
	const scoreImprovement = $derived.by(() => {
		if (!seoCalculationTransparency) return null;
		const { baseline_seo_score, refined_seo_score } = seoCalculationTransparency;
		if (baseline_seo_score === 0) return null;
		return ((refined_seo_score - baseline_seo_score) / baseline_seo_score * 100).toFixed(1);
	});

	// Get risk level styling
	const getRiskConfig = (level: string) => {
		const l = level?.toLowerCase() || '';
		if (l === 'low') return { color: 'text-success', bg: 'bg-success/10', icon: CheckCircle };
		if (l === 'medium') return { color: 'text-warning', bg: 'bg-warning/10', icon: AlertTriangle };
		return { color: 'text-error', bg: 'bg-error/10', icon: ShieldAlert };
	};

	// Get trend icon
	const getTrendIcon = (direction?: string) => {
		const d = direction?.toLowerCase() || '';
		if (d.includes('grow')) return TrendingUp;
		if (d.includes('declin')) return TrendingDown;
		return Minus;
	};

	const riskConfig = $derived(getRiskConfig(verdict.risk_level));
	const RiskIcon = $derived(riskConfig.icon);

	// Check if we have absorbed content to show
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
</script>

<section id="executive" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<BarChart3 class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Executive Summary</h2>
	</div>

	<!-- Verdict Banner -->
	<div class="verdict-banner mb-8 {verdict.verdict === 'Go' ? 'verdict-banner-go' : 'verdict-banner-no-go'}">
		<div class="verdict-header">
			<div class="verdict-main">
				<div class="verdict-icon {verdict.verdict === 'Go' ? 'verdict-icon-go' : 'verdict-icon-no-go'}">
					{#if verdict.verdict === 'Go'}
						<CheckCircle class="w-8 h-8" />
					{:else}
						<XCircle class="w-8 h-8" />
					{/if}
				</div>
				<div class="verdict-text">
					<span class="verdict-label">{verdict.verdict.toUpperCase()}</span>
					<span class="verdict-confidence">{formatPercent(data.confidence_score)} confidence</span>
				</div>
			</div>
			<Badge variant={verdict.risk_level === 'Low' ? 'success' : verdict.risk_level === 'High' ? 'error' : 'warning'}>
				{verdict.risk_level} Risk
			</Badge>
		</div>
		<p class="verdict-rationale">{verdict.rationale}</p>
		{#if verdict.primary_concern}
			<div class="verdict-concern">
				<AlertTriangle class="w-4 h-4" />
				<span>{verdict.primary_concern}</span>
			</div>
		{/if}
	</div>

	<!-- Solution Snapshot -->
	<div class="card mb-8">
		<h3 class="text-lg font-semibold text-text-primary mb-4">Recommended Solution</h3>
		<div class="mb-4">
			<h4 class="text-xl font-bold text-accent">{solution.name}</h4>
			<p class="text-text-secondary italic mt-1">{solution.tagline}</p>
		</div>
		<div class="mb-4">
			<Badge>{solution.project_type}</Badge>
		</div>
		<p class="text-text-secondary">{solution.core_value_prop}</p>
	</div>

	<!-- Bento Grid: Key Metrics & Scores -->
	<AnimateOnScroll animation="fade-up">
		<div class="bento-grid mb-8">
			<!-- Featured: Search Volume (large card) -->
			<div class="bento-card bento-featured bento-accent">
				<div class="bento-icon-large bg-accent/10 border border-accent/30">
					<Search class="w-6 h-6 text-accent" />
				</div>
				<div class="bento-value bento-value-lg text-accent">{formatNumber(metrics.total_keyword_search_volume)}</div>
				<div class="bento-label">Total Search Volume</div>
				<div class="bento-sublabel">Monthly keyword demand</div>
			</div>

			<!-- Market Fit Score -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<TrendingUp class="w-4 h-4 text-accent" />
					<span class="text-xs text-text-muted uppercase tracking-wider">Market Fit</span>
				</div>
				<div class="stat-value text-2xl {getScoreClass(metrics.market_fit_score)}">{formatScore(metrics.market_fit_score)}</div>
				<div class="score-bar mt-3">
					<div class="score-bar-fill {getScoreBarClass(metrics.market_fit_score)}" style="width: {metrics.market_fit_score * 100}%"></div>
				</div>
			</div>

			<!-- Keywords Count -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<Search class="w-4 h-4 text-text-muted" />
					<span class="text-xs text-text-muted uppercase tracking-wider">Keywords</span>
				</div>
				<div class="stat-value text-2xl text-text-primary">{metrics.total_keyword_count}</div>
				<div class="text-xs text-text-muted mt-1">opportunities found</div>
			</div>

			<!-- Competitive Advantage -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<Shield class="w-4 h-4 text-success" />
					<span class="text-xs text-text-muted uppercase tracking-wider">Competitive Edge</span>
				</div>
				<div class="stat-value text-2xl {getScoreClass(metrics.competitive_advantage_score)}">{formatScore(metrics.competitive_advantage_score)}</div>
				<div class="score-bar mt-3">
					<div class="score-bar-fill {getScoreBarClass(metrics.competitive_advantage_score)}" style="width: {metrics.competitive_advantage_score * 100}%"></div>
				</div>
			</div>

			<!-- Competitors -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<Users class="w-4 h-4 text-text-muted" />
					<span class="text-xs text-text-muted uppercase tracking-wider">Competitors</span>
				</div>
				<div class="stat-value text-2xl text-text-primary">{metrics.primary_competitor_count}</div>
				<div class="text-xs text-text-muted mt-1">in market</div>
			</div>

			<!-- Technical Feasibility -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<Zap class="w-4 h-4 text-accent" />
					<span class="text-xs text-text-muted uppercase tracking-wider">Tech Feasibility</span>
				</div>
				<div class="stat-value text-2xl {getScoreClass(metrics.technical_feasibility_score)}">{formatScore(metrics.technical_feasibility_score)}</div>
				<div class="score-bar mt-3">
					<div class="score-bar-fill {getScoreBarClass(metrics.technical_feasibility_score)}" style="width: {metrics.technical_feasibility_score * 100}%"></div>
				</div>
			</div>

			<!-- Pain Points -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<Target class="w-4 h-4 text-error" />
					<span class="text-xs text-text-muted uppercase tracking-wider">Pain Points</span>
				</div>
				<div class="stat-value text-2xl text-error">{metrics.high_priority_pain_points}</div>
				<div class="text-xs text-text-muted mt-1">high priority</div>
			</div>

			<!-- SEO Potential -->
			<div class="bento-card stat-card-animated">
				<div class="flex items-center gap-2 mb-2">
					<LineChart class="w-4 h-4 text-success" />
					<span class="text-xs text-text-muted uppercase tracking-wider">SEO Potential</span>
				</div>
				<div class="stat-value text-2xl {getScoreClass(metrics.seo_potential_score)}">{formatScore(metrics.seo_potential_score)}</div>
				<div class="score-bar mt-3">
					<div class="score-bar-fill {getScoreBarClass(metrics.seo_potential_score)}" style="width: {metrics.seo_potential_score * 100}%"></div>
				</div>
			</div>
		</div>
	</AnimateOnScroll>

	<!-- Core Pain Point -->
	<AnimateOnScroll animation="fade-up" delay={100}>
		<div class="highlight-box mb-8 card-interactive-glow">
			<div class="flex items-start gap-4">
				<div class="icon-container shrink-0">
					<Target class="w-5 h-5 text-accent" />
				</div>
				<div class="flex-1">
					<h4 class="font-semibold text-text-primary mb-2">Core Pain Point</h4>
					<p class="text-lg text-text-primary mb-3">{corePain.title}</p>
					<div class="flex flex-wrap gap-4 text-sm mb-3">
						<span>Severity: <strong class="text-accent">{formatScore(corePain.severity_score)}</strong></span>
						<span>WTP: <strong class="text-accent">{formatScore(corePain.willingness_to_pay_score)}</strong></span>
						<span class="text-text-muted">{corePain.source_platform}</span>
					</div>
					<blockquote class="quote-enhanced text-sm">"{corePain.representative_quote}"</blockquote>
				</div>
			</div>
		</div>
	</AnimateOnScroll>

	<!-- Executive Summary Text -->
	<AnimateOnScroll animation="fade-up" delay={200}>
		<div class="card card-glass mb-8">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Summary</h3>
			<div class="markdown-content narrative">
				{@html renderMarkdown(executiveSummary)}
			</div>
		</div>
	</AnimateOnScroll>

	<!-- ═══════════════════════════════════════════════════════════════
	     ABSORBED: Strategic Insights (from VerdictRationale)
	     ═══════════════════════════════════════════════════════════════ -->
	{#if hasStrategicInsights}
		<div class="mt-8 pt-6 border-t border-border">
			<div class="flex items-center gap-3 mb-6">
				<Lightbulb class="w-5 h-5 text-accent" />
				<h3 class="text-lg font-semibold text-text-primary">Strategic Rationale</h3>
			</div>

			<!-- Top Strategic Insights -->
			{#if refinementHighlights?.top_strategic_insights && refinementHighlights.top_strategic_insights.length > 0}
				<AnimateOnScroll animation="fade-up">
					<div class="card mb-6">
						<div class="flex items-center gap-2 mb-4">
							<TrendingUp class="w-5 h-5 text-accent" />
							<h4 class="font-semibold text-text-primary">Top Strategic Insights</h4>
						</div>
						<ul class="space-y-3">
							{#each refinementHighlights.top_strategic_insights as insight, i}
								<li class="flex items-start gap-3">
									<span class="flex-shrink-0 w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center text-xs font-bold text-accent">
										{i + 1}
									</span>
									<span class="text-text-secondary">{insight}</span>
								</li>
							{/each}
						</ul>
					</div>
				</AnimateOnScroll>
			{/if}

			<!-- Priority Badges -->
			{#if refinementHighlights?.geographic_priority || refinementHighlights?.feature_priority}
				<AnimateOnScroll animation="fade-up">
					<div class="grid md:grid-cols-2 gap-4 mb-6">
						{#if refinementHighlights.geographic_priority}
							<div class="card flex items-center gap-4">
								<div class="p-3 rounded-lg bg-blue-500/10">
									<Globe class="w-6 h-6 text-blue-500" />
								</div>
								<div>
									<div class="text-sm text-text-muted">Geographic Priority</div>
									<div class="text-lg font-semibold text-text-primary">{refinementHighlights.geographic_priority}</div>
								</div>
							</div>
						{/if}
						{#if refinementHighlights.feature_priority}
							<div class="card flex items-center gap-4">
								<div class="p-3 rounded-lg bg-purple-500/10">
									<Layers class="w-6 h-6 text-purple-500" />
								</div>
								<div>
									<div class="text-sm text-text-muted">Feature Priority</div>
									<div class="text-lg font-semibold text-text-primary">{refinementHighlights.feature_priority}</div>
								</div>
							</div>
						{/if}
					</div>
				</AnimateOnScroll>
			{/if}

			<!-- Category Pivot Recommendation -->
			{#if refinementHighlights?.category_pivot_recommendation}
				<AnimateOnScroll animation="fade-up">
					<div class="highlight-box mb-6 border-warning/30">
						<div class="flex items-start gap-3">
							<RefreshCw class="w-5 h-5 text-warning mt-0.5" />
							<div>
								<span class="text-warning text-sm font-semibold">Category Pivot Recommended</span>
								<p class="text-text-primary mt-1">{refinementHighlights.category_pivot_recommendation}</p>
							</div>
						</div>
					</div>
				</AnimateOnScroll>
			{/if}

			<!-- SEO Calculation Transparency -->
			{#if seoCalculationTransparency}
				<AnimateOnScroll animation="fade-up">
					<div class="card">
						<div class="flex items-center gap-2 mb-4">
							<Calculator class="w-5 h-5 text-accent" />
							<h4 class="font-semibold text-text-primary">SEO Score Calculation</h4>
						</div>

						<!-- Score Comparison -->
						<div class="grid md:grid-cols-3 gap-4 mb-6">
							<div class="card-surface text-center">
								<div class="text-sm text-text-muted mb-1">Baseline Score</div>
								<div class="text-2xl font-bold text-text-secondary">{(seoCalculationTransparency.baseline_seo_score * 100).toFixed(0)}%</div>
							</div>
							<div class="card-surface text-center border-accent/30">
								<div class="text-sm text-text-muted mb-1">Refined Score</div>
								<div class="text-2xl font-bold text-accent">{(seoCalculationTransparency.refined_seo_score * 100).toFixed(0)}%</div>
							</div>
							{#if scoreImprovement}
								<div class="card-surface text-center">
									<div class="text-sm text-text-muted mb-1">Improvement</div>
									<div class="text-2xl font-bold {parseFloat(scoreImprovement || '0') >= 0 ? 'text-success' : 'text-error'}">
										{parseFloat(scoreImprovement || '0') >= 0 ? '+' : ''}{scoreImprovement}%
									</div>
								</div>
							{/if}
						</div>

						<!-- Calculation Factors -->
						<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
							<div class="text-center p-3 rounded-lg bg-surface-secondary/50">
								<div class="text-xs text-text-muted mb-1">Volume Multiplier</div>
								<div class="text-lg font-semibold text-text-primary">{seoCalculationTransparency.volume_multiplier}x</div>
							</div>
							<div class="text-center p-3 rounded-lg bg-surface-secondary/50">
								<div class="text-xs text-text-muted mb-1">Competition Modifier</div>
								<div class="text-lg font-semibold text-text-primary">{seoCalculationTransparency.competition_modifier}x</div>
							</div>
							<div class="text-center p-3 rounded-lg bg-surface-secondary/50">
								<div class="text-xs text-text-muted mb-1">Tier 1 Multiplier</div>
								<div class="text-lg font-semibold text-text-primary">{seoCalculationTransparency.tier1_multiplier}x</div>
							</div>
							<div class="text-center p-3 rounded-lg bg-surface-secondary/50">
								<div class="text-xs text-text-muted mb-1">Est. Year 1 Pages</div>
								<div class="text-lg font-semibold text-text-primary">{seoCalculationTransparency.estimated_year1_pages}</div>
							</div>
						</div>

						<!-- Calculation Rationale -->
						{#if seoCalculationTransparency.calculation_rationale}
							<div class="p-4 rounded-lg bg-surface-secondary/30 border border-border">
								<div class="text-sm text-text-muted mb-2">Calculation Rationale</div>
								<p class="text-text-secondary text-sm">{seoCalculationTransparency.calculation_rationale}</p>
							</div>
						{/if}
					</div>
				</AnimateOnScroll>
			{/if}
		</div>
	{/if}

	<!-- ═══════════════════════════════════════════════════════════════
	     ABSORBED: Risk Assessment (from RiskTiming)
	     ═══════════════════════════════════════════════════════════════ -->
	{#if hasRiskAssessment}
		<div class="mt-8 pt-6 border-t border-border">
			<div class="flex items-center gap-3 mb-6">
				<ShieldAlert class="w-5 h-5 text-accent" />
				<h3 class="text-lg font-semibold text-text-primary">Risk Assessment & Timing</h3>
			</div>

			<!-- Risk Factors -->
			{#if trends?.risk_factors && trends.risk_factors.length > 0}
				<AnimateOnScroll animation="fade-up">
					<div class="card border-error/30 mb-6">
						<div class="flex items-center gap-2 mb-4">
							<ShieldAlert class="w-5 h-5 text-error" />
							<h4 class="font-semibold text-error">Risk Factors</h4>
						</div>
						<ul class="space-y-2">
							{#each trends.risk_factors as risk}
								<li class="text-text-secondary text-sm leading-relaxed flex items-start gap-2">
									<span class="text-error">!</span>
									{risk}
								</li>
							{/each}
						</ul>
					</div>
				</AnimateOnScroll>
			{/if}

			<!-- Market Signals -->
			{#if trends}
				<AnimateOnScroll animation="fade-up">
					<div class="grid md:grid-cols-2 gap-6 items-start">
						<!-- Trend Direction -->
						{#if trends.trend_direction}
							{@const TrendIcon = getTrendIcon(trends.trend_direction)}
							<div class="card">
								<div class="flex items-center gap-2 mb-3">
									<TrendIcon class="w-5 h-5 text-accent" />
									<h4 class="font-semibold text-text-primary">Market Trend</h4>
								</div>
								<div class="space-y-2 text-sm">
									<div class="flex justify-between">
										<span class="text-text-muted">Direction:</span>
										<span class="text-text-primary font-medium">{trends.trend_direction}</span>
									</div>
									{#if trends.momentum_score !== undefined}
										<div class="flex justify-between">
											<span class="text-text-muted">Momentum:</span>
											<span class="text-text-primary font-medium">{Math.round(trends.momentum_score * 100)}%</span>
										</div>
									{/if}
									{#if trends.longevity_verdict}
										<div class="flex justify-between">
											<span class="text-text-muted">Longevity:</span>
											<Badge variant={trends.longevity_verdict.includes('Sustain') ? 'success' : trends.longevity_verdict.includes('Fad') ? 'error' : 'warning'} size="sm">
												{trends.longevity_verdict}
											</Badge>
										</div>
									{/if}
									{#if trends.market_maturity}
										<div class="flex justify-between">
											<span class="text-text-muted">Maturity:</span>
											<span class="text-text-primary">{trends.market_maturity}</span>
										</div>
									{/if}
								</div>
							</div>
						{/if}

						<!-- Timing Details -->
						{#if trends.timing_recommendation || trends.longevity_rationale}
							<div class="card">
								<div class="flex items-center gap-2 mb-3">
									<Clock class="w-5 h-5 text-accent" />
									<h4 class="font-semibold text-text-primary">Timing Analysis</h4>
								</div>
								{#if trends.timing_recommendation}
									<div class="highlight-box mb-3">
										<p class="text-sm text-text-primary font-medium">{trends.timing_recommendation}</p>
									</div>
								{/if}
								{#if trends.longevity_rationale}
									<div class="markdown-content text-text-secondary text-sm">
										{@html renderMarkdown(trends.longevity_rationale)}
									</div>
								{/if}
							</div>
						{/if}
					</div>
				</AnimateOnScroll>
			{/if}
		</div>
	{/if}
</section>
