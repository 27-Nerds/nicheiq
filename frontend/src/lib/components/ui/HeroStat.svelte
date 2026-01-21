<script lang="ts">
	interface Props {
		value: string | number;
		label: string;
		valueColor?: string;
		class?: string;
	}

	let { value, label, valueColor, class: className = '' }: Props = $props();
</script>

<div class="hero-stat {className}">
	<span class="hero-stat-value" style:color={valueColor}>{value}</span>
	<span class="hero-stat-label">{label}</span>
</div>

<style>
	.hero-stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.125rem;
	}

	.hero-stat-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-text-primary);
	}

	.hero-stat-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}
</style>
