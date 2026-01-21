<script lang="ts">
	import { CheckCircle } from 'lucide-svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		color?: 'success' | 'accent' | 'muted' | 'error' | 'warning';
		children: Snippet;
	}

	let { color = 'success', children }: Props = $props();

	const colorClasses: Record<string, string> = {
		success: 'icon-success',
		accent: 'icon-accent',
		muted: 'icon-muted',
		error: 'icon-error',
		warning: 'icon-warning'
	};
</script>

<li class="check-list-item">
	<CheckCircle class="check-icon {colorClasses[color]}" />
	<span class="check-text">{@render children()}</span>
</li>

<style>
	.check-list-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		line-height: 1.6;
	}

	.check-list-item :global(.check-icon) {
		width: 1rem;
		height: 1rem;
		flex-shrink: 0;
		margin-top: 0.125rem;
	}

	.check-list-item :global(.check-icon.icon-success) {
		color: var(--color-success);
	}

	.check-list-item :global(.check-icon.icon-accent) {
		color: var(--color-accent);
	}

	.check-list-item :global(.check-icon.icon-muted) {
		color: var(--color-text-muted);
	}

	.check-list-item :global(.check-icon.icon-error) {
		color: var(--color-error);
	}

	.check-list-item :global(.check-icon.icon-warning) {
		color: var(--color-warning);
	}

	.check-text {
		flex: 1;
	}
</style>
