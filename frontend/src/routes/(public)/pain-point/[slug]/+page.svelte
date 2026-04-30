<script lang="ts">
  import { BarChart3, MessageSquare, UserCheck, TrendingUp, GitFork, AlertTriangle, Swords, Briefcase, Coins } from "lucide-svelte";
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    SectionCard,
    PublicCatalogCta,
    CatalogReportShell,
    CatalogLockedSection,
    PainPointHero,
  } from "$lib/components/catalog/seo";
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";
  import MarketSizing from "$lib/components/sections/MarketSizing.svelte";
  import TrendSection from "$lib/components/sections/TrendSection.svelte";
  import AlternativesSection from "$lib/components/sections/AlternativesSection.svelte";
  import PainAnalysis from "$lib/components/sections/PainAnalysis.svelte";
  import Competitors from "$lib/components/sections/Competitors.svelte";
  import { categoryPath } from "$lib/utils/urls";
  import type {
    AlternativeSolution,
    AudienceMapping,
    CompetitiveAnalysis,
    CompetitiveAnalytics,
    CompetitorProfile,
    DetailedPainPoint,
    MarketSizing as MarketSizingData,
    PainPointAnalytics,
    SolutionDetails,
    TrendLongevity,
  } from "$lib/types/report";

  let { data } = $props();

  const pp = $derived(data.painPoint);
  const r = $derived(pp.researchContext ?? null);
  const parent = $derived(pp.category.parent ?? null);

  const trail = $derived.by(() => {
    const stops: Array<{ label: string; href?: string }> = [
      { label: "Home", href: "/" },
      { label: "Ideas", href: "/ideas" },
    ];
    if (parent) {
      stops.push({ label: parent.name, href: `/ideas/${parent.slug}` });
    }
    stops.push({
      label: pp.category.name,
      href: categoryPath({
        slug: pp.category.slug,
        parentSlug: parent?.slug ?? null,
      }),
    });
    stops.push({ label: pp.title });
    return stops;
  });

  // Solutions targeting this pain — filter alternatives whose
  // pain_points_addressed contains this pain's title (case-insensitive).
  const solutionsForThisPain = $derived.by<AlternativeSolution[] | null>(() => {
    const list = (r?.alternativeSolutions ?? null) as
      | AlternativeSolution[]
      | null;
    if (!Array.isArray(list)) return null;
    const lcTitle = pp.title.toLowerCase();
    return list.filter((alt) => {
      const addressed = (alt as unknown as { pain_points_addressed?: string[] })
        .pain_points_addressed;
      return Array.isArray(addressed) && addressed.some((p) =>
        (p ?? "").toLowerCase().includes(lcTitle),
      );
    });
  });

  const quotes = $derived(
    Array.isArray(pp.representativeQuotes)
      ? pp.representativeQuotes.slice(0, 3)
      : [],
  );

  // PainAnalysis (Phase A) — wider niche-level pain context surrounding the
  // focal pain. Requires all three: detailed pain points, analytics, and
  // selected solution.
  const showPainAnalysis = $derived(
    !!r?.detailedPainPoints &&
      Array.isArray(r.detailedPainPoints) &&
      r.detailedPainPoints.length > 0 &&
      !!r?.painPointAnalytics &&
      !!r?.selectedSolution,
  );

  // Phase B (5.3) — Competitors (unlocked) + GTM/Monetization (locked)
  const showCompetitors = $derived(
    !!r?.competitorProfiles &&
      !!r?.competitiveAnalysis &&
      !!r?.competitiveAnalytics,
  );
  const showGtmLock = $derived(!!r?.goToMarketBlueprint);
  const showMonetizationLock = $derived(
    !!(r?.pricingStrategy || r?.trafficMonetization),
  );

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  const navSections = $derived.by(() => {
    const sections: Array<{ id: string; label: string; icon: typeof BarChart3 }> = [
      { id: "overview", label: "Overview", icon: BarChart3 },
    ];
    if (quotes.length > 0)
      sections.push({ id: "evidence", label: "Evidence", icon: MessageSquare });
    if (showPainAnalysis)
      sections.push({ id: "pain-analysis", label: "Pain Analysis", icon: AlertTriangle });
    if (r?.audienceMapping)
      sections.push({ id: "audience", label: "Audience", icon: UserCheck });
    if (r?.marketSizing)
      sections.push({ id: "market", label: "Market", icon: BarChart3 });
    if (r?.trendLongevity)
      sections.push({ id: "trend", label: "Trend", icon: TrendingUp });
    if (showCompetitors)
      sections.push({ id: "competitors", label: "Competitors", icon: Swords });
    if (solutionsForThisPain && solutionsForThisPain.length > 0)
      sections.push({ id: "solutions", label: "Solutions", icon: GitFork });
    if (showGtmLock)
      sections.push({ id: "gtm", label: "GTM Playbook", icon: Briefcase });
    if (showMonetizationLock)
      sections.push({ id: "monetization", label: "Monetization", icon: Coins });
    return sections;
  });
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<CatalogReportShell sections={navSections}>
  <PainPointHero painPoint={pp} researchContext={r} />

  <section id="overview" class="section-anchor">
    <SectionCard title="Overview">
      <p class="prose-body pp-prose">
        <span class="dropcap">{pp.description.charAt(0)}</span>{pp.description.slice(1)}
      </p>

      {#if pp.affectedSegments && pp.affectedSegments.length > 0}
        <h3 class="overview-subhead">Who feels this</h3>
        <ul class="bullet-list">
          {#each pp.affectedSegments as s}
            <li>{s}</li>
          {/each}
        </ul>
      {/if}

      {#if pp.solutionApproach}
        <h3 class="overview-subhead">Solution approach</h3>
        <p class="prose-body pp-prose">{pp.solutionApproach}</p>
      {/if}
    </SectionCard>
  </section>

  {#if quotes.length > 0}
    <section id="evidence" class="section-anchor">
      <SectionCard title="Evidence">
        <ul class="quote-list">
          {#each quotes as q}
            <li class="quote-item">
              <p>{q}</p>
            </li>
          {/each}
        </ul>
      </SectionCard>
    </section>
  {/if}

  {#if showPainAnalysis}
    <section id="pain-analysis" class="section-anchor">
      <PainAnalysis
        painPoints={r!.detailedPainPoints as DetailedPainPoint[]}
        analytics={r!.painPointAnalytics as PainPointAnalytics}
        solution={r!.selectedSolution as SolutionDetails}
      />
    </section>
  {/if}

  {#if r?.audienceMapping}
    <section id="audience" class="section-anchor">
      <AudienceSection data={r.audienceMapping as AudienceMapping} />
    </section>
  {/if}

  {#if r?.marketSizing}
    <section id="market" class="section-anchor">
      <MarketSizing data={r.marketSizing as MarketSizingData} />
    </section>
  {/if}

  {#if r?.trendLongevity}
    <section id="trend" class="section-anchor">
      <TrendSection data={r.trendLongevity as TrendLongevity} />
    </section>
  {/if}

  {#if showCompetitors}
    <section id="competitors" class="section-anchor">
      <Competitors
        profiles={r!.competitorProfiles as CompetitorProfile[]}
        analysis={r!.competitiveAnalysis as CompetitiveAnalysis}
        analytics={r!.competitiveAnalytics as CompetitiveAnalytics}
        summary={r!.competitiveSummary ?? undefined}
      />
    </section>
  {/if}

  {#if solutionsForThisPain && solutionsForThisPain.length > 0}
    <section id="solutions" class="section-anchor">
      <AlternativesSection data={solutionsForThisPain} />
    </section>
  {/if}

  {#if showGtmLock}
    <section id="gtm" class="section-anchor">
      <CatalogLockedSection
        title="GTM Playbook"
        summary="Channel mix, budget allocation, and 90-day acquisition plan tailored to this niche."
        ctaHref="{ctaHref}&unlock=gtm"
      />
    </section>
  {/if}

  {#if showMonetizationLock}
    <section id="monetization" class="section-anchor">
      <CatalogLockedSection
        title="Monetization Strategy"
        summary="Pricing model, packaging tiers, and unit economics with CAC breakdown."
        ctaHref="{ctaHref}&unlock=monetization"
      />
    </section>
  {/if}

  <PublicCatalogCta variant="bottom" />
</CatalogReportShell>

<style>
  .pp-prose {
    font-size: 1rem;
    line-height: 1.7;
    white-space: pre-line;
    max-width: 65ch;
  }

  .dropcap {
    float: left;
    font-family: var(--font-display);
    font-size: 3.75rem;
    font-weight: 900;
    line-height: 0.85;
    margin: 0.25rem 0.5rem 0 -0.125rem;
    color: var(--color-text-primary);
  }

  .overview-subhead {
    font-family: var(--font-display);
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 1.75rem 0 0.625rem;
    letter-spacing: -0.01em;
  }

  .bullet-list {
    margin: 0;
    padding-left: 1.25rem;
    list-style: disc;
    line-height: 1.7;
    max-width: 65ch;
  }
  .bullet-list li {
    margin-bottom: 0.5rem;
  }

  .quote-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-width: 65ch;
  }
  .quote-item {
    border-left: 2px solid var(--color-accent);
    padding: 0.5rem 0 0.5rem 1rem;
    color: var(--color-text-secondary);
    font-style: italic;
    line-height: 1.65;
  }
  .quote-item p {
    margin: 0;
  }
</style>
