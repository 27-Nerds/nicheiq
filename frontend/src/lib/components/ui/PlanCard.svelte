<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { SubscriptionPlan } from '$lib/types/billing';

	interface Props {
		plan: SubscriptionPlan;
		actions?: Snippet;
	}

	let { plan, actions }: Props = $props();

	function formatPrice(cents: number): string {
		const dollars = cents / 100;
		return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
	}
</script>

<div class="pricing-card" class:popular={plan.isPopular}>
	{#if plan.promoBadge}
		<span class="discount-badge">{plan.promoBadge}</span>
	{/if}
	{#if plan.isPopular}
		<span class="popular-badge">
			<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"
				><path
					d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
				/></svg
			>
			{plan.badgeLabel ?? 'Best Value'}
		</span>
	{/if}

	<div class="card-body">
		<p class="card-name">{plan.name}</p>
		<h3 class="card-tagline">{plan.tagline ?? plan.name}</h3>
		{#if plan.description}
			<p class="card-desc">{plan.description}</p>
		{/if}

		<div class="card-price-row">
			{#if plan.promoPriceInCents}
				<span class="old-price">{formatPrice(plan.priceInCents)}</span>
				<span class="card-price" class:price-success={plan.isPopular}
					>{formatPrice(plan.promoPriceInCents)}</span
				>
				<span class="price-interval">/mo</span>
			{:else}
				<span class="card-price" class:price-success={plan.isPopular}
					>{formatPrice(plan.priceInCents)}</span
				>
				<span class="price-interval">/mo</span>
			{/if}
		</div>

		<div class="card-credits">
			{#if plan.monthlyCredits === 0}
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					style="color: var(--color-accent);"
				>
					<path d="M12 2L2 7l10 5 10-5-10-5z" />
					<path d="M2 17l10 5 10-5" />
					<path d="M2 12l10 5 10-5" />
				</svg>
				<span><strong>Full catalog access</strong></span>
			{:else}
				<svg
					width="14"
					height="14"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					style="color: var(--color-accent);"
				>
					<circle cx="12" cy="12" r="10" />
					<path d="M12 6v6l4 2" />
				</svg>
				<span><strong>{plan.monthlyCredits}</strong> credits/mo</span>
			{/if}
			{#if plan.creditsInfo}
				<span style="color: var(--color-text-muted); margin-left: 4px;"
					>· {plan.creditsInfo}</span
				>
			{/if}
		</div>

		{#if plan.includesLabel}
			<div class="includes-badge" class:popular={plan.isPopular}>
				<svg
					width="13"
					height="13"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
				>
					<path d="M12 2L2 7l10 5 10-5-10-5z" />
					<path d="M2 17l10 5 10-5" />
					<path d="M2 12l10 5 10-5" />
				</svg>
				{plan.includesLabel}
			</div>
		{/if}

		<div class="card-divider"></div>

		{#if plan.features?.length}
			<ul class="card-features">
				{#each plan.features as feat}
					<li class:highlight={feat.highlight}>
						{#if feat.icon === 'star'}
							<svg
								class="feature-icon"
								fill="currentColor"
								viewBox="0 0 24 24"
								><path
									d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
								/></svg
							>
						{:else if feat.icon === 'plus'}
							<svg
								class="feature-icon"
								fill="none"
								stroke="currentColor"
								stroke-width="2.5"
								viewBox="0 0 24 24"
								><path d="M12 5v14M5 12h14" /></svg
							>
						{:else}
							<svg
								class="feature-icon"
								fill="none"
								stroke="currentColor"
								stroke-width="2.5"
								viewBox="0 0 24 24"
								><path d="M20 6L9 17l-5-5" /></svg
							>
						{/if}
						<span>{feat.text}</span>
					</li>
				{/each}
			</ul>
		{/if}

		{#if plan.promoLine}
			<div class="promo-line">
				<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"
					><path
						d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
					/></svg
				>
				({plan.promoLine})
			</div>
		{/if}
	</div>

	<div class="card-cta-wrap">
		{@render actions?.()}
		{#if plan.ctaSubText && plan.ctaSubUrl}
			<a href={plan.ctaSubUrl} class="cta-sub-link">{plan.ctaSubText}</a>
		{/if}
	</div>
</div>

<style>
	.pricing-card {
		position: relative;
		display: flex;
		flex-direction: column;
		border-radius: var(--radius-2xl);
		border: 1px solid var(--color-border);
		background: var(--color-bg-elevated);
		overflow: hidden;
		transition: border-color var(--duration-normal) var(--ease-default);
	}
	.pricing-card:hover {
		border-color: var(--color-border-emphasis);
	}
	.pricing-card.popular {
		border-color: var(--color-accent);
	}

	.discount-badge {
		position: absolute;
		top: 1rem;
		left: 1.25rem;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem 0.625rem;
		border-radius: var(--radius-full);
		font-size: var(--text-xs);
		font-weight: var(--font-bold);
		background: var(--color-success-subtle);
		color: var(--color-success-dark);
	}

	.popular-badge {
		position: absolute;
		top: 1rem;
		right: 1.25rem;
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.25rem 0.75rem;
		border-radius: var(--radius-full);
		font-size: var(--text-xs);
		font-weight: var(--font-bold);
		background: var(--color-accent);
		color: #fff;
	}

	.card-body {
		padding: 3.5rem 1.5rem 1.5rem;
		display: flex;
		flex-direction: column;
		flex: 1;
	}
	@media (min-width: 640px) {
		.card-body {
			padding: 3.5rem 1.75rem 1.75rem;
		}
	}

	.card-name {
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: var(--tracking-widest);
		color: var(--color-text-muted);
	}

	.card-tagline {
		font-family: var(--font-display);
		font-size: var(--text-xl);
		font-weight: var(--font-bold);
		color: var(--color-text-primary);
		margin-top: 0.5rem;
		line-height: var(--leading-tight);
	}

	.card-desc {
		font-size: var(--text-sm);
		color: var(--color-text-muted);
		margin-top: 0.375rem;
		line-height: var(--leading-relaxed);
		min-height: 3.3em;
	}

	.card-price-row {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin-top: 1.25rem;
	}

	.old-price {
		font-size: var(--text-lg);
		color: var(--color-text-muted);
		text-decoration: line-through;
		font-weight: var(--font-medium);
	}

	.card-price {
		font-family: var(--font-display);
		font-size: var(--text-5xl);
		font-weight: var(--font-bold);
		line-height: var(--leading-none);
		color: var(--color-text-primary);
	}
	.card-price.price-success {
		color: var(--color-success);
	}

	.card-credits {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		margin-top: 0.5rem;
		font-size: var(--text-sm);
		color: var(--color-text-muted);
	}
	.card-credits strong {
		color: var(--color-text-primary);
		font-weight: var(--font-semibold);
	}

	.includes-badge {
		margin-top: 1rem;
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.375rem 0.75rem;
		border-radius: var(--radius-md);
		font-size: var(--text-xs);
		font-weight: var(--font-semibold);
		background: var(--color-bg-surface);
		color: var(--color-accent);
		border: 1px solid var(--color-border-accent);
		align-self: flex-start;
	}
	.includes-badge.popular {
		background: var(--color-accent-subtle);
		border-color: transparent;
	}

	.card-divider {
		height: 1px;
		background: var(--color-border);
		margin: 1.25rem 0;
	}

	.card-features {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		flex: 1;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	.card-features li {
		display: flex;
		align-items: flex-start;
		gap: 0.625rem;
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
	}
	.card-features li.highlight {
		color: var(--color-accent);
		font-weight: var(--font-semibold);
	}
	.feature-icon {
		height: 1rem;
		width: 1rem;
		flex-shrink: 0;
		margin-top: 0.125rem;
		color: var(--color-text-muted);
	}
	.card-features li.highlight .feature-icon {
		color: var(--color-accent);
	}

	.promo-line {
		margin-top: 1.25rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: var(--text-sm);
		font-weight: var(--font-semibold);
		color: var(--color-accent);
	}

	.card-cta-wrap {
		padding: 0 1.5rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	@media (min-width: 640px) {
		.card-cta-wrap {
			padding: 0 1.75rem 1.75rem;
		}
	}

	.price-interval {
		font-size: var(--text-base);
		color: var(--color-text-muted);
		font-weight: var(--font-medium);
		margin-left: 0.125rem;
	}

	.cta-sub-link {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.375rem;
		color: var(--color-text-secondary);
		text-decoration: underline;
		text-underline-offset: 2px;
		font-size: 1rem;
		transition: color var(--duration-normal) var(--ease-default);
	}
	.cta-sub-link:hover {
		color: var(--color-accent);
	}
</style>
