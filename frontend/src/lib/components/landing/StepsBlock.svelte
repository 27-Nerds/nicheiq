<script lang="ts">
	const steps = [
		{
			number: '01',
			title: 'Scan Conversations',
			description:
				'AI analyzes Reddit, Hacker News, and more — pulled from real public discussions linked to verifiable threads.',
			image: '/landing/steps/image 93.png',
		},
		{
			number: '02',
			title: 'Score Demand',
			description: 'Each pain is ranked by frequency, urgency, and willingness to pay.',
			image: '/landing/steps/image 92.png',
		},
		{
			number: '03',
			title: 'Get Solutions',
			description:
				'Receive concrete product ideas with market size, competition analysis, and next steps.',
			image: '/landing/steps/image 91.png',
		},
	];
</script>

<section class="relative section" id="steps">
	<div class="landing-container">
		<div class="steps-box">
			<div
				class="landing-section-header-wrap"
				style="text-align: center;"
			>
				<div class="landing-section-label-row">
					<span class="landing-section-dot"></span>
					<span class="landing-section-label">Our approach</span>
				</div>
				<h2 class="landing-section-h2">
					Don't waste your time, money and energy on the wrong idea.
				</h2>
			</div>

			<div class="steps-grid">
				{#each steps as step}
					<div class="step-item">
						<div class="step-image-wrap">
							<img src={step.image} alt="" class="step-image" />
						</div>

						<h3
							style="
								font-size: var(--text-xl);
								font-weight: var(--font-bold);
								line-height: var(--leading-snug);
								color: var(--color-text-primary);
								margin-bottom: var(--space-4);
							">{step.title}</h3
						>

						<p
							style="
								font-size: var(--text-base);
								line-height: var(--leading-relaxed);
								color: var(--color-text-secondary);
							">{step.description}</p
						>
					</div>
				{/each}
			</div>
		</div>
	</div>
</section>

<style>
	.steps-box {
		background: var(--color-bg-surface);
		border-radius: var(--radius-2xl);
		padding: var(--space-12);
	}

	.steps-grid {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--space-8);
		align-items: start;
	}

	.step-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
	}

	.step-image-wrap {
		width: 100%;
		height: 130px;
		margin-bottom: var(--space-6);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.step-image {
		height: 100%;
		width: auto;
		object-fit: contain;
	}

	@media (max-width: 768px) {
		.steps-box {
			padding: var(--space-6);
		}
		.steps-grid {
			grid-template-columns: 1fr;
			gap: var(--space-8);
		}
	}
</style>
