<script lang="ts">
	import { onMount } from 'svelte';
	import { Globe, Database, Layers, FileText, X, Check, ArrowRight } from 'lucide-svelte';

	let isVisible = $state(false);
	let activeTab = $state(0);

	onMount(() => {
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					isVisible = true;
				}
			},
			{ threshold: 0.2 }
		);

		const section = document.getElementById('why-not-chatgpt');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	const problems = [
		{
			icon: Globe,
			title: 'Web Search ≠ Direct Access',
			problem: "Deep Research tools search the open web, finding indexed pages",
			competitor: 'Perplexity/Grok: Searches web for indexed social pages',
			nicheiq: 'Direct community access: real-time posts, comments, engagement data',
			detail: 'Perplexity and Grok can only find what Google indexes. NicheIQ connects directly to social platforms, accessing discussions, engagement metrics, and timestamps that web crawlers miss.'
		},
		{
			icon: Layers,
			title: 'General vs. Specialized',
			problem: "AI research tools answer any question with no structure",
			competitor: 'ChatGPT/Perplexity: "Based on my analysis..." (open-ended)',
			nicheiq: '16-stage SaaS validation pipeline with defined outputs',
			detail: 'Deep Research tools are general-purpose. NicheIQ is purpose-built for SaaS validation: pain points → solutions → keywords → competitors → SEO strategy.'
		},
		{
			icon: Database,
			title: 'Estimates vs. Real Data',
			problem: "AI tools estimate metrics instead of validating them",
			competitor: 'Grok/ChatGPT: "This keyword likely gets high search volume"',
			nicheiq: 'Real data: 5,400 searches/mo - Competition: 0.43',
			detail: 'When Perplexity says a keyword is "popular," it\'s guessing. When NicheIQ says 5,400 searches/month, that\'s real keyword data you can verify.'
		},
		{
			icon: FileText,
			title: 'Chat vs. Professional Report',
			problem: "Conversational back-and-forth instead of structured deliverables",
			competitor: 'Deep Research: 3-minute chat response you copy/paste',
			nicheiq: 'Structured 34-field report with visualizations & source links',
			detail: 'Chat responses require manual organization. NicheIQ delivers a professional report: executive summary, competitive analysis, SEO strategy, and GTM blueprint.'
		}
	];
</script>

<section id="why-not-chatgpt" class="section-alt">
	<div class="max-w-6xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header -->
			<div class="mb-16">
				<span class="section-label animate-fade-in">The Gap</span>
				<h2 class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6">
					What AI Research Tools <span class="text-gradient italic">Miss</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl">
					Perplexity, Grok, ChatGPT—they're powerful, but they can't access real data sources or validate your market.
				</p>
			</div>

			<!-- Problem Grid -->
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-16">
				{#each problems as problem, i}
					<button
						class="animate-fade-in text-left w-full group"
						style="animation-delay: {200 + i * 100}ms"
						onclick={() => (activeTab = i)}
					>
						<div
							class="p-6 lg:p-8 rounded-xl border transition-all duration-200 h-full
							{activeTab === i
								? 'bg-bg-surface border-border-accent shadow-glow'
								: 'bg-bg-elevated border-border hover:border-border-emphasis'}"
						>
							<div class="flex items-start gap-5">
								<div class="flex-shrink-0 w-12 h-12 rounded-lg flex items-center justify-center border transition-colors
									{activeTab === i ? 'bg-accent/10 border-border-accent' : 'bg-bg-surface border-border'}">
									<problem.icon class="w-6 h-6 {activeTab === i ? 'text-accent' : 'text-text-muted'}" />
								</div>

								<div class="flex-1">
									<h3 class="font-display font-semibold text-xl text-text-primary mb-2">
										{problem.title}
									</h3>
									<p class="text-sm text-text-muted mb-5">{problem.problem}</p>

									<!-- Comparison -->
									<div class="space-y-4">
										<div class="flex items-start gap-3">
											<div class="flex-shrink-0 w-5 h-5 rounded-full bg-error/10 border border-error/50 flex items-center justify-center mt-0.5">
												<X class="w-3 h-3 text-error" />
											</div>
											<div>
												<span class="text-xs text-error font-semibold uppercase tracking-wider">Deep Research</span>
												<p class="text-sm text-text-muted font-mono mt-1">{problem.competitor}</p>
											</div>
										</div>

										<div class="flex items-start gap-3">
											<div class="flex-shrink-0 w-5 h-5 rounded-full bg-success/10 border border-success/50 flex items-center justify-center mt-0.5">
												<Check class="w-3 h-3 text-success" />
											</div>
											<div>
												<span class="text-xs text-success font-semibold uppercase tracking-wider">NicheIQ</span>
												<p class="text-sm text-text-secondary font-mono mt-1">{problem.nicheiq}</p>
											</div>
										</div>
									</div>
								</div>
							</div>
						</div>
					</button>
				{/each}
			</div>

			<!-- Expanded Detail -->
			<div class="animate-fade-in delay-500 max-w-3xl mx-auto">
				<div class="p-6 rounded-xl bg-bg-surface border border-border-accent">
					<p class="text-lg text-text-secondary italic leading-relaxed">
						"{problems[activeTab].detail}"
					</p>
				</div>
			</div>

			<!-- Bottom Quote -->
			<div class="animate-fade-in delay-500 text-center mt-12">
				<div class="divider max-w-xs mx-auto"></div>
				<p class="text-text-muted italic text-lg mt-8">
					"Deep Research tools search the web. NicheIQ validates with APIs."
				</p>
			</div>
		{/if}
	</div>
</section>
