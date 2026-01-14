<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		variant?: 'default' | 'paper' | 'sand';
		hover?: boolean;
		padding?: 'none' | 'sm' | 'md' | 'lg';
		class?: string;
		children: Snippet;
	}

	let {
		variant = 'default',
		hover = false,
		padding = 'md',
		class: className = '',
		children
	}: Props = $props();

	const baseClasses = 'rounded transition-all duration-200';

	const variantClasses = {
		default: 'bg-bg-paper border border-border',
		paper: 'bg-bg-paper border border-border',
		sand: 'bg-bg-sand border border-border'
	};

	const hoverClasses = $derived(hover ? 'hover:border-border-emphasis' : '');

	const paddingClasses = {
		none: '',
		sm: 'p-4',
		md: 'p-6',
		lg: 'p-8'
	};
</script>

<div class="{baseClasses} {variantClasses[variant]} {hoverClasses} {paddingClasses[padding]} {className}">
	{@render children()}
</div>
