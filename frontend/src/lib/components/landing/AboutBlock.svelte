<section
	class="relative section about-section"
	id="about"
	style="background: var(--color-bg-surface); padding-top: var(--space-30); padding-bottom: var(--space-30);"
>
	<div class="landing-container">
		<div class="about-grid">
			<!-- Text column -->
			<div class="about-text">
				<div class="landing-section-label-row" style="margin-bottom: var(--space-6);">
					<span class="landing-section-label">WHY WE BUILT THIS</span>
				</div>
				<h2 class="landing-section-h2" style="margin-bottom: var(--space-8);">
					We're founders too.<br />
					<span style="color: var(--color-text-muted);">We know exactly how this feels</span>
				</h2>
				<div class="about-body">
					<p>Too many ideas, zero clarity.</p>
					<p>
						Ready to ship but need proof. No time for weeks of research. Scared to build the wrong
						thing. Tired of manually scrolling Reddit at midnight.
					</p>
					<p>
						<strong>So we built the tool we wished existed.</strong> NicheIQ is what we used to do by
						hand — automated, in under an hour.
					</p>
					<p>Built for founders who think win-win — great product for users, real profit for you.</p>
				</div>
			</div>

			<!-- Photos column -->
			<div class="about-photos">
				<!-- Right photo -->
				<div class="photo-right">
					<img src="/landing/l.png" alt="" class="photo-right-img" />
					<div class="photo-right-caption">
						<span class="photo-right-name">Liudmyla Hnatchuk</span>
						<span class="photo-right-role">CEO &amp; Co-founder</span>
					</div>
				</div>

				<!-- Left photo -->
				<div class="photo-wrap-left">
					<div class="photo-left">
						<img src="/landing/v.png" alt="" class="photo-left-img" />
						<div class="photo-left-caption">
							<span class="photo-left-name">Victor Rybuch</span>
							<span class="photo-left-role">CTO &amp; Co-founder</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</section>

<style>
	.about-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-20);
		align-items: center;
	}

	.about-body {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.about-body p {
		font-size: var(--text-base);
		line-height: var(--leading-relaxed);
		color: var(--color-text-secondary);
	}

	/* --- photos container --- */
	.about-photos {
		position: relative;
		height: 460px;
	}

	/* ── Right photo (Liudmyla) ── */
	.photo-right {
		position: absolute;
		bottom: 10px;
		right: 0;
		width: 56%;
		aspect-ratio: 3 / 4;
		border-radius: var(--radius-xl);
		overflow: hidden;
		border: 4px solid var(--color-bg-elevated);
		transform: rotate(3deg);
		transition: transform var(--duration-normal) var(--ease-default);
		z-index: 4;
	}

	.photo-right:hover {
		transform: translateY(-12px) scale(1.06);
		z-index: 5;
	}

	.photo-right-img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.photo-right-caption {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: var(--space-6) var(--space-4) var(--space-4);
		background: linear-gradient(to top, rgba(0, 0, 0, 0.72) 0%, transparent 100%);
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.photo-right-name {
		font-family: var(--font-display);
		font-size: var(--text-sm);
		font-weight: var(--font-semibold);
		color: #fff;
		line-height: var(--leading-tight);
	}

	.photo-right-role {
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		color: rgba(255, 255, 255, 0.6);
		letter-spacing: var(--tracking-wide);
	}

	/* ── Left photo (Victor) ── */
	.photo-wrap-left {
		position: absolute;
		bottom: 0;
		left: 0;
		width: 56%;
		aspect-ratio: 3 / 4;
		z-index: 1;
	}

	.photo-wrap-left:hover {
		z-index: 4;
	}

	.photo-left {
		width: 100%;
		height: 100%;
		border-radius: var(--radius-xl);
		overflow: hidden;
		border: 4px solid var(--color-bg-elevated);
		transform: rotate(-2deg);
		transition: transform var(--duration-normal) var(--ease-default);
	}

	.photo-wrap-left:hover .photo-left {
		transform: translateY(-12px) scale(1.06);
	}

	.photo-left-img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.photo-left-caption {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: var(--space-6) var(--space-4) var(--space-4);
		background: linear-gradient(to top, rgba(0, 0, 0, 0.72) 0%, transparent 100%);
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.photo-left-name {
		font-family: var(--font-display);
		font-size: var(--text-sm);
		font-weight: var(--font-semibold);
		color: #fff;
		line-height: var(--leading-tight);
	}

	.photo-left-role {
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		color: rgba(255, 255, 255, 0.6);
		letter-spacing: var(--tracking-wide);
	}

	@media (max-width: 768px) {
		.about-grid {
			grid-template-columns: 1fr;
			gap: var(--space-12);
		}

		.about-photos {
			height: 380px;
		}
	}
</style>
