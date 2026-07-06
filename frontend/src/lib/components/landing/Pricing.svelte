<script lang="ts">
	import { ShieldCheck } from 'lucide-svelte';
	import type { CtaConfig } from '$lib/types/cta';
	import type { SubscriptionPlan } from '$lib/types/billing';
	import CtaIcon from '$lib/components/ui/CtaIcon.svelte';
	import PlanCard from '$lib/components/ui/PlanCard.svelte';

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
		'30+ specialised AI agents on every report',
		'5+ pain points with sources',
		'100+ keywords with live search volumes',
		'Competitive landscape analysis',
		'Complete SEO strategy',
		'GTM blueprint with 30-day playbook',
		'80% hard data, 20% AI synthesis',
		'Ready-to-launch landing page (optional)',
	];

	const useDynamic = $derived(plans.length > 0);

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

	// Carry the clicked plan through auth so /billing can auto-start checkout.
	function registerHref(plan: SubscriptionPlan): string {
		return `/register?ref=pricing&returnTo=${encodeURIComponent(`/billing?plan=${plan.id}#plans`)}`;
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
				<span class="landing-section-label">PRICING</span>
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
					<PlanCard {plan}>
						{#snippet actions()}
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
									href={registerHref(plan)}
									class="pricing-cta"
									class:primary={plan.isPopular}
								>
									{pricingCtaLabel(plan, pricingCta)}
									<CtaIcon name={pricingCta?.icon} class="w-4 h-4" />
								</a>
							{/if}
						{/snippet}
					</PlanCard>
				{/each}
			</div>
			{#if subscribeError}
				<p class="subscribe-error">{subscribeError}</p>
			{/if}
		</div>

		<p class="footnote">
			*Subscription credits reset each month. Need a one-time top-up? Buy credit packs on your billing page — they never expire.
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
