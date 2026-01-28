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
	<div class="max-w-4xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header - Mobile optimized -->
			<div class="text-center mb-10 sm:mb-16">
				<span class="section-label animate-fade-in">Pricing</span>
				<h2 class="animate-fade-in delay-100 font-display text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mt-4 mb-4 sm:mb-6">
					One Price. <span class="text-gradient italic">Full Research.</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full mx-auto animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-base sm:text-lg text-text-secondary mt-4 sm:mt-6 max-w-2xl mx-auto">
					No subscriptions. No hidden fees. Pay only when you need research.
				</p>
			</div>

			<!-- Pricing Card - Mobile optimized -->
			<div class="animate-fade-in delay-300 max-w-lg mx-auto">
				<div class="bg-bg-elevated border border-border-accent rounded-xl overflow-hidden shadow-lg">
					<!-- Header - Mobile optimized price size -->
					<div class="p-6 sm:p-8 pb-4 sm:pb-6 text-center border-b border-border">
						<div class="flex items-baseline justify-center gap-2 mb-2">
							<span class="text-5xl sm:text-6xl font-display font-bold text-text-primary">$49</span>
							<span class="text-text-muted text-sm sm:text-base">/ report</span>
						</div>
						<p class="text-text-secondary text-sm sm:text-base">Complete market validation report</p>
					</div>

					<!-- Features - Mobile optimized -->
					<div class="p-6 sm:p-8">
						<ul class="space-y-3 sm:space-y-4">
							{#each features as feature}
								<li class="flex items-start gap-3">
									<div class="flex-shrink-0 w-5 h-5 rounded-full bg-success/10 border border-success/50 flex items-center justify-center mt-0.5">
										<Check class="w-3 h-3 text-success" />
									</div>
									<span class="text-text-secondary text-sm sm:text-base">{feature.text}</span>
								</li>
							{/each}
						</ul>

						<!-- Guarantee Badge - Mobile optimized -->
						<div class="mt-6 sm:mt-8 p-3 sm:p-4 rounded-lg bg-success/5 border border-success/30 flex items-center gap-3">
							<Shield class="w-6 sm:w-8 h-6 sm:h-8 text-success flex-shrink-0" />
							<div>
								<h4 class="font-semibold text-success text-xs sm:text-sm">Zero-Risk Guarantee</h4>
								<p class="text-[11px] sm:text-xs text-text-muted">
									Less than 5 pain points? Full refund.
								</p>
							</div>
						</div>
					</div>

					<!-- CTA - Mobile optimized -->
					<div class="p-6 sm:p-8 pt-0">
						{#if session?.user}
							<a
								href="/dashboard"
								class="btn-primary w-full text-sm sm:text-base py-3.5 sm:py-4 text-center"
							>
								Go to Dashboard
								<ArrowRight class="w-4 h-4" />
							</a>
						{:else}
							<a
								href="/register"
								class="btn-primary w-full text-sm sm:text-base py-3.5 sm:py-4 text-center"
							>
								Get My First Report
								<ArrowRight class="w-4 h-4" />
							</a>
							<p class="text-center text-xs sm:text-sm text-text-muted mt-3 sm:mt-4">
								Already have an account? <a href="/login" class="text-accent hover:underline">Sign in</a>
							</p>
						{/if}
					</div>
				</div>
			</div>
		{/if}
	</div>
</section>
