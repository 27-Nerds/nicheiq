<script lang="ts">
	import type { ComponentType } from 'svelte';

	interface Props {
		value: string | number;
		label: string;
		icon?: ComponentType;
		color?: 'neutral' | 'success' | 'warning' | 'error' | 'accent';
		progress?: number; // 0-1 for mini progress bar
		suffix?: string;
		class?: string;
	}

	let {
		value,
		label,
		icon: Icon,
		color = 'neutral',
		progress,
		suffix = '',
		class: className = ''
	}: Props = $props();

	// Format value if numeric
	const formattedValue = $derived.by(() => {
		if (typeof value === 'number') {
			if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
			if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
			return value.toString();
		}
		return value;
	});
</script>

<div class="hero-metric hero-metric--{color} {className}">
	<span class="hero-metric__value">
		{formattedValue}{suffix}
	</span>
	<span class="hero-metric__label">{label}</span>
	<div class="hero-metric__footer">
		{#if Icon}
			<div class="hero-metric__icon">
				<Icon size={14} />
			</div>
		{/if}
		{#if progress !== undefined}
			<div class="hero-metric__bar">
				<div
					class="hero-metric__bar-fill"
					style="--fill-width: {Math.min(Math.max(progress, 0), 1) * 100}%"
				></div>
			</div>
		{/if}
	</div>
</div>

<style>
	.hero-metric {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.125rem;
		min-width: 60px;
	}

	.hero-metric__value {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 700;
		line-height: 1.1;
		color: var(--color-text-primary);
		font-variant-numeric: tabular-nums;
	}

	.hero-metric__label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-text-muted);
	}

	/* Footer container - fixed height to ensure consistent metric heights */
	.hero-metric__footer {
		min-height: 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-start;
		margin-top: 0.25rem;
	}

	.hero-metric__icon {
		opacity: 0.5;
		color: var(--color-text-muted);
		transition: opacity 0.15s ease;
	}

	.hero-metric:hover .hero-metric__icon {
		opacity: 0.7;
	}

	/* Mini progress bar */
	.hero-metric__bar {
		width: 100%;
		max-width: 48px;
		height: 3px;
		background: var(--color-border);
		border-radius: 2px;
		margin-top: 0.25rem;
		overflow: hidden;
	}

	.hero-metric__bar-fill {
		height: 100%;
		width: var(--fill-width, 0%);
		border-radius: 2px;
		transition: width 0.5s ease-out 0.3s;
	}

	/* Color variants */
	.hero-metric--neutral .hero-metric__value {
		color: var(--color-text-primary);
	}

	.hero-metric--neutral .hero-metric__bar-fill {
		background: var(--color-text-muted);
	}

	.hero-metric--success .hero-metric__value {
		color: var(--color-success);
	}

	.hero-metric--success .hero-metric__bar-fill {
		background: var(--color-success);
	}

	.hero-metric--success .hero-metric__icon {
		color: var(--color-success);
	}

	.hero-metric--warning .hero-metric__value {
		color: var(--color-warning);
	}

	.hero-metric--warning .hero-metric__bar-fill {
		background: var(--color-warning);
	}

	.hero-metric--warning .hero-metric__icon {
		color: var(--color-warning);
	}

	.hero-metric--error .hero-metric__value {
		color: var(--color-error);
	}

	.hero-metric--error .hero-metric__bar-fill {
		background: var(--color-error);
	}

	.hero-metric--error .hero-metric__icon {
		color: var(--color-error);
	}

	.hero-metric--accent .hero-metric__value {
		color: var(--color-accent);
	}

	.hero-metric--accent .hero-metric__bar-fill {
		background: var(--color-accent);
	}

	.hero-metric--accent .hero-metric__icon {
		color: var(--color-accent);
	}

	/* Responsive */
	@media (max-width: 768px) {
		.hero-metric__value {
			font-size: 1.25rem;
		}

		.hero-metric__label {
			font-size: 0.5rem;
		}
	}
</style>
