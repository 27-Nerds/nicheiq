<script lang="ts">
	import {
		Hero,
		HowItWorks,
		SampleReport,
		ComparisonTable,
		Pricing,
		FAQ,
		Footer
	} from '$lib/components';
	import { ArrowRight } from 'lucide-svelte';

	let scrollY = $state(0);
	const showMobileCTA = $derived(scrollY > 600);

	function scrollToPricing() {
		document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
	}
</script>

<svelte:window bind:scrollY />

<main class="relative overflow-hidden">
	<!-- Noise overlay for entire page -->
	<div class="noise pointer-events-none fixed inset-0 z-50"></div>

	<!-- Page Sections -->
	<!-- 1. Hook with value proposition -->
	<Hero />

	<!-- 2. Show how it works -->
	<HowItWorks />

	<!-- 3. Prove value with sample output -->
	<SampleReport />

	<!-- 4. Position against alternatives -->
	<ComparisonTable />

	<!-- 5. Pricing -->
	<Pricing />

	<!-- 9. Handle final objections -->
	<FAQ />

	<!-- 10. Footer -->
	<Footer />

	<!-- Mobile Sticky CTA -->
	{#if showMobileCTA}
		<div
			class="fixed bottom-0 left-0 right-0 p-4 glass border-t border-border md:hidden z-40 transform transition-transform duration-300"
		>
			<button onclick={scrollToPricing} class="btn-primary w-full py-3">
				Join Waitlist - $49
				<ArrowRight class="w-4 h-4" />
			</button>
		</div>
	{/if}
</main>
