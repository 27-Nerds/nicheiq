<script lang="ts">
	import { ShieldCheck } from 'lucide-svelte';
	import type { CtaConfig } from '$lib/types/cta';
	import type { TokenPackage } from '$lib/types/billing';
	import CtaIcon from '$lib/components/ui/CtaIcon.svelte';

	interface Props {
		session?: { user?: { name?: string | null; email?: string | null } } | null;
		ctaTexts?: Record<string, CtaConfig | null>;
		packages?: TokenPackage[];
	}

	let { session = null, ctaTexts, packages = [] }: Props = $props();

	const fallbackTiers = [
		{ name: 'Starter', reports: 1, price: 19, popular: false },
		{ name: 'Basic', reports: 3, price: 45, popular: true },
		{ name: 'Pro', reports: 10, price: 100, popular: false },
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

	const useDynamic = $derived(packages.length > 0);

	function formatPrice(cents: number): string {
		const dollars = cents / 100;
		return dollars % 1 === 0 ? `$${dollars}` : `$${dollars.toFixed(2)}`;
	}

	function fallbackToPackage(tier: {
		name: string;
		reports: number;
		price: number;
		popular: boolean;
	}): TokenPackage {
		return {
			id: tier.name.toLowerCase(),
			name: tier.name,
			credits: tier.reports,
			priceInCents: tier.price * 100,
			isPopular: tier.popular,
			description: `~${tier.reports} ${tier.reports === 1 ? 'report' : 'reports'}`,
			creditsInfo:
				tier.reports > 1 ? `$${(tier.price / tier.reports).toFixed(0)}/report` : null,
			promoLine: '+1 FREE Discovery (up to 10 ideas)',
			tagline: null,
			includesLabel: null,
			features: null,
			ctaText: null,
			badgeLabel: null,
			promoPriceInCents: null,
			promoBadge: null,
			ctaSubText: null,
			ctaSubUrl: null,
		};
	}

	const renderedPackages = $derived(
		useDynamic ? packages : fallbackTiers.map(fallbackToPackage),
	);

	function pricingCtaLabel(pkg: TokenPackage, cta: CtaConfig | null | undefined): string {
		if (pkg.ctaText) return pkg.ctaText;
		if (cta?.text) {
			return cta.text
				.replace('{count}', String(pkg.credits))
				.replace('(s)', pkg.credits === 1 ? '' : 's');
		}
		return `Get ${pkg.credits} ${pkg.credits === 1 ? 'Report' : 'Reports'}`;
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
				Simple Pricing. <span style="color:var(--color-accent)">Full Research</span>
			</h2>
			<p
				style="font-size: var(--text-base); color: var(--color-accent); font-weight: var(--font-medium); margin-top: 0.75rem;"
			>
				Get AI-driven niche research from billions of discussions on social media.
			</p>
			<p style="font-size: var(--text-sm); color: var(--color-text-muted); margin-top: 0.5rem;">
				Every package includes 1 FREE Discovery (up to 10 ideas). Don't worry about your first try.
			</p>
		</div>

		<div class="landing-container-inner">
			<div
				class="pricing-grid"
				class:cols-1={renderedPackages.length === 1}
				class:cols-2={renderedPackages.length === 2}
				class:cols-3={renderedPackages.length >= 3}
			>
				{#each renderedPackages as pkg (pkg.id)}
					<div class="pricing-card" class:popular={pkg.isPopular}>
						{#if pkg.promoBadge}
							<span class="discount-badge">{pkg.promoBadge}</span>
						{/if}
						{#if pkg.isPopular}
							<span class="popular-badge">
								<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"
									><path
										d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
									/></svg
								>
								{pkg.badgeLabel ?? 'Best Value'}
							</span>
						{/if}

						<div class="card-body">
							<p class="card-name">{pkg.name}</p>
							<h3 class="card-tagline">{pkg.tagline ?? pkg.name}</h3>
							{#if pkg.description}
								<p class="card-desc">{pkg.description}</p>
							{/if}

							<div class="card-price-row">
								{#if pkg.promoPriceInCents}
									<span class="old-price">{formatPrice(pkg.priceInCents)}</span>
									<span class="card-price" class:price-success={pkg.isPopular}
										>{formatPrice(pkg.promoPriceInCents)}</span
									>
								{:else}
									<span class="card-price" class:price-success={pkg.isPopular}
										>{formatPrice(pkg.priceInCents)}</span
									>
								{/if}
							</div>

							<div class="card-credits">
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
								<span><strong>{pkg.credits}</strong> credits</span>
								{#if pkg.creditsInfo}
									<span style="color: var(--color-text-muted); margin-left: 4px;"
										>· {pkg.creditsInfo}</span
									>
								{/if}
							</div>

							{#if pkg.includesLabel}
								<div class="includes-badge" class:popular={pkg.isPopular}>
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
									{pkg.includesLabel}
								</div>
							{/if}

							<div class="card-divider"></div>

							{#if pkg.features?.length}
								<ul class="card-features">
									{#each pkg.features as feat}
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

							{#if pkg.promoLine}
								<div class="promo-line">
									<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"
										><path
											d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
										/></svg
									>
									({pkg.promoLine})
								</div>
							{/if}
						</div>

						<div class="card-cta-wrap">
							{#if session?.user}
								<a href="/dashboard" class="pricing-cta" class:primary={pkg.isPopular}>
									Go to Dashboard
								</a>
							{:else if ctaTexts?.cta_pricing_button?.visible !== false}
								{@const pricingCta = ctaTexts?.cta_pricing_button}
								<a
									href={pricingCta?.url ?? '/register'}
									class="pricing-cta"
									class:primary={pkg.isPopular}
								>
									{pricingCtaLabel(pkg, pricingCta)}
									<CtaIcon name={pricingCta?.icon} class="w-4 h-4" />
								</a>
							{/if}
							{#if pkg.ctaSubText && pkg.ctaSubUrl}
								<a href={pkg.ctaSubUrl} class="cta-sub-link">{pkg.ctaSubText}</a>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>

		<p class="footnote">
			*Credit-based system — estimated report count, use however works best for you
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
