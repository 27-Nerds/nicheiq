<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    CategoryHeroV2,
    SectionDivider,
    SectionAttribution,
    AudienceSegmentCard,
    PainPointsByTheme,
    PainPointRankTable,
    SubNicheCell,
    IdeaCardV2,
    AllIdeasSection,
    BuildCTA,
    CollectionTeaser,
    CatalogBand,
    CategoryFAQ,
  } from "$lib/components/catalog/seo";
  import { categoryPath } from "$lib/utils/urls";

  let { data } = $props();

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  // Build breadcrumb trail per route kind.
  const trail = $derived.by(() => {
    if (data.kind === "category") {
      const stops: Array<{ label: string; href?: string }> = [
        { label: "Home", href: "/" },
        { label: "Ideas", href: "/ideas" },
      ];
      if (data.payload.parent) {
        stops.push({
          label: data.payload.parent.name,
          href: `/ideas/${data.payload.parent.slug}`,
        });
      }
      stops.push({ label: data.payload.category.name });
      return stops;
    }
    return [
      { label: "Home", href: "/" },
      { label: "Ideas", href: "/ideas" },
      { label: data.pseo.title },
    ];
  });

  // Hero stat tiles. Four canonical facts in slot order:
  //   1. Ideas tracked  — primary anchor (emphasized, larger, tinted bg)
  //   2. Sub-niches     — depth indicator (count of category children)
  //   3. Pain points    — research density
  //   4. Engagement / Sources mined — content scale, accent (orange) tone
  // GO/NO-GO verdicts aren't computed at this stage, so the GO tile is
  // intentionally absent — Sub-niches replaces its slot.
  const heroStats = $derived.by(() => {
    if (data.kind !== "category") return [];
    const p = data.payload;
    const itemsMined = p.contentItemsMined;
    const formatK = (n: number) =>
      n >= 1000
        ? `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K`
        : n.toLocaleString();
    const engagement = p.qualitySignals?.engagementMetrics?.totalEngagement;
    const fourth =
      engagement != null && engagement > 0
        ? itemsMined > 0
          ? {
              value: formatK(engagement),
              label: `Engagement · ${itemsMined} discussions`,
              tone: "amber" as const,
            }
          : {
              value: formatK(engagement),
              label: "Total engagement",
              tone: "amber" as const,
            }
        : {
            value: formatK(itemsMined),
            label: "Sources mined",
            tone: "amber" as const,
          };
    return [
      { value: p.totalIdeas.toLocaleString(), label: "Ideas tracked" },
      { value: p.children.length.toLocaleString(), label: "Sub-niches" },
      { value: p.totalPainPoints.toLocaleString(), label: "Pain points" },
      fourth,
    ];
  });

  // Phase 16/17 provenance: themes still use the most-recent research source.
  // Parent audience is now aggregated per sub-niche when possible. Multi-source
  // audiences use per-card sourceSubNiche attribution; single-source audiences
  // keep the quieter section-level attribution. Pain points are aggregated
  // across the subtree and intentionally don't get this attribution.
  const researchSource = $derived(
    data.kind === "category" ? (data.payload.researchSourceSubNiche ?? null) : null,
  );
  const researchSourceHref = $derived(
    researchSource && data.kind === "category"
      ? categoryPath({ slug: researchSource.slug, parentSlug: data.payload.category.slug })
      : "",
  );

  // All section numbers are derived from running counters — do NOT hardcode
  // literals here. Hidden sections leave the next visible section's number
  // contiguous instead of skipping (e.g., "01 → 03 → 05").
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const hasThemesSection = $derived(
    data.kind === "category" && !!data.payload.themes && data.payload.themes.length > 0,
  );
  const hasAudienceSegments = $derived(
    data.kind === "category" &&
      !!data.payload.audienceSegments &&
      data.payload.audienceSegments.length > 0,
  );
  const audienceSourceSlugs = $derived.by(() => {
    if (data.kind !== "category") return new Set<string>();
    return new Set(
      (data.payload.audienceSegments ?? [])
        .map((segment) => segment.sourceSubNiche?.slug)
        .filter((slug): slug is string => !!slug),
    );
  });
  const audienceMultiSource = $derived(audienceSourceSlugs.size > 1);
  const showAudienceSectionAttribution = $derived(!!researchSource && !audienceMultiSource);
  // Wave 3 — themes adaptive attribution mirrors audience. Backend's
  // aggregation activation rule guarantees `theme.sourceSubNiche` is only set
  // when ≥2 sub-niches contributed themes; the slug-set size derives multi-
  // source state. Single-source falls back to the section-level attribution.
  const themeSourceSlugs = $derived.by(() => {
    if (data.kind !== "category") return new Set<string>();
    return new Set(
      (data.payload.themes ?? [])
        .map((t) => t.sourceSubNiche?.slug)
        .filter((slug): slug is string => !!slug),
    );
  });
  const themeMultiSource = $derived(themeSourceSlugs.size > 1);
  const showThemeSectionAttribution = $derived(!!researchSource && !themeMultiSource);
  const hasRankedPains = $derived(
    data.kind === "category" && data.payload.topPainPoints.length > 0,
  );
  const hasSubNiches = $derived(
    data.kind === "category" && data.payload.children.length > 0,
  );
  const hasIdeasSection = $derived(
    data.kind === "category" && data.payload.topIdeas.length > 0,
  );
  // Section numbers — Phase 16 drops <AudienceSignalsSection> on parent (it's
  // sub-niche-specific depth content); audience section is gated on segments
  // alone. Chain: themes → audience (segments only) → ranked pain → sub-niches
  // → ideas.
  const num1 = $derived(nextNum(0, hasThemesSection));
  const num2 = $derived(nextNum(num1, hasAudienceSegments));
  const num3 = $derived(nextNum(num2, hasRankedPains));
  const num4 = $derived(nextNum(num3, hasSubNiches));
  const num5 = $derived(nextNum(num4, hasIdeasSection));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

{#if data.kind === "category"}
  <CategoryHeroV2
    name={data.payload.category.name}
    slug={data.payload.category.slug}
    description={data.payload.category.description}
    parentChip={data.payload.parent}
    growthPercent={data.payload.growthPercent}
    stats={heroStats}
    nicheContext={data.payload.nicheContext}
    kind="parent"
  />

  <!-- Section: Top themes — themes are flattened from a single research
       context (one sub-niche), so we surface a <SectionAttribution> line
       linking to that sub-niche. The OVERVIEW deck (categorizationSummary
       prose) is intentionally omitted on parent: that prose talks about the
       source sub-niche specifically and reads as misleading at category
       level. The hero description carries category-level orientation. -->
  {#if hasThemesSection}
    <SectionDivider num={num1} label="Top themes" />
    {#if showThemeSectionAttribution}
      <SectionAttribution source={researchSource!} href={researchSourceHref} />
    {/if}
    <PainPointsByTheme
      themes={data.payload.themes ?? []}
      painsHref={hasRankedPains ? "#section-ranked-pain" : undefined}
      audienceHref={hasAudienceSegments ? "#section-audience" : undefined}
      showSource={themeMultiSource}
    />
  {/if}

  <!-- Section: Audience — segments grid only on parent (signals are sub-niche-
       specific depth content; aggregating them produces incoherent jumble).
       Sub-niche route still renders both segments + signals. Multi-source
       parent audience cards carry per-card source links; single-source
       audience keeps the quieter section-level attribution. -->
  {#if hasAudienceSegments}
    <div id="section-audience">
      <SectionDivider num={num2} label="Audience" />
      {#if showAudienceSectionAttribution}
        <SectionAttribution source={researchSource!} href={researchSourceHref} />
      {/if}
      <CatalogBand>
        <div class="segments-grid">
          {#each data.payload.audienceSegments ?? [] as s, i}
            <div
              class="catalog-fade-in"
              style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
            >
              <AudienceSegmentCard segment={s} showSource={audienceMultiSource} />
            </div>
          {/each}
        </div>
      </CatalogBand>
    </div>
  {/if}

  <!-- Section: Top pain points (ranked table). Wrapped in #section-ranked-pain
       so theme-card "View ranked pain points →" links work. -->
  {#if hasRankedPains}
    <div id="section-ranked-pain">
      <SectionDivider
        num={num3}
        label="Top pain points"
        metaText="ranked by mention volume × severity"
      />
      <PainPointRankTable painPoints={data.payload.topPainPoints} />
    </div>
  {/if}

  <!-- Section: Sub-niches -->
  {#if hasSubNiches}
    <SectionDivider
      num={num4}
      label="Sub-niches"
      metaText={`${data.payload.children.length} categories`}
    />
    <div class="subniche-grid">
      {#each data.payload.children as sub}
        <SubNicheCell
          name={sub.name}
          href={categoryPath({ slug: sub.slug, parentSlug: data.payload.category.slug })}
          count={sub.ideaCount}
        />
      {/each}
    </div>
  {/if}

  <!-- Featured collection teaser — only when current category appears in any
       active collection's categorySlugs. Sits between sub-niches and the
       all-ideas section. Skips silently when nothing maps. -->
  {#if data.featuredCollection}
    <CollectionTeaser collection={data.featuredCollection} />
  {/if}

  <!-- Section: All ideas (filterable, with sub-niche chips) -->
  {#if hasIdeasSection}
    <div id="all-ideas">
      <SectionDivider
        num={num5}
        label={`Ideas in ${data.payload.category.name}`}
        metaText={`${data.payload.totalIdeas} total`}
      />
      <AllIdeasSection
        ideas={data.payload.topIdeas}
        subNiches={data.payload.children}
      />
    </div>
  {/if}

  {#if (data.payload.category.faqJson?.length ?? 0) >= 2}
    <CategoryFAQ items={data.payload.category.faqJson ?? []} />
  {/if}

  <BuildCTA
    headline="Ready to validate your own niche?"
    body="Run research on your exact niche. Get pain points, solution ideas, audience segments, and SEO keywords — all sourced from real community discussions."
    ctaLabel="Run your own research"
    {ctaHref}
  />
{:else}
  <!-- Programmatic SEO landing-page variant (existing behavior, lighter render). -->
  <CategoryHeroV2
    name={data.pseo.title}
    slug={data.pseo.slug}
    description={data.pseo.seoDescription}
    stats={[
      { value: data.featuredIdeas.length.toLocaleString(), label: "Ideas tracked" },
    ]}
  />

  {#if data.featuredIdeas.length > 0}
    <SectionDivider num={1} label="Featured ideas" />
    <div class="ideas-grid">
      {#each data.featuredIdeas as idea}
        <IdeaCardV2 {idea} />
      {/each}
    </div>
  {/if}

  {#if data.pseo.faqJson.length >= 2}
    <CategoryFAQ items={data.pseo.faqJson} />
  {/if}

  <BuildCTA
    headline="Ready to validate your own niche?"
    body="Run research on your exact niche. Get pain points, solution ideas, audience segments, and SEO keywords — all sourced from real community discussions."
    ctaLabel="Run your own research"
    {ctaHref}
  />
{/if}

<style>
  .segments-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  @media (max-width: 768px) {
    .segments-grid {
      grid-template-columns: 1fr;
    }
  }
  .subniche-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1px;
    background: var(--color-border);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }
  .ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
  }
</style>
