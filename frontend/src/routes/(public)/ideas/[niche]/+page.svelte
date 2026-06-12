<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    CategoryHeroV2,
    SectionDivider,
    SectionAttribution,
    AudienceSection,
    PainPointsByTheme,
    PainPointRankTable,
    SubNicheDirectory,
    IdeaCardV2,
    AllIdeasSection,
    BuildCTA,
    CollectionTeaser,
    CategoryFAQ,
    NicheSeoSummary,
  } from "$lib/components/catalog/seo";
  import { categoryPath } from "$lib/utils/urls";
  import { categoryLede } from "$lib/seo/catalogSeo";

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
  // Parent-niche hero lede — totals-rich template wrapping the admin
  // `category.description`. Computed alongside `heroStats` so both
  // derivations share the same `data.kind === 'category'` gate.
  const parentLede = $derived.by(() =>
    data.kind === "category" ? categoryLede(data.payload) : null,
  );

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
  // Section numbers — chain follows visual order:
  // ideas → ranked pain → themes → sub-niches → audience.
  // Audience on parent is segments-only (signals are sub-niche-specific depth).
  const num1 = $derived(nextNum(0, hasIdeasSection));
  const num2 = $derived(nextNum(num1, hasRankedPains));
  const num3 = $derived(nextNum(num2, hasThemesSection));
  const num4 = $derived(nextNum(num3, hasSubNiches));
  const num5 = $derived(nextNum(num4, hasAudienceSegments));

  // §04 sub-niche directory split — researched (idea+pain > 0) vs atlas (the
  // rest). Computed here so the section meta and the SubNicheDirectory's
  // internal split stay derived from the same predicate; route owns the meta
  // string, component owns the render. Returns zero counts on non-category
  // routes so the consuming markup is gated by `hasSubNiches`.
  const subNicheDirectoryCounts = $derived.by(() => {
    if (data.kind !== "category") return { researched: 0, atlas: 0 };
    const researched = data.payload.children.filter(
      (c) => c.ideaCount + c.painPointCount > 0,
    ).length;
    return {
      researched,
      atlas: data.payload.children.length - researched,
    };
  });
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

{#if data.kind === "category"}
  <CategoryHeroV2
    name={data.payload.category.name}
    slug={data.payload.category.slug}
    kicker={data.payload.superGroup?.name
      ? `Category · ${data.payload.superGroup.name}`
      : "Category"}
    description={parentLede}
    parentChip={data.payload.parent}
    growthPercent={data.payload.growthPercent}
    stats={heroStats}
    nicheContext={data.payload.nicheContext}
    kind="parent"
  />

  <!-- Section: All ideas — lead with the concrete artifact a visitor came to
       see. Top/All scope toggle remains; sub-niche navigation lives in §04. -->
  {#if hasIdeasSection}
    <div id="all-ideas">
      <SectionDivider
        num={num1}
        label={`Ideas in ${data.payload.category.name}`}
      />
      <AllIdeasSection ideas={data.payload.topIdeas} lockedCount={data.lockedIdeaCount} />
    </div>
  {/if}

  <!-- Section: Top pain points (ranked table). Wrapped in #section-ranked-pain
       so theme-card "View ranked pain points →" links work. -->
  {#if hasRankedPains}
    <div id="section-ranked-pain">
      <SectionDivider
        num={num2}
        label="Top pain points"
        metaText="ranked by mention volume × severity"
      />
      <PainPointRankTable
        painPoints={data.payload.topPainPoints}
        lockedCount={data.lockedPainCount}
        showSubNicheColumn={data.payload.children.length > 0}
      />
    </div>
  {/if}

  <!-- Section: Top themes — themes are flattened from a single research
       context (one sub-niche), so we surface a <SectionAttribution> line
       linking to that sub-niche. The OVERVIEW deck (categorizationSummary
       prose) is intentionally omitted on parent: that prose talks about the
       source sub-niche specifically and reads as misleading at category
       level. The hero description carries category-level orientation. -->
  {#if hasThemesSection}
    <SectionDivider
      num={num3}
      label="What people are talking about"
      metaText="sorted by mention volume"
    />
    {#if showThemeSectionAttribution}
      <SectionAttribution source={researchSource!} href={researchSourceHref} />
    {/if}
    <PainPointsByTheme
      themes={data.payload.themes ?? []}
      showSource={themeMultiSource}
    />
  {/if}

  <!-- Section: Sub-niches — two-tier directory. Researched sub-niches get
       rich cards; placeholders fall into the dot-separated atlas list. -->
  {#if hasSubNiches}
    <SectionDivider
      num={num4}
      label="Sub-niches"
      metaText={subNicheDirectoryCounts.researched > 0 &&
      subNicheDirectoryCounts.atlas > 0
        ? `${subNicheDirectoryCounts.researched} researched · ${subNicheDirectoryCounts.atlas} mapped · research pending`
        : subNicheDirectoryCounts.researched > 0
          ? `${subNicheDirectoryCounts.researched} researched`
          : `${subNicheDirectoryCounts.atlas} mapped · research pending`}
    />
    <SubNicheDirectory
      subNiches={data.payload.children}
      parentSlug={data.payload.category.slug}
    />
  {/if}

  <!-- Featured collection teaser — only when current category appears in any
       active collection's categorySlugs. Stays attached to the sub-niches
       navigation surface. Skips silently when nothing maps. -->
  {#if data.featuredCollection}
    <CollectionTeaser collection={data.featuredCollection} />
  {/if}

  <!-- Section: Audience — segments grid only on parent (signals are sub-niche-
       specific depth content; aggregating them produces incoherent jumble).
       Sub-niche route still renders both segments + signals. Multi-source
       parent audience cards carry per-card source links; single-source
       audience keeps the quieter section-level attribution. -->
  {#if hasAudienceSegments}
    <div id="section-audience">
      <SectionDivider num={num5} label="Audience" />
      {#if showAudienceSectionAttribution}
        <SectionAttribution source={researchSource!} href={researchSourceHref} />
      {/if}
      <AudienceSection
        segments={data.payload.audienceSegments ?? []}
        showSegmentSource={audienceMultiSource}
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

  <NicheSeoSummary
    name={data.payload.category.name}
    kind="niche"
    sourceCommunities={data.payload.sourceCommunities}
    contentItemsMined={data.payload.contentItemsMined}
    topPainPoints={data.payload.topPainPoints}
    totalPainPoints={data.payload.totalPainPoints}
    themes={data.payload.themes}
    qualitySignals={data.payload.qualitySignals}
    latestModifiedAt={data.payload.latestModifiedAt}
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
  .ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
  }
</style>
