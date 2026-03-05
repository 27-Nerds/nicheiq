<script lang="ts">
  import { page } from "$app/state";
  import {
    Hero,
    HowItWorks,
    SampleReport,
    WhoItsFor,
    BusinessIntelligence,
    ComparisonTable,
    Credibility,
    Pricing,
    FAQ,
    FinalCTA,
    Footer,
  } from "$lib/components/landing";

  let { data } = $props();

  const session = $derived(page.data.session);
</script>

<svelte:head>
  <title>NicheIQ - AI-Powered Market Research for SaaS Founders</title>
  <meta
    name="description"
    content="Two-phase AI research: discover pain points and solution ideas, then choose which to validate with competitive analysis, SEO strategy, and go/no-go verdict."
  />
  <meta
    property="og:title"
    content="NicheIQ - AI-Powered Market Research for SaaS Founders"
  />
  <meta
    property="og:description"
    content="Two-phase AI research: discover pain points and solution ideas, then choose which to validate with competitive analysis, SEO strategy, and go/no-go verdict."
  />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary" />
  <meta
    name="twitter:title"
    content="NicheIQ - AI-Powered Market Research for SaaS Founders"
  />
  <meta
    name="twitter:description"
    content="Two-phase AI research: discover pain points and solution ideas, then choose which to validate with competitive analysis, SEO strategy, and go/no-go verdict."
  />
</svelte:head>

<main class="overflow-hidden">
  <Hero {session} hasSampleReport={data.hasSampleReport} ctaTexts={data.ctaTexts} />
  <SampleReport hasSampleReport={data.hasSampleReport} ctaTexts={data.ctaTexts} />
  <HowItWorks />
  <WhoItsFor />
  <BusinessIntelligence />
  <ComparisonTable />
  <Credibility />
  <Pricing {session} ctaTexts={data.ctaTexts} packages={data.packages ?? []} />
  <FAQ />
  <FinalCTA {session} hasSampleReport={data.hasSampleReport} ctaTexts={data.ctaTexts} />
  <Footer hasSampleReport={data.hasSampleReport} ctaTexts={data.ctaTexts} />
</main>
