<script lang="ts">
	import { onMount } from 'svelte';

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

		const section = document.getElementById('about-maker');
		if (section) observer.observe(section);

		return () => observer.disconnect();
	});
</script>

<section id="about-maker" class="section-alt">
	<div class="max-w-4xl mx-auto px-6 lg:px-12">
		{#if isVisible}
			<div class="animate-fade-in">
				<!-- Simple, personal intro - Mobile optimized -->
				<div class="flex flex-col md:flex-row items-start gap-6 sm:gap-8 md:gap-12">
					<!-- Avatar placeholder -->
					<div class="flex-shrink-0">
						<div class="w-20 sm:w-24 h-20 sm:h-24 rounded-full bg-accent/10 border-2 border-accent/30 flex items-center justify-center">
							<span class="text-accent font-display font-bold text-2xl sm:text-3xl">M</span>
						</div>
					</div>

					<!-- Content -->
					<div class="flex-1">
						<span class="section-label mb-3 sm:mb-4 block">About the Maker</span>

						<h2 class="font-display text-2xl sm:text-3xl lg:text-4xl font-bold text-text-primary mb-4 sm:mb-6">
							Hi, I'm the solo dev behind NicheIQ
						</h2>

						<div class="space-y-3 sm:space-y-4 text-text-secondary leading-relaxed text-sm sm:text-base">
							<p>
								I built NicheIQ because I was tired of the same problem every indie hacker faces:
								spending weeks researching a market, only to discover the data was either made up by ChatGPT
								or required expensive tools to verify.
							</p>

							<p>
								After validating my own SaaS ideas the hard way—manually reading hundreds of Reddit threads,
								cross-referencing keyword tools, and building spreadsheets—I decided to automate it.
							</p>

							<p>
								Built with CrewAI + multi-agent AI, NicheIQ runs the same research process I used to do manually—except it takes 12 minutes instead of 3 weeks. Every claim links to a real source. Every data point is verifiable. No hallucinations, no guessing.
							</p>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</section>
