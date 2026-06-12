<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    CategoryHeroV2,
    SectionDivider,
    AudienceSection,
    PainPointsByTheme,
    PainPointRankTable,
    AllIdeasSection,
    BuildCTA,
    SubcategoryOpportunityPanel,
    NicheMethodology,
    NicheSeoSummary,
    CategoryFAQ,
  } from "$lib/components/catalog/seo";
  import type { Theme } from "$lib/types/publicCatalog.js";
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
  // Use the backend aggregate verdict-GO count when available (accurate across
  // all ideas, not just the visible preview slice). Fall back to counting the
  // visible top-N for older payloads without the field.
  // GO-count is computed server-side BEFORE the topIdeas list is trimmed for
  // the teaser (see +page.server.ts), so it reflects the full set.
  const goCount = $derived(data.goCount);

  // Phase 2: themes render as a single unified section. PainPointsByTheme
  // sorts by mentionCount desc internally and emphasizes the first card
  // (most-cited). No more separate dominant-theme rendering.
  const allThemes = $derived<Theme[]>(data.payload.themes ?? []);

  // Section numbers derived from running counters; do NOT hardcode literals.
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const hasThemesSection = $derived(hasResearch && allThemes.length > 0);
  const hasAudienceSegments = $derived(
    !!data.payload.audienceSegments && data.payload.audienceSegments.length > 0,
  );
  const hasAudienceSignals = $derived(!!data.payload.audienceSignals);
  // Phase 3: unified Audience section renders when EITHER segments or signals
  // exist — so theme persona chips can always anchor to #section-audience.
  const hasAudienceSection = $derived(hasAudienceSegments || hasAudienceSignals);
  // Pain points render even pre-research: catalog cards and pain detail pages
  // already advertise these counts, so hiding them here was a dead end. Only
  // themes/audience stay gated on hasResearch.
  const hasRankedPains = $derived(data.payload.topPainPoints.length > 0);
  const hasIdeasSection = $derived(data.payload.topIdeas.length > 0);
  // Chain follows visual order: ideas → ranked pain → themes → audience.
  // "About this niche" continues to use `num4 + 1` as the methodology footer.
  const num1 = $derived(nextNum(0, hasIdeasSection));
  const num2 = $derived(nextNum(num1, hasRankedPains));
  const num3 = $derived(nextNum(num2, hasThemesSection));
  const num4 = $derived(nextNum(num3, hasAudienceSection));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<CategoryHeroV2
  name={data.payload.category.name}
  slug={data.payload.category.slug}
  kicker={data.payload.parent?.name
    ? `${data.payload.parent.name} · Sub-niche`
    : "Sub-niche"}
  description={data.payload.category.description}
  growthPercent={data.payload.growthPercent}
  stats={heroStats}
  nicheContext={data.payload.nicheContext}
  statsVariant={hasResearch ? "inline" : "tiles"}
  showNicheContext={false}
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
    <a class="rpn-cta" href={ctaHref} data-sveltekit-preload-data="hover">Run research now →</a>
  </p>
{/if}

<!-- Section: Ideas — lead with the concrete artifact. List view differentiates
     the sub-page from the category's grid view per the mock. The verdict-GO
     half of the meta copy renders only when goCount > 0 — most sub-niches
     don't have verdicts at this stage (those come from a separate validation
     run). Anchor #sub-ideas used by the hero's opportunity panel "see all" link. -->
{#if hasIdeasSection}
  <div id="sub-ideas">
    <SectionDivider
      num={num1}
      label={`Ideas in ${data.payload.category.name}`}
    />
    <AllIdeasSection
      ideas={data.payload.topIdeas}
      showRank
      lockedCount={data.lockedIdeaCount}
    />
  </div>
{/if}

<!-- Section: Top pain points (ranked table) — validating evidence for the
     ideas above. -->
{#if hasRankedPains}
  <div id="section-ranked-pain">
    <SectionDivider
      num={num2}
      label="Ranked pain points"
      metaText={`${data.payload.totalPainPoints} ranked · mention volume × severity`}
    />
    <PainPointRankTable
      painPoints={data.payload.topPainPoints}
      themes={allThemes.length > 0 ? allThemes : undefined}
      lockedCount={data.lockedPainCount}
    />
  </div>
{/if}

<!-- Section: Themes — unified list (Phase 2). Most-cited theme sorts first
     and gets accent-rail emphasis + "Most-cited" badge. Pain text is
     canonicalized to the ranked-pain table; theme cards link there via the
     "View ranked pain points →" footer. Persona chips link to #section-audience. -->
{#if hasThemesSection}
  <div id="section-themes">
    <SectionDivider
      num={num3}
      label="What people are talking about"
      metaText="sorted by mention volume"
    />
    <PainPointsByTheme
      themes={allThemes}
      deck={sectionOneLede}
    />
  </div>
{/if}

<!-- Section: Audience — merged "Who's complaining" + "Audience signals" into
     a single section per the IA restructure. The segments grid keeps its
     CatalogBand tonal stripe; the signals panel sits below outside the band
     on plain page surface. Anchor #section-audience used by theme persona
     chips (Phase 2). -->
{#if hasAudienceSection}
  <div id="section-audience">
    <SectionDivider num={num4} label="Audience" />
    <AudienceSection
      segments={data.payload.audienceSegments ?? []}
      signals={data.payload.audienceSignals}
      segmentColumns={2}
    />
  </div>
{/if}

<!-- About this niche — methodology footer. Receives the scope/segments data
     that used to live in the hero (Phase 1+5 paired commit). Editorial-quiet
     section that reads as supplementary context after the main report. -->
{#if hasResearch && data.payload.nicheContext}
  <div id="section-about-niche">
    <SectionDivider num={num4 + 1} label="About this niche" />
    <NicheMethodology
      nicheContext={data.payload.nicheContext}
      contentItemsMined={data.payload.contentItemsMined}
      sourceCommunities={data.payload.sourceCommunities}
      qualitySignals={data.payload.qualitySignals}
    />
  </div>
{/if}

<!-- FAQ supplements the methodology block: methodology establishes trust,
     FAQs answer follow-up questions a founder would ask after reading. Both
     visibly rendered here AND emitted as FAQPage JSON-LD by buildCategoryJsonLd
     when faqJson.length >= 2 (same gate, structural visible-vs-schema match). -->
{#if (data.payload.category.faqJson?.length ?? 0) >= 2}
  <CategoryFAQ items={data.payload.category.faqJson ?? []} />
{/if}

<BuildCTA
  headline="Ready to validate your own niche?"
  body="Run research on your exact niche. Get pain points, solution ideas, audience segments, and SEO keywords — all sourced from real community discussions."
  ctaLabel="Run your own research"
  {ctaHref}
/>

{#if hasResearch}
  <NicheSeoSummary
    name={data.payload.category.name}
    kind="sub-niche"
    subredditSources={data.payload.subredditSources}
    sourceCommunities={data.payload.sourceCommunities}
    contentItemsMined={data.payload.contentItemsMined}
    topPainPoints={data.payload.topPainPoints}
    totalPainPoints={data.payload.totalPainPoints}
    themes={data.payload.themes}
    audienceSignals={data.payload.audienceSignals}
    audienceSegments={data.payload.audienceSegments}
    qualitySignals={data.payload.qualitySignals}
    latestModifiedAt={data.payload.latestModifiedAt}
  />
{/if}

<style>
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
    color: var(--color-accent-muted);
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
</style>
