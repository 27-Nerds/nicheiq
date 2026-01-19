<script lang="ts">
	interface Props {
		value: number;
		size?: number;
		strokeWidth?: number;
		color?: 'accent' | 'success' | 'error' | 'warning' | 'auto' | string;
		showValue?: boolean;
		showLabel?: boolean;
		label?: string;
		animate?: boolean;
		showTooltip?: boolean;
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
		showTooltip = true,
		class: className = ''
	}: Props = $props();

	const radius = $derived((size - strokeWidth) / 2);
	const circumference = $derived(2 * Math.PI * radius);
	const progress = $derived(Math.min(Math.max(value, 0), 1));
	const offset = $derived(circumference - progress * circumference);

	// Check if color is a custom hex/rgb value
	const isCustomColor = $derived(color.startsWith('#') || color.startsWith('rgb'));

	// Auto color based on value thresholds
	const computedColor = $derived.by(() => {
		if (isCustomColor) return color;
		if (color !== 'auto') return color;
		if (value >= 0.7) return 'success';
		if (value >= 0.4) return 'warning';
		return 'error';
	});

	const colorVar = $derived.by(() => {
		if (isCustomColor) return computedColor;
		if (computedColor === 'accent') return 'var(--color-accent)';
		if (computedColor === 'success') return 'var(--color-success)';
		if (computedColor === 'error') return 'var(--color-error)';
		if (computedColor === 'warning') return 'var(--color-warning)';
		return 'var(--color-accent)';
	});

	// Score interpretation for tooltip
	const scoreInterpretation = $derived.by(() => {
		const percentage = Math.round(value * 100);
		if (percentage >= 80) return 'Excellent';
		if (percentage >= 70) return 'Strong';
		if (percentage >= 50) return 'Moderate';
		if (percentage >= 40) return 'Needs Work';
		return 'Critical';
	});

	let visible = $state(false);
	let isHovered = $state(false);
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

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
	bind:this={ref}
	class="progress-ring {className}"
	class:hovered={isHovered}
	role={showTooltip ? "button" : "img"}
	aria-label="{label || 'Score'}: {Math.round(value * 100)}%"
	onmouseenter={() => (isHovered = true)}
	onmouseleave={() => (isHovered = false)}
	onfocus={() => (isHovered = true)}
	onblur={() => (isHovered = false)}
	tabindex={showTooltip ? 0 : -1}
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
			stroke={colorVar}
			stroke-width={strokeWidth}
			stroke-linecap="round"
			stroke-dasharray={circumference}
			stroke-dashoffset={visible ? offset : circumference}
			class="progress-ring-progress"
			class:animate={animate && visible}
			class:hovered={isHovered}
		/>
	</svg>
	{#if showValue || showLabel}
		<div class="progress-ring-content">
			{#if showValue}
				<span class="progress-ring-value" style:color={colorVar}>
					{Math.round(value * 100)}
				</span>
			{/if}
			{#if showLabel && label}
				<span class="progress-ring-label">{label}</span>
			{/if}
		</div>
	{/if}

	<!-- Tooltip -->
	{#if showTooltip && isHovered}
		<div class="progress-ring-tooltip" style:--tooltip-color={colorVar}>
			<span class="tooltip-value">{Math.round(value * 100)}%</span>
			<span class="tooltip-interpretation">{scoreInterpretation}</span>
			{#if label}
				<span class="tooltip-label">{label}</span>
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
		cursor: help;
		transition: transform 0.2s ease;
	}

	.progress-ring:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 4px;
		border-radius: 50%;
	}

	.progress-ring.hovered {
		transform: scale(1.06);
	}

	.progress-ring-svg {
		transform: rotate(-90deg);
	}

	.progress-ring-bg {
		opacity: 0.3;
	}

	.progress-ring-progress {
		filter: drop-shadow(0 0 4px currentColor);
		transition: stroke-dashoffset 0s, filter 0.2s ease;
	}

	.progress-ring-progress.animate {
		transition: stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1), filter 0.2s ease;
	}

	.progress-ring-progress.hovered {
		filter: drop-shadow(0 0 10px currentColor);
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
		transition: transform 0.2s ease;
	}

	.progress-ring.hovered .progress-ring-value {
		transform: scale(1.05);
	}

	.progress-ring-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}

	/* Tooltip */
	.progress-ring-tooltip {
		position: absolute;
		bottom: calc(100% + 8px);
		left: 50%;
		transform: translateX(-50%);
		padding: 0.5rem 0.75rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		box-shadow: var(--shadow-md);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.125rem;
		white-space: nowrap;
		z-index: 50;
		animation: tooltipFadeIn 0.15s ease;
	}

	.progress-ring-tooltip::after {
		content: '';
		position: absolute;
		top: 100%;
		left: 50%;
		transform: translateX(-50%);
		border: 6px solid transparent;
		border-top-color: var(--color-bg-elevated);
	}

	@keyframes tooltipFadeIn {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	.tooltip-value {
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 700;
		color: var(--tooltip-color, var(--color-text-primary));
	}

	.tooltip-interpretation {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--tooltip-color, var(--color-text-secondary));
	}

	.tooltip-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin-top: 0.125rem;
	}
</style>
