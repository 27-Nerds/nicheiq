<script lang="ts">
	import { onMount } from 'svelte';
	import { PieChart, DollarSign, Shield, CheckCircle2, TrendingUp, Search, Users } from 'lucide-svelte';

	let isVisible = $state(false);

	onMount(() => {
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					isVisible = true;
				}
			},
			{ threshold: 0.2 }
		);

		const section = document.getElementById('business-intelligence');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	const features = [
		{
			icon: PieChart,
			title: 'Market Sizing',
			question: 'How big is this opportunity?',
			description: 'Know the opportunity size before you build—with real numbers, not guesses.',
			points: [
				{ icon: Search, text: 'Calculated from real keyword search volumes' },
				{ icon: TrendingUp, text: 'Industry growth rate analysis' },
				{ icon: CheckCircle2, text: 'TAM → SAM → SOM breakdown' }
			],
			highlight: 'Data-driven, not AI estimates'
		},
		{
			icon: DollarSign,
			title: 'Pricing Strategy',
			question: 'What should I charge?',
			description: 'Get validated pricing tiers based on what the market actually pays.',
			points: [
				{ icon: Users, text: 'Competitor pricing analysis' },
				{ icon: Search, text: 'WTP signals from customer discussions' },
				{ icon: CheckCircle2, text: 'Recommended tier structure' }
			],
			highlight: 'Based on real market data'
		},
		{
			icon: Shield,
			title: 'Risk Assessment',
			question: 'Should I build this?',
			description: 'Clear go/no-go verdict with confidence scores so you can decide with data.',
			points: [
				{ icon: CheckCircle2, text: 'GO / NO-GO / CONDITIONAL verdict' },
				{ icon: TrendingUp, text: 'Confidence score with key factors' },
				{ icon: Search, text: 'Key risks and mitigations identified' }
			],
			highlight: 'Clear decision framework'
		}
	];
</script>

<section id="business-intelligence" class="section-alt">
	<div class="max-w-6xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header -->
			<div class="mb-16">
				<span class="section-label animate-fade-in">Beyond Keywords</span>
				<h2 class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6">
					The Numbers That <span class="text-gradient italic">Matter</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl">
					Beyond pain points and keywords—get the business intelligence you need to make confident decisions.
				</p>
			</div>

			<!-- Feature Cards Grid -->
			<div class="animate-fade-in delay-300 grid grid-cols-1 lg:grid-cols-3 gap-6">
				{#each features as feature, i}
					<div class="p-6 lg:p-8 rounded-xl bg-bg-elevated border border-border hover:border-border-emphasis transition-all duration-200">
						<!-- Icon & Title -->
						<div class="flex items-start gap-4 mb-4">
							<div class="flex-shrink-0 w-12 h-12 rounded-lg bg-accent/10 border border-accent/30 flex items-center justify-center">
								<feature.icon class="w-6 h-6 text-accent" />
							</div>
							<div>
								<h3 class="font-display font-semibold text-xl text-text-primary mb-1">
									{feature.title}
								</h3>
								<p class="text-accent text-sm font-medium italic">"{feature.question}"</p>
							</div>
						</div>

						<!-- Description -->
						<p class="text-text-secondary text-sm leading-relaxed mb-5">
							{feature.description}
						</p>

						<!-- Feature Points -->
						<div class="space-y-3 mb-5">
							{#each feature.points as point}
								<div class="flex items-center gap-3">
									<point.icon class="w-4 h-4 text-accent shrink-0" />
									<span class="text-sm text-text-muted">{point.text}</span>
								</div>
							{/each}
						</div>

						<!-- Highlight -->
						<div class="pt-4 border-t border-border">
							<span class="inline-flex items-center gap-2 text-xs font-semibold text-accent">
								<CheckCircle2 class="w-3.5 h-3.5" />
								{feature.highlight}
							</span>
						</div>
					</div>
				{/each}
			</div>

			<!-- Bottom Tagline -->
			<div class="animate-fade-in delay-500 text-center mt-12">
				<div class="divider max-w-xs mx-auto"></div>
				<p class="text-text-muted italic text-lg mt-8">
					"Know your numbers. Build with confidence."
				</p>
			</div>
		{/if}
	</div>
</section>
