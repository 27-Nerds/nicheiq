<script lang="ts">
	import type { CtaConfig } from '$lib/types/cta';
	import { openCookiePreferences } from '$lib/utils/cookies';

	interface Props {
		hasSampleReport?: boolean;
		ctaTexts?: Record<string, CtaConfig | null>;
	}

	let { hasSampleReport = false, ctaTexts }: Props = $props();

	const currentYear = new Date().getFullYear();

	// "About Us" column — product entry points. Mirrors landing_zip footer column 1.
	const baseAboutLinks = [
		{ name: 'Features', href: '#how-it-works' },
		{ name: 'Pricing', href: '#pricing' },
		{ name: 'How it works', href: '/help' },
		{ name: 'FAQ', href: '#faq' },
	];

	let aboutLinks = $derived(
		hasSampleReport && ctaTexts?.cta_view_sample_link?.visible !== false
			? [
					...baseAboutLinks,
					{
						name: ctaTexts?.cta_view_sample_link?.text ?? 'Sample Reports',
						href: ctaTexts?.cta_view_sample_link?.url ?? '/sample-report',
					},
				]
			: baseAboutLinks,
	);

	// "Contact Us" column. landing_zip lists LinkedIn/Twitter/Support — we don't have
	// real NicheIQ social URLs yet, so the column starts with the real support email.
	// When socials go live, add them via the same ctaTexts settings table (e.g.
	// cta_social_linkedin / cta_social_twitter) and they'll surface here.
	const contactLinks = [{ name: 'Support', href: 'mailto:hello@nicheiq.dev' }];

	// "Legal" column. Cookie Preferences renders as a real button (not a link) because
	// it triggers the cookie-consent dialog via $lib/utils/cookies.
	const legalLinks = [{ name: 'Privacy policy', href: '/privacy' }];
</script>

<footer class="footer-root">
	<div class="landing-container footer-inner">
		<div class="footer-grid">
			<!-- Brand column -->
			<div class="brand-col">
				<a href="/" class="brand-link">
					<img src="/niche-logo-beta.svg" alt="NicheIQ" class="brand-logo" />
				</a>
				<div class="brand-cta-wrap">
					<p class="brand-tagline">Find the idea that's already winning.</p>
					<a href="/register" class="landing-btn-dark">Start for free</a>
				</div>
			</div>

			<!-- Link groups: 3 columns matching landing_zip layout -->
			<div class="link-groups">
				<div>
					<h4 class="link-h">About Us</h4>
					<ul class="link-list">
						{#each aboutLinks as link}
							<li>
								<a href={link.href} class="link-item">{link.name}</a>
							</li>
						{/each}
					</ul>
				</div>

				<div>
					<h4 class="link-h">Contact Us</h4>
					<ul class="link-list">
						{#each contactLinks as link}
							<li>
								<a href={link.href} class="link-item">{link.name}</a>
							</li>
						{/each}
					</ul>
				</div>

				<div>
					<h4 class="link-h">Legal</h4>
					<ul class="link-list">
						{#each legalLinks as link}
							<li>
								<a href={link.href} class="link-item">{link.name}</a>
							</li>
						{/each}
						<li>
							<button type="button" class="link-item link-button" onclick={openCookiePreferences}
								>Cookie Preferences</button
							>
						</li>
					</ul>
				</div>
			</div>
		</div>

		<div class="footer-bottom">
			<p class="copyright">&copy; {currentYear} NicheIQ. All rights reserved.</p>
			<p class="powered-by">Made with care by a solo dev.</p>
		</div>
	</div>
</footer>

<style>
	.footer-root {
		background: var(--color-bg-surface);
	}

	.footer-inner {
		padding-top: 2.5rem;
		padding-bottom: 2.5rem;
	}
	@media (min-width: 640px) {
		.footer-inner {
			padding-top: 4rem;
			padding-bottom: 4rem;
		}
	}

	.footer-grid {
		display: flex;
		flex-direction: column;
		gap: 2.5rem;
		margin-bottom: 2rem;
	}
	@media (min-width: 1024px) {
		.footer-grid {
			flex-direction: row;
			gap: 3rem;
		}
	}
	@media (min-width: 640px) {
		.footer-grid {
			gap: 3rem;
			margin-bottom: 3rem;
		}
	}

	.brand-col {
		display: flex;
		flex-direction: column;
		justify-content: space-between;
	}
	@media (min-width: 1024px) {
		.brand-col {
			flex: 1;
		}
	}

	.brand-link {
		display: inline-flex;
		align-items: center;
	}
	.brand-logo {
		height: 32px;
		width: auto;
		filter: grayscale(1) opacity(0.55);
	}

	.brand-cta-wrap {
		margin-top: 2rem;
	}
	@media (min-width: 1024px) {
		.brand-cta-wrap {
			margin-top: 0;
		}
	}

	.brand-tagline {
		font-weight: var(--font-semibold);
		color: var(--color-text-primary);
		margin-bottom: 0.75rem;
		font-size: var(--text-base);
	}

	.link-groups {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 2rem;
	}
	@media (min-width: 640px) {
		.link-groups {
			gap: 3rem;
		}
	}

	.link-h {
		font-weight: var(--font-semibold);
		color: var(--color-text-primary);
		margin-bottom: 2rem;
		font-size: var(--text-base);
		font-family: var(--font-display);
	}

	.link-list {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
	}

	.link-item {
		color: var(--color-text-muted);
		font-size: var(--text-base);
		transition: color var(--duration-normal) var(--ease-default);
		background: none;
		border: none;
		padding: 0;
		font-family: inherit;
		cursor: pointer;
		text-align: left;
	}
	.link-item:hover {
		color: var(--color-accent);
	}
	.link-item:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
		border-radius: 2px;
	}

	.link-button {
		text-decoration: none;
	}

	.footer-bottom {
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		align-items: center;
		justify-content: space-between;
	}
	@media (min-width: 640px) {
		.footer-bottom {
			padding-top: 2rem;
			flex-direction: row;
		}
	}

	.copyright,
	.powered-by {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		margin: 0;
	}
</style>
