<script lang="ts">
	import type { CatalogTopPainPoint } from '$lib/types/publicCatalog';

	interface Props {
		topPainPoints?: CatalogTopPainPoint[];
	}

	let { topPainPoints = [] }: Props = $props();

	let setEl = $state<HTMLElement | null>(null);

	let offset = $derived.by(() => {
		if (!setEl) return 0;
		const gap = parseFloat(getComputedStyle(setEl.parentElement!).gap) || 20;
		return setEl.offsetWidth + gap;
	});

	const speed = 0.058;
	let duration = $derived(offset ? Math.round(offset / speed) : 40000);

	function scoreFor(pp: CatalogTopPainPoint): number {
		return Math.max(0, Math.min(100, Math.round((pp.severityScore ?? 0) * 100)));
	}

	function hashHue(slug: string): number {
		let h = 0;
		for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
		return h % 360;
	}
</script>

{#if topPainPoints.length > 0}
	<section class="samples-section" id="samples">
		<div class="landing-container">
			<div class="landing-section-header-wrap">
				<div class="landing-section-label-row">
					<span class="landing-section-label">SAMPLES · FROM THE CATALOG</span>
				</div>
				<h2 class="landing-section-h2">
					See what a market research run <span style="color: var(--color-accent)">looks like</span>
				</h2>
				<p class="landing-section-subtitle">
					Each report is packed with demand data, competitor gaps, and audience insights — ready to
					act on.
				</p>
			</div>
		</div>

		<div class="slider-viewport">
			<div class="slider-inner" style="--offset: {offset}px; animation-duration: {duration}ms">
				<div class="slider-set" bind:this={setEl}>
					{#each topPainPoints as pp}
						{@const hue = hashHue(pp.slug)}
						<a href={`/pain-point/${pp.slug}`} class="card-link" draggable="false">
							<article
								class="sample-card"
								style={`background: linear-gradient(135deg, hsl(${hue}, 65%, 55%) 0%, hsl(${(hue + 40) % 360}, 70%, 35%) 100%);`}
							>
								<div class="card-bottom-overlay"></div>
								<div class="card-body">
									<span class="demand-badge">Severity · {scoreFor(pp)}</span>
									<div class="card-footer">
										<h3 class="card-title">{pp.title}</h3>
										<div class="card-arrow" aria-hidden="true">
											<span class="card-arrow-icon">&#8594;</span>
										</div>
									</div>
								</div>
							</article>
						</a>
					{/each}
				</div>

				<div class="slider-set" aria-hidden="true">
					{#each topPainPoints as pp}
						{@const hue = hashHue(pp.slug)}
						<a href={`/pain-point/${pp.slug}`} tabindex="-1" class="card-link" draggable="false">
							<article
								class="sample-card"
								style={`background: linear-gradient(135deg, hsl(${hue}, 65%, 55%) 0%, hsl(${(hue + 40) % 360}, 70%, 35%) 100%);`}
							>
								<div class="card-bottom-overlay"></div>
								<div class="card-body">
									<span class="demand-badge">Severity · {scoreFor(pp)}</span>
									<div class="card-footer">
										<h3 class="card-title">{pp.title}</h3>
										<div class="card-arrow" aria-hidden="true">
											<span class="card-arrow-icon">&#8594;</span>
										</div>
									</div>
								</div>
							</article>
						</a>
					{/each}
				</div>
			</div>
		</div>
	</section>
{/if}

<style>
	.samples-section {
		position: relative;
		/* landing_zip uses var(--space-24) = 6rem; frontend token set lacks --space-24 so inline 6rem. */
		padding: 6rem 0;
		overflow-x: clip;
	}

	.slider-viewport {
		margin-top: var(--space-10);
		overflow: hidden;
		padding-top: 12px;
		padding-bottom: var(--space-10);
	}

	.slider-inner {
		display: flex;
		gap: var(--space-5);
		width: max-content;
		animation: scroll-cards linear infinite;
		will-change: transform;
	}

	.slider-set {
		display: flex;
		gap: var(--space-5);
	}

	@keyframes scroll-cards {
		from {
			transform: translateX(calc(-1 * var(--offset)));
		}
		to {
			transform: translateX(0);
		}
	}

	.slider-viewport:hover .slider-inner {
		animation-play-state: paused;
	}

	@media (prefers-reduced-motion: reduce) {
		.slider-inner {
			animation: none;
		}
	}

	.card-link {
		display: block;
		text-decoration: none;
		flex-shrink: 0;
	}

	.card-link:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 4px;
		border-radius: var(--radius-2xl);
	}

	.sample-card {
		position: relative;
		width: 270px;
		height: 360px;
		border-radius: var(--radius-2xl);
		overflow: hidden;
		transition:
			transform var(--duration-normal) var(--ease-default),
			box-shadow var(--duration-normal) var(--ease-default);
	}

	.card-link:hover .sample-card {
		box-shadow: 0 12px 24px rgba(0, 0, 0, 0.12);
	}

	.card-bottom-overlay {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 38%;
		background: linear-gradient(
			to top,
			rgba(0, 0, 0, 0.75) 0%,
			rgba(0, 0, 0, 0.4) 55%,
			transparent 100%
		);
	}

	.card-body {
		position: absolute;
		inset: 0;
		padding: var(--space-5);
		display: flex;
		flex-direction: column;
	}

	.demand-badge {
		align-self: flex-start;
		background: var(--color-bg-elevated);
		color: var(--color-text-secondary);
		font-family: var(--font-mono);
		font-size: 12px;
		letter-spacing: var(--tracking-wide);
		padding: 6px 16px;
		border-radius: 10px;
		border: 1px solid var(--color-border);
		white-space: nowrap;
	}

	.card-footer {
		margin-top: auto;
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: var(--space-3);
	}

	.card-title {
		font-size: var(--text-xl);
		font-weight: var(--font-bold);
		color: #fff;
		line-height: var(--leading-snug);
	}

	.card-arrow {
		flex-shrink: 0;
		width: 40px;
		height: 40px;
		border-radius: var(--radius-full);
		background: #fff;
		color: var(--color-text-primary);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: var(--text-lg);
	}

	.card-arrow-icon {
		display: inline-block;
		transition: transform var(--duration-fast) var(--ease-default);
	}

	.card-link:hover .card-arrow-icon {
		transform: rotate(-30deg);
	}
</style>
