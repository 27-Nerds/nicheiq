<script lang="ts">
	let activeTab = $state(0);

	// Facade pattern: show a thumbnail + custom play button at rest (no YouTube
	// chrome, no player JS loaded). The real iframe mounts only after a click.
	// Reset to the facade whenever the user switches tabs.
	let playing = $state(false);

	const tabs = [
		{
			label: 'Research',
			videoId: 'YyHB-DlPcEI',
			icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`,
		},
		{
			label: 'Niche Catalog',
			videoId: '3IzhDAJbV5A',
			icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
		},
		{
			label: 'My Reports',
			videoId: 'HoUMFQr2rc4',
			icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
		},
	];
</script>

<section
	class="relative section demo-section overflow-hidden"
	style="background: #fff; padding-top: var(--space-3)"
>
	<div class="relative landing-container">
		<div
			class="demo-card"
			style="
				border-radius: 40px;
				background:
					radial-gradient(ellipse 70% 100% at 0% 50%, rgba(234, 88, 12, 0.10) 0%, transparent 55%),
					radial-gradient(ellipse 70% 100% at 100% 50%, rgba(99, 102, 241, 0.14) 0%, transparent 55%),
					#f0f0f6;
				box-shadow: 0 2px 24px rgba(0,0,0,.06);
				padding: 1.5rem 5rem 1.5rem;
			"
		>
			<div class="tab-bar" role="tablist">
				{#each tabs as tab, i}
					<button
						class="tab-item"
						class:tab-active={activeTab === i}
						onclick={() => {
							activeTab = i;
							playing = false;
						}}
						role="tab"
						aria-selected={activeTab === i}
					>
						{@html tab.icon}
						{tab.label}
					</button>
				{/each}
			</div>

			<div
				style="
					border-radius: 20px;
					overflow: hidden;
					border: 1px solid var(--color-border-emphasis);
					box-shadow:
						0 24px 60px rgba(0,0,0,.18),
						0 6px 16px rgba(0,0,0,.1);
				"
			>
				<div style="position:relative; padding-bottom:56.25%; height:0; overflow:hidden;">
					{#if playing}
						<iframe
							src={`https://www.youtube-nocookie.com/embed/${tabs[activeTab].videoId}?autoplay=1&rel=0&playsinline=1`}
							title={`${tabs[activeTab].label} demo`}
							allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
							allowfullscreen
							style="position:absolute; top:0; left:0; width:100%; height:100%; border:0; display:block"
						></iframe>
					{:else}
						<button
							type="button"
							class="video-facade"
							onclick={() => (playing = true)}
							aria-label={`Play ${tabs[activeTab].label} demo`}
						>
							<img
								src={`https://i.ytimg.com/vi_webp/${tabs[activeTab].videoId}/maxresdefault.webp`}
								onerror={(e) =>
									((e.currentTarget as HTMLImageElement).src = `https://i.ytimg.com/vi/${tabs[activeTab].videoId}/maxresdefault.jpg`)}
								alt=""
								loading="lazy"
							/>
							<span class="play-overlay" aria-hidden="true">
								<svg width="30" height="30" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
							</span>
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
</section>

<style>
	.tab-bar {
		display: flex;
		align-items: center;
		gap: 4px;
		width: fit-content;
		margin: 0 auto 1.5rem;
		white-space: nowrap;
	}

	.tab-item {
		display: flex;
		align-items: center;
		gap: 7px;
		padding: 8px 20px;
		border-radius: 999px;
		border: none;
		background: transparent;
		color: var(--color-text-primary);
		font-size: var(--text-base);
		font-weight: var(--font-medium);
		font-family: inherit;
		cursor: pointer;
		transition: background var(--duration-fast) var(--ease-default);
		white-space: nowrap;
	}

	.tab-item:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	.tab-item:hover:not(.tab-active) {
		background: rgba(255, 255, 255, 0.7);
	}

	.tab-active {
		background: rgba(255, 255, 255, 0.5);
	}

	.video-facade {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		padding: 0;
		border: 0;
		background: #000;
		cursor: pointer;
		display: block;
	}

	.video-facade img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.play-overlay {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		display: flex;
		align-items: center;
		justify-content: center;
		width: 72px;
		height: 72px;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.55);
		color: #fff;
		padding-left: 4px;
		transition:
			background var(--duration-fast) var(--ease-default),
			transform var(--duration-fast) var(--ease-default);
	}

	.video-facade:hover .play-overlay,
	.video-facade:focus-visible .play-overlay {
		background: var(--color-accent);
		transform: translate(-50%, -50%) scale(1.06);
	}

	.video-facade:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	@media (max-width: 640px) {
		.demo-card {
			padding: 1rem !important;
			border-radius: 20px !important;
		}
		.demo-section {
			padding-bottom: var(--space-8) !important;
		}
		.tab-bar {
			width: 100%;
			justify-content: center;
		}
		.tab-item {
			padding: 7px 12px;
			font-size: var(--text-sm);
		}
	}
</style>
