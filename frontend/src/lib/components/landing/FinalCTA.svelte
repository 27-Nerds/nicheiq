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
			<div class="animate-fade-in flex flex-wrap justify-center gap-3 mb-8">
				<div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 border border-accent/30">
					<Sparkles class="w-4 h-4 text-accent" />
					<span class="text-sm font-medium text-accent">$49 per report</span>
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

			<!-- CTA Buttons -->
			<div class="animate-fade-in delay-400 flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
				{#if session?.user}
					<a
						href="/dashboard"
						class="btn-primary px-8 py-4 text-base"
					>
						Go to Dashboard
						<ArrowRight class="w-5 h-5" />
					</a>
				{:else}
					<a
						href="/register"
						class="btn-primary px-8 py-4 text-base"
					>
						Get Started Free
						<ArrowRight class="w-5 h-5" />
					</a>
					<a
						href="/login"
						class="btn-secondary px-6 py-3"
					>
						Sign In
					</a>
				{/if}
			</div>

			<!-- Trust badges -->
			<div class="animate-fade-in delay-500 flex flex-wrap justify-center gap-6 text-sm text-text-muted">
				<span class="flex items-center gap-2">
					<Shield class="w-4 h-4 text-success" />
					Zero hallucination guarantee
				</span>
				<span class="flex items-center gap-2">
					<Link2 class="w-4 h-4 text-success" />
					Every claim links to source
				</span>
			</div>
		{/if}
	</div>
</section>
