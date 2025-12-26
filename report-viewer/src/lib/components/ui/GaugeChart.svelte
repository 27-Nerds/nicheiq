<script lang="ts">
	interface Props {
		value: number;
		width?: number;
		height?: number;
		showZones?: boolean;
		showValue?: boolean;
		label?: string;
		animate?: boolean;
		class?: string;
	}

	let {
		value,
		width = 120,
		height = 70,
		showZones = true,
		showValue = true,
		label = '',
		animate = true,
		class: className = ''
	}: Props = $props();

	// Gauge arc calculations
	const centerX = $derived(width / 2);
	const centerY = $derived(height - 10);
	const radius = $derived(Math.min(width / 2 - 10, height - 20));
	const strokeWidth = 8;
	const innerRadius = $derived(radius - strokeWidth / 2);

	// Arc path helper
	function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
		const start = polarToCartesian(cx, cy, r, endAngle);
		const end = polarToCartesian(cx, cy, r, startAngle);
		const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
		return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
	}

	function polarToCartesian(cx: number, cy: number, r: number, angle: number) {
		const radians = ((angle - 180) * Math.PI) / 180;
		return {
			x: cx + r * Math.cos(radians),
			y: cy + r * Math.sin(radians)
		};
	}

	// Needle angle (0-180 degrees)
	const progress = $derived(Math.min(Math.max(value, 0), 1));
	const needleAngle = $derived(progress * 180);

	// Color based on value
	const valueColor = $derived(() => {
		if (value >= 0.7) return 'var(--color-success)';
		if (value >= 0.4) return 'var(--color-warning)';
		return 'var(--color-error)';
	});

	let visible = $state(false);
	let ref: HTMLDivElement;

	$effect(() => {
		if (ref && animate) {
			const observer = new IntersectionObserver(
				([entry]) => {
					if (entry.isIntersecting) {
						visible = true;
						observer.disconnect();
					}
				},
				{ threshold: 0.3 }
			);
			observer.observe(ref);
			return () => observer.disconnect();
		} else if (!animate) {
			visible = true;
		}
	});
</script>

<div
	bind:this={ref}
	class="gauge-chart {className}"
>
	<svg {width} {height} class="gauge-svg" overflow="visible">
		<!-- Background arc -->
		<path
			d={describeArc(centerX, centerY, innerRadius, 0, 180)}
			fill="none"
			stroke="var(--color-bg-surface)"
			stroke-width={strokeWidth}
			stroke-linecap="round"
			class="gauge-bg"
		/>

		{#if showZones}
			<!-- Red zone (0-40%) -->
			<path
				d={describeArc(centerX, centerY, innerRadius, 0, 72)}
				fill="none"
				stroke="var(--color-error)"
				stroke-width={strokeWidth}
				stroke-linecap="round"
				opacity="0.3"
			/>
			<!-- Amber zone (40-70%) -->
			<path
				d={describeArc(centerX, centerY, innerRadius, 72, 126)}
				fill="none"
				stroke="var(--color-warning)"
				stroke-width={strokeWidth}
				opacity="0.3"
			/>
			<!-- Green zone (70-100%) -->
			<path
				d={describeArc(centerX, centerY, innerRadius, 126, 180)}
				fill="none"
				stroke="var(--color-success)"
				stroke-width={strokeWidth}
				stroke-linecap="round"
				opacity="0.3"
			/>
		{/if}

		<!-- Progress arc -->
		<path
			d={describeArc(centerX, centerY, innerRadius, 0, visible ? needleAngle : 0)}
			fill="none"
			stroke={valueColor()}
			stroke-width={strokeWidth}
			stroke-linecap="round"
			class="gauge-progress"
			class:animate={animate && visible}
		/>

		<!-- Center dot -->
		<circle cx={centerX} cy={centerY} r="4" fill={valueColor()} class="gauge-center" />

		<!-- Needle -->
		<line
			x1={centerX}
			y1={centerY}
			x2={polarToCartesian(centerX, centerY, innerRadius - 12, visible ? needleAngle : 0).x}
			y2={polarToCartesian(centerX, centerY, innerRadius - 12, visible ? needleAngle : 0).y}
			stroke={valueColor()}
			stroke-width="2"
			stroke-linecap="round"
			class="gauge-needle"
			class:animate={animate && visible}
		/>
	</svg>

	{#if showValue || label}
		<div class="gauge-content">
			{#if showValue}
				<span class="gauge-value" style:color={valueColor()}>
					{Math.round(value * 100)}%
				</span>
			{/if}
			{#if label}
				<span class="gauge-label">{label}</span>
			{/if}
		</div>
	{/if}
</div>

<style>
	.gauge-chart {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 4px;
		overflow: visible;
	}

	.gauge-bg {
		opacity: 0.2;
	}

	.gauge-progress {
		filter: drop-shadow(0 0 4px currentColor);
		transition: d 0s;
	}

	.gauge-progress.animate {
		transition: d 1s cubic-bezier(0.4, 0, 0.2, 1);
	}

	.gauge-needle {
		filter: drop-shadow(0 0 2px currentColor);
		transform-origin: center bottom;
		transition: x2 0s, y2 0s;
	}

	.gauge-needle.animate {
		transition: x2 1s cubic-bezier(0.4, 0, 0.2, 1), y2 1s cubic-bezier(0.4, 0, 0.2, 1);
	}

	.gauge-center {
		filter: drop-shadow(0 0 4px currentColor);
	}

	.gauge-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.125rem;
		margin-top: 0.25rem;
	}

	.gauge-value {
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: 700;
		line-height: 1;
	}

	.gauge-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}
</style>
