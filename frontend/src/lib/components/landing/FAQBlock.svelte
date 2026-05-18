<script lang="ts">
	import { slide } from 'svelte/transition';
	import { cubicInOut } from 'svelte/easing';

	let openFaq = $state<number | null>(null);

	const faqs = [
		{
			q: 'Can I trust the data — or is this AI hallucinating?',
			a: 'All data is sourced from real community discussions and public datasets. Every claim links to its source. Pain points link to real Reddit / Hacker News threads. Keywords come with real search volumes. AI is only used to find patterns — not to invent them. You can verify any insight before you act on it.',
		},
		{
			q: 'How is this different from ChatGPT or Perplexity?',
			a: 'General AI tools give you plausible-sounding text. NicheIQ gives you scored, source-cited analysis built for SaaS validation — with a proprietary pain scoring system.<br><br>Every comment is weighted by functional impact, not emotional volume. "I hate this UI" scores low. "We lost 3 clients because of this" scores high.<br><br>Each comment gets its own score across three dimensions:<br>— Severity<br>— Willingness to pay<br>— Opportunity<br><br>The key principle: functional impact over emotional volume.',
		},
		{
			q: 'What if my niche is too specialized?',
			a: 'Niche is actually better. The more specific your topic, the more signal-dense the community data tends to be. Very broad markets (e.g. "productivity") are harder to validate than specific ones.',
		},
		{
			q: 'What if I get a NO-GO verdict?',
			a: "A NO-GO is actually valuable. It tells you exactly where the gaps are and which adjacent niches have stronger signals. You just saved weeks of wasted effort building the wrong thing.",
		},
		{
			q: 'Can I run multiple researches?',
			a: 'Yes. Credits never expire — buy them in bulk and use them on your schedule. Each research is independent, so you can validate multiple ideas side by side.',
		},
		{
			q: 'Do you store my research data?',
			a: "Your reports are private to your account. We don't sell or share your data with anyone. You can download and delete your reports at any time.",
		},
	];

	const splitIdx = Math.ceil(faqs.length / 2);
</script>

<section id="faq" class="relative section" style="background: var(--color-bg-elevated);">
	<div class="landing-container">
		<div class="landing-section-header-wrap">
			<div class="landing-section-label-row">
				<span class="landing-section-dot"></span>
				<span class="landing-section-label">F.A.Q</span>
			</div>
			<h2 class="landing-section-h2 faq-h2">Any questions?<br />We've got answers</h2>
			<p class="landing-section-subtitle">
				We asked our early founders what held them back before their first report.
			</p>
		</div>

		<div class="faq-grid">
			{#each [faqs.slice(0, splitIdx), faqs.slice(splitIdx)] as col, colIdx}
				<div class="faq-col">
					{#each col as item, i}
						{@const idx = colIdx * splitIdx + i}
						{@const open = openFaq === idx}
						<div class="faq-item">
							<button
								onclick={() => (openFaq = open ? null : idx)}
								class="faq-trigger"
								aria-expanded={open}
								aria-controls={`faq-answer-${idx}`}
							>
								<span class="faq-question">{item.q}</span>
								<svg
									class="faq-chevron"
									class:faq-chevron--open={open}
									fill="none"
									stroke="currentColor"
									stroke-width="1.75"
									viewBox="0 0 24 24"
									aria-hidden="true"
								>
									<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
								</svg>
							</button>
							{#if open}
								<div
									id={`faq-answer-${idx}`}
									transition:slide={{ duration: 240, easing: cubicInOut }}
									class="faq-answer"
								>
									{@html item.a}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/each}
		</div>
	</div>
</section>

<style>
	.faq-h2 {
		font-weight: var(--font-medium);
	}

	.faq-grid {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.faq-col {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	@media (min-width: 768px) {
		.faq-grid {
			flex-direction: row;
		}
		.faq-col {
			flex: 1;
		}
	}

	.faq-item {
		background: var(--color-bg-surface);
		border-radius: var(--radius-2xl);
		overflow: hidden;
	}

	.faq-trigger {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-5);
		padding: var(--space-6);
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font-family: inherit;
	}

	.faq-trigger:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: -2px;
	}

	.faq-question {
		font-size: 1.125rem;
		font-weight: var(--font-bold);
		color: var(--color-text-primary);
		line-height: var(--leading-snug);
	}

	.faq-chevron {
		width: 1.125rem;
		height: 1.125rem;
		flex-shrink: 0;
		color: var(--color-text-muted);
		transition: transform var(--duration-normal) var(--ease-default);
	}

	.faq-chevron--open {
		transform: rotate(180deg);
	}

	.faq-answer {
		padding: 0 var(--space-6) var(--space-6);
		font-size: var(--text-sm);
		line-height: var(--leading-relaxed);
		color: var(--color-text-secondary);
	}
</style>
