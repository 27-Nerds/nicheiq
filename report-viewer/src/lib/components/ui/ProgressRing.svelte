<script lang="ts">
	interface Props {
		value: number;
		size?: number;
		strokeWidth?: number;
		color?: 'accent' | 'success' | 'error' | 'warning' | 'auto';
		showValue?: boolean;
		showLabel?: boolean;
		label?: string;
		animate?: boolean;
		class?: string;
	}

	let {
		value,
		size = 80,
		strokeWidth = 6,
		color = 'auto',
		showValue = true,
		showLabel = false,
		label = '',
		animate = true,
		class: className = ''
	}: Props = $props();

	const radius = $derived((size - strokeWidth) / 2);
	const circumference = $derived(2 * Math.PI * radius);
	const progress = $derived(Math.min(Math.max(value, 0), 1));
	const offset = $derived(circumference - progress * circumference);

	// Auto color based on value thresholds
	const computedColor = $derived(() => {
		if (color !== 'auto') return color;
		if (value >= 0.7) return 'success';
		if (value >= 0.4) return 'warning';
		return 'error';
	});

	const colorVar = $derived(() => {
		const c = computedColor();
		if (c === 'accent') return 'var(--color-accent)';
		if (c === 'success') return 'var(--color-success)';
		if (c === 'error') return 'var(--color-error)';
		if (c === 'warning') return 'var(--color-warning)';
		return 'var(--color-accent)';
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
	class="progress-ring {className}"
>
	<svg width={size} height={size} class="progress-ring-svg" overflow="visible">
		<!-- Background circle -->
		<circle
			cx={size / 2}
			cy={size / 2}
			r={radius}
			fill="none"
			stroke="var(--color-bg-surface)"
			stroke-width={strokeWidth}
			class="progress-ring-bg"
		/>
		<!-- Progress circle -->
		<circle
			cx={size / 2}
			cy={size / 2}
			r={radius}
			fill="none"
			stroke={colorVar()}
			stroke-width={strokeWidth}
			stroke-linecap="round"
			stroke-dasharray={circumference}
			stroke-dashoffset={visible ? offset : circumference}
			class="progress-ring-progress"
			class:animate={animate && visible}
		/>
	</svg>
	{#if showValue || showLabel}
		<div class="progress-ring-content">
			{#if showValue}
				<span class="progress-ring-value" style:color={colorVar()}>
					{Math.round(value * 100)}
				</span>
			{/if}
			{#if showLabel && label}
				<span class="progress-ring-label">{label}</span>
			{/if}
		</div>
	{/if}
</div>

<style>
	.progress-ring {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 4px;
		overflow: visible;
	}

	.progress-ring-svg {
		transform: rotate(-90deg);
	}

	.progress-ring-bg {
		opacity: 0.3;
	}

	.progress-ring-progress {
		filter: drop-shadow(0 0 4px currentColor);
		transition: stroke-dashoffset 0s;
	}

	.progress-ring-progress.animate {
		transition: stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1);
	}

	.progress-ring-content {
		position: absolute;
		inset: 4px; /* Match container padding to center over ring */
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.125rem;
	}

	.progress-ring-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		line-height: 1;
	}

	.progress-ring-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}
</style>
