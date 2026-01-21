<script lang="ts">
	import type { Component } from 'svelte';

	interface Props {
		icon?: Component;
		value: string | number;
		label: string;
		iconClass?: string;
		valueClass?: string;
	}

	let { icon, value, label, iconClass = 'w-4 h-4', valueClass = '' }: Props = $props();
</script>

<div class="meta-item">
	{#if icon}
		<svelte:component this={icon} class="meta-icon {iconClass}" />
	{/if}
	<span class="meta-value {valueClass}">{value}</span>
	{#if label}
		<span class="meta-label">{label}</span>
	{/if}
</div>

<style>
	.meta-item {
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	:global(.meta-icon) {
		flex-shrink: 0;
	}

	.meta-value {
		font-family: var(--font-display);
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.meta-label {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}
</style>
