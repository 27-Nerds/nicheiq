<script lang="ts">
	interface Props {
		text: string;
		variant?: 'default' | 'accent' | 'success' | 'warning' | 'error' | 'muted';
		size?: 'xs' | 'sm';
		class?: string;
	}

	let { text, variant = 'default', size = 'xs', class: className = '' }: Props = $props();
</script>

<span class="section-label section-label--{variant} section-label--{size} {className}">
	{text}
</span>

<style>
	.section-label {
		font-family: var(--font-mono);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* Sizes */
	.section-label--xs {
		font-size: 0.5625rem;
	}

	.section-label--sm {
		font-size: 0.6875rem;
	}

	/* Variants */
	.section-label--default {
		color: var(--color-text-muted);
	}

	.section-label--accent {
		color: var(--color-accent);
	}

	.section-label--success {
		color: var(--color-success);
	}

	.section-label--warning {
		color: var(--color-warning);
	}

	.section-label--error {
		color: var(--color-error);
	}

	.section-label--muted {
		color: var(--color-text-muted);
		opacity: 0.7;
	}
</style>
