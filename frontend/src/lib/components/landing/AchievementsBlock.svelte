<script lang="ts">
	import { onMount } from 'svelte';
	import { formatCompact } from '$lib/utils/format-numbers';

	interface Props {
		reportsDelivered?: number | null;
		commentsAnalyzed?: number | null;
		subNiches?: number | null;
	}

	let { reportsDelivered = null, commentsAnalyzed = null, subNiches = null }: Props = $props();

	type Stat = { value: number; suffix: string; title: string };

	const tiles = $derived.by<Stat[]>(() => {
		const out: Stat[] = [];
		if (typeof reportsDelivered === 'number' && reportsDelivered > 0) {
			out.push({ value: reportsDelivered, suffix: '+', title: 'Reports run' });
		}
		if (typeof commentsAnalyzed === 'number' && commentsAnalyzed > 0) {
			out.push({ value: commentsAnalyzed, suffix: '', title: 'Comments analyzed' });
		}
		if (typeof subNiches === 'number' && subNiches > 0) {
			out.push({ value: subNiches, suffix: '', title: 'Sub-niches' });
		}
		return out;
	});

	// SSR-final values; client may overwrite on view to animate from 0.
	let displayed = $state<number[]>([]);
	$effect(() => {
		displayed = tiles.map((t) => t.value);
	});

	let sectionEl: HTMLElement | undefined = $state();
	let animated = false;

	function animateCounters() {
		if (animated) return;
		animated = true;

		// Respect reduced-motion: leave SSR final values untouched.
		if (
			typeof window !== 'undefined' &&
			window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
		) {
			return;
		}

		tiles.forEach((tile, index) => {
			const duration = 1800;
			const start = performance.now();
			displayed[index] = 0;

			function update(currentTime: number) {
				const elapsed = currentTime - start;
				const progress = Math.min(elapsed / duration, 1);
				const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
				displayed[index] = Math.floor(tile.value * eased);
				if (progress < 1) {
					requestAnimationFrame(update);
				} else {
					displayed[index] = tile.value;
				}
			}

			requestAnimationFrame(update);
		});
	}

	onMount(() => {
		if (!sectionEl) return;
		const observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) animateCounters();
				});
			},
			{ threshold: 0.35 },
		);
		observer.observe(sectionEl);
		return () => observer.disconnect();
	});
</script>

{#if tiles.length > 0}
	<section class="relative section" id="achievements" bind:this={sectionEl}>
		<div class="landing-container">
			<div class="steps-box">
				<div
					class="landing-section-header-wrap"
					style="text-align: center;"
				>
					<div class="landing-section-label-row">
						<span class="landing-section-dot"></span>
						<span class="landing-section-label">ACHIEVEMENTS</span>
					</div>
					<h2 class="landing-section-h2" style="color: var(--color-text-primary);">
						The numbers founders care about
					</h2>
				</div>

				<div class="steps-grid" style={`grid-template-columns: repeat(${tiles.length}, 1fr);`}>
					{#each tiles as tile, i}
						<div class="step-item">
							<span
								class="step-image-wrap"
								style={i === 0
									? 'color: var(--color-accent)'
									: 'color: var(--color-text-secondary)'}
							>
								{formatCompact(displayed[i] ?? tile.value)}{tile.suffix}
							</span>
							<p class="step-title">{tile.title}</p>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</section>
{/if}

<style>
	.steps-box {
		background: var(--color-bg-surface);
		border-radius: var(--radius-2xl);
		padding: var(--space-12);
		margin-top: 40px;
	}

	.steps-grid {
		display: grid;
		background: white;
		border-radius: 24px;
		overflow: hidden;
		border: 1px solid rgba(0, 0, 0, 0.06);
		margin-top: var(--space-10);
	}

	.step-item {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		padding: 48px 32px;
		background: white;
	}

	.step-item:not(:last-child)::after {
		content: '';
		position: absolute;
		top: 0;
		right: 0;
		width: 1px;
		height: 100%;
		background: rgba(0, 0, 0, 0.08);
	}

	.step-image-wrap {
		font-size: clamp(3rem, 7vw, 5rem);
		font-weight: 700;
		line-height: 1;
		margin-bottom: 18px;
		letter-spacing: -0.04em;
		font-variant-numeric: tabular-nums;
	}

	.step-title {
		font-size: var(--text-base);
		line-height: var(--leading-relaxed);
		color: var(--color-text-secondary);
	}

	@media (max-width: 768px) {
		.steps-box {
			padding: var(--space-6);
		}
		.steps-grid {
			grid-template-columns: 1fr !important;
		}
		.step-item {
			padding: 40px 24px;
		}
		.step-item:not(:last-child)::after {
			content: '';
			position: absolute;
			top: auto;
			left: 24px;
			right: 24px;
			bottom: 0;
			width: auto;
			height: 1px;
			background: rgba(0, 0, 0, 0.08);
		}
	}
</style>
