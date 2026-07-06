<section class="relative section" id="how-it-works">
	<div class="landing-container">
		<div class="landing-section-header-wrap">
			<div class="landing-section-label-row">
				<span class="landing-section-label">HOW IT WORKS · 3 STEPS</span>
			</div>
			<h2 class="landing-section-h2">
				From <span style="color:var(--color-accent)">noise</span> to validated ideas
			</h2>
			<p class="landing-section-subtitle">
				NicheIQ scans thousands of real conversations, scores real pain points, and turns them into
				data-backed ranked business ideas — so you know exactly what to build and how to profit.
			</p>
		</div>

		<div class="steps-list">
			<div class="step-row">
				<div class="step-text">
					<span class="step-num">01 · DISCOVER</span>
					<h3 class="step-heading">Stop guessing what people want</h3>
					<p class="step-body">
						We scan Reddit, Hacker News and more — every pain point linked to a real public
						discussion you can verify.
					</p>
				</div>
				<div class="step-img-wrap">
					<img src="/landing/pic_1.png" alt="" class="step-placeholder" />
				</div>
			</div>

			<div class="step-row reverse">
				<div class="step-text">
					<span class="step-num">02 · CHOOSE</span>
					<h3 class="step-heading">Pick the idea worth your evenings</h3>
					<p class="step-body">
						5–10 solution ideas scored by market fit, feasibility and SEO potential. Ranked, not
						random.
					</p>
				</div>
				<div class="step-img-wrap">
					<img src="/landing/pic_2.png" alt="" class="step-placeholder" />
				</div>
			</div>

			<div class="step-row">
				<div class="step-text">
					<span class="step-num">03 · DECIDE</span>
					<h3 class="step-heading">Ship with confidence</h3>
					<p class="step-body">
						Know your market, competition, SEO strategy, tech blueprint and revenue potential. Know
						if it's worth building. In under an hour.
					</p>
				</div>
				<div class="step-img-wrap">
					<img src="/landing/pic_3.png" alt="" class="step-placeholder" />
				</div>
			</div>
		</div>

		<div style="text-align:center; margin-top:var(--space-12);">
			<a href="/sample-report" class="landing-btn-pill-secondary">See a real report</a>
		</div>
	</div>
</section>

<style>
	.steps-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-20);
	}

	.step-row {
		display: grid;
		grid-template-columns: 1fr 1.55fr;
		gap: var(--space-16);
		align-items: center;
	}

	.step-row.reverse {
		grid-template-columns: 1.35fr 1fr;
	}

	.step-row.reverse .step-text {
		order: 2;
	}
	.step-row.reverse .step-img-wrap {
		order: 1;
	}

	.step-num {
		display: inline-block;
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		font-weight: var(--font-semibold);
		letter-spacing: 0.08em;
		color: var(--color-accent);
		margin-bottom: var(--space-3);
	}

	.step-heading {
		font-size: var(--text-2xl);
		font-weight: var(--font-bold);
		line-height: var(--leading-tight);
		color: var(--color-text-primary);
		margin-bottom: var(--space-4);
	}

	.step-body {
		font-size: var(--text-base);
		line-height: var(--leading-relaxed);
		color: var(--color-text-secondary);
	}

	.step-placeholder {
		width: 100%;
		display: block;
	}

	@media (max-width: 768px) {
		.step-row,
		.step-row.reverse {
			grid-template-columns: 1fr;
			gap: var(--space-8);
		}

		.step-row.reverse .step-text {
			order: 1;
		}
		.step-row.reverse .step-img-wrap {
			order: 2;
		}
	}
</style>
