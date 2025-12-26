<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import { Mail, ArrowRight, Sparkles, Calendar, Shield, Link2 } from 'lucide-svelte';
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

		const section = document.getElementById('final-cta');
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
</script>

<section id="final-cta" class="section relative overflow-hidden">
	<!-- Background Effects -->
	<div class="absolute inset-0 bg-radial-amber opacity-40"></div>
	<div class="absolute inset-0 bg-gradient-to-b from-bg-base via-transparent to-bg-base"></div>

	<div class="relative max-w-4xl mx-auto px-6 lg:px-12 text-center">
		{#if isVisible}
			<!-- Urgency Badges -->
			<div class="animate-fade-in flex flex-wrap justify-center gap-3 mb-8">
				<div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 border border-accent/30">
					<Sparkles class="w-4 h-4 text-accent" />
					<span class="text-sm font-medium text-accent">Early Bird: $49 (reg. $79)</span>
				</div>
				<div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-bg-surface border border-border">
					<Calendar class="w-4 h-4 text-text-muted" />
					<span class="text-sm font-medium text-text-secondary">Launching January 2025</span>
				</div>
			</div>

			<!-- Headline -->
			<h2 class="animate-fade-in delay-100 font-display text-4xl sm:text-5xl lg:text-6xl font-bold text-text-primary tracking-tight mb-6">
				Validate With
				<br />
				<span class="text-gradient italic">Confidence.</span>
			</h2>

			<!-- Subheadline -->
			<p class="animate-fade-in delay-200 text-xl text-text-muted mb-2 max-w-2xl mx-auto">
				Verified data from real sources. 12 minutes.
			</p>
			<p class="animate-fade-in delay-300 text-xl text-text-primary font-medium mb-12 max-w-2xl mx-auto">
				Then get back to building.
			</p>

			<!-- Email Form -->
			<div class="animate-fade-in delay-400 max-w-md mx-auto mb-8">
				<div class="bg-bg-elevated border border-border rounded-xl p-2 shadow-glow">
					<div class="flex flex-col sm:flex-row gap-3">
						<div class="relative flex-1">
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
						<button
							onclick={handleSubmit}
							disabled={$waitlist.status === 'loading'}
							class="btn-primary whitespace-nowrap"
						>
							{#if $waitlist.status === 'loading'}
								<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
								</svg>
							{:else if $waitlist.status === 'success'}
								You're In!
							{:else}
								Get Early Access
								<ArrowRight class="w-4 h-4" />
							{/if}
						</button>
					</div>
					{#if emailError}
						<p class="mt-2 text-sm text-error text-left pl-4">{emailError}</p>
					{/if}
				</div>

				{#if $waitlist.status === 'success'}
					<p in:fade class="mt-4 text-success font-medium">
						Welcome aboard! We'll notify you when we launch.
					</p>
				{/if}

				<p class="mt-4 text-text-muted text-sm">
					<span class="text-text-primary font-semibold">{$waitlist.count}+</span> founders already on the waitlist
				</p>
			</div>

			<!-- Trust badges -->
			<div class="animate-fade-in delay-500 flex flex-wrap justify-center gap-6 text-sm text-text-muted mb-8">
				<span class="flex items-center gap-2">
					<Shield class="w-4 h-4 text-success" />
					Zero hallucination guarantee
				</span>
				<span class="flex items-center gap-2">
					<Link2 class="w-4 h-4 text-success" />
					Every claim links to source
				</span>
			</div>

			<!-- Final urgency note -->
			<p class="animate-fade-in delay-500 text-text-muted text-sm">
				Early bird pricing ends when we launch. Lock in your $30 savings now.
			</p>
		{/if}
	</div>
</section>
