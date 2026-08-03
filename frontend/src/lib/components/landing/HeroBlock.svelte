<script lang="ts">
	import type { CtaConfig } from '$lib/types/cta';
	import CtaIcon from '$lib/components/ui/CtaIcon.svelte';

	interface Props {
		session?: { user?: { name?: string | null; email?: string | null } } | null;
		hasSampleReport?: boolean;
		ctaTexts?: Record<string, CtaConfig | null>;
		activeFounders?: number | null;
	}

	let {
		session = null,
		hasSampleReport = false,
		ctaTexts,
		activeFounders = null,
	}: Props = $props();

	// Live source badges only — matches what the pipeline currently fans out to.
	// When Twitter/YouTube go live in production env, add them here.
	const sources = [
		{
			label: 'Reddit',
			icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="#ff4500" xmlns="http://www.w3.org/2000/svg"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/></svg>`,
		},
		{
			label: 'Hacker News',
			icon: `<svg width="14" height="14" viewBox="0 0 24 24" fill="#ff6600" xmlns="http://www.w3.org/2000/svg"><path d="M0 24V0h24v24H0zM6.951 5.896l4.112 7.708v5.064h1.583v-4.972l4.148-7.799h-1.749l-2.457 4.875c-.372.745-.688 1.434-.688 1.434s-.297-.708-.651-1.434L8.831 5.896h-1.88z"/></svg>`,
		},
	];

	const avatars: Array<{ photo?: string; initials?: string; bg?: string }> = [
		{ photo: '/landing/avatars/avatar-1.jpg' },
		{ photo: '/landing/avatars/avatar-2.jpg' },
		{ initials: 'JM', bg: '#3b82f6' },
		{ photo: '/landing/avatars/avatar-3.jpg' },
		{ initials: '+', bg: '#71717a' },
	];

	const phrases = [
		'to discover untapped niches',
		'to find your next idea',
		'to validate before you build',
		'to hear what the market wants',
		'to generate business ideas',
	];

	// SSR renders the first phrase fully typed (no hydration mismatch, no empty hero for no-JS).
	let displayedText = $state(phrases[0]);

	$effect(() => {
		// Reduced-motion: do not start the typing loop; leave the SSR phrase visible.
		if (
			typeof window !== 'undefined' &&
			window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
		) {
			return;
		}

		let timeout: ReturnType<typeof setTimeout> | undefined;
		let idx = 0;
		let current = phrases[0];

		function type() {
			const target = phrases[idx];
			if (current.length < target.length) {
				current = target.slice(0, current.length + 1);
				displayedText = current;
				timeout = setTimeout(type, 65);
			} else {
				timeout = setTimeout(erase, 2500);
			}
		}

		function erase() {
			if (current.length > 0) {
				current = current.slice(0, -1);
				displayedText = current;
				timeout = setTimeout(erase, 35);
			} else {
				idx = (idx + 1) % phrases.length;
				timeout = setTimeout(type, 200);
			}
		}

		// Start by erasing the SSR phrase, then cycle.
		timeout = setTimeout(erase, 2500);

		return () => {
			if (timeout) clearTimeout(timeout);
		};
	});

	function handleAnchorClick(e: MouseEvent, url: string | undefined) {
		if (!url || !url.startsWith('#')) return;
		e.preventDefault();
		document.getElementById(url.slice(1))?.scrollIntoView({ behavior: 'smooth' });
	}

	// Total registered users. null when the real count is unavailable (or zero)
	// — we hide the line rather than guess.
	const foundersCount = $derived(
		typeof activeFounders === 'number' && activeFounders > 0 ? activeFounders : null,
	);
</script>

<section class="relative overflow-hidden hero-section">
	<div
		class="relative w-full landing-container hero-inner"
		style="display:flex; flex-direction:column; align-items:center; text-align:center;"
	>
		<!-- Source badges -->
		<div class="source-badges">
			{#each sources as s}
				<span class="source-pill">
					{@html s.icon}
					{s.label}
				</span>
			{/each}
		</div>

		<!-- H1 -->
		<h1 class="hero-h1">
			We provide market research<br />
			<span class="hero-rotator">{displayedText}<span class="cursor" aria-hidden="true"></span></span>
		</h1>

		<p class="hero-sub">Real pain points. Ranked solutions. A clear verdict on what to build.</p>

		<!-- CTAs -->
		<div class="hero-ctas">
			{#if session?.user}
				<a href="/dashboard" class="landing-btn-pill-primary"> Go to Dashboard </a>
			{:else}
					{@const heroPrimary = ctaTexts?.cta_hero_primary}
					{@const heroSecondary = ctaTexts?.cta_hero_secondary}
					{@const secondaryUrl = heroSecondary?.url ?? '/sample-report'}
					{@const secondaryNeedsSample = secondaryUrl.split(/[?#]/, 1)[0] === '/sample-report'}
				{#if heroPrimary?.visible !== false}
					<a href={heroPrimary?.url ?? '/register'} class="landing-btn-pill-primary">
						{heroPrimary?.text ?? 'Start for free'}
						<CtaIcon name={heroPrimary?.icon} />
					</a>
				{/if}
					{#if heroSecondary?.visible !== false && (!secondaryNeedsSample || hasSampleReport)}
					<a
						href={secondaryUrl}
						onclick={(e) => handleAnchorClick(e, secondaryUrl)}
						class="landing-btn-pill-secondary"
					>
						{heroSecondary?.text ?? 'See sample report'}
						<CtaIcon name={heroSecondary?.icon} />
					</a>
				{/if}
			{/if}
		</div>

		<!-- Social proof (hidden when the real founder count is unavailable) -->
		{#if foundersCount}
			<div class="social-proof">
				<div class="avatars" aria-hidden="true">
					{#each avatars as a}
						{#if a.photo}
							<img src={a.photo} alt="" class="avatar" />
						{:else}
							<div class="avatar avatar-initials" style={`background:${a.bg ?? '#71717a'};`}>
								{a.initials}
							</div>
						{/if}
					{/each}
				</div>
				<span class="social-proof-text">
					Join {foundersCount}+ founders already exploring their niche
				</span>
			</div>
		{/if}

		<!-- View sample report (gated on backend flag) -->
		{#if hasSampleReport && ctaTexts?.cta_view_sample_link?.visible !== false}
			<a
				href={ctaTexts?.cta_view_sample_link?.url ?? '/sample-report'}
				class="sample-link"
			>
				{ctaTexts?.cta_view_sample_link?.text ?? 'View Sample Report'}
				<CtaIcon name={ctaTexts?.cta_view_sample_link?.icon} class="w-4 h-4" />
			</a>
		{/if}
	</div>
</section>

<style>
	.hero-section {
		background: #fff;
	}

	.hero-inner {
		padding-top: 4rem;
		padding-bottom: 1.5rem;
	}
	@media (min-width: 640px) {
		.hero-inner {
			padding-top: 5rem;
		}
	}

	.source-badges {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		margin-bottom: 2.5rem;
	}

	.source-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.375rem 1rem;
		border: 1px solid var(--color-border);
		background: var(--color-bg-elevated);
		color: var(--color-text-secondary);
		font-size: 12px;
		border-radius: 10px;
	}

	.hero-h1 {
		margin: 0 auto 1.5rem;
		max-width: 48rem;
		color: var(--color-text-primary);
		font-family: var(--font-display);
		font-size: clamp(2.5rem, 6vw, 4.5rem);
		font-weight: 700;
		line-height: var(--leading-tight);
		letter-spacing: var(--tracking-tight);
		/* Override the global `h1 { text-wrap: balance; }` from app.css — */
		/* landing_zip's design relies on default greedy wrap to match its 3-line layout. */
		text-wrap: wrap;
	}

	.hero-rotator {
		display: block;
		min-height: 2.2em;
		color: #828282;
	}

	.cursor {
		display: inline-block;
		width: 2px;
		height: 0.8em;
		background: #a1a1aa;
		vertical-align: middle;
		margin-left: 2px;
		border-radius: 1px;
		animation: blink 0.75s step-end infinite;
	}

	@keyframes blink {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.cursor {
			animation: none;
			opacity: 0;
		}
	}

	.hero-sub {
		margin: 0 auto 2.5rem;
		max-width: 32rem;
		color: var(--color-text-secondary);
		font-size: 0.875rem;
		line-height: var(--leading-relaxed);
	}

	.hero-ctas {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		margin-bottom: 2.5rem;
		width: 100%;
	}
	@media (min-width: 640px) {
		.hero-ctas {
			flex-direction: row;
			width: auto;
		}
	}
	.hero-ctas > :global(a) {
		width: 100%;
	}
	@media (min-width: 640px) {
		.hero-ctas > :global(a) {
			width: auto;
		}
	}

	.social-proof {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}
	@media (min-width: 640px) {
		.social-proof {
			flex-direction: row;
			gap: 0.75rem;
		}
	}

	.avatars {
		display: flex;
	}
	.avatar {
		width: 2rem;
		height: 2rem;
		border-radius: 9999px;
		border: 2px solid #fff;
		object-fit: cover;
		margin-left: -0.625rem;
	}
	.avatar:first-child {
		margin-left: 0;
	}
	.avatar-initials {
		display: flex;
		align-items: center;
		justify-content: center;
		color: #fff;
		font-weight: 700;
		font-size: 9px;
		font-family: var(--font-mono);
	}

	.social-proof-text {
		color: var(--color-text-muted);
		font-size: 0.875rem;
	}

	.sample-link {
		margin-top: 1.5rem;
		color: var(--color-text-muted);
		font-size: 0.875rem;
		text-decoration: underline;
		text-underline-offset: 4px;
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		transition: color var(--duration-normal) var(--ease-default);
	}
	.sample-link:hover {
		color: var(--color-accent);
	}
</style>
