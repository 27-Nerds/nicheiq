<script lang="ts">
	import type { ComponentType } from 'svelte';

	interface Props {
		text: string;
		variant?: 'default' | 'accent' | 'success' | 'warning' | 'error' | 'muted';
		size?: 'xs' | 'sm';
		icon?: ComponentType;
		class?: string;
	}

	let { text, variant = 'default', size = 'xs', icon, class: className = '' }: Props = $props();
</script>

<span class="section-label section-label--{variant} section-label--{size} {className}">
	{#if icon}
		{@const Icon = icon}
		<Icon class="section-label-icon" />
	{/if}
	{text}
</span>

<style>
	.section-label {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		font-family: var(--font-mono);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.section-label :global(.section-label-icon) {
		width: 0.875rem;
		height: 0.875rem;
	}

	/* Sizes */
	.section-label--xs {
		font-size: 0.5625rem;
	}

	.section-label--sm {
		font-size: 0.6875rem;
	}

	/* Variants */
	.section-label--default {
		color: var(--color-text-muted);
	}

	.section-label--accent {
		color: var(--color-accent);
	}

	.section-label--success {
		color: var(--color-success);
	}

	.section-label--warning {
		color: var(--color-warning);
	}

	.section-label--error {
		color: var(--color-error);
	}

	.section-label--muted {
		color: var(--color-text-muted);
		opacity: 0.7;
	}
</style>
