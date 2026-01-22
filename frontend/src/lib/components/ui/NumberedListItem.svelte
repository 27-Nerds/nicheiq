<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		number: number | string;
		variant?: 'default' | 'success' | 'warning' | 'error' | 'accent' | 'muted';
		size?: 'sm' | 'md';
		children: Snippet;
		class?: string;
	}

	let {
		number,
		variant = 'accent',
		size = 'md',
		children,
		class: className = ''
	}: Props = $props();

	// Format number with leading zero if numeric
	const displayNumber = $derived(
		typeof number === 'number' && number < 10 ? String(number).padStart(2, '0') : String(number)
	);
</script>

<div class="numbered-item numbered-item--{variant} numbered-item--{size} {className}">
	<span class="item-number">{displayNumber}</span>
	<span class="item-content">
		{@render children()}
	</span>
</div>

<style>
	.numbered-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}

	.item-number {
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		font-family: var(--font-mono);
		font-weight: 600;
		border-radius: 50%;
	}

	.item-content {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		line-height: 1.45;
	}

	/* Sizes */
	.numbered-item--sm .item-number {
		width: 1.125rem;
		height: 1.125rem;
		font-size: 0.5625rem;
	}

	.numbered-item--sm .item-content {
		font-size: 0.75rem;
		margin-top: 0.0625rem;
	}

	.numbered-item--md .item-number {
		width: 1.25rem;
		height: 1.25rem;
		font-size: 0.625rem;
	}

	.numbered-item--md .item-content {
		margin-top: 0.125rem;
	}

	/* Variants */
	.numbered-item--accent .item-number {
		background: rgba(229, 90, 40, 0.15);
		color: var(--color-accent);
	}

	.numbered-item--success .item-number {
		background: rgba(34, 197, 94, 0.15);
		color: var(--color-success);
	}

	.numbered-item--warning .item-number {
		background: rgba(234, 179, 8, 0.15);
		color: var(--color-warning);
	}

	.numbered-item--error .item-number {
		background: rgba(239, 68, 68, 0.15);
		color: var(--color-error);
	}

	.numbered-item--muted .item-number {
		background: var(--color-bg-surface);
		color: var(--color-text-muted);
	}

	.numbered-item--default .item-number {
		background: var(--color-bg-elevated);
		color: var(--color-text-primary);
	}
</style>
