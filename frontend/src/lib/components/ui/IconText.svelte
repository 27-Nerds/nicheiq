<script lang="ts">
	import type { ComponentType, Snippet } from 'svelte';

	interface Props {
		icon: ComponentType;
		iconClass?: string;
		gap?: string;
		children: Snippet;
	}

	let { icon: Icon, iconClass = 'w-4 h-4', gap = 'gap-2', children }: Props = $props();
</script>

<div class="icon-text {gap}">
	<Icon class={iconClass} />
	{@render children()}
</div>

<style>
	.icon-text {
		display: flex;
		align-items: center;
	}

	.icon-text.gap-1 { gap: 0.25rem; }
	.icon-text.gap-2 { gap: 0.5rem; }
	.icon-text.gap-3 { gap: 0.75rem; }
	.icon-text.gap-4 { gap: 1rem; }
</style>
