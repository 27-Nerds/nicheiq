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
    AllIdeasSection,
    BuildCTA,
    SubcategoryOpportunityPanel,
    DominantTheme,
    CatalogBand,
  } from "$lib/components/catalog/seo";
  import type { Theme } from "$lib/types/publicCatalog.js";
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils.js";

  let { data } = $props();

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  const trail = $derived<Array<{ label: string; href?: string }>>([
    { label: "Home", href: "/" },
    { label: "Ideas", href: "/ideas" },
    {
      label: data.payload.parent?.name ?? "Category",
      href: data.payload.parent ? `/ideas/${data.payload.parent.slug}` : "/ideas",
    },
    { label: data.payload.category.name },
  ]);

  // Has-research-context gate. When false the page renders an empty-state
  // prose note + ideas grid only, skipping the 4 voids it used to show.
  const hasResearch = $derived(
    !!(
      (data.payload.themes && data.payload.themes.length > 0) ||
      (data.payload.audienceSegments && data.payload.audienceSegments.length > 0) ||
      data.payload.researchContext
    ),
  );

  // Hero stat strip. Returns null in empty-research mode so CategoryHeroV2
  // suppresses the strip entirely; the page renders a one-line prose note
  // between hero and ideas grid in that branch.
  const heroStats = $derived.by(() => {
    if (!hasResearch) return null;
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
      { value: p.totalPainPoints.toLocaleString(), label: "Pain points" },
      { value: (p.themes?.length ?? 0).toLocaleString(), label: "Themes" },
      fourth,
    ];
  });

  // Section 1 prose lede — categorization summary preferred over pain analysis
  // summary (the former is theme-focused, the latter is pain-focused).
  const sectionOneLede = $derived(
    data.payload.categorizationSummary ?? data.payload.painAnalysisSummary,
  );

  // Top pain (highest severity) and top idea (highest opportunity) feed the
  // SubcategoryOpportunityPanel right rail.
  const topPainPoint = $derived(
    data.payload.topPainPoints.length > 0 ? data.payload.topPainPoints[0] : null,
  );
  const topIdea = $derived.by(() => {
    if (data.payload.topIdeas.length === 0) return null;
    return [...data.payload.topIdeas].sort(
      (a, b) =>
        (b.seo_scalability_score ?? 0) - (a.seo_scalability_score ?? 0),
    )[0];
  });
  // Sub-page payload doesn't carry a backend-aggregate verdictGoCount the way
  // the parent landing does — count from the visible top-N as a best-effort
  // proxy. Underestimates total when payload.topIdeas is capped, but the
  // panel's framing ("X of Y ideas") still reads correctly.
  const goCount = $derived(
    data.payload.topIdeas.filter((i) => {
      const v = (i.source_verdict ?? "").trim().toUpperCase();
      return v === "GO";
    }).length,
  );

  // Dominant theme = highest-mention theme. Backend ordering isn't guaranteed,
  // so sort defensively here.
  const dominantTheme = $derived.by(() => {
    const themes = data.payload.themes ?? [];
    if (themes.length === 0) return null;
    return [...themes].sort(
      (a, b) => (b.mentionCount ?? 0) - (a.mentionCount ?? 0),
    )[0];
  });

  // Themes minus the dominant one — passed to PainPointsByTheme so the
  // dominant-theme callout (section 01) doesn't duplicate as the first row.
  // Theme.id is nullable on legacy rows (publicCatalog.ts:63-75); fall back
  // to object identity in that case (dominantTheme came from sorting the
  // same themes array, so reference equality is reliable).
  const themesWithoutDominant = $derived.by(() => {
    const all = data.payload.themes ?? [];
    if (!dominantTheme) return all;
    if (dominantTheme.id != null) {
      return all.filter((t) => t.id !== dominantTheme.id);
    }
    return all.filter((t) => t !== dominantTheme);
  });

  // Group visible top-pain-points by theme id. Used to (a) feed DominantTheme's
  // mini-list with its own theme's pain points, (b) let PainPointsByTheme
  // render a top-3 preview under each populated theme card. Only operates on
  // the capped visible preview set — frontend cannot derive true per-theme
  // totals from this slice (TOP_PREVIEW_LIMIT = 6 backend-side).
  const painsByThemeId = $derived.by(() => {
    const map = new Map<string, PainPointPreview[]>();
    for (const pp of data.payload.topPainPoints ?? []) {
      if (!pp.themeId) continue;
      const arr = map.get(pp.themeId) ?? [];
      arr.push(pp);
      map.set(pp.themeId, arr);
    }
    for (const list of map.values()) {
      list.sort((a, b) => b.severityScore - a.severityScore);
    }
    return map;
  });

  const dominantTopPains = $derived<PainPointPreview[]>(
    dominantTheme?.id ? (painsByThemeId.get(dominantTheme.id) ?? []).slice(0, 3) : [],
  );

  // Unioned themes list for chip resolution in PainPointRankTable.
  // Explicit predicate handles the (Theme | null) narrowing that filter(Boolean)
  // does not perform.
  const allThemesForChips = $derived<Theme[]>(
    [dominantTheme, ...themesWithoutDominant].filter((t): t is Theme => t != null),
  );

  // Section numbers derived from running counters; do NOT hardcode literals.
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const hasDominantTheme = $derived(hasResearch && !!dominantTheme);
  const hasThemesSection = $derived(
    hasResearch && themesWithoutDominant.length > 0,
  );
  const hasAudienceSection = $derived(
    !!data.payload.audienceSegments && data.payload.audienceSegments.length > 0,
  );
  const hasAudienceSignals = $derived(!!data.payload.audienceSignals);
  const hasRankedPains = $derived(
    hasResearch && data.payload.topPainPoints.length > 0,
  );
  const hasIdeasSection = $derived(data.payload.topIdeas.length > 0);
  const num1 = $derived(nextNum(0, hasDominantTheme));
  const num2 = $derived(nextNum(num1, hasThemesSection));
  const num3 = $derived(nextNum(num2, hasAudienceSection));
  const num4 = $derived(nextNum(num3, hasAudienceSignals));
  const num5 = $derived(nextNum(num4, hasRankedPains));
  const num6 = $derived(nextNum(num5, hasIdeasSection));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<CategoryHeroV2
  name={data.payload.category.name}
  slug={data.payload.category.slug}
  description={data.payload.category.description}
  growthPercent={data.payload.growthPercent}
  stats={heroStats}
  nicheContext={data.payload.nicheContext}
  statsVariant={hasResearch ? "inline" : "tiles"}
>
  {#snippet aside()}
    {#if hasResearch}
      <SubcategoryOpportunityPanel
        {topPainPoint}
        {topIdea}
        {goCount}
        totalIdeas={data.payload.totalIdeas}
        seeAllHref="#sub-ideas"
      />
    {/if}
  {/snippet}
</CategoryHeroV2>

{#if !hasResearch}
  <p class="research-pending-note">
    <span class="rpn-key">Research pending</span>
    <span>
      {data.payload.totalIdeas.toLocaleString()} ideas tracked · Full theme + audience analysis populates after the next research run.
    </span>
    <a class="rpn-cta" href={ctaHref} data-sveltekit-preload-data="hover">Commission a research file →</a>
  </p>
{/if}

<!-- Section: Dominant signal — featured callout for the highest-mention theme,
     unique to sub-niche pages (mock differentiates sub from category). -->
{#if hasDominantTheme}
  <SectionDivider num={num1} label="Dominant signal" />
  <DominantTheme theme={dominantTheme} topPainPoints={dominantTopPains} />
{/if}

<!-- Section: Other themes — theme summaries with the dominant theme sliced out
     (it appears as the callout above). Per ideas-v2/page-subcategory.jsx:88. -->
{#if hasThemesSection}
  <SectionDivider num={num2} label="Other themes" />
  {#if sectionOneLede}
    <p class="section-lede">{sectionOneLede}</p>
  {/if}
  <PainPointsByTheme
    themes={themesWithoutDominant}
    painPoints={data.payload.topPainPoints}
    showPainRows={false}
    topPainRowsLimit={3}
    displayOffset={1}
  />
{/if}

{#if hasAudienceSection}
  <SectionDivider num={num3} label="Who's complaining" />
  <CatalogBand>
    <div class="segments-grid sub-page-2col">
      {#each data.payload.audienceSegments ?? [] as s, i}
        <div
          class="catalog-fade-in"
          style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
        >
          <AudienceSegmentCard segment={s} />
        </div>
      {/each}
    </div>
  </CatalogBand>
{/if}

{#if hasAudienceSignals}
  <SectionDivider num={num4} label="Audience signals" />
  <AudienceSignalsSection signals={data.payload.audienceSignals!} />
{/if}

<!-- Section: Top pain points (ranked table) -->
{#if hasRankedPains}
  <div id="section-ranked-pain">
    <SectionDivider
      num={num5}
      label="Ranked pain points"
      metaText={`${data.payload.topPainPoints.length} ranked · mention volume × severity`}
    />
    <PainPointRankTable
      painPoints={data.payload.topPainPoints}
      themes={allThemesForChips}
    />
  </div>
{/if}

<!-- Section: Ideas — list view as anchor, differentiating sub-page from
     category's grid view per the mock. -->
{#if hasIdeasSection}
  <div id="sub-ideas">
    <SectionDivider
      num={num6}
      label={`Ideas in ${data.payload.category.name}`}
      metaText={`${data.payload.totalIdeas} tracked · ${goCount} verdict GO`}
    />
    <AllIdeasSection ideas={data.payload.topIdeas} defaultView="list" showRank />
  </div>
{/if}

<BuildCTA
  headline="Don't see what you need?"
  body="Commission a research file scoped to your exact niche. Get themes, pain points, audience segments, and SEO opportunities — all in one validated report."
  ctaLabel="Commission a research file"
  {ctaHref}
/>

<style>
  .section-lede {
    font-size: 14px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.65;
    max-width: 780px;
    margin: 0 0 12px;
  }
  /* Empty-research one-liner — replaces both the EmptyResearchState block and
     the 4 voids that used to sit between hero and ideas grid. */
  .research-pending-note {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding: 14px 18px;
    margin: 16px 0 24px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface-elevated, #fafafa);
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.4;
  }
  .rpn-key {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    border-right: 1px solid var(--color-border);
    padding-right: 12px;
  }
  .rpn-cta {
    margin-left: auto;
    font-size: 13px;
    font-weight: 500;
    color: var(--color-accent);
    text-decoration: none;
  }
  .rpn-cta:hover {
    text-decoration: underline;
  }
  .segments-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  /* Sub-page persona strip: 2-col, denser than category's 3-col, per mock. */
  .segments-grid.sub-page-2col {
    grid-template-columns: repeat(2, 1fr);
  }
  @media (max-width: 768px) {
    .segments-grid,
    .segments-grid.sub-page-2col {
      grid-template-columns: 1fr;
    }
  }
</style>
