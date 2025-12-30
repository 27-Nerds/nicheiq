<script lang="ts">
	import type { Snippet } from 'svelte';

	type BadgeVariant = 'default' | 'success' | 'error' | 'warning' | 'muted' | 'info';
	type BadgeSize = 'sm' | 'md';

	interface Props {
		variant?: BadgeVariant;
		size?: BadgeSize;
		class?: string;
		children: Snippet;
	}

	let { variant = 'default', size = 'md', class: className = '', children }: Props = $props();

	const variantClasses: Record<BadgeVariant, string> = {
		default: 'badge',
		success: 'badge badge-success',
		error: 'badge badge-error',
		warning: 'badge badge-warning',
		muted: 'badge badge-muted',
		info: 'badge badge-info'
	};

	const sizeClass = size === 'sm' ? 'badge-sm' : '';
</script>

<span class="{variantClasses[variant]} {sizeClass} {className}">
	{@render children()}
</span>
