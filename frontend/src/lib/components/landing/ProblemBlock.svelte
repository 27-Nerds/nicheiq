<script lang="ts">
	const cards = [
		{
			label: 'PROBLEM 01',
			stat: '65%',
			statLabel: 'of founders',
			title: 'Too many ideas, zero clarity',
			accent: true,
		},
		{
			label: 'PROBLEM 02',
			stat: '$3K+',
			statLabel: 'avg. research cost',
			title: 'Traditional research is slow & expensive',
			accent: false,
		},
		{
			label: 'PROBLEM 03',
			stat: '42%',
			statLabel: 'fail — no demand',
			title: 'Building what nobody wants',
			accent: false,
		},
		{
			label: 'PROBLEM 04',
			stat: '90%',
			statLabel: 'never find first 100<br>users',
			title: 'No customers on day one',
			accent: false,
		},
	];
</script>

<section class="relative section" id="problem">
	<div class="landing-container">
		<div class="landing-section-header-wrap">
			<div class="landing-section-label-row">
				<span class="landing-section-dot"></span>
				<span class="landing-section-label">The Problem Space</span>
			</div>
			<h2 class="landing-section-h2">Four walls every founder hits</h2>
		</div>

		<div class="cards-grid">
			{#each cards as card}
				<div class="problem-card" class:problem-card--accent={card.accent}>
					<div class="card-body">
						<span class="card-label" class:card-label--accent={card.accent}>{card.label}</span>

						<div class="card-stat-row">
							<span class="card-stat" class:card-stat--accent={card.accent}>{card.stat}</span>
							{#if card.statLabel}
								<span class="card-stat-sub" class:card-stat-sub--accent={card.accent}
									>{@html card.statLabel}</span
								>
							{/if}
						</div>

						<p class="card-title" class:card-title--accent={card.accent}>{card.title}</p>
					</div>
				</div>
			{/each}
		</div>
	</div>
</section>

<style>
	.cards-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: var(--space-4);
	}

	@media (max-width: 1024px) {
		.cards-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 600px) {
		.cards-grid {
			grid-template-columns: 1fr;
		}
	}

	.problem-card {
		position: relative;
		border-radius: var(--radius-xl);
		border: none;
		padding: var(--space-8);
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
		min-width: 0;
		background: var(--color-bg-surface);
		color: var(--color-text-primary);
	}
	.problem-card--accent {
		background: linear-gradient(145deg, var(--color-accent-light), var(--color-accent));
		color: #fff;
	}

	.card-body {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.card-label {
		font-size: var(--text-xs);
		font-weight: var(--font-semibold);
		letter-spacing: var(--tracking-widest);
		color: var(--color-accent);
		font-family: var(--font-mono);
		text-transform: uppercase;
		margin-bottom: 30px;
	}
	.card-label--accent {
		color: rgba(255, 255, 255, 0.75);
	}

	.card-stat-row {
		display: flex;
		align-items: flex-end;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
	.card-stat {
		font-size: clamp(2.5rem, 5vw, 3rem);
		font-weight: var(--font-medium);
		line-height: var(--leading-none);
		letter-spacing: var(--tracking-tight);
		color: #828282;
	}
	.card-stat--accent {
		color: #fff;
	}

	.card-stat-sub {
		font-size: var(--text-sm);
		line-height: 14px;
		color: var(--color-text-muted);
	}
	.card-stat-sub--accent {
		color: rgba(255, 255, 255, 0.75);
	}

	.card-title {
		font-size: var(--text-xl);
		font-weight: var(--font-semibold);
		line-height: 20px;
		color: var(--color-accent);
		margin: 0;
	}
	.card-title--accent {
		color: #fff;
	}
</style>
