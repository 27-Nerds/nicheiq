<script lang="ts">
	import '$lib/styles/landing.css';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import type { CtaConfig } from '$lib/types/cta';
	import CtaIcon from '$lib/components/ui/CtaIcon.svelte';
	import Footer from '$lib/components/landing/Footer.svelte';
	import AppHeader from '$lib/components/layout/AppHeader.svelte';
	import AppFooter from '$lib/components/layout/AppFooter.svelte';
	import CreditTopUpModal from '$lib/components/CreditTopUpModal.svelte';
	import { isCatalogPath } from '$lib/utils/urls';

	let { data, children } = $props();

	const session = $derived(page.data.session);
	const ctaHeader: CtaConfig | null = $derived(data.ctaTexts?.cta_header ?? null);
	const hasSampleReport = $derived(Boolean(page.data.hasSampleReport));

	// Logged-in users browsing the catalog get the dashboard chrome instead of the
	// public marketing header/footer; anonymous visitors keep the marketing shell.
	const useAppShell = $derived(isCatalogPath(page.url.pathname) && !!session?.user);

	let menuOpen = $state(false);
	let scrolled = $state(false);

	// Close any stuck-open mobile menu when switching to the app shell so it can't
	// reappear after navigating back to a marketing route.
	$effect(() => {
		if (useAppShell) menuOpen = false;
	});

	const navLinks = $derived([
		{ label: 'Idea Catalog', href: '/ideas' },
		{ label: 'Features', href: '#how-it-works' },
		{ label: 'Pricing', href: '#pricing' },
		...(hasSampleReport ? [{ label: 'Sample Report', href: '/sample-report' }] : []),
		{ label: 'Blog', href: '/blog' },
	]);

	function onScroll() {
		// The public header isn't rendered under the app shell — skip the work.
		if (useAppShell) return;
		scrolled = window.scrollY > 0;
	}

	function isActive(href: string): boolean {
		return page.url.pathname === href;
	}

	function handleNavClick(e: MouseEvent, href: string) {
		if (!href.startsWith('#')) return;
		// Only smooth-scroll on the homepage where the anchor targets exist.
		if (page.url.pathname !== '/') return;
		e.preventDefault();
		document.getElementById(href.slice(1))?.scrollIntoView({ behavior: 'smooth' });
	}

	onMount(() => {
		onScroll();
	});
</script>

<svelte:window onscroll={onScroll} />

<div class="min-h-screen flex flex-col public-shell">
	{#if useAppShell}
		<AppHeader />
	{:else}
	<header
		class="public-header"
		style={`border-color: ${scrolled ? 'var(--color-border)' : 'transparent'};`}
	>
		<div class="landing-container header-inner">
			<a href="/" class="header-logo">
				<img src="/niche-logo-beta.svg" alt="NicheIQ" />
			</a>

			<!-- Desktop nav -->
			<div class="header-desktop">
				{#each navLinks as link}
					<a
						href={link.href}
						onclick={(e) => handleNavClick(e, link.href)}
						class="nav-link"
						style={`color: ${
							isActive(link.href)
								? 'var(--color-text-primary)'
								: 'var(--color-text-secondary)'
						};`}
					>
						{link.label}
					</a>
				{/each}

				{#if session?.user}
					<a
						href="/dashboard"
						class="nav-link"
						style={`color: ${
							isActive('/dashboard')
								? 'var(--color-text-primary)'
								: 'var(--color-text-secondary)'
						};`}
					>
						Dashboard
					</a>
				{:else}
					<a
						href="/login"
						class="nav-link"
						style={`color: ${
							isActive('/login')
								? 'var(--color-text-primary)'
								: 'var(--color-text-secondary)'
						};`}
					>
						Log in
					</a>
					{#if ctaHeader?.visible !== false}
						<a
							href={ctaHeader?.url ?? '/register'}
							class="landing-btn-pill-primary header-cta"
						>
							{ctaHeader?.text ?? 'Start for free'}
							<CtaIcon name={ctaHeader?.icon} />
						</a>
					{/if}
				{/if}
			</div>

			<!-- Mobile burger -->
			<button
				class="header-burger"
				onclick={() => (menuOpen = !menuOpen)}
				aria-label="Toggle menu"
				aria-expanded={menuOpen}
			>
				{#if menuOpen}
					<svg
						width="20"
						height="20"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						viewBox="0 0 24 24"
					>
						<path d="M18 6L6 18M6 6l12 12" />
					</svg>
				{:else}
					<svg
						width="20"
						height="20"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						viewBox="0 0 24 24"
					>
						<path d="M4 6h16M4 12h16M4 18h16" />
					</svg>
				{/if}
			</button>
		</div>

		<!-- Mobile menu panel -->
		{#if menuOpen}
			<div class="mobile-panel">
				<div class="landing-container mobile-inner">
					{#each navLinks as link}
						<a
							href={link.href}
							onclick={(e) => {
								handleNavClick(e, link.href);
								menuOpen = false;
							}}
							class="mobile-link"
						>
							{link.label}
						</a>
					{/each}
					<div class="mobile-divider"></div>
					{#if session?.user}
						<a href="/dashboard" onclick={() => (menuOpen = false)} class="mobile-link">
							Dashboard
						</a>
					{:else}
						<a href="/login" onclick={() => (menuOpen = false)} class="mobile-link">Log in</a>
						{#if ctaHeader?.visible !== false}
							<a
								href={ctaHeader?.url ?? '/register'}
								class="landing-btn-pill-primary mobile-cta"
								onclick={() => (menuOpen = false)}
							>
								{ctaHeader?.text ?? 'Start for free'}
							</a>
						{/if}
					{/if}
				</div>
			</div>
		{/if}
	</header>
	{/if}

	<main class="flex-1">
		{@render children()}
	</main>

	{#if useAppShell}
		<AppFooter />
	{:else}
		<Footer {hasSampleReport} ctaTexts={data.ctaTexts} />
	{/if}
</div>

<!-- Credit top-up modal (store-driven + portal). Mounted here so the research
     confirmation flow on catalog detail pages can open it; only renders when
     `creditTopUp.open` (logged-in catalog users). -->
{#if useAppShell}
	<CreditTopUpModal />
{/if}

<style>
	/* Override the global app body bg (#FAFAFA + radial dot pattern from app.css). */
	/* Landing design assumes a pure-white canvas; sections paint colored backgrounds */
	/* on top as needed (Footer = bg-surface, AboutBlock = bg-surface, etc.). */
	.public-shell {
		background: #ffffff;
	}

	.public-header {
		position: sticky;
		top: 0;
		z-index: var(--z-overlay);
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border-bottom: 1px solid transparent;
		transition: border-color var(--duration-normal) var(--ease-default);
	}

	.header-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 3.5rem;
	}

	.header-logo {
		display: flex;
		align-items: center;
		flex-shrink: 0;
	}
	.header-logo img {
		height: 36px;
		width: auto;
	}

	.header-desktop {
		display: none;
	}
	@media (min-width: 768px) {
		.header-desktop {
			display: flex;
			align-items: center;
			gap: 2rem;
		}
	}

	.nav-link {
		font-weight: var(--font-medium);
		font-size: var(--text-md);
		text-decoration: none;
		transition: color var(--duration-normal) var(--ease-default);
	}
	.nav-link:hover {
		color: var(--color-text-primary) !important;
	}
	.nav-link:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
		border-radius: 4px;
	}

	.header-cta {
		padding: 0.5rem 1.125rem !important;
		font-size: var(--text-md) !important;
		box-shadow: none !important;
	}

	.header-burger {
		display: inline-flex;
		padding: 0.5rem;
		color: var(--color-text-muted);
		background: none;
		border: none;
		cursor: pointer;
		transition: color var(--duration-normal) var(--ease-default);
	}
	.header-burger:hover {
		color: var(--color-text-primary);
	}
	.header-burger:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
		border-radius: 4px;
	}
	@media (min-width: 768px) {
		.header-burger {
			display: none;
		}
	}

	.mobile-panel {
		border-top: 1px solid var(--color-border);
		background: var(--color-bg-surface);
	}
	@media (min-width: 768px) {
		.mobile-panel {
			display: none;
		}
	}

	.mobile-inner {
		padding-top: 1rem;
		padding-bottom: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.mobile-link {
		padding: 0.625rem 0;
		font-weight: var(--font-medium);
		font-size: var(--text-md);
		color: var(--color-text-secondary);
		text-decoration: none;
		transition: color var(--duration-normal) var(--ease-default);
	}
	.mobile-link:hover {
		color: var(--color-text-primary);
	}

	.mobile-divider {
		height: 1px;
		background: var(--color-border);
		margin: 0.5rem 0;
	}

	.mobile-cta {
		margin-top: 0.5rem;
		width: 100%;
	}
</style>
