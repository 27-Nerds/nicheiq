<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title?: string;
		subtitle?: string;
		variant?: 'default' | 'surface' | 'highlight' | 'glass';
		interactive?: boolean;
		glow?: boolean;
		glowColor?: 'accent' | 'success';
		class?: string;
		children: Snippet;
		headerSlot?: Snippet;
	}

	let {
		title,
		subtitle,
		variant = 'default',
		interactive = false,
		glow = false,
		glowColor = 'accent',
		class: className = '',
		children,
		headerSlot
	}: Props = $props();

	const variantClasses: Record<string, string> = {
		default: 'card',
		surface: 'card-surface',
		highlight: 'highlight-box',
		glass: 'card-glass'
	};

	const interactiveClass = $derived(interactive ? 'card-interactive' : '');
	const glowClass = $derived(glow
		? glowColor === 'success'
			? 'card-interactive-glow card-interactive-glow-success'
			: 'card-interactive-glow'
		: '');
</script>

<div class="{variantClasses[variant]} {interactiveClass} {glowClass} {className}">
	{#if title || headerSlot}
		<div class="mb-4 pb-4 border-b border-border">
			{#if headerSlot}
				{@render headerSlot()}
			{:else}
				<h3 class="text-lg font-semibold text-text-primary">{title}</h3>
				{#if subtitle}
					<p class="text-sm text-text-muted mt-1">{subtitle}</p>
				{/if}
			{/if}
		</div>
	{/if}
	{@render children()}
</div>
