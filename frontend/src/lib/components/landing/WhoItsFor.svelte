<script lang="ts">
	import { onMount } from 'svelte';
	import { User, Rocket, Users, Check, X } from 'lucide-svelte';

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

		const section = document.getElementById('who-its-for');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	const personas = [
		{
			icon: User,
			title: 'Solo Founders',
			tagline: 'Validate before you build',
			description: "Stop wasting months building something nobody wants. Get proof your idea has real demand in 12 minutes.",
			benefits: [
				'Know your market size (TAM/SAM/SOM)',
				'Get validated pricing recommendations',
				'Clear go/no-go verdict with confidence score'
			]
		},
		{
			icon: Rocket,
			title: 'Indie Hackers',
			tagline: 'Find proven niches fast',
			description: "Skip the guesswork. Let AI analyze thousands of Reddit threads to find niches with real problems worth solving.",
			benefits: [
				'Analyze 1,000+ posts in minutes',
				'See WTP (willingness-to-pay) scores',
				'Know exactly what to charge from day one'
			]
		},
		{
			icon: Users,
			title: 'Product Teams',
			tagline: 'Data-driven ideation',
			description: "Back your product decisions with verified market data. Every insight links to its source for easy validation.",
			benefits: [
				'Market sizing for stakeholder buy-in',
				'Risk assessment with confidence scores',
				'GTM blueprint with 30-day playbook'
			]
		}
	];

	const antiPersonas = [
		'Enterprise teams needing custom qualitative research',
		'Agencies wanting white-label reports',
		'Researchers studying non-English markets'
	];
</script>

<section id="who-its-for" class="section">
	<div class="max-w-6xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header - Mobile optimized -->
			<div class="mb-10 sm:mb-16">
				<span class="section-label animate-fade-in">Who It's For</span>
				<h2 class="animate-fade-in delay-100 font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6">
					I Built This for <span class="text-gradient italic">Builders Who Ship</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl">
					I built NicheIQ for makers who want to validate fast and build with confidence.
				</p>
			</div>

			<!-- Persona Cards - Mobile optimized -->
			<div class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-5 sm:gap-8 mb-10 sm:mb-16">
				{#each personas as persona, i}
					<div
						class="group p-6 sm:p-8 bg-bg-elevated border border-border rounded-xl hover:border-border-accent transition-all hover:shadow-glow"
						style="animation-delay: {300 + i * 100}ms"
					>
						<!-- Icon -->
						<div class="w-12 sm:w-14 h-12 sm:h-14 rounded-xl bg-accent/10 border border-accent/30 flex items-center justify-center mb-4 sm:mb-6 group-hover:bg-accent/20 transition-colors">
							<persona.icon class="w-6 sm:w-7 h-6 sm:h-7 text-accent" />
						</div>

						<!-- Content -->
						<h3 class="font-display font-semibold text-lg sm:text-xl text-text-primary mb-1.5 sm:mb-2">
							{persona.title}
						</h3>
						<p class="text-accent text-xs sm:text-sm font-medium mb-3 sm:mb-4">{persona.tagline}</p>
						<p class="text-text-secondary text-sm leading-relaxed mb-4 sm:mb-6">
							{persona.description}
						</p>

						<!-- Benefits -->
						<ul class="space-y-2.5 sm:space-y-3">
							{#each persona.benefits as benefit}
								<li class="flex items-start gap-2.5 sm:gap-3 text-sm">
									<div class="flex-shrink-0 w-4 sm:w-5 h-4 sm:h-5 rounded-full bg-success/10 border border-success/50 flex items-center justify-center mt-0.5">
										<Check class="w-2.5 sm:w-3 h-2.5 sm:h-3 text-success" />
									</div>
									<span class="text-text-muted text-xs sm:text-sm">{benefit}</span>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>

			<!-- Anti-Persona Section - Mobile optimized -->
			<div class="animate-fade-in delay-500 max-w-2xl mx-auto">
				<div class="p-5 sm:p-6 bg-bg-surface border border-border rounded-xl">
					<h4 class="font-display font-semibold text-text-primary mb-3 sm:mb-4 text-center text-sm sm:text-base">
						Not the right fit for everyone
					</h4>
					<p class="text-text-muted text-xs sm:text-sm text-center mb-3 sm:mb-4">
						NicheIQ is specialized for fast SaaS validation. For these use cases, consider alternatives:
					</p>
					<ul class="space-y-2">
						{#each antiPersonas as antiPersona}
							<li class="flex items-center gap-2.5 sm:gap-3 text-xs sm:text-sm">
								<X class="w-3.5 sm:w-4 h-3.5 sm:h-4 text-text-muted flex-shrink-0" />
								<span class="text-text-muted">{antiPersona}</span>
							</li>
						{/each}
					</ul>
				</div>
			</div>
		{/if}
	</div>
</section>
