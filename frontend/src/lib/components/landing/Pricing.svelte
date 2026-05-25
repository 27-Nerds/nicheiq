<script lang="ts">
	import { ShieldCheck } from 'lucide-svelte';
	import type { CtaConfig } from '$lib/types/cta';
	import type { SubscriptionPlan } from '$lib/types/billing';
	import CtaIcon from '$lib/components/ui/CtaIcon.svelte';

	interface Props {
		session?: { user?: { name?: string | null; email?: string | null } } | null;
		ctaTexts?: Record<string, CtaConfig | null>;
		plans?: SubscriptionPlan[];
	}

	let { session = null, ctaTexts, plans = [] }: Props = $props();

	const fallbackTiers: Array<{
		name: string;
		monthlyCredits: number;
		price: number;
		popular: boolean;
	}> = [
		{ name: 'Catalog', monthlyCredits: 0, price: 19, popular: false },
		{ name: 'Founder', monthlyCredits: 20, price: 49, popular: true },
		{ name: 'Studio', monthlyCredits: 60, price: 129, popular: false },
	];

	const reportFeatures = [
		'16-stage research pipeline',
		'5+ pain points with sources',
		'100+ keywords with live search volumes',
		'Competitive landscape analysis',
		'Complete SEO strategy',
		'GTM blueprint with 30-day playbook',
		'80% hard data, 20% AI synthesis',
		'Ready-to-launch landing page (optional)',
	];

	const useDynamic = $derived(plans.length > 0);

	function formatPrice(cents: number): string {
		const dollars = cents / 100;
		return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
	}

	function fallbackToPlan(tier: {
		name: string;
		monthlyCredits: number;
		price: number;
		popular: boolean;
	}): SubscriptionPlan {
		return {
			id: tier.name.toLowerCase(),
			name: tier.name,
			monthlyCredits: tier.monthlyCredits,
			priceInCents: tier.price * 100,
			interval: 'month',
			trialDays: null,
			isPopular: tier.popular,
			description:
				tier.monthlyCredits === 0
					? 'Full catalog access — browse every validated idea'
					: `${tier.monthlyCredits} research credits every month`,
			creditsInfo: tier.monthlyCredits > 0 ? 'Resets each cycle' : null,
			promoLine: null,
			tagline: null,
			includesLabel: 'Full catalog access',
			features: null,
			ctaText: null,
			badgeLabel: null,
			promoPriceInCents: null,
			promoBadge: null,
			ctaSubText: null,
			ctaSubUrl: null,
		};
	}

	const renderedPlans = $derived(
		useDynamic ? plans : fallbackTiers.map(fallbackToPlan),
	);

	let subscribeLoading = $state<string | null>(null);
	let subscribeError = $state('');

	const pricingCta = $derived(ctaTexts?.cta_pricing_button);

	function pricingCtaLabel(plan: SubscriptionPlan, cta: CtaConfig | null | undefined): string {
		if (plan.ctaText) return plan.ctaText;
		if (cta?.text) return cta.text.replace('{count}', String(plan.monthlyCredits));
		return 'Subscribe';
	}

	// Logged-in subscribe: start checkout, or fall through to the portal on 409
	// (already subscribed) — mirrors the /billing behavior.
	async function subscribe(planId: string) {
		if (subscribeLoading) return;
		subscribeLoading = planId;
		subscribeError = '';
		try {
			const response = await fetch('/api/billing/subscribe', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ planId }),
			});
			const result = await response.json();
			if (response.status === 409) {
				const portalRes = await fetch('/api/billing/portal', { method: 'POST' });
				const portal = await portalRes.json();
				if (portalRes.ok && portal.url) {
					window.location.href = portal.url;
					return;
				}
				subscribeError = portal.error || 'Unable to open the billing portal.';
				return;
			}
			if (response.ok && result.url) {
				window.location.href = result.url;
			} else {
				subscribeError = result.error || 'Failed to start subscription.';
			}
		} catch {
			subscribeError = 'Network error. Please try again.';
		} finally {
			subscribeLoading = null;
		}
	}
</script>

<section id="pricing" class="section">
	<div class="landing-container">
		<div
			class="landing-section-header-wrap"
			style="text-align: center;"
		>
			<div class="landing-section-label-row">
				<span class="landing-section-dot"></span>
				<span class="landing-section-label">Simple Pricing</span>
			</div>
			<h2 class="landing-section-h2">
				Simple Pricing. <span style="color:var(--color-accent)">Monthly Research</span>
			</h2>
			<p
				style="font-size: var(--text-base); color: var(--color-accent); font-weight: var(--font-medium); margin-top: 0.75rem;"
			>
				Subscribe for monthly research credits and full access to the validated-idea catalog.
			</p>
			<p style="font-size: var(--text-sm); color: var(--color-text-muted); margin-top: 0.5rem;">
				Credits reset every month. Cancel or switch anytime from the billing portal.
			</p>
		</div>

		<div class="landing-container-inner">
			<div
				class="pricing-grid"
				class:cols-1={renderedPlans.length === 1}
				class:cols-2={renderedPlans.length === 2}
				class:cols-3={renderedPlans.length >= 3}
			>
				{#each renderedPlans as plan (plan.id)}
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
							{#if session?.user}
								<button
									type="button"
									class="pricing-cta"
									class:primary={plan.isPopular}
									onclick={() => subscribe(plan.id)}
									disabled={subscribeLoading !== null}
								>
									{subscribeLoading === plan.id
										? 'Redirecting…'
										: pricingCtaLabel(plan, pricingCta)}
									<CtaIcon name={pricingCta?.icon} class="w-4 h-4" />
								</button>
							{:else}
								<a
									href="/register?ref=pricing"
									class="pricing-cta"
									class:primary={plan.isPopular}
								>
									{pricingCtaLabel(plan, pricingCta)}
									<CtaIcon name={pricingCta?.icon} class="w-4 h-4" />
								</a>
							{/if}
							{#if plan.ctaSubText && plan.ctaSubUrl}
								<a href={plan.ctaSubUrl} class="cta-sub-link">{plan.ctaSubText}</a>
							{/if}
						</div>
					</div>
				{/each}
			</div>
			{#if subscribeError}
				<p class="subscribe-error">{subscribeError}</p>
			{/if}
		</div>

		<p class="footnote">
			*Subscription credits reset each month. Need a one-time top-up? Buy credit packs on your billing page.
		</p>

		<div class="whats-included">
			<h3 class="whats-included-h">What's included in every report</h3>
			<div class="features-grid">
				{#each reportFeatures as feature}
					<div class="feature-row">
						<span class="feature-arrow">→</span>
						<span class="feature-text">{feature}</span>
					</div>
				{/each}
			</div>

			<div class="guarantee-badge">
				<ShieldCheck class="w-8 h-8" style="color: var(--color-success); flex-shrink: 0;" />
				<div>
					<h4 class="guarantee-h">Zero-Risk Guarantee</h4>
					<p class="guarantee-p">
						If a report can't be completed due to insufficient data or any other reason, your
						research credit is automatically returned — no risk, no loss.
					</p>
				</div>
			</div>

			{#if !session?.user}
				<p class="signin-line">
					Already have an account?
					<a href="/login" style="color: var(--color-accent); text-decoration: underline;">Sign in</a
					>
				</p>
			{/if}
		</div>
	</div>
</section>

<style>
	.pricing-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1.25rem;
		max-width: 48rem;
		margin: 0 auto;
		align-items: stretch;
	}
	@media (min-width: 768px) {
		.pricing-grid {
			gap: 1.5rem;
		}
		.pricing-grid.cols-2 {
			grid-template-columns: repeat(2, 1fr);
			max-width: 48rem;
		}
		.pricing-grid.cols-3 {
			grid-template-columns: repeat(3, 1fr);
			max-width: 64rem;
		}
	}

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

	.subscribe-error {
		text-align: center;
		font-size: var(--text-sm);
		color: var(--color-error);
		margin-top: 1rem;
	}

	.pricing-cta {
		display: inline-flex;
		justify-content: center;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.875rem 1.5rem;
		font-family: var(--font-body);
		font-weight: var(--font-semibold);
		font-size: var(--text-md);
		text-decoration: none;
		border-radius: var(--radius-full);
		transition: all var(--duration-normal) var(--ease-default);
		color: var(--color-text-primary);
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border-emphasis);
		cursor: pointer;
	}

	.pricing-cta:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.pricing-cta:hover {
		border-color: var(--color-text-primary);
		background: var(--color-bg-surface);
		transform: translateY(-1px);
	}
	.pricing-cta:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	.pricing-cta.primary {
		color: #fff;
		background: var(--color-accent);
		border: 1.5px solid transparent;
		box-shadow:
			0 1px 3px rgba(234, 88, 12, 0.25),
			0 4px 12px rgba(234, 88, 12, 0.15);
	}
	.pricing-cta.primary:hover {
		background: var(--color-accent-hover);
		box-shadow: 0 4px 16px rgba(234, 88, 12, 0.3);
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

	.footnote {
		text-align: center;
		font-size: var(--text-xs);
		color: var(--color-text-muted);
		margin-top: 2rem;
	}

	.whats-included {
		margin-top: 3rem;
		max-width: 48rem;
		margin-left: auto;
		margin-right: auto;
	}
	@media (min-width: 640px) {
		.whats-included {
			margin-top: 4rem;
		}
	}

	.whats-included-h {
		text-align: center;
		font-size: var(--text-xl);
		font-weight: var(--font-semibold);
		color: var(--color-text-primary);
		margin-bottom: 1.5rem;
	}

	.features-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.75rem;
	}
	@media (min-width: 640px) {
		.features-grid {
			grid-template-columns: repeat(2, 1fr);
			gap: 1rem;
		}
	}

	.feature-row {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
	}
	.feature-arrow {
		color: var(--color-accent);
		font-size: var(--text-sm);
		margin-top: 0.125rem;
		flex-shrink: 0;
	}
	.feature-text {
		color: var(--color-text-secondary);
		font-size: var(--text-base);
	}

	.guarantee-badge {
		margin-top: 2.5rem;
		padding: 1rem;
		border-radius: var(--radius-lg);
		background: var(--color-success-subtle);
		border: 1px solid var(--color-border-success);
		display: flex;
		align-items: center;
		gap: 0.75rem;
		max-width: 28rem;
		margin-left: auto;
		margin-right: auto;
	}

	.guarantee-h {
		font-weight: var(--font-semibold);
		color: var(--color-success);
		font-size: var(--text-sm);
	}

	.guarantee-p {
		font-size: var(--text-xs);
		color: var(--color-text-muted);
		margin-top: 0.125rem;
	}

	.signin-line {
		text-align: center;
		font-size: var(--text-sm);
		color: var(--color-text-muted);
		margin-top: 1.5rem;
	}
</style>
