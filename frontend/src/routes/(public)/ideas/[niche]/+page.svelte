<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    CategoryHeroV2,
    SectionDivider,
    AudienceSegmentCard,
    AudienceSignalsSection,
    PainPointsByTheme,
    PainPointRankTable,
    SubNicheCell,
    IdeaCardV2,
    AllIdeasSection,
    BuildCTA,
    CollectionTeaser,
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

  // Hero stat tiles.
  // - GO count uses the backend-aggregate `verdictGoCount` covering the entire
  //   category subtree, NOT just the visible top set. Tile is hidden when 0.
  // - 4th tile shows "Engagement" when metrics present, else "Sources mined".
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
    const tiles: Array<{ value: string; label: string; tone?: "go" | "amber" }> = [
      { value: p.totalIdeas.toLocaleString(), label: "Ideas tracked" },
    ];
    if (p.verdictGoCount > 0) {
      tiles.push({
        value: p.verdictGoCount.toLocaleString(),
        label: "Verdict: GO",
        tone: "go" as const,
      });
    }
    tiles.push({ value: p.totalPainPoints.toLocaleString(), label: "Pain points" });
    tiles.push(fourth);
    return tiles;
  });

  // Section 1 prose lede — see sub-category route for fallback rationale.
  const sectionOneLede = $derived(
    data.kind === "category"
      ? (data.payload.categorizationSummary ?? data.payload.painAnalysisSummary)
      : null,
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
  const hasAudienceSection = $derived(
    data.kind === "category" &&
      !!data.payload.audienceSegments &&
      data.payload.audienceSegments.length > 0,
  );
  const hasAudienceSignals = $derived(
    data.kind === "category" && !!data.payload.audienceSignals,
  );
  const hasRankedPains = $derived(
    data.kind === "category" && data.payload.topPainPoints.length > 0,
  );
  const hasSubNiches = $derived(
    data.kind === "category" && data.payload.children.length > 0,
  );
  const hasIdeasSection = $derived(
    data.kind === "category" && data.payload.topIdeas.length > 0,
  );
  // Top ideas anchor section only renders when there's a meaningful "best of"
  // cut to surface above the dense filterable AllIdeasSection. Below 4, the
  // all-ideas grid IS the top.
  const hasTopIdeasSection = $derived(
    data.kind === "category" && data.payload.topIdeas.length >= 4,
  );
  const topIdeasForAnchor = $derived(
    data.kind === "category"
      ? [...data.payload.topIdeas]
          .sort(
            (a, b) =>
              (b.seo_scalability_score ?? 0) - (a.seo_scalability_score ?? 0),
          )
          .slice(0, 6)
      : [],
  );
  const num1 = $derived(nextNum(0, hasThemesSection));
  const num2 = $derived(nextNum(num1, hasAudienceSection));
  const num3 = $derived(nextNum(num2, hasAudienceSignals));
  const num4 = $derived(nextNum(num3, hasRankedPains));
  const num5 = $derived(nextNum(num4, hasSubNiches));
  const num6 = $derived(nextNum(num5, hasTopIdeasSection));
  const num7 = $derived(nextNum(num6, hasIdeasSection));
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

  <!-- Section: Themes & audience signals (theme summaries only; pain rows
       move to the dedicated ranked table below). -->
  {#if hasThemesSection}
    <SectionDivider num={num1} label="Themes & audience signals" />
    {#if sectionOneLede}
      <p class="section-lede">{sectionOneLede}</p>
    {/if}
    <PainPointsByTheme
      themes={data.payload.themes ?? []}
      painPoints={data.payload.topPainPoints}
      showPainRows={false}
    />
  {/if}

  <!-- Section: Audience segments -->
  {#if hasAudienceSection}
    {@const segments = data.payload.audienceSegments ?? []}
    <SectionDivider num={num2} label="Audience segments" />
    <div class="segments-grid">
      {#each segments as s, i}
        <div
          class="catalog-fade-in"
          style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
        >
          <AudienceSegmentCard segment={s} />
        </div>
      {/each}
    </div>
  {/if}

  <!-- Section: Audience signals -->
  {#if hasAudienceSignals}
    <SectionDivider num={num3} label="Audience signals" />
    <AudienceSignalsSection signals={data.payload.audienceSignals!} />
  {/if}

  <!-- Section: Top pain points (ranked table — separated from theme summaries
       above so the scanning anchor is independent of theme grouping). -->
  {#if hasRankedPains}
    <SectionDivider
      num={num4}
      label="Top pain points"
      metaText="ranked by mention volume × severity"
    />
    <PainPointRankTable painPoints={data.payload.topPainPoints} />
  {/if}

  <!-- Section: Sub-niches -->
  {#if hasSubNiches}
    <SectionDivider
      num={num5}
      label="Sub-niches"
      metaText={`${data.payload.children.length} sub-niches`}
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

  <!-- Section: Top ideas (sorted by opportunity, ≤6 cards) — anchor before
       the dense filterable AllIdeasSection. Hidden when totalIdeas < 4. -->
  {#if hasTopIdeasSection}
    {#snippet viewAll()}
      <a class="view-all" href="#all-ideas">View all →</a>
    {/snippet}
    <SectionDivider num={num6} label={`Top ideas in ${data.payload.category.name}`} right={viewAll} />
    <div class="top-ideas-grid">
      {#each topIdeasForAnchor as idea, i}
        <div
          class="catalog-fade-in"
          style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
        >
          <IdeaCardV2 {idea} />
        </div>
      {/each}
    </div>
  {/if}

  <!-- Featured collection teaser — only when current category appears in any
       active collection's categorySlugs. Sits between Top ideas and All ideas
       per the v2 mock IA. Skips silently when nothing maps. -->
  {#if data.featuredCollection}
    <CollectionTeaser collection={data.featuredCollection} />
  {/if}

  <!-- Section: All ideas (filterable, with sub-niche chips) -->
  {#if hasIdeasSection}
    <div id="all-ideas">
      <SectionDivider
        num={num7}
        label={`Ideas in ${data.payload.category.name}`}
        metaText={`${data.payload.totalIdeas} total`}
      />
      <AllIdeasSection
        ideas={data.payload.topIdeas}
        subNiches={data.payload.children}
      />
    </div>
  {/if}

  <BuildCTA
    headline="Don't see what you need?"
    body="Commission a research file scoped to your exact niche. Get themes, pain points, audience segments, and SEO opportunities — all in one validated report."
    ctaLabel="Commission a research file"
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

  <BuildCTA
    headline="Don't see what you need?"
    body="Commission a research file scoped to your exact niche. Get themes, pain points, audience segments, and SEO opportunities — all in one validated report."
    ctaLabel="Commission a research file"
    {ctaHref}
  />
{/if}

<style>
  /* Section 1 prose lede sits between the divider and the theme list. */
  .section-lede {
    font-size: 14px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.65;
    max-width: 780px;
    margin: 0 0 12px;
  }
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
  .top-ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }
  .view-all {
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s;
  }
  .view-all:hover {
    color: var(--color-text-primary);
  }
</style>
