<script lang="ts">
	import {
		TrendingUp,
		TrendingDown,
		Minus,
		Clock,
		AlertTriangle,
		Calendar,
		Activity,
		ChevronDown,
		ChevronRight,
		BarChart3,
		Zap
	} from 'lucide-svelte';
	import type { TrendLongevity } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';

	interface Props {
		data: TrendLongevity;
	}

	let { data }: Props = $props();

	// Expandable sections state
	let showAnalysis = $state(false);
	let showGrowth = $state(false);
	let showRisks = $state(false);

	// Determine trend icon and color
	const trendConfig = $derived.by(() => {
		const direction = data.trend_direction?.toLowerCase() || '';
		if (direction.includes('grow')) {
			return { icon: TrendingUp, color: 'var(--color-success)', label: 'Growing' };
		} else if (direction.includes('declin')) {
			return { icon: TrendingDown, color: 'var(--color-error)', label: 'Declining' };
		}
		return { icon: Minus, color: 'var(--color-warning)', label: 'Stable' };
	});

	// Determine verdict badge variant
	const verdictConfig = $derived.by(() => {
		const verdict = data.longevity_verdict?.toLowerCase() || '';
		if (verdict.includes('sustain'))
			return { variant: 'success' as const, color: 'var(--color-success)', label: 'SUSTAINABLE' };
		if (verdict.includes('risky') || verdict.includes('fad'))
			return { variant: 'error' as const, color: 'var(--color-error)', label: 'RISKY' };
		return { variant: 'warning' as const, color: 'var(--color-warning)', label: 'MODERATE' };
	});

	// Momentum score percentage
	const momentumPercent = $derived(
		data.momentum_score !== undefined ? Math.round(data.momentum_score * 100) : null
	);
</script>

<section id="trends" class="trends-section">
	<!-- Section Header -->
	<div class="section-header">
		<div class="header-icon">
			<Activity class="icon" />
		</div>
		<div>
			<h2 class="section-title">Market Trends & Longevity</h2>
			<p class="section-subtitle">Trend analysis and market timing</p>
		</div>
	</div>

	<!-- Hero Strip -->
	<div class="hero-strip">
		<!-- Momentum Score -->
		{#if momentumPercent !== null}
			<div class="hero-metric">
				<ProgressRing
					value={momentumPercent / 100}
					size={56}
					strokeWidth={5}
					color={momentumPercent >= 70 ? 'success' : momentumPercent >= 40 ? 'warning' : 'error'}
					showValue={true}
				/>
				<div class="hero-metric-content">
					<span class="hero-metric-label">Momentum</span>
					<span class="hero-metric-value"
						>{momentumPercent >= 70 ? 'Strong' : momentumPercent >= 40 ? 'Moderate' : 'Weak'}</span
					>
				</div>
			</div>
		{/if}

		<!-- Trend Direction -->
		{#if data.trend_direction}
			{@const TrendIcon = trendConfig.icon}
			<div class="hero-trend">
				<div class="trend-indicator" style="--trend-color: {trendConfig.color}">
					<TrendIcon class="trend-icon" />
				</div>
				<div class="trend-content">
					<span class="trend-label">Direction</span>
					<span class="trend-value" style="color: {trendConfig.color}">{data.trend_direction}</span>
				</div>
			</div>
		{/if}

		<!-- Longevity Verdict -->
		{#if data.longevity_verdict}
			<div class="hero-verdict" style="--verdict-color: {verdictConfig.color}">
				<span class="verdict-label">Longevity</span>
				<Badge variant={verdictConfig.variant} size="sm">{data.longevity_verdict}</Badge>
			</div>
		{/if}
	</div>

	<!-- Timing Recommendation (Always Visible) -->
	{#if data.timing_recommendation}
		<div class="timing-card">
			<div class="timing-header">
				<Clock class="timing-icon" />
				<span class="timing-title">Timing Recommendation</span>
			</div>
			<p class="timing-text">{data.timing_recommendation}</p>
		</div>
	{/if}

	<!-- Stats Strip -->
	<div class="stats-strip">
		{#if data.keyword_volume_trend}
			<div class="stat-pill">
				<span class="stat-label">Keyword Volume</span>
				<span class="stat-value">{data.keyword_volume_trend}</span>
			</div>
		{/if}
		{#if data.discussion_frequency_trend}
			<div class="stat-pill">
				<span class="stat-label">Discussions</span>
				<span class="stat-value">{data.discussion_frequency_trend}</span>
			</div>
		{/if}
		{#if data.new_entrants_trend}
			<div class="stat-pill">
				<span class="stat-label">New Entrants</span>
				<span class="stat-value">{data.new_entrants_trend}</span>
			</div>
		{/if}
		{#if data.market_maturity}
			<div class="stat-pill">
				<span class="stat-label">Maturity</span>
				<span class="stat-value">{data.market_maturity}</span>
			</div>
		{/if}
	</div>

	<!-- Seasonality Card (Always Visible if present) -->
	{#if data.seasonal_pattern || data.peak_periods}
		<div class="seasonality-card">
			<div class="seasonality-header">
				<Calendar class="seasonality-icon" />
				<span class="seasonality-title">Seasonality</span>
			</div>
			{#if data.seasonal_pattern}
				<p class="seasonality-text">{data.seasonal_pattern}</p>
			{/if}
			{#if data.peak_periods}
				<div class="peak-periods">
					<span class="periods-label">Peak Periods:</span>
					<Badge variant="muted" size="sm">{data.peak_periods}</Badge>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Longevity Analysis -->
	{#if data.longevity_rationale}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showAnalysis = !showAnalysis)}>
				<div class="expandable-title">
					<BarChart3 class="expandable-icon" />
					<span>Longevity Analysis</span>
				</div>
				<ChevronDown class="chevron-icon {showAnalysis ? 'expanded' : ''}" />
			</button>
			{#if showAnalysis}
				<div class="expandable-content">
					<div class="analysis-content">
						{@html renderMarkdown(data.longevity_rationale)}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Growth Indicators -->
	{#if data.community_growth_indicators && data.community_growth_indicators.length > 0}
		<div class="expandable-section success-accent">
			<button class="expandable-header" onclick={() => (showGrowth = !showGrowth)}>
				<div class="expandable-title">
					<Zap class="expandable-icon success" />
					<span>Growth Indicators</span>
					<Badge variant="success" size="sm">{data.community_growth_indicators.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showGrowth ? 'expanded' : ''}" />
			</button>
			{#if showGrowth}
				<div class="expandable-content">
					<ul class="indicator-list">
						{#each data.community_growth_indicators as indicator}
							<li class="indicator-item">
								<ChevronRight class="indicator-icon" />
								<span>{indicator}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Risk Factors -->
	{#if data.risk_factors && data.risk_factors.length > 0}
		<div class="expandable-section error-accent">
			<button class="expandable-header" onclick={() => (showRisks = !showRisks)}>
				<div class="expandable-title">
					<AlertTriangle class="expandable-icon error" />
					<span>Risk Factors</span>
					<Badge variant="error" size="sm">{data.risk_factors.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showRisks ? 'expanded' : ''}" />
			</button>
			{#if showRisks}
				<div class="expandable-content">
					<ul class="risk-list">
						{#each data.risk_factors as risk}
							<li class="risk-item">
								<span class="risk-bullet">!</span>
								<span>{risk}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Metadata Footer -->
	{#if data.data_sources_analyzed || data.analysis_timeframe}
		<div class="metadata-footer">
			{#if data.data_sources_analyzed}
				<span class="metadata-item">
					<span class="metadata-label">Sources:</span>
					{data.data_sources_analyzed}
				</span>
			{/if}
			{#if data.analysis_timeframe}
				<span class="metadata-item">
					<span class="metadata-label">Timeframe:</span>
					{data.analysis_timeframe}
				</span>
			{/if}
		</div>
	{/if}
</section>

<style>
	.trends-section {
		padding: 1.5rem 0;
	}

	/* Section Header */
	.section-header {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.header-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		background: rgba(229, 90, 40, 0.1);
		border: 1px solid rgba(229, 90, 40, 0.2);
		border-radius: 0.625rem;
		flex-shrink: 0;
	}

	.header-icon :global(.icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--color-accent);
	}

	.section-title {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--color-text-primary);
		margin-bottom: 0.125rem;
	}

	.section-subtitle {
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}

	/* Hero Strip */
	.hero-strip {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		padding: 1rem 1.25rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.hero-metric {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding-right: 1.5rem;
		border-right: 1px solid var(--color-border);
	}

	.hero-metric-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.hero-metric-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}

	.hero-metric-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.hero-trend {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding-right: 1.5rem;
		border-right: 1px solid var(--color-border);
	}

	.trend-indicator {
		width: 2.25rem;
		height: 2.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		background: color-mix(in srgb, var(--trend-color) 15%, transparent);
		border: 2px solid var(--trend-color);
		border-radius: 50%;
	}

	.trend-indicator :global(.trend-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--trend-color);
	}

	.trend-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.trend-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}

	.trend-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 700;
	}

	.hero-verdict {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.verdict-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}

	/* Timing Card */
	.timing-card {
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.08) 0%, transparent 60%);
		border: 1px solid rgba(229, 90, 40, 0.25);
		border-left: 3px solid var(--color-accent);
		border-radius: 0.75rem;
		padding: 1.25rem;
		margin-bottom: 1rem;
	}

	.timing-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.timing-header :global(.timing-icon) {
		width: 1rem;
		height: 1rem;
		color: var(--color-accent);
	}

	.timing-title {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-accent);
	}

	.timing-text {
		font-size: 0.9375rem;
		color: var(--color-text-primary);
		line-height: 1.6;
		margin: 0;
	}

	/* Stats Strip */
	.stats-strip {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.stat-pill {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.75rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 999px;
	}

	.stat-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}

	.stat-value {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	/* Seasonality Card */
	.seasonality-card {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.25rem;
		margin-bottom: 1rem;
	}

	.seasonality-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.seasonality-header :global(.seasonality-icon) {
		width: 1rem;
		height: 1rem;
		color: var(--color-accent);
	}

	.seasonality-title {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.seasonality-text {
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
		margin: 0 0 0.75rem;
	}

	.peak-periods {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.periods-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}

	/* Expandable Sections */
	.expandable-section {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		overflow: hidden;
	}

	.expandable-section.success-accent {
		border-color: rgba(34, 197, 94, 0.3);
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.05) 0%, transparent 40%);
	}

	.expandable-section.error-accent {
		border-color: rgba(239, 68, 68, 0.3);
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, transparent 40%);
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 1rem 1.25rem;
		background: transparent;
		border: none;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.expandable-header:hover {
		background: var(--color-bg-surface);
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.expandable-title :global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-accent);
	}

	.expandable-title :global(.expandable-icon.success) {
		color: var(--color-success);
	}

	.expandable-title :global(.expandable-icon.error) {
		color: var(--color-error);
	}

	:global(.chevron-icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--color-text-muted);
		transition: transform 0.2s ease;
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 1.25rem 1.25rem;
	}

	/* Analysis Content */
	.analysis-content {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		line-height: 1.7;
	}

	.analysis-content :global(p) {
		margin: 0 0 0.75rem;
	}

	.analysis-content :global(p:last-child) {
		margin-bottom: 0;
	}

	/* Indicator List */
	.indicator-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.indicator-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}

	.indicator-item :global(.indicator-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: var(--color-success);
		flex-shrink: 0;
		margin-top: 0.125rem;
	}

	/* Risk List */
	.risk-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.risk-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}

	.risk-bullet {
		font-weight: 700;
		color: var(--color-error);
		flex-shrink: 0;
	}

	/* Metadata Footer */
	.metadata-footer {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--color-border);
	}

	.metadata-item {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.metadata-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		margin-right: 0.25rem;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.hero-strip {
			flex-direction: column;
			align-items: flex-start;
			gap: 1rem;
		}

		.hero-metric {
			padding-right: 0;
			border-right: none;
			padding-bottom: 1rem;
			border-bottom: 1px solid var(--color-border);
			width: 100%;
		}

		.hero-trend {
			padding-right: 0;
			border-right: none;
			padding-bottom: 1rem;
			border-bottom: 1px solid var(--color-border);
			width: 100%;
		}
	}

	@media (max-width: 480px) {
		.section-title {
			font-size: 1.25rem;
		}

		.expandable-header {
			padding: 0.875rem 1rem;
		}

		.expandable-content {
			padding: 0 1rem 1rem;
		}

		.stats-strip {
			flex-direction: column;
		}

		.stat-pill {
			width: 100%;
			justify-content: space-between;
		}
	}
</style>
