<script lang="ts">
	import {
		PieChart,
		TrendingUp,
		Database,
		CheckCircle,
		AlertTriangle,
		Timer,
		Target,
		Zap,
		ChevronDown,
		BarChart3,
		DollarSign
	} from 'lucide-svelte';
	import type { MarketSizing } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import ExpandableSection from '$lib/components/ui/ExpandableSection.svelte';
	import MarketFunnel from '$lib/components/charts/MarketFunnel.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';

	interface Props {
		data: MarketSizing;
	}

	let { data }: Props = $props();

	// Expandable sections state
	let showSegments = $state(false);
	let showDriversRisks = $state(false);
	let showMethodology = $state(false);
	let showStrategy = $state(false);

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
	<div class="hero-strip">
		<div class="verdict-hero" style="--verdict-color: {viabilityConfig.color}">
			<div class="verdict-indicator">
				<CheckCircle class="verdict-icon" />
			</div>
			<div class="verdict-content">
				<span class="verdict-label">MARKET VIABILITY</span>
				<span class="verdict-value">{viabilityConfig.label}</span>
			</div>
		</div>

		<div class="hero-signals">
			{#if data.market_growth_rate}
				<div class="hero-signal">
					<TrendingUp class="signal-icon success" />
					<div class="signal-content">
						<span class="signal-label">Growth Rate</span>
						<span class="signal-value">{data.market_growth_rate}</span>
					</div>
				</div>
			{/if}

			{#if data.market_saturation_level}
				<div class="hero-signal">
					<div class="signal-content">
						<span class="signal-label">Saturation</span>
						<Badge variant={getSaturationVariant(data.market_saturation_level)} size="sm">
							{data.market_saturation_level}
						</Badge>
					</div>
				</div>
			{/if}

			{#if data.market_timing_assessment}
				<div class="hero-signal">
					<Timer class="signal-icon" />
					<div class="signal-content">
						<span class="signal-label">Timing</span>
						<Badge variant={getTimingVariant(data.market_timing_assessment)} size="sm">
							{data.market_timing_assessment}
						</Badge>
					</div>
				</div>
			{/if}
		</div>
	</div>

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
			<div class="stat-pill">
				<span class="stat-label">Keyword Demand</span>
				<span class="stat-value">{data.keyword_demand_signal}</span>
			</div>
		{/if}
		{#if data.pain_point_frequency}
			<div class="stat-pill">
				<span class="stat-label">Pain Frequency</span>
				<span class="stat-value">{data.pain_point_frequency}</span>
			</div>
		{/if}
		{#if data.competitor_market_presence}
			<div class="stat-pill">
				<span class="stat-label">Competition</span>
				<span class="stat-value">{data.competitor_market_presence}</span>
			</div>
		{/if}
		{#if data.primary_methodology}
			<div class="stat-pill">
				<span class="stat-label">Method</span>
				<span class="stat-value">{data.primary_methodology}</span>
			</div>
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
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showDriversRisks = !showDriversRisks)}>
				<div class="expandable-title">
					<BarChart3 class="expandable-icon" />
					<span>Growth Drivers & Risks</span>
					<Badge variant="muted" size="sm">
						{(data.growth_drivers?.length || 0) + (data.risk_factors?.length || 0)}
					</Badge>
				</div>
				<ChevronDown class="chevron-icon {showDriversRisks ? 'expanded' : ''}" />
			</button>
			{#if showDriversRisks}
				<div class="expandable-content">
					<div class="drivers-risks-grid">
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
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Segment Breakdown -->
	{#if data.segment_sizing && data.segment_sizing.length > 0}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showSegments = !showSegments)}>
				<div class="expandable-title">
					<Target class="expandable-icon" />
					<span>Segment Breakdown</span>
					<Badge variant="muted" size="sm">{data.segment_sizing.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showSegments ? 'expanded' : ''}" />
			</button>
			{#if showSegments}
				<div class="expandable-content">
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
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Methodology -->
	{#if data.methodology_explanation}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showMethodology = !showMethodology)}>
				<div class="expandable-title">
					<Database class="expandable-icon" />
					<span>Methodology</span>
					{#if data.data_sources_used && data.data_sources_used.length > 0}
						<Badge variant="muted" size="sm">{data.data_sources_used.length} sources</Badge>
					{/if}
				</div>
				<ChevronDown class="chevron-icon {showMethodology ? 'expanded' : ''}" />
			</button>
			{#if showMethodology}
				<div class="expandable-content">
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
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Viability Rationale -->
	{#if data.viability_rationale}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showStrategy = !showStrategy)}>
				<div class="expandable-title">
					<CheckCircle class="expandable-icon" />
					<span>Viability Rationale</span>
				</div>
				<ChevronDown class="chevron-icon {showStrategy ? 'expanded' : ''}" />
			</button>
			{#if showStrategy}
				<div class="expandable-content">
					<div class="rationale-content">
						{@html renderMarkdown(data.viability_rationale)}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</section>

<style>
	/* =========================
	   HERO STRIP
	   ========================= */
	.hero-strip {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		padding: 1.125rem 1.25rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.verdict-hero {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding-right: 1.5rem;
		border-right: 1px solid rgba(0, 0, 0, 0.08);
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
		color: #A1A1AA;
	}

	.verdict-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--verdict-color);
	}

	.hero-signals {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.hero-signal {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	:global(.signal-icon) {
		width: 1rem;
		height: 1rem;
		color: #A1A1AA;
	}

	:global(.signal-icon.success) {
		color: #22C55E;
	}

	.signal-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.signal-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #A1A1AA;
	}

	.signal-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 700;
		color: #22C55E;
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

	.stat-pill {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 0.75rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 9999px;
	}

	.stat-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: #A1A1AA;
	}

	.stat-value {
		font-family: var(--font-display);
		font-size: 0.75rem;
		font-weight: 600;
		color: #18181B;
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

	/* Drivers & Risks Grid */
	.drivers-risks-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 0.75rem;
	}


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
		.hero-strip {
			flex-direction: column;
			align-items: flex-start;
			gap: 1rem;
		}

		.verdict-hero {
			padding-right: 0;
			border-right: none;
			padding-bottom: 1rem;
			border-bottom: 1px solid rgba(0, 0, 0, 0.06);
			width: 100%;
		}

		.hero-signals {
			width: 100%;
			justify-content: space-between;
		}

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
