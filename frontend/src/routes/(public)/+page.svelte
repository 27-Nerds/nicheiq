<script lang="ts">
  import { page } from "$app/stores";
  import {
    Hero,
    HowItWorks,
    AboutMaker,
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

  const session = $derived($page.data.session);
</script>

<svelte:head>
  <title>NicheIQ - AI-Powered Market Research for SaaS Founders</title>
  <meta
    name="description"
    content="Discover SaaS opportunities in 45 minutes with AI-powered market research. Get real pain points, market sizing, SEO strategy, and a clear go/no-go verdict."
  />
  <meta
    property="og:title"
    content="NicheIQ - AI-Powered Market Research for SaaS Founders"
  />
  <meta
    property="og:description"
    content="Discover SaaS opportunities in 45 minutes with AI-powered market research. Get real pain points, market sizing, SEO strategy, and a clear go/no-go verdict."
  />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary" />
  <meta
    name="twitter:title"
    content="NicheIQ - AI-Powered Market Research for SaaS Founders"
  />
  <meta
    name="twitter:description"
    content="Discover SaaS opportunities in 45 minutes with AI-powered market research. Get real pain points, market sizing, SEO strategy, and a clear go/no-go verdict."
  />
</svelte:head>

<main class="overflow-hidden">
  <Hero {session} hasSampleReport={data.hasSampleReport} />
  <HowItWorks />
  <AboutMaker />
  <SampleReport hasSampleReport={data.hasSampleReport} />
  <WhoItsFor />
  <BusinessIntelligence />
  <ComparisonTable />
  <Credibility />
  <Pricing {session} />
  <FAQ />
  <FinalCTA {session} />
  <Footer hasSampleReport={data.hasSampleReport} />
</main>
