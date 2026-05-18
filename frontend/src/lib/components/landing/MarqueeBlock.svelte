<script lang="ts">
	const items = [
		'Which niche is worth entering?',
		'Where is demand hiding?',
		'What problems are people paying to solve?',
		'Which market has room for a new player?',
		"Where's the gap nobody's filling?",
		'Which idea deserves my weekends?',
		'Will they actually pay for this?',
		'How big can this get?',
	];

	const track = [...items, ...items, ...items];
</script>

<div class="marquee-wrapper relative" aria-hidden="true">
	<div class="marquee-fade-left"></div>
	<div class="marquee-fade-right"></div>

	<div class="marquee-track">
		{#each track as item}
			<span class="marquee-item">
				<img src="/landing/logo-mark.svg" alt="" class="marquee-mark" aria-hidden="true" />
				{item}
			</span>
		{/each}
	</div>
</div>

<style>
	.marquee-wrapper {
		width: 100%;
		overflow: hidden;
		background: var(--color-bg-elevated);
		padding: var(--space-5) 0;
		margin: calc(var(--space-20) * 1.5) 0;
	}

	@media (max-width: 640px) {
		.marquee-wrapper {
			margin: 0;
		}
	}

	.marquee-fade-left,
	.marquee-fade-right {
		position: absolute;
		top: 0;
		width: 120px;
		height: 100%;
		z-index: 2;
		pointer-events: none;
	}
	.marquee-fade-left {
		left: 0;
		background: linear-gradient(to right, var(--color-bg-elevated), transparent);
	}
	.marquee-fade-right {
		right: 0;
		background: linear-gradient(to left, var(--color-bg-elevated), transparent);
	}

	.marquee-track {
		display: flex;
		align-items: center;
		width: max-content;
		animation: marquee-scroll 40s linear infinite;
	}

	@keyframes marquee-scroll {
		from {
			transform: translateX(-33.333%);
		}
		to {
			transform: translateX(0);
		}
	}

	.marquee-item {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		white-space: nowrap;
		padding: 0 var(--space-5);
		font-size: var(--text-base);
		font-weight: var(--font-medium);
		color: var(--color-text-secondary);
		text-transform: uppercase;
	}

	.marquee-mark {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
		opacity: 0.5;
	}

	.marquee-wrapper:hover .marquee-track {
		animation-play-state: paused;
	}

	@media (prefers-reduced-motion: reduce) {
		.marquee-track {
			animation: none;
			transform: translateX(-33.333%);
		}
	}
</style>
