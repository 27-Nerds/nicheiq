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
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import { canonicalUrl } from "$lib/seo/canonical";
  import { organization, website } from "$lib/seo/jsonld";

  let { data } = $props();

  const session = $derived(page.data.session);

  const homeTitle = "NicheIQ — AI-Powered Market Research for SaaS Founders";
  const homeDescription =
    "Two-phase AI research: discover pain points and solution ideas, then choose which to validate with competitive analysis, SEO strategy, and go/no-go verdict.";
</script>

<SeoHead
  title={homeTitle}
  description={homeDescription}
  canonical={canonicalUrl("/", "")}
/>
<JsonLd data={[organization(), website()]} />

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
