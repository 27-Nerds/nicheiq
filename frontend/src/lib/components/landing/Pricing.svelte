<script lang="ts">
	import { onMount } from 'svelte';
	import {
		Check,
		Shield,
		Target,
		TrendingUp,
		Users,
		BarChart3,
		Clock,
		ArrowRight,
		FileText
	} from 'lucide-svelte';

	interface Props {
		session?: { user?: { name?: string | null; email?: string | null } } | null;
	}

	let { session = null }: Props = $props();

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

		const section = document.getElementById('pricing');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	const tiers = [
		{
			name: 'Starter',
			reports: 1,
			price: 19,
			popular: false
		},
		{
			name: 'Basic',
			reports: 3,
			price: 45,
			popular: true
		},
		{
			name: 'Pro',
			reports: 10,
			price: 100,
			popular: false
		}
	];

	const features = [
		{ icon: Target, text: '16-stage validation pipeline' },
		{ icon: FileText, text: '18+ validated pain points with sources' },
		{ icon: TrendingUp, text: '100+ keywords with live search volumes' },
		{ icon: Users, text: 'Competitive landscape analysis' },
		{ icon: BarChart3, text: 'Complete SEO strategy' },
		{ icon: Clock, text: 'GTM blueprint with 30-day playbook' },
		{ icon: Shield, text: 'Zero hallucination guarantee' }
	];
</script>

<section id="pricing" class="section">
	<div class="max-w-6xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header -->
			<div class="text-center mb-10 sm:mb-16">
				<span class="section-label animate-fade-in">Pricing</span>
				<h2 class="animate-fade-in delay-100 font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6">
					Simple Pricing. <span class="text-gradient italic">Full Research.</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full mx-auto animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl mx-auto">
					No subscriptions. No hidden fees. Buy report bundles and use them whenever you need.
				</p>
			</div>

			<!-- Pricing Tiers Grid -->
			<div class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 max-w-5xl mx-auto">
				{#each tiers as tier}
					<div class="relative bg-bg-elevated border rounded-xl overflow-hidden shadow-lg transition-transform hover:scale-[1.02] {tier.popular ? 'border-accent md:-translate-y-2' : 'border-border'}">
						<!-- Popular Badge -->
						{#if tier.popular}
							<div class="absolute top-0 right-0 bg-accent text-white text-xs font-semibold px-3 py-1 rounded-bl-lg">
								Most Popular
							</div>
						{/if}

						<!-- Tier Header -->
						<div class="p-6 sm:p-8 pb-4 sm:pb-6 text-center border-b border-border">
							<h3 class="text-lg font-semibold text-text-primary mb-3">{tier.name}</h3>
							<div class="flex items-baseline justify-center gap-1 mb-2">
								<span class="text-4xl sm:text-5xl font-display font-bold text-text-primary">${tier.price}</span>
							</div>
							<p class="text-text-secondary text-sm sm:text-base">
								{tier.reports} {tier.reports === 1 ? 'report' : 'reports'}
							</p>
							{#if tier.reports > 1}
								<p class="text-text-muted text-xs mt-1">
									${(tier.price / tier.reports).toFixed(0)}/report
								</p>
							{/if}
						</div>

						<!-- CTA -->
						<div class="p-6 sm:p-8">
							{#if session?.user}
								<a
									href="/dashboard"
									class="w-full text-sm sm:text-base py-3 text-center {tier.popular ? 'btn-primary' : 'btn-secondary'}"
								>
									Go to Dashboard
									<ArrowRight class="w-4 h-4" />
								</a>
							{:else}
								<a
									href="/register"
									class="w-full text-sm sm:text-base py-3 text-center {tier.popular ? 'btn-primary' : 'btn-secondary'}"
								>
									Validate My First Idea
									<ArrowRight class="w-4 h-4" />
								</a>
							{/if}
						</div>
					</div>
				{/each}
			</div>

			<!-- What's Included Section -->
			<div class="animate-fade-in delay-400 mt-12 sm:mt-16 max-w-3xl mx-auto">
				<h3 class="text-center text-lg sm:text-xl font-semibold text-text-primary mb-6 sm:mb-8">
					What's included in every report
				</h3>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
					{#each features as feature}
						<div class="flex items-start gap-3">
							<div class="flex-shrink-0 w-5 h-5 rounded-full bg-success/10 border border-success/50 flex items-center justify-center mt-0.5">
								<Check class="w-3 h-3 text-success" />
							</div>
							<span class="text-text-secondary text-sm sm:text-base">{feature.text}</span>
						</div>
					{/each}
				</div>

				<!-- Guarantee Badge -->
				<div class="mt-8 sm:mt-10 p-4 rounded-lg bg-success/5 border border-success/30 flex items-center gap-3 max-w-md mx-auto">
					<Shield class="w-8 h-8 text-success flex-shrink-0" />
					<div>
						<h4 class="font-semibold text-success text-sm">Zero-Risk Guarantee</h4>
						<p class="text-xs text-text-muted">
							If your report has fewer than 5 validated pain points with sources, full refund within 7 days.
						</p>
					</div>
				</div>

				{#if !session?.user}
					<p class="text-center text-xs sm:text-sm text-text-muted mt-6">
						Already have an account? <a href="/login" class="text-accent hover:underline">Sign in</a>
					</p>
				{/if}
			</div>
		{/if}
	</div>
</section>
