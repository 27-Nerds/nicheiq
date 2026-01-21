<script lang="ts">
	import { ChevronDown } from 'lucide-svelte';
	import Badge from './Badge.svelte';
	import type { Component, Snippet } from 'svelte';

	interface Props {
		title: string;
		icon?: Component;
		count?: number | null;
		defaultOpen?: boolean;
		variant?: 'default' | 'success' | 'warning' | 'error';
		children: Snippet;
	}

	let { title, icon, count = null, defaultOpen = false, variant = 'default', children }: Props = $props();

	let expanded = $state<boolean>(false);

	$effect(() => {
		expanded = defaultOpen;
	});

	const variantClasses: Record<string, string> = {
		default: '',
		success: 'expandable-section-success',
		warning: 'expandable-section-warning',
		error: 'expandable-section-error'
	};

	const iconVariantClasses: Record<string, string> = {
		default: '',
		success: 'icon-success',
		warning: 'icon-warning',
		error: 'icon-error'
	};

	const badgeVariants: Record<string, 'muted' | 'success' | 'warning' | 'error'> = {
		default: 'muted',
		success: 'success',
		warning: 'warning',
		error: 'error'
	};
</script>

<div class="expandable-section {variantClasses[variant]}">
	<button class="expandable-header" onclick={() => expanded = !expanded}>
		<div class="expandable-title">
			{#if icon}
				<svelte:component this={icon} class="expandable-icon {iconVariantClasses[variant]}" />
			{/if}
			<span>{title}</span>
			{#if count != null}
				<Badge variant={badgeVariants[variant]} size="sm">{count}</Badge>
			{/if}
		</div>
		<ChevronDown class="chevron-icon {expanded ? 'expanded' : ''}" />
	</button>
	{#if expanded}
		<div class="expandable-content">
			{@render children()}
		</div>
	{/if}
</div>

<style>
	.expandable-section {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		overflow: hidden;
	}

	.expandable-section-success {
		border-color: rgba(34, 197, 94, 0.3);
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.05) 0%, transparent 40%);
	}

	.expandable-section-warning {
		border-color: rgba(245, 158, 11, 0.3);
		background: linear-gradient(135deg, rgba(245, 158, 11, 0.05) 0%, transparent 40%);
	}

	.expandable-section-error {
		border-color: rgba(239, 68, 68, 0.3);
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, transparent 40%);
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 1rem 1.25rem;
		background: transparent;
		border: none;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.expandable-header:hover {
		background: var(--color-bg-surface);
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.expandable-title :global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-accent);
	}

	.expandable-title :global(.expandable-icon.icon-success) {
		color: var(--color-success);
	}

	.expandable-title :global(.expandable-icon.icon-warning) {
		color: var(--color-warning);
	}

	.expandable-title :global(.expandable-icon.icon-error) {
		color: var(--color-error);
	}

	:global(.chevron-icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--color-text-muted);
		transition: transform 0.2s ease;
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 1.25rem 1.25rem;
	}
</style>
