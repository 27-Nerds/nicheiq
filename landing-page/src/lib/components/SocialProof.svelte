<script lang="ts">
	import { onMount } from 'svelte';
	import { Star, Quote } from 'lucide-svelte';

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

		const section = document.getElementById('social-proof');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});

	const testimonials = [
		{
			name: 'Sarah K.',
			role: 'Indie Hacker',
			avatar: 'SK',
			quote: 'Saved me 3 weeks of manual research. The Reddit pain points were gold—I could click through and verify every single one.',
			rating: 5
		},
		{
			name: 'Marcus T.',
			role: 'SaaS Founder',
			avatar: 'MT',
			quote: "Finally, market data I can actually verify. No more guessing if ChatGPT made something up. Every claim links to a real discussion.",
			rating: 5
		},
		{
			name: 'Elena R.',
			role: 'Product Manager',
			avatar: 'ER',
			quote: 'Used this to validate 3 different ideas before committing. The SEO keywords alone would have cost $200+ from other tools.',
			rating: 5
		}
	];

	const stats = [
		{ value: '500+', label: 'Founders on waitlist' },
		{ value: '47', label: 'Reports generated' },
		{ value: '89%', label: 'Satisfaction rate' },
		{ value: '12 min', label: 'Average delivery' }
	];
</script>

<section id="social-proof" class="py-16 bg-bg-elevated border-y border-border">
	<div class="max-w-6xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<!-- Stats Bar -->
			<div class="animate-fade-in grid grid-cols-2 md:grid-cols-4 gap-6 mb-16">
				{#each stats as stat, i}
					<div class="text-center" style="animation-delay: {i * 100}ms">
						<div class="text-3xl font-display font-bold text-accent mb-1">{stat.value}</div>
						<div class="text-sm text-text-muted">{stat.label}</div>
					</div>
				{/each}
			</div>

			<!-- Section Header -->
			<div class="animate-fade-in delay-200 text-center mb-12">
				<h2 class="font-display text-2xl font-semibold text-text-primary mb-2">
					Trusted by Builders Who Ship
				</h2>
				<p class="text-text-muted">Join founders who validate smarter, not harder</p>
			</div>

			<!-- Testimonials Grid -->
			<div class="animate-fade-in delay-300 grid grid-cols-1 md:grid-cols-3 gap-6">
				{#each testimonials as testimonial, i}
					<div
						class="relative p-6 bg-bg-surface border border-border rounded-xl hover:border-border-emphasis transition-all"
						style="animation-delay: {300 + i * 100}ms"
					>
						<!-- Quote Icon -->
						<Quote class="absolute top-4 right-4 w-8 h-8 text-accent/20" />

						<!-- Rating -->
						<div class="flex gap-1 mb-4">
							{#each Array(testimonial.rating) as _, j}
								<Star class="w-4 h-4 fill-accent text-accent" />
							{/each}
						</div>

						<!-- Quote -->
						<p class="text-text-secondary leading-relaxed mb-6 text-sm">
							"{testimonial.quote}"
						</p>

						<!-- Author -->
						<div class="flex items-center gap-3">
							<div class="w-10 h-10 rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center">
								<span class="text-accent font-semibold text-sm">{testimonial.avatar}</span>
							</div>
							<div>
								<div class="font-medium text-text-primary text-sm">{testimonial.name}</div>
								<div class="text-xs text-text-muted">{testimonial.role}</div>
							</div>
						</div>
					</div>
				{/each}
			</div>

			<!-- Trust Note -->
			<p class="animate-fade-in delay-500 text-center text-xs text-text-muted mt-8 italic">
				* Placeholder testimonials - will be replaced with real user feedback
			</p>
		{/if}
	</div>
</section>
