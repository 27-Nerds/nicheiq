<script lang="ts">
	import type { Component, Snippet } from 'svelte';

	interface Props {
		icon?: Component;
		iconVariant?: 'default' | 'success' | 'warning' | 'error' | 'accent' | 'muted';
		iconSize?: 'sm' | 'md';
		children: Snippet;
		class?: string;
	}

	let {
		icon,
		iconVariant = 'accent',
		iconSize = 'sm',
		children,
		class: className = ''
	}: Props = $props();
</script>

<div class="icon-list-item icon-list-item--icon-{iconSize} {className}">
	{#if icon}
		{@const Icon = icon}
		<span class="item-icon item-icon--{iconVariant}">
			<Icon class="icon" />
		</span>
	{/if}
	<span class="item-content">
		{@render children()}
	</span>
</div>

<style>
	.icon-list-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}

	.item-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.item-icon :global(.icon) {
		flex-shrink: 0;
	}

	/* Icon sizes */
	.icon-list-item--icon-sm .item-icon :global(.icon) {
		width: 0.875rem;
		height: 0.875rem;
	}

	.icon-list-item--icon-sm .item-content {
		margin-top: 0.0625rem;
	}

	.icon-list-item--icon-md .item-icon :global(.icon) {
		width: 1rem;
		height: 1rem;
	}

	.icon-list-item--icon-md .item-content {
		margin-top: 0.125rem;
	}

	/* Icon variants */
	.item-icon--default :global(.icon) {
		color: var(--color-text-muted);
	}

	.item-icon--accent :global(.icon) {
		color: var(--color-accent);
	}

	.item-icon--success :global(.icon) {
		color: var(--color-success);
	}

	.item-icon--warning :global(.icon) {
		color: var(--color-warning);
	}

	.item-icon--error :global(.icon) {
		color: var(--color-error);
	}

	.item-icon--muted :global(.icon) {
		color: var(--color-text-muted);
	}

	.item-content {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}
</style>
