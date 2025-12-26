<script lang="ts">
	import { scaleLinear, scaleBand } from 'd3-scale';
	import ChartTheme from './ChartTheme.svelte';
	import type { CompetitorProfile } from '$lib/types/report';

	interface Props {
		competitors: CompetitorProfile[];
		class?: string;
	}

	let { competitors, class: className = '' }: Props = $props();

	// Process competitors data
	const chartData = $derived(
		competitors.slice(0, 8).map((c) => ({
			name: c.name.length > 18 ? c.name.slice(0, 15) + '...' : c.name,
			fullName: c.name,
			featureCount: c.key_features?.length || 0,
			strengthCount: c.strengths?.length || 0,
			weaknessCount: c.weaknesses?.length || 0,
			type: c.competitor_type,
			pricingModel: c.pricing_model,
			url: c.url,
			// Calculate a "threat score" based on features and strengths
			threatScore: (c.key_features?.length || 0) + (c.strengths?.length || 0) * 1.5 - (c.weaknesses?.length || 0) * 0.5
		})).sort((a, b) => b.threatScore - a.threatScore)
	);

	const maxFeatures = $derived(Math.max(...chartData.map((d) => d.featureCount), 1));

	// Type colors
	function getTypeColor(type: string): string {
		switch (type) {
			case 'direct':
				return 'var(--color-error)';
			case 'indirect':
				return 'var(--color-accent)';
			case 'potential':
				return 'var(--viz-cat-2)';
			default:
				return 'var(--color-text-muted)';
		}
	}

	// Chart dimensions
	const width = 500;
	const height = $derived(Math.max(250, chartData.length * 45 + 60));
	const margin = { top: 30, right: 60, bottom: 30, left: 130 };
	const innerWidth = width - margin.left - margin.right;
	const innerHeight = $derived(height - margin.top - margin.bottom);

	// Scales
	const xScale = $derived(scaleLinear().domain([0, maxFeatures]).range([0, innerWidth]));
	const yScale = $derived(
		scaleBand()
			.domain(chartData.map((d) => d.name))
			.range([0, innerHeight])
			.padding(0.3)
	);

	// Hover state
	let hoveredBar = $state<(typeof chartData)[0] | null>(null);
</script>

<ChartTheme title="Competitive Landscape" class={className}>
	<div class="competitor-chart-container">
		<svg {width} {height} viewBox="0 0 {width} {height}" class="competitor-chart-svg">
			<g transform="translate({margin.left}, {margin.top})">
				<!-- Grid lines -->
				{#each Array.from({ length: maxFeatures + 1 }, (_, i) => i) as tick}
					{#if tick > 0}
						<line
							x1={xScale(tick)}
							y1={0}
							x2={xScale(tick)}
							y2={innerHeight}
							class="grid-line"
						/>
					{/if}
				{/each}

				<!-- X-axis label -->
				<text x={innerWidth / 2} y={-12} class="axis-title" text-anchor="middle">
					Key Features
				</text>

				<!-- Bars -->
				{#each chartData as item}
					{@const barWidth = xScale(item.featureCount)}
					{@const barY = yScale(item.name) ?? 0}
					{@const barHeight = yScale.bandwidth()}

					<!-- Background bar -->
					<rect
						x={0}
						y={barY}
						width={innerWidth}
						height={barHeight}
						fill="var(--color-bg-hover)"
						rx={4}
						opacity={0.3}
					/>

					<!-- Data bar with gradient -->
					<rect
						x={0}
						y={barY}
						width={barWidth}
						height={barHeight}
						fill={getTypeColor(item.type)}
						rx={4}
						opacity={hoveredBar === item ? 1 : 0.8}
						class="bar-data"
						onmouseenter={() => (hoveredBar = item)}
						onmouseleave={() => (hoveredBar = null)}
						role="graphics-symbol"
						aria-label="{item.fullName}: {item.featureCount} features"
					/>

					<!-- Type indicator dot -->
					<circle
						cx={-15}
						cy={barY + barHeight / 2}
						r={4}
						fill={getTypeColor(item.type)}
					/>

					<!-- Competitor name -->
					<text
						x={-25}
						y={barY + barHeight / 2}
						class="competitor-label"
						text-anchor="end"
						dominant-baseline="middle"
					>
						{item.name}
					</text>

					<!-- Feature count -->
					<text
						x={barWidth + 8}
						y={barY + barHeight / 2}
						class="count-label"
						dominant-baseline="middle"
					>
						{item.featureCount}
					</text>
				{/each}
			</g>
		</svg>

		<!-- Tooltip -->
		{#if hoveredBar}
			<div class="competitor-tooltip">
				<div class="tooltip-header">
					<span class="tooltip-name">{hoveredBar.fullName}</span>
					<span class="tooltip-type" style="color: {getTypeColor(hoveredBar.type)}">
						{hoveredBar.type}
					</span>
				</div>
				<div class="tooltip-stats">
					<div class="stat-row">
						<span class="stat-label">Features</span>
						<span class="stat-value">{hoveredBar.featureCount}</span>
					</div>
					<div class="stat-row">
						<span class="stat-label">Strengths</span>
						<span class="stat-value success">{hoveredBar.strengthCount}</span>
					</div>
					<div class="stat-row">
						<span class="stat-label">Weaknesses</span>
						<span class="stat-value error">{hoveredBar.weaknessCount}</span>
					</div>
				</div>
				{#if hoveredBar.pricingModel}
					<div class="tooltip-pricing">
						<span class="pricing-label">Pricing:</span>
						<span class="pricing-value">{hoveredBar.pricingModel}</span>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Legend -->
		<div class="competitor-legend">
			<div class="legend-item">
				<span class="legend-dot" style="background: var(--color-error)"></span>
				<span>Direct</span>
			</div>
			<div class="legend-item">
				<span class="legend-dot" style="background: var(--color-accent)"></span>
				<span>Indirect</span>
			</div>
			<div class="legend-item">
				<span class="legend-dot" style="background: var(--viz-cat-2)"></span>
				<span>Potential</span>
			</div>
		</div>
	</div>
</ChartTheme>

<style>
	.competitor-chart-container {
		position: relative;
		width: 100%;
		max-width: 550px;
		margin: 0 auto;
	}

	.competitor-chart-svg {
		width: 100%;
		height: auto;
	}

	.grid-line {
		stroke: var(--color-border);
		stroke-dasharray: 2 4;
		opacity: 0.5;
	}

	.axis-title {
		font-family: var(--font-body);
		font-size: 11px;
		font-weight: 500;
		fill: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.bar-data {
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.bar-data:hover {
		filter: brightness(1.15);
	}

	.competitor-label {
		font-family: var(--font-body);
		font-size: 11px;
		font-weight: 500;
		fill: var(--color-text-secondary);
	}

	.count-label {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 600;
		fill: var(--color-text-primary);
	}

	.competitor-tooltip {
		position: absolute;
		top: 1rem;
		right: 1rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border-emphasis);
		border-radius: 8px;
		padding: 0.875rem 1rem;
		box-shadow: var(--shadow-lg);
		min-width: 200px;
		animation: tooltip-in 0.15s ease-out;
	}

	@keyframes tooltip-in {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.tooltip-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--color-border);
	}

	.tooltip-name {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.tooltip-type {
		font-size: 0.6875rem;
		font-weight: 500;
		text-transform: capitalize;
	}

	.tooltip-stats {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.stat-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.75rem;
	}

	.stat-label {
		color: var(--color-text-muted);
	}

	.stat-value {
		font-weight: 600;
		color: var(--color-text-secondary);
	}

	.stat-value.success {
		color: var(--color-success);
	}

	.stat-value.error {
		color: var(--color-error);
	}

	.tooltip-pricing {
		margin-top: 0.75rem;
		padding-top: 0.5rem;
		border-top: 1px solid var(--color-border);
		font-size: 0.75rem;
	}

	.pricing-label {
		color: var(--color-text-muted);
	}

	.pricing-value {
		color: var(--color-text-secondary);
		margin-left: 0.25rem;
	}

	.competitor-legend {
		display: flex;
		justify-content: center;
		gap: 1.5rem;
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}

	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.legend-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
</style>
