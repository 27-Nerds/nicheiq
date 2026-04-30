<script lang="ts">
  import { UserCheck, BarChart3, TrendingUp, GitFork, AlertTriangle, Swords, Briefcase, Coins } from "lucide-svelte";
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    SectionCard,
    PublicCatalogCta,
    CatalogReportShell,
    CatalogLockedSection,
    IdeaHero,
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

  const idea = $derived(data.idea);
  const r = $derived(idea.researchContext ?? null);
  const parent = $derived(idea.category.parent ?? null);

  const trail = $derived.by(() => {
    const stops: Array<{ label: string; href?: string }> = [
      { label: "Home", href: "/" },
      { label: "Ideas", href: "/ideas" },
    ];
    if (parent) {
      stops.push({ label: parent.name, href: `/ideas/${parent.slug}` });
    }
    stops.push({
      label: idea.category.name,
      href: categoryPath({
        slug: idea.category.slug,
        parentSlug: parent?.slug ?? null,
      }),
    });
    stops.push({ label: idea.solution_name });
    return stops;
  });

  // Drop alternatives whose solution_name matches the current idea — no point
  // showing the user the same item they're reading.
  const alternativesMinusSelf = $derived.by<AlternativeSolution[] | null>(
    () => {
      const list = (r?.alternativeSolutions ?? null) as
        | AlternativeSolution[]
        | null;
      if (!Array.isArray(list)) return null;
      const lcName = idea.solution_name.toLowerCase();
      return list.filter(
        (a) => (a?.solution_name ?? "").toLowerCase() !== lcName,
      );
    },
  );

  // PainAnalysis (Phase A) requires all three: detailed pain points,
  // analytics, and the selected solution. Same conditional gates the rail
  // entry too.
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

  // Subscribe CTA target for the locked sections.
  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  // Auto-build the SectionNav entries from non-null backing data — sparse
  // reports get a sparser rail.
  const navSections = $derived.by(() => {
    const sections: Array<{ id: string; label: string; icon: typeof UserCheck }> = [
      { id: "overview", label: "Overview", icon: BarChart3 },
    ];
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
    if (alternativesMinusSelf && alternativesMinusSelf.length > 0)
      sections.push({ id: "alternatives", label: "Alternatives", icon: GitFork });
    if (showGtmLock)
      sections.push({ id: "gtm", label: "GTM Playbook", icon: Briefcase });
    if (showMonetizationLock)
      sections.push({ id: "monetization", label: "Monetization", icon: Coins });
    return sections;
  });

  const scoreItems = $derived(
    [
      { label: "Market fit", value: idea.market_fit_score },
      { label: "Feasibility", value: idea.technical_feasibility_score },
      { label: "Novelty", value: idea.novelty_score },
      { label: "Solo-dev", value: idea.solo_dev_feasibility },
    ].filter((s) => typeof s.value === "number"),
  );

  function pct(v: number | null): string {
    return v != null ? `${Math.round(v * 100)}%` : "—";
  }
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<CatalogReportShell sections={navSections}>
  <IdeaHero {idea} researchContext={r} />

  <section id="overview" class="section-anchor">
    <SectionCard title="Overview">
      <p class="prose-body idea-prose"><span class="dropcap">{idea.description.charAt(0)}</span>{idea.description.slice(1)}</p>

      {#if idea.core_features && idea.core_features.length > 0}
        <h3 class="overview-subhead">Core features</h3>
        <ul class="bullet-list">
          {#each idea.core_features as feat}
            <li>{feat}</li>
          {/each}
        </ul>
      {/if}

      {#if idea.target_personas && idea.target_personas.length > 0}
        <h3 class="overview-subhead">Target personas</h3>
        <ul class="bullet-list">
          {#each idea.target_personas as p}
            <li>{p}</li>
          {/each}
        </ul>
      {/if}

      {#if idea.differentiation_factors && idea.differentiation_factors.length > 0}
        <h3 class="overview-subhead">Differentiation</h3>
        <ul class="bullet-list">
          {#each idea.differentiation_factors as d}
            <li>{d}</li>
          {/each}
        </ul>
      {/if}

      {#if idea.pricing_strategy || idea.estimated_development_time || idea.estimated_cac_organic}
        <h3 class="overview-subhead">Pricing & feasibility</h3>
        {#if idea.pricing_strategy}
          <p class="prose-body">
            <strong>Pricing.</strong>
            {idea.pricing_strategy}
          </p>
        {/if}
        {#if idea.estimated_development_time}
          <p class="prose-body">
            <strong>Time to V1.</strong>
            {idea.estimated_development_time}
          </p>
        {/if}
        {#if idea.estimated_cac_organic}
          <p class="prose-body">
            <strong>Organic CAC.</strong>
            {idea.estimated_cac_organic}
          </p>
        {/if}
      {/if}

      {#if scoreItems.length > 0}
        <ul class="score-grid">
          {#each scoreItems as s}
            <li class="score-tile">
              <div class="score-value font-mono tabular-nums">{pct(s.value)}</div>
              <div class="score-label font-mono">{s.label}</div>
            </li>
          {/each}
        </ul>
      {/if}
    </SectionCard>
  </section>

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
        selectedSolutionName={idea.solution_name}
      />
    </section>
  {/if}

  {#if alternativesMinusSelf && alternativesMinusSelf.length > 0}
    <section id="alternatives" class="section-anchor">
      <AlternativesSection data={alternativesMinusSelf} />
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
  .idea-prose {
    font-size: 1rem;
    line-height: 1.7;
    white-space: pre-line;
  }

  /* Drop-cap on the first paragraph of the Overview only. NOT
     ::first-letter (CSS auto-treatment is the editorial-cosplay tell).
     Negative left margin so the letter hangs into the gutter. */
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

  .score-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0;
    list-style: none;
    padding: 0;
    margin: 1.75rem 0 0;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  @media (min-width: 640px) {
    .score-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .score-tile {
    padding: 1rem;
    border-left: 1px solid var(--color-border);
  }

  .score-tile:first-child {
    border-left: none;
  }

  @media (max-width: 639px) {
    .score-tile:nth-child(odd) {
      border-left: none;
    }
    .score-tile:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }
  }

  .score-value {
    font-size: 1.5rem;
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1;
  }

  .score-label {
    margin-top: 0.375rem;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
</style>
