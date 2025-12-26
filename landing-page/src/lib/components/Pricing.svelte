<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import {
		Check,
		Shield,
		Target,
		TrendingUp,
		Users,
		BarChart3,
		Clock,
		ArrowRight,
		FileText,
		Mail
	} from 'lucide-svelte';
	import { waitlist } from '$lib/stores/waitlist';

	let isVisible = $state(false);
	let email = $state('');
	let emailError = $state('');

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

	function validateEmail(email: string): boolean {
		const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		return regex.test(email);
	}

	async function handleSubmit() {
		emailError = '';

		if (!email) {
			emailError = 'Please enter your email';
			return;
		}

		if (!validateEmail(email)) {
			emailError = 'Please enter a valid email';
			return;
		}

		await waitlist.submit(email);
	}

	const features = [
		{ icon: Target, text: '10-stage validation pipeline' },
		{ icon: FileText, text: '18+ validated pain points with sources' },
		{ icon: TrendingUp, text: '150+ keywords with live search volumes' },
		{ icon: Users, text: 'Competitive landscape analysis' },
		{ icon: BarChart3, text: 'Complete SEO strategy' },
		{ icon: Clock, text: 'GTM blueprint with 30-day playbook' },
		{ icon: Shield, text: 'Zero hallucination guarantee' }
	];
</script>

<section id="pricing" class="section">
	<div class="max-w-4xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Section Header -->
			<div class="text-center mb-16">
				<span class="section-label animate-fade-in">Pricing</span>
				<h2 class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl font-bold text-text-primary mt-4 mb-6">
					One Price. <span class="text-gradient italic">Full Research.</span>
				</h2>
				<div class="w-16 h-1 bg-gradient-to-r from-accent to-accent-hover rounded-full mx-auto animate-fade-in delay-200"></div>
				<p class="animate-fade-in delay-200 text-lg text-text-secondary mt-6 max-w-2xl mx-auto">
					No subscriptions. No hidden fees. Pay only when you need research.
				</p>
			</div>

			<!-- Pricing Card -->
			<div class="animate-fade-in delay-300 max-w-lg mx-auto">
				<div class="bg-bg-elevated border border-border-accent rounded-xl overflow-hidden shadow-glow">
					<!-- Header -->
					<div class="p-8 pb-6 text-center border-b border-border">
						<div class="flex items-baseline justify-center gap-2 mb-2">
							<span class="text-6xl font-display font-bold text-text-primary">$49</span>
							<span class="text-text-muted">/ report</span>
						</div>
						<p class="text-text-secondary">Complete market validation report</p>
					</div>

					<!-- Features -->
					<div class="p-8">
						<ul class="space-y-4">
							{#each features as feature}
								<li class="flex items-start gap-3">
									<div class="flex-shrink-0 w-5 h-5 rounded-full bg-success/10 border border-success/50 flex items-center justify-center mt-0.5">
										<Check class="w-3 h-3 text-success" />
									</div>
									<span class="text-text-secondary">{feature.text}</span>
								</li>
							{/each}
						</ul>

						<!-- Guarantee Badge -->
						<div class="mt-8 p-4 rounded-lg bg-success/5 border border-success/30 flex items-center gap-3">
							<Shield class="w-8 h-8 text-success flex-shrink-0" />
							<div>
								<h4 class="font-semibold text-success text-sm">Zero-Risk Guarantee</h4>
								<p class="text-xs text-text-muted">
									Less than 5 pain points? Full refund + $25 gift card.
								</p>
							</div>
						</div>
					</div>

					<!-- CTA -->
					<div class="p-8 pt-0">
						<div class="space-y-3">
							<div class="relative">
								<div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
									<Mail class="w-5 h-5 text-text-muted" />
								</div>
								<input
									type="email"
									placeholder="you@company.com"
									bind:value={email}
									disabled={$waitlist.status === 'loading'}
									onkeydown={(e) => e.key === 'Enter' && handleSubmit()}
									class="input pl-12 {emailError ? 'border-error' : ''}"
								/>
							</div>
							{#if emailError}
								<p class="text-sm text-error">{emailError}</p>
							{/if}

							<button
								onclick={handleSubmit}
								disabled={$waitlist.status === 'loading'}
								class="btn-primary w-full text-base py-4"
							>
								{#if $waitlist.status === 'loading'}
									<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
										<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
										<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
								{:else if $waitlist.status === 'success'}
									You're In!
								{:else}
									Join Waitlist
									<ArrowRight class="w-4 h-4" />
								{/if}
							</button>
						</div>

						{#if $waitlist.status === 'success'}
							<p in:fade class="mt-4 text-success text-sm font-medium text-center">
								Welcome aboard! We'll notify you when we launch.
							</p>
						{:else if $waitlist.status === 'error'}
							<p in:fade class="mt-4 text-error text-sm text-center">
								{$waitlist.error}
							</p>
						{/if}

						<p class="text-center text-xs text-text-muted mt-4">
							Join <span class="text-accent font-semibold">{$waitlist.count}+</span> founders on the waitlist
						</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
</section>
