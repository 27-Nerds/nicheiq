<script lang="ts">
	import { HelpCircle } from 'lucide-svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		content: string;
		position?: 'top' | 'bottom' | 'left' | 'right';
		children?: Snippet;
		class?: string;
	}

	let { content, position = 'top', children, class: className = '' }: Props = $props();

	let isVisible = $state(false);
	let triggerRef: HTMLElement | null = $state(null);
</script>

<span
	class="tooltip-wrapper {className}"
	bind:this={triggerRef}
	onmouseenter={() => (isVisible = true)}
	onmouseleave={() => (isVisible = false)}
	onfocus={() => (isVisible = true)}
	onblur={() => (isVisible = false)}
	role="button"
	tabindex="0"
>
	{#if children}
		{@render children()}
	{:else}
		<span class="tooltip-trigger" aria-label="More information">
			<HelpCircle class="w-3.5 h-3.5" />
		</span>
	{/if}

	{#if isVisible}
		<div class="tooltip tooltip-{position}" role="tooltip">
			<div class="tooltip-content">
				{content}
			</div>
			<div class="tooltip-arrow"></div>
		</div>
	{/if}
</span>

<style>
	.tooltip-wrapper {
		position: relative;
		display: inline-flex;
		align-items: center;
	}

	.tooltip-trigger {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		color: var(--color-text-muted);
		border: 1px solid var(--color-border);
		border-radius: 50%;
		cursor: help;
		transition: all 0.2s ease;
	}

	.tooltip-trigger:hover {
		color: var(--color-accent);
		border-color: var(--color-accent);
		background: rgba(229, 90, 40, 0.1);
	}

	.tooltip {
		position: absolute;
		z-index: 100;
		pointer-events: none;
		animation: tooltip-fade-in 0.2s ease-out;
	}

	.tooltip-content {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border-emphasis);
		border-radius: 8px;
		padding: 0.75rem 1rem;
		box-shadow: var(--shadow-lg);
		max-width: 280px;
		font-family: var(--font-body);
		font-size: 0.8125rem;
		line-height: 1.5;
		color: var(--color-text-secondary);
	}

	.tooltip-arrow {
		position: absolute;
		width: 8px;
		height: 8px;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border-emphasis);
		transform: rotate(45deg);
	}

	/* Position: Top */
	.tooltip-top {
		bottom: calc(100% + 8px);
		left: 50%;
		transform: translateX(-50%);
	}

	.tooltip-top .tooltip-arrow {
		bottom: -5px;
		left: 50%;
		margin-left: -4px;
		border-top: none;
		border-left: none;
	}

	/* Position: Bottom */
	.tooltip-bottom {
		top: calc(100% + 8px);
		left: 50%;
		transform: translateX(-50%);
	}

	.tooltip-bottom .tooltip-arrow {
		top: -5px;
		left: 50%;
		margin-left: -4px;
		border-bottom: none;
		border-right: none;
	}

	/* Position: Left */
	.tooltip-left {
		right: calc(100% + 8px);
		top: 50%;
		transform: translateY(-50%);
	}

	.tooltip-left .tooltip-arrow {
		right: -5px;
		top: 50%;
		margin-top: -4px;
		border-top: none;
		border-right: none;
	}

	/* Position: Right */
	.tooltip-right {
		left: calc(100% + 8px);
		top: 50%;
		transform: translateY(-50%);
	}

	.tooltip-right .tooltip-arrow {
		left: -5px;
		top: 50%;
		margin-top: -4px;
		border-bottom: none;
		border-left: none;
	}

	@keyframes tooltip-fade-in {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	.tooltip-bottom {
		animation-name: tooltip-fade-in-bottom;
	}

	@keyframes tooltip-fade-in-bottom {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(-4px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	.tooltip-left,
	.tooltip-right {
		animation-name: tooltip-fade-in-horizontal;
	}

	@keyframes tooltip-fade-in-horizontal {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>
