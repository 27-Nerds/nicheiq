<script lang="ts">
	interface Props {
		text: string;
		variant?: 'default' | 'card' | 'enhanced';
		class?: string;
		style?: string;
	}

	let { text, variant = 'default', class: className = '', style }: Props = $props();
</script>

<blockquote class="quote-block quote-block--{variant} {className}" {style}>
	<span class="quote-mark">"</span>
	<p class="quote-text">{text}</p>
</blockquote>

<style>
	.quote-block {
		position: relative;
		background: var(--color-bg-elevated);
		border-left: 3px solid var(--color-text-muted);
		border-radius: 0 0.5rem 0.5rem 0;
		padding: 0.875rem 1rem 0.875rem 2.5rem;
	}

	.quote-mark {
		position: absolute;
		top: 0.5rem;
		left: 0.75rem;
		font-family: var(--font-display);
		font-size: 1.5rem;
		color: var(--color-text-muted);
		opacity: 0.4;
		line-height: 1;
	}

	.quote-text {
		font-size: 0.9375rem;
		font-style: italic;
		color: var(--color-text-secondary);
		line-height: 1.7;
		margin: 0;
	}

	/* Variants */
	.quote-block--card {
		background: var(--color-bg-surface);
	}

	.quote-block--enhanced {
		background: linear-gradient(135deg, var(--color-accent-subtle) 0%, transparent 60%);
		border-left-color: var(--color-accent);
		animation: fadeInUp 0.3s ease forwards;
	}

	.quote-block--enhanced .quote-mark {
		color: var(--color-accent);
		opacity: 0.5;
	}

	@keyframes fadeInUp {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
