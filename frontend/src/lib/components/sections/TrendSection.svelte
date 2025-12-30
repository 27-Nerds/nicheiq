<script lang="ts">
	import { TrendingUp, TrendingDown, Minus, Clock, AlertTriangle, Calendar, Activity } from 'lucide-svelte';
	import type { TrendLongevity } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';

	interface Props {
		data: TrendLongevity;
	}

	let { data }: Props = $props();

	// Determine trend icon and color
	const trendConfig = $derived(() => {
		const direction = data.trend_direction?.toLowerCase() || '';
		if (direction.includes('grow')) {
			return { icon: TrendingUp, color: 'text-success', bg: 'bg-success/10' };
		} else if (direction.includes('declin')) {
			return { icon: TrendingDown, color: 'text-error', bg: 'bg-error/10' };
		}
		return { icon: Minus, color: 'text-warning', bg: 'bg-warning/10' };
	});

	// Determine verdict badge variant
	const verdictVariant = $derived(() => {
		const verdict = data.longevity_verdict?.toLowerCase() || '';
		if (verdict.includes('sustain')) return 'success';
		if (verdict.includes('risky') || verdict.includes('fad')) return 'error';
		return 'warning';
	});
</script>

<section id="trends" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<Activity class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Market Trends & Longevity</h2>
	</div>

	<!-- Trend Overview Cards -->
	<AnimateOnScroll animation="fade-up">
		<div class="grid md:grid-cols-3 gap-4 mb-8">
			<!-- Trend Direction -->
			{#if data.trend_direction}
				{@const config = trendConfig()}
				{@const TrendIcon = config.icon}
				<div class="card card-sm flex items-center gap-4">
					<div class="p-3 rounded-lg {config.bg}">
						<TrendIcon class="w-6 h-6 {config.color}" />
					</div>
					<div>
						<div class="text-sm text-text-muted">Trend Direction</div>
						<div class="text-lg font-semibold {config.color}">{data.trend_direction}</div>
					</div>
				</div>
			{/if}

			<!-- Momentum Score -->
			{#if data.momentum_score !== undefined}
				<div class="card card-sm flex items-center gap-4">
					<ProgressRing value={data.momentum_score} size={56} strokeWidth={6} />
					<div>
						<div class="text-sm text-text-muted">Momentum Score</div>
						<div class="text-lg font-semibold text-text-primary">{Math.round(data.momentum_score * 100)}%</div>
					</div>
				</div>
			{/if}

			<!-- Longevity Verdict -->
			{#if data.longevity_verdict}
				<div class="card card-sm flex items-center gap-4">
					<div class="p-3 rounded-lg bg-accent/10">
						<Clock class="w-6 h-6 text-accent" />
					</div>
					<div>
						<div class="text-sm text-text-muted">Longevity Verdict</div>
						<Badge variant={verdictVariant()}>{data.longevity_verdict}</Badge>
					</div>
				</div>
			{/if}
		</div>
	</AnimateOnScroll>

	<!-- Timing Recommendation -->
	{#if data.timing_recommendation}
		<AnimateOnScroll animation="fade-up">
			<div class="highlight-box mb-8">
				<div class="flex items-start gap-3">
					<Clock class="w-5 h-5 text-accent mt-0.5" />
					<div>
						<span class="text-text-muted text-sm">Timing Recommendation:</span>
						<p class="text-text-primary font-medium mt-1">{data.timing_recommendation}</p>
					</div>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Longevity Rationale -->
	{#if data.longevity_rationale}
		<div class="card mb-8">
			<h3 class="text-lg font-semibold text-text-primary mb-3">Analysis</h3>
			<div class="markdown-content narrative">
				{@html renderMarkdown(data.longevity_rationale)}
			</div>
		</div>
	{/if}

	<!-- Trend Signals -->
	<div class="grid md:grid-cols-2 gap-4 mb-8">
		{#if data.keyword_volume_trend}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">Keyword Volume Trend</div>
				<div class="text-text-primary">{data.keyword_volume_trend}</div>
			</div>
		{/if}
		{#if data.discussion_frequency_trend}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">Discussion Frequency</div>
				<div class="text-text-primary">{data.discussion_frequency_trend}</div>
			</div>
		{/if}
		{#if data.new_entrants_trend}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">New Entrants</div>
				<div class="text-text-primary">{data.new_entrants_trend}</div>
			</div>
		{/if}
		{#if data.market_maturity}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">Market Maturity</div>
				<div class="text-text-primary">{data.market_maturity}</div>
			</div>
		{/if}
	</div>

	<!-- Community Growth & Seasonality -->
	<div class="grid md:grid-cols-2 gap-6 mb-8 items-start">
		<!-- Community Growth Indicators -->
		{#if data.community_growth_indicators && data.community_growth_indicators.length > 0}
			<div class="card">
				<div class="flex items-center gap-2 mb-4">
					<TrendingUp class="w-5 h-5 text-success" />
					<h3 class="text-lg font-semibold text-text-primary">Community Growth Indicators</h3>
				</div>
				<ul class="space-y-2">
					{#each data.community_growth_indicators as indicator}
						<li class="text-text-secondary text-sm leading-relaxed flex items-start gap-2">
							<span class="text-success">+</span>
							{indicator}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Seasonality -->
		{#if data.seasonal_patterns || (data.peak_periods && data.peak_periods.length > 0)}
			<div class="card">
				<div class="flex items-center gap-2 mb-4">
					<Calendar class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Seasonality</h3>
				</div>
				{#if data.seasonal_patterns}
					<p class="text-text-secondary text-sm leading-relaxed mb-3">{data.seasonal_patterns}</p>
				{/if}
				{#if data.peak_periods && data.peak_periods.length > 0}
					<div class="flex flex-wrap gap-2">
						{#each data.peak_periods as period}
							<Badge variant="info">{period}</Badge>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Risk Factors -->
	{#if data.risk_factors && data.risk_factors.length > 0}
		<div class="card border-error/30">
			<div class="flex items-center gap-2 mb-4">
				<AlertTriangle class="w-5 h-5 text-error" />
				<h3 class="text-lg font-semibold text-error">Risk Factors</h3>
			</div>
			<ul class="space-y-2">
				{#each data.risk_factors as risk}
					<li class="text-text-secondary text-sm leading-relaxed flex items-start gap-2">
						<span class="text-error">!</span>
						{risk}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- Metadata -->
	{#if data.data_sources_analyzed || data.analysis_timeframe}
		<div class="mt-6 pt-4 border-t border-border text-xs text-text-muted">
			{#if data.data_sources_analyzed}
				<span>Sources: {data.data_sources_analyzed}</span>
			{/if}
			{#if data.data_sources_analyzed && data.analysis_timeframe}
				<span class="mx-2">|</span>
			{/if}
			{#if data.analysis_timeframe}
				<span>Timeframe: {data.analysis_timeframe}</span>
			{/if}
		</div>
	{/if}
</section>
