<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		variant?: 'default' | 'success' | 'error' | 'warning';
		size?: 'sm' | 'md';
		icon?: Snippet;
		class?: string;
		children: Snippet;
	}

	let { variant = 'default', size = 'md', icon, class: className = '', children }: Props = $props();

	const variantClasses = {
		default: 'text-accent-copper border-accent-copper',
		success: 'text-success border-success',
		error: 'text-error border-error',
		warning: 'text-warning border-warning'
	};

	const sizeClasses = {
		sm: 'px-2 py-1 text-[10px]',
		md: 'px-3 py-1.5 text-xs'
	};
</script>

<span
	class="inline-flex items-center gap-1.5 font-body font-semibold uppercase tracking-wider bg-transparent border rounded {variantClasses[variant]} {sizeClasses[size]} {className}"
>
	{#if icon}
		<span class="w-3 h-3">{@render icon()}</span>
	{/if}
	{@render children()}
</span>
