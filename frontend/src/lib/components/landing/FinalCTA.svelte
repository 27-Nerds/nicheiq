<script lang="ts">
	import { onMount } from 'svelte';
	import { ArrowRight, Sparkles, Shield, Link2 } from 'lucide-svelte';

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

		const section = document.getElementById('final-cta');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});
</script>

<section id="final-cta" class="section relative overflow-hidden">
	<!-- Background Effects -->
	<div class="absolute inset-0 bg-radial-amber opacity-40"></div>
	<div class="absolute inset-0 bg-gradient-to-b from-bg-base via-transparent to-bg-base"></div>

	<div class="relative max-w-4xl mx-auto px-6 lg:px-12 text-center">
		{#if isVisible}
			<!-- Badge -->
			<div class="animate-fade-in flex flex-wrap justify-center gap-3 mb-6 sm:mb-8">
				<div class="inline-flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-accent/10 border border-accent/30">
					<Sparkles class="w-3.5 sm:w-4 h-3.5 sm:h-4 text-accent" />
					<span class="text-xs sm:text-sm font-medium text-accent">Starting at $19</span>
				</div>
			</div>

			<!-- Headline - Mobile optimized -->
			<h2 class="animate-fade-in delay-100 font-display text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold text-text-primary tracking-tight mb-4 sm:mb-6">
				Find Your Next SaaS Idea.
				<br class="hidden sm:block" /><span class="sm:hidden"> </span>With <span class="text-gradient italic">Confidence.</span>
			</h2>

			<!-- Subheadline - Mobile optimized -->
			<p class="animate-fade-in delay-200 text-lg sm:text-xl text-text-muted mb-2 max-w-2xl mx-auto">
				Real Data. Real Sources. 45 Minutes.
			</p>
			<p class="animate-fade-in delay-300 text-lg sm:text-xl text-text-primary font-medium mb-8 sm:mb-12 max-w-2xl mx-auto">
				Then ship.
			</p>

			<!-- CTA Buttons - Mobile optimized with full width on small screens -->
			<div class="animate-fade-in delay-400 flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 mb-6 sm:mb-8">
				{#if session?.user}
					<a
						href="/dashboard"
						class="btn-primary w-full sm:w-auto px-8 py-4 text-base"
					>
						Go to Dashboard
						<ArrowRight class="w-5 h-5" />
					</a>
				{:else}
					<a
						href="/register"
						class="btn-primary w-full sm:w-auto px-8 py-4 text-base"
					>
						Get Started
						<ArrowRight class="w-5 h-5" />
					</a>
				{/if}
			</div>

			<!-- Trust badges - Mobile optimized -->
			<div class="animate-fade-in delay-500 flex flex-col sm:flex-row flex-wrap justify-center gap-4 sm:gap-6 text-xs sm:text-sm text-text-muted">
				<span class="flex items-center justify-center gap-2">
					<Shield class="w-4 h-4 text-success" />
					Zero hallucination guarantee
				</span>
				<span class="flex items-center justify-center gap-2">
					<Link2 class="w-4 h-4 text-success" />
					Every claim links to source
				</span>
			</div>
		{/if}
	</div>
</section>
