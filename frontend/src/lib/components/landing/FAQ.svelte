<script lang="ts">
	import { onMount } from 'svelte';
	import { Accordion } from './ui';

	let isVisible = $state(false);

	onMount(() => {
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					isVisible = true;
				}
			},
			{ threshold: 0.1 }
		);

		const section = document.getElementById('faq');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	// Optimized FAQs: Trust first, consolidated competitor question, common objections
	const faqs = [
		{
			question: "Can I trust the numbers? Or is this AI hallucinating?",
			answer:
				"No hallucinations. 80% of your report is real data from APIs—keyword volumes, source discussions, engagement metrics. Every pain point links to a specific Reddit post with post ID, upvote count, and timestamp. Click through and verify it yourself. The hybrid architecture uses 80% programmatic data assembly (zero hallucination) and only 20% LLM synthesis. The data comes from APIs, not AI imagination."
		},
		{
			question: "Can't I just use ChatGPT, Perplexity, or Grok?",
			answer:
				"Better prompts improve output, but they can't solve architectural limitations. No AI chat tool has direct access to social platforms, real-time keyword APIs, or live community discussions. ChatGPT uses training data (months old). Perplexity crawls indexed pages (misses real-time posts). Grok excels at X/Twitter but can't access Reddit. NicheIQ connects directly to APIs for current data with source attribution on every claim."
		},
		{
			question: 'How long does research take?',
			answer:
				'Typically around 45 minutes. The system autonomously searches social media, extracts pain points, calculates market sizing, validates pricing, and compiles your report. You submit your niche and wait while the 16-stage pipeline runs.'
		},
		{
			question: 'How do you calculate market size and pricing?',
			answer:
				"Market sizing (TAM/SAM/SOM) uses real keyword search volumes from DataForSEO API - actual search demand, not AI estimates. Pricing recommendations combine competitor analysis (what similar tools charge) with willingness-to-pay signals from customer discussions. The report shows methodology so you can analyze the numbers."
		},
		{
			question: 'Can I get a refund?',
			answer:
				"Yes. If your report doesn't deliver at least 5 validated pain points with verifiable sources, you get a full refund. Email support@nicheiq.com within 7 days with your report ID."
		},
		{
			question: 'What if my niche is too specialized?',
			answer:
				"NicheIQ works best when there's active social discussion about your niche. Consumer SaaS, developer tools, and creator tools typically have great coverage. For highly specialized B2B niches, you might get fewer data points. The guarantee still applies: less than 5 validated pain points means a full refund."
		},
		{
			question: 'What if the research says my idea is bad?',
			answer:
				"A 'no' is valuable data. If research shows weak pain points or saturated competition, you just saved months of building the wrong thing. Think of it as $19 insurance against building something nobody wants. Most founders who get 'negative' results tell us it was their best $19 spent - they pivoted to a better opportunity."
		},
		{
			question: 'Can I run multiple researches?',
			answer:
				"Yes - pay per research report. Explore as many niches as you want. This is NicheIQ's strength: fast research means you can explore 5 niches in an afternoon instead of committing months to one. Most founders use it to narrow down from several niches to their best opportunity."
		},
		{
			question: 'Do you store my research data?',
			answer:
				"We store your reports for your account access only. Your research is 100% private - no shared database, no data sharing between customers, no marketing use of your niche ideas. NicheIQ is a tool, not a marketplace. Your research stays your competitive advantage."
		}
	];
</script>

<section id="faq" class="section-alt">
	<div class="max-w-3xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header -->
			<div class="text-center mb-16">
				<span class="section-label animate-fade-in">FAQ</span>
				<h2 class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6">
					Common <span class="text-gradient italic">Questions</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full mx-auto animate-fade-in delay-200"></div>
			</div>

			<!-- FAQ Items - Dark Accordion Style -->
			<div class="animate-fade-in delay-300 border-t border-border">
				{#each faqs as faq}
					<Accordion title={faq.question}>
						<p>{faq.answer}</p>
					</Accordion>
				{/each}
			</div>

			<!-- Contact CTA -->
			<div class="animate-fade-in delay-400 mt-12 text-center">
				<div class="divider max-w-xs mx-auto mb-8"></div>
				<p class="text-text-muted">
					Still have questions?
					<a href="mailto:hello@nicheiq.com" class="text-accent hover:text-accent-hover hover:underline font-medium transition-colors">
						Contact us
					</a>
				</p>
			</div>
		{/if}
	</div>
</section>
