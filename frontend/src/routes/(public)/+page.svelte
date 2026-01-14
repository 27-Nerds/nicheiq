<script lang="ts">
  import { page } from '$app/stores';
  import {
    Hero,
    SocialProof,
    HowItWorks,
    SampleReport,
    WhoItsFor,
    BusinessIntelligence,
    ComparisonTable,
    Credibility,
    Pricing,
    FAQ,
    FinalCTA,
    Footer
  } from '$lib/components/landing';

  const session = $derived($page.data.session);
</script>

<svelte:head>
  <title>NicheIQ - AI-Powered Market Research for SaaS Founders</title>
  <meta name="description" content="Validate your SaaS idea in 12 minutes with verified market research. Get real pain points, market sizing, SEO strategy, and a clear go/no-go verdict." />
</svelte:head>

<main class="overflow-hidden">
  <Hero {session} />
  <SocialProof />
  <HowItWorks />
  <SampleReport />
  <WhoItsFor />
  <BusinessIntelligence />
  <ComparisonTable />
  <Credibility />
  <Pricing {session} />
  <FAQ />
  <FinalCTA {session} />
  <Footer />
</main>
