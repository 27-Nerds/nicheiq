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

	// Focused FAQs: Trust/verification first, then common objections
	const faqs = [
		{
			question: "How do I know the AI isn't making this up?",
			answer:
				"Every pain point in your report links to a specific Reddit post with post ID, upvote count, and timestamp. Click through and verify it yourself. Our hybrid architecture uses 80% programmatic data assembly (zero hallucination) and only 20% LLM synthesis. The data comes from APIs, not AI imagination."
		},
		{
			question: "How is this different from Perplexity Deep Research?",
			answer:
				"Perplexity searches the open web for indexed social pages. NicheIQ connects directly to social platforms, accessing real-time posts, comments, and engagement data that web crawlers miss. Plus, we validate keywords with real search APIs - actual volumes, not estimates. And you get a structured 34-field report, not chat responses."
		},
		{
			question: "Why not just use Grok's DeepSearch?",
			answer:
				"Grok excels at X/Twitter research but can't access other social platforms directly. NicheIQ is purpose-built for SaaS validation: community pain points + real keyword data + competitive analysis in one structured report. Grok gives you chat responses; NicheIQ gives you a professional validation report."
		},
		{
			question: "Can't I just use ChatGPT with better prompts?",
			answer:
				"Better prompts improve output quality, but they can't solve architectural limitations. No prompt can give ChatGPT direct access to social platforms, real-time keyword data from search APIs, or live community discussions. It's not a prompting problem - it's a data access problem. NicheIQ has these integrations built-in."
		},
		{
			question: 'How long does research take?',
			answer:
				'Typically 10-15 minutes. The system autonomously searches social media, extracts pain points, calculates market sizing, validates pricing, and compiles your report. You submit your niche and wait while the 16-stage pipeline runs.'
		},
		{
			question: 'How do you calculate market size?',
			answer:
				'We calculate TAM (Total Addressable Market), SAM (Serviceable Addressable Market), and SOM (Serviceable Obtainable Market) using real keyword search volumes and market data. These are data-driven estimates based on actual search demand, not AI guesses. The report shows the methodology so you can verify the numbers.'
		},
		{
			question: 'Where does pricing data come from?',
			answer:
				'Pricing recommendations are based on two sources: competitor pricing analysis (what similar tools charge) and willingness-to-pay signals extracted from real customer discussions. We look at what people say they would pay, what they complain about current pricing, and map it against the competitive landscape.'
		},
		{
			question: 'Can I get a refund?',
			answer:
				"Yes - Zero-Risk Research Guarantee. If your report doesn't deliver at least 5 validated pain points with verifiable sources, we refund 100% plus a $25 Amazon gift card for your time. Email support@nicheiq.com within 48 hours with your report ID."
		},
		{
			question: 'What if my niche is too specialized?',
			answer:
				"NicheIQ works best when there's active social discussion about your niche. Consumer SaaS, developer tools, and creator tools typically have great coverage. For highly specialized B2B niches, you might get fewer data points. Our guarantee covers this: less than 5 validated pain points = full refund + $25."
		},
		{
			question: 'What formats do reports come in?',
			answer:
				'Reports are delivered as structured JSON (for programmatic use) with optional PDF export (human-readable). The JSON includes all 34+ data fields including pain points, solutions, keywords, competitive analysis, and GTM blueprint.'
		},
		{
			question: 'Can competitors see my research?',
			answer:
				"No. Your research reports are 100% private. No shared database, no data sharing between customers, no marketing use of your niche ideas. We're a tool, not a marketplace."
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
