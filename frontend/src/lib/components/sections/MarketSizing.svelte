<script lang="ts">
	import {
		TrendingUp,
		Database,
		CheckCircle,
		AlertTriangle,
		Timer,
		Target,
		Zap,
		BarChart3,
		DollarSign
	} from 'lucide-svelte';
	import type { MarketSizing } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import ExpandableSection from '$lib/components/ui/ExpandableSection.svelte';
	import HeroStrip from '$lib/components/ui/HeroStrip.svelte';
	import HeroMetric from '$lib/components/ui/HeroMetric.svelte';
	import MarketFunnel from '$lib/components/charts/MarketFunnel.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';
	import StatPill from '$lib/components/ui/StatPill.svelte';
	import CardGrid from '$lib/components/ui/CardGrid.svelte';

	interface Props {
		data: MarketSizing;
	}

	let { data }: Props = $props();

	// Get viability verdict styling
	const getViabilityConfig = (verdict?: string) => {
		const v = verdict?.toLowerCase() || '';
		if (v === 'strong') return { color: '#22C55E', variant: 'success' as const, label: 'STRONG' };
		if (v === 'moderate') return { color: '#EAB308', variant: 'warning' as const, label: 'MODERATE' };
		return { color: '#EF4444', variant: 'error' as const, label: 'WEAK' };
	};

	// Get saturation level styling
	const getSaturationVariant = (level?: string): 'success' | 'warning' | 'error' => {
		const l = level?.toLowerCase() || '';
		if (l === 'low') return 'success';
		if (l === 'medium') return 'warning';
		return 'error';
	};

	// Get timing styling
	const getTimingVariant = (timing?: string): 'success' | 'warning' | 'error' => {
		const t = timing?.toLowerCase() || '';
		if (t === 'early') return 'success';
		if (t === 'growth') return 'warning';
		return 'error';
	};

	const viabilityConfig = $derived(getViabilityConfig(data.market_viability_verdict));
</script>

<section id="market-sizing" class="report-section">
	<SectionHeader
		icon={DollarSign}
		title="Market Sizing"
		subtitle="TAM/SAM/SOM analysis and growth opportunity"
	/>

	<!-- Hero Strip: Viability Verdict + Key Signals -->
	<HeroStrip>
		{#snippet primary()}
			<div class="verdict-hero" style="--verdict-color: {viabilityConfig.color}">
				<div class="verdict-indicator">
					<CheckCircle class="verdict-icon" />
				</div>
				<div class="verdict-content">
					<span class="verdict-label">MARKET VIABILITY</span>
					<span class="verdict-value">{viabilityConfig.label}</span>
				</div>
			</div>
		{/snippet}
		{#if data.market_growth_rate}
			<HeroMetric
				value={data.market_growth_rate}
				label="Growth Rate"
				icon={TrendingUp}
				color="success"
			/>
		{/if}
		{#if data.market_saturation_level}
			<HeroMetric
				value={data.market_saturation_level}
				label="Saturation"
				color={getSaturationVariant(data.market_saturation_level)}
			/>
		{/if}
		{#if data.market_timing_assessment}
			<HeroMetric
				value={data.market_timing_assessment}
				label="Timing"
				icon={Timer}
				color={getTimingVariant(data.market_timing_assessment)}
			/>
		{/if}
	</HeroStrip>

	<!-- Market Funnel Visualization -->
	<div class="funnel-card">
		<MarketFunnel
			tam={data.total_addressable_market}
			sam={data.serviceable_available_market}
			somY1={data.serviceable_obtainable_market_y1}
			somY3={data.serviceable_obtainable_market_y3}
		/>
	</div>

	<!-- Stats Strip -->
	<div class="stats-strip">
		{#if data.keyword_demand_signal}
			<StatPill label="Keyword Demand" value={data.keyword_demand_signal} />
		{/if}
		{#if data.pain_point_frequency}
			<StatPill label="Pain Frequency" value={data.pain_point_frequency} />
		{/if}
		{#if data.competitor_market_presence}
			<StatPill label="Competition" value={data.competitor_market_presence} />
		{/if}
		{#if data.primary_methodology}
			<StatPill label="Method" value={data.primary_methodology} />
		{/if}
	</div>

	<!-- Entry Strategy Card (Always Visible) -->
	{#if data.recommended_entry_strategy}
		<div class="strategy-hero">
			<div class="strategy-header">
				<Zap class="strategy-icon" />
				<span class="strategy-title">Recommended Entry Strategy</span>
			</div>
			<p class="strategy-text">{data.recommended_entry_strategy}</p>
		</div>
	{/if}

	<!-- Expandable: Growth Drivers & Risks -->
	{#if (data.growth_drivers && data.growth_drivers.length > 0) || (data.risk_factors && data.risk_factors.length > 0)}
		<ExpandableSection
			title="Growth Drivers & Risks"
			icon={BarChart3}
			count={(data.growth_drivers?.length || 0) + (data.risk_factors?.length || 0)}
		>
			<CardGrid minWidth={240} gap="md">
				{#if data.growth_drivers && data.growth_drivers.length > 0}
					<div class="insight-card insight-card--success">
						<h4 class="card-label success">
							<TrendingUp class="label-icon" />
							Growth Drivers
						</h4>
						<ul class="item-list">
							{#each data.growth_drivers as driver}
								<li class="item success">
									<span class="bullet">+</span>
									<span>{driver}</span>
								</li>
							{/each}
						</ul>
					</div>
				{/if}

				{#if data.risk_factors && data.risk_factors.length > 0}
					<div class="insight-card insight-card--error">
						<h4 class="card-label error">
							<AlertTriangle class="label-icon" />
							Market Risks
						</h4>
						<ul class="item-list">
							{#each data.risk_factors as risk}
								<li class="item error">
									<span class="bullet">!</span>
									<span>{risk}</span>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			</CardGrid>
		</ExpandableSection>
	{/if}

	<!-- Expandable: Segment Breakdown -->
	{#if data.segment_sizing && data.segment_sizing.length > 0}
		<ExpandableSection
			title="Segment Breakdown"
			icon={Target}
			count={data.segment_sizing.length}
		>
			<div class="segments-grid">
				{#each data.segment_sizing as segment}
					<div class="segment-card">
						<div class="segment-header">
							<h4 class="segment-name">{segment.segment_name}</h4>
							<Badge
								variant={segment.confidence_level === 'High' ? 'success' : 'warning'}
								size="sm"
							>
								{segment.confidence_level}
							</Badge>
						</div>
						<div class="segment-metrics">
							<div class="metric">
								<span class="metric-label">
									TAM <Tooltip content={getTermTooltip('TAM')} position="top" />
								</span>
								<span class="metric-value">{segment.tam_estimate}</span>
							</div>
							<div class="metric">
								<span class="metric-label">
									SAM <Tooltip content={getTermTooltip('SAM')} position="top" />
								</span>
								<span class="metric-value">{segment.sam_estimate}</span>
							</div>
							<div class="metric highlight">
								<span class="metric-label">
									SOM <Tooltip content={getTermTooltip('SOM')} position="top" />
								</span>
								<span class="metric-value accent">{segment.som_estimate}</span>
							</div>
						</div>
						{#if segment.sizing_methodology}
							<p class="segment-method">{segment.sizing_methodology}</p>
						{/if}
					</div>
				{/each}
			</div>
		</ExpandableSection>
	{/if}

	<!-- Expandable: Methodology -->
	{#if data.methodology_explanation}
		<ExpandableSection
			title="Methodology"
			icon={Database}
			count={data.data_sources_used?.length}
			countSuffix="sources"
		>
			<div class="methodology-content">
				{@html renderMarkdown(data.methodology_explanation)}
			</div>
			{#if data.data_sources_used && data.data_sources_used.length > 0}
				<div class="sources-row">
					<span class="sources-label">Data Sources:</span>
					<div class="sources-tags">
						{#each data.data_sources_used as source}
							<span class="source-tag">{source}</span>
						{/each}
					</div>
				</div>
			{/if}
		</ExpandableSection>
	{/if}

	<!-- Expandable: Viability Rationale -->
	{#if data.viability_rationale}
		<ExpandableSection
			title="Viability Rationale"
			icon={CheckCircle}
		>
			<div class="rationale-content">
				{@html renderMarkdown(data.viability_rationale)}
			</div>
		</ExpandableSection>
	{/if}
</section>

<style>
	/* =========================
	   VERDICT HERO (inside HeroStrip primary)
	   ========================= */
	.verdict-hero {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.verdict-indicator {
		width: 2.5rem;
		height: 2.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		background: color-mix(in srgb, var(--verdict-color) 12%, transparent);
		border: 2px solid var(--verdict-color);
		border-radius: 50%;
	}

	:global(.verdict-icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--verdict-color);
	}

	.verdict-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.verdict-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--color-text-muted);
	}

	.verdict-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--verdict-color);
	}

	/* =========================
	   FUNNEL CARD
	   ========================= */
	.funnel-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		padding: 1.25rem;
		margin-bottom: 1rem;
	}

	/* =========================
	   STATS STRIP
	   ========================= */
	.stats-strip {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	/* =========================
	   STRATEGY HERO
	   ========================= */
	.strategy-hero {
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.06) 0%, transparent 60%);
		border: 1px solid rgba(229, 90, 40, 0.2);
		border-left: 3px solid #E55A28;
		border-radius: 0.75rem;
		padding: 1.125rem;
		margin-bottom: 0.75rem;
	}

	.strategy-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	:global(.strategy-icon) {
		width: 1rem;
		height: 1rem;
		color: #E55A28;
	}

	.strategy-title {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: #E55A28;
	}

	.strategy-text {
		font-size: 0.875rem;
		color: #18181B;
		line-height: 1.6;
		margin: 0;
	}

	/* Drivers & Risks */
	.card-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		margin-bottom: 0.625rem;
	}

	.card-label.success {
		color: #22C55E;
	}

	.card-label.error {
		color: #EF4444;
	}

	:global(.label-icon) {
		width: 0.875rem;
		height: 0.875rem;
	}

	.item-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.75rem;
		color: #71717A;
		line-height: 1.5;
	}

	.item .bullet {
		font-weight: 700;
		flex-shrink: 0;
	}

	.item.success .bullet {
		color: #22C55E;
	}

	.item.error .bullet {
		color: #EF4444;
	}

	/* Segments Grid */
	.segments-grid {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
	}

	.segment-card {
		padding: 0.875rem;
		background: rgba(0, 0, 0, 0.02);
		border-radius: 0.5rem;
		border: 1px solid rgba(0, 0, 0, 0.06);
		position: relative;
	}

	/* Raise z-index when card contains a hovered tooltip */
	.segment-card:has(:global(.tooltip-wrapper:hover)),
	.segment-card:has(:global(.tooltip-wrapper:focus-within)) {
		z-index: 10;
	}

	.segment-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.625rem;
	}

	.segment-name {
		font-family: var(--font-display);
		font-size: 0.875rem;
		font-weight: 600;
		color: #18181B;
		margin: 0;
	}

	.segment-metrics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.875rem;
		margin-bottom: 0.5rem;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.metric.highlight {
		padding: 0.375rem 0.5rem;
		background: rgba(229, 90, 40, 0.08);
		border-radius: 0.375rem;
	}

	.metric-label {
		font-family: var(--font-mono);
		font-size: 0.5rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #A1A1AA;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}

	.metric-value {
		font-family: var(--font-display);
		font-size: 0.8125rem;
		font-weight: 600;
		color: #18181B;
	}

	.metric-value.accent {
		color: #E55A28;
	}

	.segment-method {
		font-size: 0.6875rem;
		color: #A1A1AA;
		line-height: 1.45;
		margin: 0;
	}

	/* Methodology Content */
	.methodology-content {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.65;
		margin-bottom: 0.875rem;
	}

	.methodology-content :global(p) {
		margin-bottom: 0.5rem;
	}

	.methodology-content :global(p:last-child) {
		margin-bottom: 0;
	}

	.sources-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding-top: 0.875rem;
		border-top: 1px solid rgba(0, 0, 0, 0.06);
	}

	.sources-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #A1A1AA;
	}

	.sources-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	.source-tag {
		font-size: 0.6875rem;
		padding: 0.25rem 0.5rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.25rem;
		color: #A1A1AA;
	}

	/* Rationale Content */
	.rationale-content {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.65;
	}

	.rationale-content :global(p) {
		margin-bottom: 0.5rem;
	}

	.rationale-content :global(p:last-child) {
		margin-bottom: 0;
	}

	/* =========================
	   RESPONSIVE
	   ========================= */
	@media (max-width: 768px) {
		.segment-metrics {
			flex-direction: column;
			gap: 0.5rem;
		}
	}

	@media (max-width: 480px) {
		.section-title {
			font-size: 1.25rem;
		}

		.funnel-card {
			padding: 1rem;
		}
	}
</style>
