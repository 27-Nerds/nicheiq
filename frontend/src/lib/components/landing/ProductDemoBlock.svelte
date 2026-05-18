<script lang="ts">
	let activeTab = $state(0);

	const tabs = [
		{
			label: 'Research',
			icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`,
		},
		{
			label: 'Niche Catalog',
			icon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
		},
		{
			label: 'My Reports',
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
						onclick={() => (activeTab = i)}
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
					<img
						src="/landing/video_placeholder_image.png"
						alt="Product demo preview"
						style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; display:block"
					/>
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
