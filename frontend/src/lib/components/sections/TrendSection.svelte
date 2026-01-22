<script lang="ts">
	import {
		TrendingUp,
		TrendingDown,
		Minus,
		Clock,
		AlertTriangle,
		Calendar,
		Activity,
		ChevronRight,
		BarChart3,
		Zap
	} from 'lucide-svelte';
	import type { TrendLongevity } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import ExpandableSection from '$lib/components/ui/ExpandableSection.svelte';
	import HeroStrip from '$lib/components/ui/HeroStrip.svelte';
	import HeroPrimary from '$lib/components/ui/HeroPrimary.svelte';
	import StatPill from '$lib/components/ui/StatPill.svelte';
	import InsightCard from '$lib/components/ui/InsightCard.svelte';
	import IconListItem from '$lib/components/ui/IconListItem.svelte';
	import SectionLabel from '$lib/components/ui/SectionLabel.svelte';

	interface Props {
		data: TrendLongevity;
	}

	let { data }: Props = $props();

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

<section id="trends" class="report-section">
	<SectionHeader
		icon={Activity}
		title="Market Trends & Longevity"
		subtitle="Trend analysis and market timing"
	/>

	<!-- Hero Strip -->
	<HeroStrip>
		{#snippet primary()}
			{#if momentumPercent !== null}
				<HeroPrimary
					value={momentumPercent / 100}
					label="Momentum"
					sublabel={momentumPercent >= 70 ? 'Strong' : momentumPercent >= 40 ? 'Moderate' : 'Weak'}
					color={momentumPercent >= 70 ? 'success' : momentumPercent >= 40 ? 'warning' : 'error'}
				/>
			{/if}
		{/snippet}

		<!-- Trend Direction -->
		{#if data.trend_direction}
			{@const TrendIcon = trendConfig.icon}
			<div class="trend-metric">
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
			<div class="verdict-metric" style="--verdict-color: {verdictConfig.color}">
				<span class="verdict-label">Longevity</span>
				<Badge variant={verdictConfig.variant} size="sm">{data.longevity_verdict}</Badge>
			</div>
		{/if}
	</HeroStrip>

	<!-- Timing Recommendation (Always Visible) -->
	{#if data.timing_recommendation}
		<InsightCard variant="accent" border="left" padding="md" class="timing-card">
			{#snippet header()}
				<SectionLabel text="Timing Recommendation" variant="accent" icon={Clock} />
			{/snippet}
			<p class="timing-text">{data.timing_recommendation}</p>
		</InsightCard>
	{/if}

	<!-- Stats Strip -->
	<div class="stats-strip">
		{#if data.keyword_volume_trend}
			<StatPill label="Keyword Volume" value={data.keyword_volume_trend} />
		{/if}
		{#if data.discussion_frequency_trend}
			<StatPill label="Discussions" value={data.discussion_frequency_trend} />
		{/if}
		{#if data.new_entrants_trend}
			<StatPill label="New Entrants" value={data.new_entrants_trend} />
		{/if}
		{#if data.market_maturity}
			<StatPill label="Maturity" value={data.market_maturity} />
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
		<ExpandableSection title="Longevity Analysis" icon={BarChart3}>
			<div class="analysis-content">
				{@html renderMarkdown(data.longevity_rationale)}
			</div>
		</ExpandableSection>
	{/if}

	<!-- Expandable: Growth Indicators -->
	{#if data.community_growth_indicators && data.community_growth_indicators.length > 0}
		<ExpandableSection
			title="Growth Indicators"
			icon={Zap}
			count={data.community_growth_indicators.length}
			variant="success"
		>
			<div class="item-list">
				{#each data.community_growth_indicators as indicator}
					<IconListItem icon={ChevronRight} iconVariant="success">{indicator}</IconListItem>
				{/each}
			</div>
		</ExpandableSection>
	{/if}

	<!-- Expandable: Risk Factors -->
	{#if data.risk_factors && data.risk_factors.length > 0}
		<ExpandableSection
			title="Risk Factors"
			icon={AlertTriangle}
			count={data.risk_factors.length}
			variant="error"
		>
			<div class="item-list">
				{#each data.risk_factors as risk}
					<IconListItem icon={AlertTriangle} iconVariant="error">{risk}</IconListItem>
				{/each}
			</div>
		</ExpandableSection>
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
	/* Trend Metric (custom for direction display in hero rail) */
	.trend-metric {
		display: flex;
		align-items: center;
		gap: 0.75rem;
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

	/* Verdict Metric */
	.verdict-metric {
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

	/* Timing Card - using InsightCard, just need text styling */
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

	/* Item List - using IconListItem component */
	.item-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
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
		.trend-metric {
			padding-bottom: 0.5rem;
		}
	}

	@media (max-width: 480px) {
		.stats-strip {
			flex-direction: column;
		}
	}
</style>
