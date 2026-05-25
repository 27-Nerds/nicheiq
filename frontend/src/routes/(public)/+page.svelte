<script lang="ts">
	import { page } from '$app/state';
	import HeroBlock from '$lib/components/landing/HeroBlock.svelte';
	import ProductDemoBlock from '$lib/components/landing/ProductDemoBlock.svelte';
	import ProblemBlock from '$lib/components/landing/ProblemBlock.svelte';
	import MarqueeBlock from '$lib/components/landing/MarqueeBlock.svelte';
	import HowItWorksBlock from '$lib/components/landing/HowItWorksBlock.svelte';
	import StepsBlock from '$lib/components/landing/StepsBlock.svelte';
	import SamplesBlock from '$lib/components/landing/SamplesBlock.svelte';
	import AboutBlock from '$lib/components/landing/AboutBlock.svelte';
	import AchievementsBlock from '$lib/components/landing/AchievementsBlock.svelte';
	import TestimonialsBlock from '$lib/components/landing/TestimonialsBlock.svelte';
	import Pricing from '$lib/components/landing/Pricing.svelte';
	import FAQBlock from '$lib/components/landing/FAQBlock.svelte';
	import { SeoHead, JsonLd } from '$lib/components/seo';
	import { canonicalUrl } from '$lib/seo/canonical';
	import { organization, website } from '$lib/seo/jsonld';

	let { data } = $props();

	const session = $derived(page.data.session);

	const homeTitle = 'NicheIQ — AI-Powered Market Research for SaaS Founders';
	const homeDescription =
		'Two-phase AI research: discover pain points and solution ideas, then choose which to validate with competitive analysis, SEO strategy, and go/no-go verdict.';
</script>

<SeoHead title={homeTitle} description={homeDescription} canonical={canonicalUrl('/', '')} />
<JsonLd data={[organization(), website()]} />

<main class="overflow-hidden">
	<HeroBlock
		{session}
		hasSampleReport={data.hasSampleReport}
		ctaTexts={data.ctaTexts}
		activeFounders={data.activeFounders}
	/>
	<ProductDemoBlock />
	<ProblemBlock />
	<MarqueeBlock />
	<HowItWorksBlock />
	<StepsBlock />
	<SamplesBlock topPainPoints={data.topPainPoints} />
	<AboutBlock />
	<AchievementsBlock
		reportsDelivered={data.reportsDelivered}
		commentsAnalyzed={data.commentsAnalyzed}
		subNiches={data.subNiches}
	/>
	<TestimonialsBlock ctaTexts={data.ctaTexts} />
	<Pricing {session} ctaTexts={data.ctaTexts} plans={data.plans ?? []} />
	<FAQBlock />
</main>
