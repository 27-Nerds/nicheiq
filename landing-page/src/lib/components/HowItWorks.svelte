<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import {
		Search,
		Target,
		MessageSquare,
		Lightbulb,
		TrendingUp,
		BarChart3,
		FileText,
		ChevronDown,
		MousePointer,
		Clock,
		Download,
		Cpu,
		Users,
		DollarSign,
		PieChart,
		Layout
	} from 'lucide-svelte';

	let isVisible = $state(false);
	let showStages = $state(false);
	let expandedStage = $state<number | null>(null);

	onMount(() => {
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					isVisible = true;
				}
			},
			{ threshold: 0.1 }
		);

		const section = document.getElementById('how-it-works');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	// Simple user steps - how to GET your report
	const userSteps = [
		{
			number: '1',
			icon: MousePointer,
			title: 'Enter Your Niche',
			time: '30 seconds',
			description: "Pick any niche you want to explore—we'll validate it"
		},
		{
			number: '2',
			icon: Cpu,
			title: 'NicheIQ Does Everything',
			time: '~12 minutes',
			description: 'Our AI system searches social communities, validates keywords, and analyzes your market'
		},
		{
			number: '3',
			icon: Download,
			title: 'Get Personal Business Blueprint',
			time: 'Instant download',
			description: 'Receive validated pain points, solution opportunities, SEO keywords, competitive analysis, and a clear go/no-go verdict — and more to build fast and generate revenue.'
		},
		{
			number: '4',
			icon: Layout,
			title: 'Ready-to-Launch Landing Page',
			time: 'Ready to use',
			description: 'You receive a fully built landing page that you can launch immediately to capture interest, leads, and potential orders'
		}
	];

	// Detailed stages - how the report is CREATED
	const stages = [
		{
			id: 1,
			name: 'Niche Validation',
			icon: Target,
			metric: '3-7 segments defined',
			description: 'Your niche idea gets refined into a precise market definition with specific customer segments.',
			details: 'AI structures your input into clear market boundaries, target segments (e.g., "Small e-commerce businesses with 10-50 employees"), and scope definitions.'
		},
		{
			id: 2,
			name: 'Search & Discover',
			icon: Search,
			metric: '89+ discussions found',
			description: 'Autonomously searches social media and online communities for real discussions about your niche.',
			details: 'Direct access to communities, discussions, and engagement data. 3-layer filtering: relevance validation, engagement quality, deduplication.'
		},
		{
			id: 3,
			name: 'Pain Point Analysis',
			icon: MessageSquare,
			metric: '18 pain points extracted',
			description: 'Extracts and scores pain points from real discussions with severity and willingness-to-pay metrics.',
			details: 'Specialized AI agents categorize discussions, extract pain points with evidence, and score them. Every insight traceable to specific posts.'
		},
		{
			id: 4,
			name: 'Audience Mapping',
			icon: Users,
			metric: 'Detailed buyer personas',
			description: 'Creates detailed ideal customer profiles with demographics, pain triggers, and buying behavior.',
			details: 'AI maps your target audience: who they are, where they hang out online, what triggers purchasing decisions, and how to reach them effectively.'
		},
		{
			id: 5,
			name: 'Solution Development',
			icon: Lightbulb,
			metric: '3+ solutions generated',
			description: 'Generates multiple solution concepts with competitive analysis and market gap identification.',
			details: 'Multi-agent collaboration: Solution Ideator, Competitive Researcher, Market Analyst, Solution Refiner. Each solution scored across key dimensions.'
		},
		{
			id: 6,
			name: 'Competitive Analysis',
			icon: Search,
			metric: 'Market gaps identified',
			description: 'Maps the competitive landscape to find positioning opportunities and underserved needs.',
			details: 'Identifies direct, partial, and indirect competitors. Analyzes pricing strategies, feature gaps, and differentiation opportunities.'
		},
		{
			id: 7,
			name: 'Pricing Strategy',
			icon: DollarSign,
			metric: 'Validated pricing tiers',
			description: 'Recommends pricing based on competitor analysis and willingness-to-pay signals.',
			details: 'Analyzes competitor pricing, maps customer willingness-to-pay from discussions, and recommends pricing tiers with positioning rationale.'
		},
		{
			id: 8,
			name: 'Market Sizing',
			icon: PieChart,
			metric: 'TAM/SAM/SOM calculated',
			description: 'Calculates total market opportunity with real keyword demand data.',
			details: 'Estimates Total Addressable Market (TAM), Serviceable Addressable Market (SAM), and Serviceable Obtainable Market (SOM) using keyword volumes and market data.'
		},
		{
			id: 9,
			name: 'SEO Strategy',
			icon: BarChart3,
			metric: '150+ keywords tiered',
			description: 'Comprehensive keyword research with strategic tiering and content planning.',
			details: 'Iterative expansion from seed keywords. Tier 0 (Premium), Tier 1 (Quick Wins), Tier 2 (Growth) classification. Full content strategy included.'
		},
		{
			id: 10,
			name: 'Final Report',
			icon: FileText,
			metric: 'Go/No-Go verdict',
			description: 'Complete report with risk assessment, executive dashboard, and 30-day GTM playbook.',
			details: 'Hybrid Python + LLM generation: 80% programmatic data (0% hallucination), 20% strategic synthesis. Clear go/no-go recommendation with confidence score.'
		}
	];
</script>

<section id="how-it-works" class="section">
	<div class="max-w-6xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header -->
			<div class="mb-16">
				<span class="section-label animate-fade-in">The Process</span>
				<h2 class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6">
					How It <span class="text-gradient italic">Works</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl">
					Three steps from choosing a niche to having everything you need to build and launch: validated opportunity, step-by-step roadmap, and ready-to-use landing page. No research or prompting skills required.
				</p>
			</div>

			<!-- Steps Grid -->
			<div class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
				{#each userSteps as step}
					<div class="relative p-6 bg-bg-elevated border border-border rounded-xl hover:border-border-accent transition-all group">
						<div class="absolute -top-4 left-6 bg-accent text-bg-base px-4 py-1 rounded-full text-sm font-bold">
							Step {step.number}
						</div>
						<div class="w-12 h-12 rounded-xl bg-accent/10 border border-accent/30 flex items-center justify-center mb-4 group-hover:bg-accent/20 transition-colors">
							<step.icon class="w-6 h-6 text-accent" />
						</div>
						<h3 class="font-display font-semibold text-xl text-text-primary mb-2">
							{step.title}
						</h3>
						<div class="flex items-center gap-2 mb-3">
							<Clock class="w-4 h-4 text-text-muted" />
							<span class="text-sm text-accent font-medium">{step.time}</span>
						</div>
						<p class="text-text-secondary leading-relaxed">
							{step.description}
						</p>
					</div>
				{/each}
			</div>

			<!-- Expandable: Under the Hood Section -->
			<div class="animate-fade-in delay-500">
				<button
					onclick={() => (showStages = !showStages)}
					class="w-full flex items-center justify-center gap-3 py-4 text-text-secondary hover:text-accent transition-colors group"
				>
					<span class="font-medium">See what happens under the hood</span>
					<ChevronDown
						class="w-5 h-5 transition-transform duration-300
						{showStages ? 'rotate-180' : ''}"
					/>
				</button>

				{#if showStages}
					<div transition:slide={{ duration: 400 }} class="mt-8">
						<!-- Section Header for Stages -->
						<div class="text-center mb-12">
							<h3 class="font-display text-2xl font-semibold text-text-primary mb-2">
								16-Stage Autonomous Pipeline
							</h3>
							<p class="text-text-muted text-sm">
								Each stage is built with validation and quality checks
							</p>
						</div>

						<!-- Timeline of Stages -->
						<div class="relative">
							<!-- Vertical Line with glow -->
							<div class="hidden lg:block absolute left-8 top-0 bottom-0 w-px bg-gradient-to-b from-accent/50 via-border-emphasis to-border"></div>

							<!-- Stages -->
							<div class="space-y-0">
								{#each stages as stage, i}
									<div class="relative">
										<!-- Stage Number (Desktop) -->
										<div class="hidden lg:flex absolute left-0 top-6 w-16 h-16 items-center justify-center">
											<span class="font-display text-4xl font-bold text-text-muted/30">{stage.id}</span>
										</div>

										<!-- Card -->
										<div class="lg:ml-24 border-b border-border">
											<button
												onclick={() => (expandedStage = expandedStage === i ? null : i)}
												class="w-full text-left py-6 group"
											>
												<div class="flex items-start gap-5">
													<!-- Icon -->
													<div class="flex-shrink-0 w-10 h-10 rounded-lg border flex items-center justify-center transition-all
														{expandedStage === i
															? 'border-border-accent bg-accent/10'
															: 'border-border bg-bg-elevated group-hover:border-border-emphasis'}">
														<stage.icon class="w-5 h-5 {expandedStage === i ? 'text-accent' : 'text-text-muted'}" />
													</div>

													<!-- Content -->
													<div class="flex-1 min-w-0">
														<div class="flex items-center gap-4 mb-1">
															<span class="lg:hidden text-xs font-mono text-text-muted">Stage {stage.id}</span>
															<span class="text-xs text-accent font-semibold uppercase tracking-wider">
																{stage.metric}
															</span>
														</div>

														<h4 class="font-display font-semibold text-lg text-text-primary mb-1 group-hover:text-accent transition-colors">
															{stage.name}
														</h4>

														<p class="text-text-secondary text-sm leading-relaxed">
															{stage.description}
														</p>
													</div>

													<!-- Expand Icon -->
													<ChevronDown
														class="flex-shrink-0 w-4 h-4 text-text-muted transition-transform duration-300
														{expandedStage === i ? 'rotate-180 text-accent' : ''}"
													/>
												</div>
											</button>

											<!-- Expanded Details -->
											{#if expandedStage === i}
												<div transition:slide={{ duration: 300 }} class="pb-6 lg:ml-15">
													<p class="text-text-muted leading-relaxed font-mono text-xs bg-bg-surface border border-border p-4 rounded-lg">
														{stage.details}
													</p>
												</div>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</section>
