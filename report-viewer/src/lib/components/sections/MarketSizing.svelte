<script lang="ts">
	import { PieChart, TrendingUp, Database, CheckCircle, AlertTriangle, Timer, Target, Zap } from 'lucide-svelte';
	import type { MarketSizing } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import MetricCard from '$lib/components/ui/MetricCard.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import MarketFunnel from '$lib/components/charts/MarketFunnel.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		data: MarketSizing;
	}

	let { data }: Props = $props();

	// Get viability verdict styling
	const getViabilityConfig = (verdict?: string) => {
		const v = verdict?.toLowerCase() || '';
		if (v === 'strong') return { color: 'text-success', bg: 'bg-success/10', icon: CheckCircle };
		if (v === 'moderate') return { color: 'text-warning', bg: 'bg-warning/10', icon: AlertTriangle };
		return { color: 'text-error', bg: 'bg-error/10', icon: AlertTriangle };
	};

	// Get saturation level styling
	const getSaturationVariant = (level?: string) => {
		const l = level?.toLowerCase() || '';
		if (l === 'low') return 'success';
		if (l === 'medium') return 'warning';
		return 'error';
	};

	// Get timing styling
	const getTimingVariant = (timing?: string) => {
		const t = timing?.toLowerCase() || '';
		if (t === 'early') return 'success';
		if (t === 'growth') return 'accent';
		return 'warning';
	};
</script>

<section id="market-sizing" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<PieChart class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Market Sizing</h2>
	</div>

	<!-- TAM/SAM/SOM Funnel -->
	<AnimateOnScroll animation="fade-up">
		<div class="mb-8">
			<MarketFunnel
				tam={data.total_addressable_market}
				sam={data.serviceable_available_market}
				somY1={data.serviceable_obtainable_market_y1}
				somY3={data.serviceable_obtainable_market_y3}
			/>
		</div>
	</AnimateOnScroll>

	<!-- Methodology -->
	<div class="card mb-8">
		<div class="flex items-center gap-2 mb-4">
			<Database class="w-5 h-5 text-accent" />
			<h3 class="text-lg font-semibold text-text-primary">Methodology</h3>
			<Badge>{data.primary_methodology}</Badge>
		</div>
		<div class="markdown-content narrative">
			{@html renderMarkdown(data.methodology_explanation)}
		</div>

		{#if data.data_sources_used && data.data_sources_used.length > 0}
			<div class="mt-4 pt-4 border-t border-border">
				<h4 class="text-sm font-semibold text-text-muted mb-2">Data Sources</h4>
				<div class="flex flex-wrap gap-2">
					{#each data.data_sources_used as source}
						<span class="text-xs px-2 py-1 rounded bg-bg-surface border border-border text-text-muted">{source}</span>
					{/each}
				</div>
			</div>
		{/if}
	</div>

	<!-- Market Signals -->
	<div class="grid md:grid-cols-3 gap-4 mb-8">
		{#if data.keyword_demand_signal}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">Keyword Demand</div>
				<div class="text-lg font-semibold text-text-primary">{data.keyword_demand_signal}</div>
			</div>
		{/if}
		{#if data.pain_point_frequency}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">Pain Point Frequency</div>
				<div class="text-lg font-semibold text-text-primary">{data.pain_point_frequency}</div>
			</div>
		{/if}
		{#if data.competitor_market_presence}
			<div class="card-surface card-sm">
				<div class="text-sm text-text-muted mb-1">Competitor Presence</div>
				<div class="text-lg font-semibold text-text-primary">{data.competitor_market_presence}</div>
			</div>
		{/if}
	</div>

	<!-- Growth Rate -->
	{#if data.market_growth_rate}
		<div class="highlight-box mb-8">
			<div class="flex items-center gap-3">
				<TrendingUp class="w-5 h-5 text-success" />
				<div>
					<span class="text-text-muted">Market Growth Rate:</span>
					<span class="text-lg font-semibold text-success ml-2">{data.market_growth_rate}</span>
				</div>
			</div>
		</div>
	{/if}

	<!-- Growth Drivers & Risks -->
	<div class="grid md:grid-cols-2 gap-6">
		{#if data.growth_drivers && data.growth_drivers.length > 0}
			<div class="card">
				<h3 class="text-lg font-semibold text-success mb-4">Growth Drivers</h3>
				<ul class="space-y-2">
					{#each data.growth_drivers as driver}
						<li class="text-text-secondary text-sm leading-relaxed flex items-start gap-2">
							<span class="text-success">+</span>
							{driver}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if data.market_risks && data.market_risks.length > 0}
			<div class="card">
				<h3 class="text-lg font-semibold text-error mb-4">Market Risks</h3>
				<ul class="space-y-2">
					{#each data.market_risks as risk}
						<li class="text-text-secondary text-sm leading-relaxed flex items-start gap-2">
							<span class="text-error">-</span>
							{risk}
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</div>

	<!-- Segment Sizing -->
	{#if data.segment_sizing && data.segment_sizing.length > 0}
		<div class="mt-8">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Segment Breakdown</h3>
			<div class="space-y-4">
				{#each data.segment_sizing as segment}
					<div class="card-surface">
						<div class="flex items-center justify-between mb-2">
							<h4 class="font-semibold text-text-primary">{segment.segment_name}</h4>
							<Badge variant={segment.confidence_level === 'High' ? 'success' : 'warning'}>
								{segment.confidence_level} confidence
							</Badge>
						</div>
						<div class="grid grid-cols-3 gap-4 text-sm">
							<div>
								<span class="text-text-muted">TAM:</span>
								<span class="text-text-primary ml-1">{segment.tam_estimate}</span>
							</div>
							<div>
								<span class="text-text-muted">SAM:</span>
								<span class="text-text-primary ml-1">{segment.sam_estimate}</span>
							</div>
							<div>
								<span class="text-text-muted">SOM:</span>
								<span class="text-accent ml-1">{segment.som_estimate}</span>
							</div>
						</div>
						<p class="text-xs text-text-muted mt-2">{segment.sizing_methodology}</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Market Assessment -->
	{#if data.market_saturation_level || data.market_timing_assessment || data.market_viability_verdict}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<Target class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Market Assessment</h3>
				</div>
				<div class="grid md:grid-cols-3 gap-4 mb-6">
					{#if data.market_saturation_level}
						<div class="card card-sm flex items-center gap-4">
							<div class="p-3 rounded-lg bg-{getSaturationVariant(data.market_saturation_level)}/10">
								<AlertTriangle class="w-6 h-6 text-{getSaturationVariant(data.market_saturation_level)}" />
							</div>
							<div>
								<div class="text-sm text-text-muted">Saturation Level</div>
								<Badge variant={getSaturationVariant(data.market_saturation_level)}>
									{data.market_saturation_level}
								</Badge>
							</div>
						</div>
					{/if}
					{#if data.market_timing_assessment}
						<div class="card card-sm flex items-center gap-4">
							<div class="p-3 rounded-lg bg-accent/10">
								<Timer class="w-6 h-6 text-accent" />
							</div>
							<div>
								<div class="text-sm text-text-muted">Market Timing</div>
								<Badge variant={getTimingVariant(data.market_timing_assessment)}>
									{data.market_timing_assessment}
								</Badge>
							</div>
						</div>
					{/if}
					{#if data.market_viability_verdict}
						{@const config = getViabilityConfig(data.market_viability_verdict)}
						{@const ViabilityIcon = config.icon}
						<div class="card card-sm flex items-center gap-4">
							<div class="p-3 rounded-lg {config.bg}">
								<ViabilityIcon class="w-6 h-6 {config.color}" />
							</div>
							<div>
								<div class="text-sm text-text-muted">Viability Verdict</div>
								<Badge variant={data.market_viability_verdict === 'Strong' ? 'success' : data.market_viability_verdict === 'Moderate' ? 'warning' : 'error'}>
									{data.market_viability_verdict}
								</Badge>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Viability Rationale & Entry Strategy -->
	{#if data.viability_rationale || data.recommended_entry_strategy}
		<AnimateOnScroll animation="fade-up">
			<div class="grid md:grid-cols-2 gap-6 mt-6 items-start">
				{#if data.viability_rationale}
					<div class="card">
						<h3 class="text-lg font-semibold text-text-primary mb-3">Viability Rationale</h3>
						<div class="markdown-content narrative text-sm">
							{@html renderMarkdown(data.viability_rationale)}
						</div>
					</div>
				{/if}
				{#if data.recommended_entry_strategy}
					<div class="card border-accent/30">
						<div class="flex items-center gap-2 mb-3">
							<Zap class="w-5 h-5 text-accent" />
							<h3 class="text-lg font-semibold text-accent">Recommended Entry Strategy</h3>
						</div>
						<p class="text-text-secondary">{data.recommended_entry_strategy}</p>
					</div>
				{/if}
			</div>
		</AnimateOnScroll>
	{/if}
</section>
