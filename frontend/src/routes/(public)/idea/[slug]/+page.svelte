<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    IdeaHeroV2,
    SectionDivider,
    PainPointsList,
    IdeaBuildSketch,
    IdeaCardV2,
    CompetitorTable,
    KeywordClusterPanel,
    SourceCommunityChips,
    AudienceSegmentCard,
    BuildCTA,
    CatalogBand,
    Chip,
  } from "$lib/components/catalog/seo";
  import ArrowRight from "lucide-svelte/icons/arrow-right";
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

  // Niche-ideas tile = sibling ideas in the same leaf-category + this idea.
  // Mock label is "Sub-ideas" but our data has no idea-decomposition hierarchy
  // — these are ideas in the same niche, surfaced as `siblingIdeas` on the
  // detail payload (also used by the "Other ideas in [niche]" section below).
  const nicheIdeasCount = $derived((data.idea.siblingIdeas?.length ?? 0) + 1);

  // Mock spec (ideas-v2/page-idea.jsx:97-100): niche-score panel footer shows
  // exactly 2 stats. TAM and source count render elsewhere (source count as
  // the inline `Sourced from N discussions` line under the hero CTA).
  const heroStats = $derived<
    Array<{ value: string | number | null; label: string }>
  >([
    {
      value: Array.isArray(r?.detailedPainPoints) ? r!.detailedPainPoints.length : 0,
      label: "Pain points",
    },
    { value: nicheIdeasCount, label: "Niche ideas" },
  ]);

  const hasPains = $derived(
    Array.isArray(r?.detailedPainPoints) && r!.detailedPainPoints.length > 0,
  );

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
  const hasAudience = $derived(
    filteredSegments.length > 0 || targetPersonaNames.length > 0,
  );
  const hasCompetitors = $derived(
    Array.isArray(data.idea.competitors) && data.idea.competitors.length > 0,
  );
  const hasKeywordClusters = $derived(
    Array.isArray(data.idea.keywordClusters) && data.idea.keywordClusters.length > 0,
  );
  // Discovery queries, keyword clusters, and the SEO-opportunity markdown
  // share Section 5 — it renders when any of the three is truthy.
  const hasDiscoveryQueries = $derived(
    Array.isArray(idea.organic_discovery_queries) && idea.organic_discovery_queries.length > 0,
  );
  const hasSection5 = $derived(
    hasKeywordClusters || hasDiscoveryQueries || !!idea.programmatic_seo_opportunity,
  );
  const hasSourceSignal = $derived(
    Array.isArray(data.idea.subredditSources) && data.idea.subredditSources.length > 0,
  );
  const hasSiblingIdeas = $derived(
    Array.isArray(data.idea.siblingIdeas) && data.idea.siblingIdeas.length > 0,
  );

  // Solution-aside content for PainPointsList — value_proposition headline
  // plus first 4 core_features. Pairs the pain narrative with a stable
  // solution direction without forcing per-pain artificial mapping.
  const solutionFeatures = $derived(
    Array.isArray(idea.core_features)
      ? idea.core_features
          .filter((f): f is string => typeof f === "string" && f.trim() !== "")
          .slice(0, 4)
      : [],
  );
  const hasSolutionAside = $derived(
    !!(idea.value_proposition?.trim() || solutionFeatures.length > 0),
  );

  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  // Section order — pain narrative leads the page, build metadata follows
  // (mock IA: "this pain exists → here is the solution direction" before
  // the build details). Source signal is now its own numbered section,
  // promoted out of the muted footer it lived in previously.
  // 1. Pain points addressed → 2. Build sketch → 3. Audience → 4. Competitors
  // → 5. Keyword/SEO → 6. Source signal → 7. Sibling ideas
  const num1 = $derived(nextNum(0, hasPains));
  const num2 = $derived(nextNum(num1, hasBuildSketch));
  const num3 = $derived(nextNum(num2, hasAudience));
  const num4 = $derived(nextNum(num3, hasCompetitors));
  const num5 = $derived(nextNum(num4, hasSection5));
  const num6 = $derived(nextNum(num5, hasSourceSignal));
  const num7 = $derived(nextNum(num6, hasSiblingIdeas));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<IdeaHeroV2 {idea} stats={heroStats} {ctaHref} sourceCount={data.idea.contentItemsMined} />

{#if hasPains}
  {#snippet painCount()}
    <span>{(r?.detailedPainPoints as unknown[])?.length ?? 0} ranked</span>
  {/snippet}
  <SectionDivider num={num1} label="Pain points addressed" right={painCount} />
  {#snippet solutionAside()}
    <article class="solution-card">
      <span class="sc-label">
        <ArrowRight size={11} aria-hidden="true" />
        <span>Solution direction</span>
      </span>
      {#if idea.value_proposition}
        <h4>{idea.value_proposition}</h4>
      {/if}
      {#if solutionFeatures.length > 0}
        <ul>
          {#each solutionFeatures as f}
            <li>{f}</li>
          {/each}
        </ul>
      {/if}
    </article>
  {/snippet}
  {#if hasSolutionAside}
    <PainPointsList
      pains={r?.detailedPainPoints}
      addressedPains={data.idea.addressedPains}
      {solutionAside}
    />
  {:else}
    <PainPointsList pains={r?.detailedPainPoints} addressedPains={data.idea.addressedPains} />
  {/if}
{/if}

{#if hasBuildSketch}
  <SectionDivider num={num2} label="Build sketch" />
  <IdeaBuildSketch {idea} audienceSignals={data.idea.audienceSignals} />
{/if}

{#if hasAudience}
  <SectionDivider num={num3} label="Audience segments" />
  <CatalogBand>
    {#if filteredSegments.length > 0}
      <div class="seg-grid">
        {#each filteredSegments as s, i}
          <div
            class="catalog-fade-in"
            style:animation-delay={`${Math.min(i, 5) * 0.06}s`}
          >
            <AudienceSegmentCard segment={s} />
          </div>
        {/each}
      </div>
    {:else if targetPersonaNames.length > 0}
      {@const rawPersonas = idea.target_personas ?? []}
      <div class="persona-fallback">
        <span class="persona-label">Target personas</span>
        <div class="chip-strip muted">
          {#each rawPersonas as p}
            <Chip label={p} />
          {/each}
        </div>
      </div>
    {/if}
  </CatalogBand>
{/if}

{#if hasCompetitors}
  {@const comps = data.idea.competitors ?? []}
  {#snippet compCount()}
    <span>{comps.length} tracked</span>
  {/snippet}
  <SectionDivider num={num4} label="Competitive landscape" right={compCount} />
  <p class="section-lede">Active players in {idea.category?.name ?? 'this niche'}.</p>
  <CompetitorTable competitors={comps} />
{/if}

{#if hasSection5}
  {#snippet pagesPill()}
    {#if indexablePagesFmt}
      <span class="pages-pill">{indexablePagesFmt} pages</span>
    {/if}
  {/snippet}
  <SectionDivider num={num5} label="Keyword clusters & SEO opportunity" right={pagesPill} />
  {#if idea.programmatic_seo_opportunity}
    {@const seoOnly = !hasKeywordClusters && !hasDiscoveryQueries}
    <div
      class="section-lede markdown-content"
      class:seo-card={seoOnly}
    >
      {@html renderTechnicalContent(idea.programmatic_seo_opportunity)}
    </div>
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

{#if hasSourceSignal}
  {@const sources = data.idea.subredditSources ?? []}
  <SectionDivider num={num6} label="Source signal" />
  <CatalogBand>
    <SourceCommunityChips {sources} />
  </CatalogBand>
{/if}

{#if hasSiblingIdeas}
  {@const siblings = data.idea.siblingIdeas ?? []}
  {#snippet sibCount()}
    <span>{siblings.length} more</span>
  {/snippet}
  <SectionDivider num={num7} label={`Other ideas in ${idea.category?.name ?? 'this niche'}`} right={sibCount} />
  <div class="idea-grid">
    {#each siblings as si}
      <IdeaCardV2 idea={si} />
    {/each}
  </div>
{/if}

<BuildCTA
  {ctaHref}
  secondaryLabel={`More in ${idea.category?.name ?? 'catalog'}`}
  secondaryHref={categoryPath({
    slug: idea.category.slug,
    parentSlug: parent?.slug ?? null,
  })}
/>

<style>
  .seg-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 24px;
  }
  @media (max-width: 768px) {
    .seg-grid {
      grid-template-columns: 1fr;
    }
  }
  .chip-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 24px;
  }
  .chip-strip.muted {
    margin-top: 4px;
  }
  /* Audience-segments fallback path: when filteredSegments is empty but raw
     target_personas exist, show them as a labeled chip-strip so the section
     reads as deliberate content, not as floating remnants inside the band. */
  .persona-fallback {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 24px;
  }
  .persona-label {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .section-lede {
    margin: 0 0 16px;
    font-size: 14px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
    max-width: 720px;
  }
  /* When keyword clusters & discovery queries are both empty for this idea,
     the section's only content is the programmatic-SEO markdown. Wrap it in
     a hairline-bordered card so the section has visible density rather than
     a floating prose blob between two H2s. */
  .section-lede.seo-card {
    max-width: none;
    padding: 18px 22px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-bg-elevated, #fff);
    margin-bottom: 24px;
  }
  /* Scoped markdown styles for `renderTechnicalContent()` output. `:global`
     rules sit under the `.section-lede.markdown-content` ancestor so they
     don't leak to other markdown instances elsewhere in the app. */
  .section-lede.markdown-content :global(p) {
    margin: 0 0 8px;
    font-size: 14px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .section-lede.markdown-content :global(p:last-child) { margin-bottom: 0; }
  .section-lede.markdown-content :global(ul) {
    margin: 4px 0 8px;
    padding-left: 20px;
    font-size: 14px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .section-lede.markdown-content :global(li) { margin-bottom: 2px; }
  .section-lede.markdown-content :global(strong) {
    color: var(--color-text-primary);
    font-weight: 600;
  }
  .section-lede.markdown-content :global(h2),
  .section-lede.markdown-content :global(h3) {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    font-weight: 600;
    margin: 12px 0 4px;
  }
  .discovery-block {
    margin: 18px 0 24px;
    padding: 14px 18px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-bg-elevated, #fff);
  }
  .discovery-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
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
  @media (max-width: 768px) {
    .idea-grid {
      grid-template-columns: 1fr;
    }
  }
  /* Solution direction aside, paired with PainPointsList. Hairline-bordered
     card with mono kicker, headline, and feature bullets — matches the mock's
     `.solution-card` idiom (left rail accent + + bullet glyphs). */
  .solution-card {
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-left: 3px solid var(--color-success-dark, #16a34a);
    border-radius: 6px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .sc-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-success-dark, #16a34a);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .solution-card h4 {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.35;
    color: var(--color-text-primary);
    margin: 0;
  }
  .solution-card ul {
    list-style: none;
    display: grid;
    gap: 6px;
    margin: 2px 0 0;
    padding: 0;
  }
  .solution-card li {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .solution-card li::before {
    content: "+";
    color: var(--color-success-dark, #16a34a);
    flex-shrink: 0;
    font-weight: 700;
  }
</style>
