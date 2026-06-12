<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    IdeaHeroV2,
    SectionDivider,
    PainPointRankTable,
    IdeaBuildSketch,
    IdeaCardV2,
    CompetitorTable,
    KeywordClusterPanel,
    SourceCommunityChips,
    AudienceSection,
    BuildCTA,
    Chip,
    CategoryFAQ,
    CatalogLockedSection,
    LockedListSkeleton,
    TriLegend,
  } from "$lib/components/catalog/seo";
  import ResearchCtaButton from "$lib/components/catalog/ResearchCtaButton.svelte";
  import type { PainPointPreview } from "$lib/types/catalog-landing";
  import { categoryPath } from "$lib/utils/urls";
  import { renderTechnicalContent } from "$lib/utils/format";

  let { data } = $props();

  const idea = $derived(data.idea);
  const r = $derived(idea.researchContext ?? null);
  const parent = $derived(idea.category.parent ?? null);

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  const trail = $derived.by<Array<{ label: string; href?: string }>>(() => {
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

  // TAM string from the heavy researchContext.marketSizing JSON. Defensive
  // unwrap — the column is loose `unknown | null`.
  const tam = $derived.by<string | null>(() => {
    const ms = r?.marketSizing;
    if (ms && typeof ms === "object" && ms !== null) {
      const tamStr = (ms as Record<string, unknown>).total_addressable_market;
      return typeof tamStr === "string" ? tamStr : null;
    }
    return null;
  });

  // Source-of-truth row set for the "Pain points addressed" section: walk
  // idea.addressedPainTitles (canonicalized at publish time), enriching each
  // row from researchContext.detailedPainPoints (description / severity /
  // mentions) and idea.addressedPains (slug + DB-backed metadata when
  // available). Rows with no slug match render un-linked but still present —
  // honest rendering when a canonical pain hasn't been published yet.
  const addressedTitles = $derived(idea.addressedPainTitles ?? []);

  const addressedPainsTable = $derived.by<PainPointPreview[]>(() => {
    if (addressedTitles.length === 0) return [];

    const detailByTitle = new Map<string, Record<string, unknown>>();
    const raw = r?.detailedPainPoints;
    if (Array.isArray(raw)) {
      for (const p of raw as Array<Record<string, unknown>>) {
        if (!p || typeof p !== "object") continue;
        const t = p.title;
        if (typeof t === "string" && t && !detailByTitle.has(t)) {
          detailByTitle.set(t, p);
        }
      }
    }

    const lookup = idea.addressedPains;
    const seen = new Set<string>();
    const out: PainPointPreview[] = [];

    for (const title of addressedTitles) {
      if (!title || seen.has(title)) continue;
      seen.add(title);
      const detail = detailByTitle.get(title);
      const resolved = lookup?.[title];
      const severity =
        typeof resolved?.severityScore === "number"
          ? resolved.severityScore
          : ((detail?.severity_score ?? detail?.severityScore ?? 0) as number);
      const mentions =
        typeof resolved?.mentionCount === "number"
          ? resolved.mentionCount
          : ((detail?.mention_count ?? detail?.mentionCount ?? 0) as number);
      out.push({
        // `id` is required by PainPointPreview but unused by the table renderer
        // (PainPointRankTable.svelte uses an unkeyed each). Title is unique
        // post-dedup so it satisfies the type without lying about identity.
        id: title,
        // Empty string disables the row link via the truthy guard inside
        // PainPointRankTable; matches the intent without an `as never` cast.
        slug: resolved?.slug ?? "",
        title,
        description: (detail?.description as string) ?? "",
        severityScore: severity,
        mentionCount: mentions,
        themeId: null,
        // Unused-by-renderer fields with safe defaults to satisfy the type.
        willingnessToPayScore: 0,
        opportunityLevel: "",
        representativeQuotes: null,
        sourcePlatforms: null,
        categories: null,
        affectedSegments: null,
        solutionApproach: null,
        isFeatured: false,
        isActive: true,
        category: idea.category as never,
        sourceNiche: idea.source_niche,
        sourceItemIndex: 0,
        sourceGeneratedAt: null,
        createdAt: "",
        updatedAt: "",
        // Synthetic row used only by the addressed-pain table renderer; the
        // table doesn't read these so null defaults are safe.
        faqJson: null,
        faqJsonMeta: null,
      });
    }
    // Order preserved from addressedPainTitles (pipeline-emitted priority,
    // not severity desc — see plan note on order semantics).
    return out;
  });

  const hasPains = $derived(addressedPainsTable.length > 0);

  // Filter the niche-wide audience grid to only the personas targeted by
  // THIS idea (case-insensitive substring match). Falls back to a chip strip
  // of raw target_personas names when the filter empties.
  const targetPersonaNames = $derived(
    Array.isArray(idea.target_personas)
      ? idea.target_personas
          .filter((p): p is string => typeof p === "string" && p.trim() !== "")
          .map((p) => p.trim().toLowerCase())
      : [],
  );
  const filteredSegments = $derived.by(() => {
    const all = Array.isArray(data.idea.audienceSegments) ? data.idea.audienceSegments : [];
    if (targetPersonaNames.length === 0) return [];
    return all.filter((seg) => {
      const name = seg.name?.toLowerCase() ?? "";
      return targetPersonaNames.some((t) => name.includes(t) || t.includes(name));
    });
  });

  const indexablePagesFmt = $derived(
    typeof idea.estimated_indexable_pages === "number"
      ? new Intl.NumberFormat("en-US").format(idea.estimated_indexable_pages)
      : null,
  );

  // Section visibility flags + dynamic numbering — same pattern as pain page.
  const hasBuildSketch = $derived(
    !!(
      (Array.isArray(idea.core_features) && idea.core_features.length > 0) ||
      (Array.isArray(idea.target_personas) && idea.target_personas.length > 0) ||
      (Array.isArray(idea.differentiation_factors) && idea.differentiation_factors.length > 0) ||
      idea.pricing_strategy ||
      idea.estimated_development_time ||
      idea.estimated_cac_organic ||
      idea.estimated_indexable_pages != null ||
      idea.programmatic_seo_opportunity ||
      idea.technical_approach
    ),
  );
  // Persona-fallback path was removed — personas already render inside the
  // Build sketch, and double-displaying them in Audience created visual
  // repetition. So the section gate is now strictly: do we have segment
  // cards or audience signals? Personas alone don't justify the section.
  const hasAudience = $derived(filteredSegments.length > 0);
  const hasCompetitors = $derived(
    Array.isArray(data.idea.competitors) && data.idea.competitors.length > 0,
  );
  const hasKeywordClusters = $derived(
    Array.isArray(data.idea.keywordClusters) && data.idea.keywordClusters.length > 0,
  );
  // Discovery queries and keyword clusters justify a full numbered "Search
  // opportunity" section. SEO-opportunity prose ALONE doesn't — a numbered
  // section holding two lines of text undersells itself; that case folds
  // into the Build sketch as a "Search angle" sub-block instead.
  const hasDiscoveryQueries = $derived(
    Array.isArray(idea.organic_discovery_queries) && idea.organic_discovery_queries.length > 0,
  );
  const hasSection5 = $derived(hasKeywordClusters || hasDiscoveryQueries);
  const searchProseOnly = $derived(
    !hasSection5 && !!idea.programmatic_seo_opportunity,
  );
  // Source-of-truth communities for the addressed pains. Used as an
  // attribution strip directly under the "Pain points addressed" divider,
  // not as a standalone numbered section — same provenance idiom as
  // SectionAttribution on /ideas pages.
  const hasSourceStrip = $derived(
    Array.isArray(data.idea.subredditSources) && data.idea.subredditSources.length > 0,
  );
  const hasAudienceSignals = $derived(
    !!data.idea.audienceSignals &&
      ((data.idea.audienceSignals.vocabulary?.length ?? 0) > 0 ||
        (data.idea.audienceSignals.frustrations?.length ?? 0) > 0 ||
        (data.idea.audienceSignals.currentTools?.length ?? 0) > 0 ||
        (data.idea.audienceSignals.communityHubs?.length ?? 0) > 0 ||
        (data.idea.audienceSignals.recommendedChannels?.length ?? 0) > 0 ||
        (data.idea.audienceSignals.messagingFrameworks?.length ?? 0) > 0 ||
        !!data.idea.audienceSignals.contentPreferences ||
        !!data.idea.audienceSignals.earlyAdopterTactics),
  );
  const hasSiblingIdeas = $derived(
    Array.isArray(data.idea.siblingIdeas) && data.idea.siblingIdeas.length > 0,
  );

  // Gated-item counts (non-entitled users). > 0 means there's more behind the
  // subscription wall, so the section renders a teaser even with no visible rows.
  const addressedLocked = $derived(data.idea.addressedLockedCount ?? 0);
  const siblingsLocked = $derived(data.idea.siblingIdeasLockedCount ?? 0);
  const showPains = $derived(hasPains || addressedLocked > 0);
  const showSiblings = $derived(hasSiblingIdeas || siblingsLocked > 0);

  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  // Section order: pain points addressed (with source strip) → build sketch
  // → audience (segments + signals) → competitors → search opportunity →
  // sibling ideas. Source signal is no longer a numbered section.
  const num1 = $derived(nextNum(0, showPains));
  const num2 = $derived(nextNum(num1, hasBuildSketch));
  const num3 = $derived(nextNum(num2, hasAudience || hasAudienceSignals));
  const num4 = $derived(nextNum(num3, hasCompetitors));
  const num5 = $derived(nextNum(num4, hasSection5));
  const num6 = $derived(nextNum(num5, showSiblings));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<IdeaHeroV2
  {idea}
  {ctaHref}
  sourceCount={data.idea.contentItemsMined}
  updatedAt={idea.updated_at ?? idea.created_at}
/>

{#if showPains}
  {#snippet painCount()}
    <span>{addressedPainsTable.length + addressedLocked} addressed</span>
  {/snippet}
  <SectionDivider num={num1} label="Pain points addressed" right={painCount} />
  {#if hasSourceStrip}
    <div class="source-strip">
      <span class="source-strip-label">Sourced from</span>
      <SourceCommunityChips sources={data.idea.subredditSources ?? []} />
    </div>
  {/if}
  <PainPointRankTable painPoints={addressedPainsTable} lockedCount={addressedLocked} />
{/if}

{#if hasBuildSketch}
  <SectionDivider num={num2} label="Build sketch" />
  <IdeaBuildSketch {idea} />
  {#if searchProseOnly}
    <!-- Prose-only search note — too thin for its own numbered section, so
         it closes the Build sketch as a labeled sub-block. -->
    <aside class="search-angle">
      <span class="search-angle-kicker">
        Search angle{#if indexablePagesFmt}<span class="search-angle-pages">· {indexablePagesFmt} pages</span>{/if}
      </span>
      <div class="catalog-deck-note markdown-content">
        <div class="catalog-deck-text">
          {@html renderTechnicalContent(idea.programmatic_seo_opportunity)}
        </div>
      </div>
    </aside>
  {/if}
{/if}

{#if hasAudience || hasAudienceSignals}
  <SectionDivider num={num3} label="Audience" />
  <AudienceSection
    segments={filteredSegments}
    signals={data.idea.audienceSignals}
  />
{/if}

{#if hasCompetitors}
  {@const comps = data.idea.competitors ?? []}
  {#snippet compCount()}
    <span>{comps.length} tracked</span>
  {/snippet}
  <SectionDivider num={num4} label="Competitive landscape" right={compCount} />
  <aside class="catalog-deck-note">
    <p class="catalog-deck-text">Active players in {idea.category?.name ?? 'this niche'}.</p>
  </aside>
  <CompetitorTable competitors={comps} />
{/if}

{#if hasSection5}
  {#snippet pagesPill()}
    {#if indexablePagesFmt}
      <span class="pages-pill">{indexablePagesFmt} pages</span>
    {/if}
  {/snippet}
  <SectionDivider num={num5} label="Search opportunity" right={pagesPill} />
  {#if idea.programmatic_seo_opportunity}
    <aside class="catalog-deck-note markdown-content">
      <div class="catalog-deck-text">
        {@html renderTechnicalContent(idea.programmatic_seo_opportunity)}
      </div>
    </aside>
  {/if}
  {#if hasDiscoveryQueries}
    {@const queries = idea.organic_discovery_queries ?? []}
    <div class="discovery-block">
      <h4 class="discovery-label">How they search for this</h4>
      <div class="discovery-queries">
        {#each queries as q}
          <Chip label={q} />
        {/each}
      </div>
    </div>
  {/if}
  {#if hasKeywordClusters}
    {@const clusters = data.idea.keywordClusters ?? []}
    <KeywordClusterPanel {clusters} />
  {/if}
{/if}

{#if showSiblings}
  {@const siblings = data.idea.siblingIdeas ?? []}
  {#snippet sibCount()}
    <span class="sib-right">
      <span class="sib-legend"><TriLegend /></span>
      <span>{siblings.length + siblingsLocked} more</span>
    </span>
  {/snippet}
  <SectionDivider num={num6} label={`Other ideas in ${idea.category?.name ?? 'this niche'}`} right={sibCount} />
  <div class="idea-grid">
    {#each siblings as si}
      <IdeaCardV2 idea={si} />
    {/each}
    {#if siblingsLocked > 0}
      <LockedListSkeleton variant="idea" count={siblingsLocked} />
    {/if}
  </div>
  {#if siblingsLocked > 0}
    <CatalogLockedSection
      title={`More ideas in ${idea.category?.name ?? 'this niche'}`}
      summary={`Subscribe to unlock ${siblingsLocked} more validated idea${siblingsLocked === 1 ? '' : 's'} in this niche — each with scores, audience, and competitors.`}
      ctaHref="/unlock-catalog"
      ctaLabel={`Unlock ${siblingsLocked} more idea${siblingsLocked === 1 ? '' : 's'}`}
    />
  {/if}
{/if}

<!-- FAQ — visible accordion paired with FAQPage JSON-LD (gated identically on
     idea.faqJson.length >= 2 in buildIdeaDetailJsonLd). Anchored on niche
     name in the LLM prompt, never the solution_name codename. -->
{#if (data.idea.faqJson?.length ?? 0) >= 2}
  <CategoryFAQ items={data.idea.faqJson ?? []} />
{/if}

<BuildCTA
  headline="Go deeper on this idea"
  body="Run a full deep-research report on this exact idea — SEO opportunity, market sizing, pricing, competitive landscape, and a go/no-go verdict, delivered to your dashboard."
  secondaryLabel={`More in ${idea.category?.name ?? 'catalog'}`}
  secondaryHref={categoryPath({
    slug: idea.category.slug,
    parentSlug: parent?.slug ?? null,
  })}
>
  {#snippet primary()}
    <ResearchCtaButton
      kind="idea"
      slug={idea.slug}
      label="Deep research on this idea"
      subject={idea.headline || idea.solution_name}
    />
  {/snippet}
</BuildCTA>

<style>
  /* Source attribution strip — sits directly under the "Pain points addressed"
     SectionDivider. Same idiom as <SectionAttribution> on /ideas pages: tells
     the reader where the underlying pain evidence came from before they read
     the table. Mono kicker + chip strip in one row. */
  .source-strip {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin: -8px 0 18px;
    padding-bottom: 12px;
    border-bottom: 1px dashed var(--color-border);
  }
  /* Exception to the "all kickers colored" rule: this kicker sits directly
     next to SourceChip data that uses platform-identity accent colors
     (orange for Reddit/HN, blue for Twitter/Discord). A colored kicker
     would compete with the chips for the eye instead of introducing them.
     Stays muted so the chips own the color hierarchy. */
  .source-strip-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }
  /* Canonical lede — matches `.theme-deck-note` (PainPointsByTheme) and the
     `.signals-deck-text` lede inside AudienceSignalsSection compact card.
     One typography for every "intro prose under section title" across the
     catalog consumer pages. */
  .catalog-deck-note {
    display: block;
    max-width: 720px;
    margin: 0 0 20px;
  }
  .catalog-deck-text {
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-muted);
    margin: 0;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }
  /* Scoped markdown styles for the programmatic-SEO summary variant. Same
     base typography as the simple deck-text; child elements (ul, li, strong,
     h2/h3) inherit size/color and only override structural rules. */
  .catalog-deck-note.markdown-content .catalog-deck-text :global(p) {
    margin: 0 0 8px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-muted);
  }
  .catalog-deck-note.markdown-content .catalog-deck-text :global(p:last-child) { margin-bottom: 0; }
  .catalog-deck-note.markdown-content .catalog-deck-text :global(ul) {
    margin: 4px 0 8px;
    padding-left: 20px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-muted);
  }
  .catalog-deck-note.markdown-content .catalog-deck-text :global(li) { margin-bottom: 2px; }
  .catalog-deck-note.markdown-content .catalog-deck-text :global(strong) {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .catalog-deck-note.markdown-content .catalog-deck-text :global(h2),
  .catalog-deck-note.markdown-content .catalog-deck-text :global(h3) {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-accent-muted);
    font-weight: 600;
    margin: 12px 0 6px;
  }
  /* "Search angle" sub-block closing the Build sketch (prose-only fallback
     for the Search opportunity section). Mono kicker matches .discovery-label. */
  .search-angle {
    margin: 18px 0 24px;
  }
  .search-angle-kicker {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin: 0 0 8px;
  }
  .search-angle-pages {
    color: var(--color-text-muted);
    margin-left: 4px;
  }
  .discovery-block {
    margin: 18px 0 24px;
    padding: 14px 18px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-bg-elevated, #fff);
  }
  .discovery-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-accent-muted);
    margin: 0 0 10px;
  }
  .discovery-queries {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .pages-pill {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .idea-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 36px;
  }
  /* Ring-color legend + count in the section divider's right slot. Legend
     hides on narrow widths where the slot can't fit three labels. */
  .sib-right {
    display: inline-flex;
    align-items: center;
    gap: 14px;
  }
  @media (max-width: 768px) {
    .idea-grid {
      grid-template-columns: 1fr;
    }
    .sib-legend {
      display: none;
    }
  }
</style>
