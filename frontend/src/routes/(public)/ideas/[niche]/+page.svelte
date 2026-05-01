<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    CategoryHeroV2,
    SectionDivider,
    ThemeCard,
    AudienceSegmentCard,
    AudienceSignalsSection,
    TopPainTable,
    SubNicheCell,
    IdeaCardV2,
    AllIdeasSection,
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

  // Hero stat tiles. GO count is computed from topIdeas verdict labels — a
  // best-effort visible-set count, not the database aggregate (which would
  // require a backend change). Sources stat uses contentItemsMined (Phase 5.4).
  // Phase 5.5: 4th tile shows "Engagement" when metrics present.
  const heroStats = $derived.by(() => {
    if (data.kind !== "category") return [];
    const p = data.payload;
    const goCount = p.topIdeas.filter((i) => i.source_verdict === "GO").length;
    const itemsMined = p.contentItemsMined;
    const formatK = (n: number) =>
      n >= 1000
        ? `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K`
        : n.toLocaleString();
    const engagement = p.qualitySignals?.engagementMetrics?.totalEngagement;
    const fourth =
      engagement != null && engagement > 0
        ? {
            value: formatK(engagement),
            label: `Engagement · ${itemsMined} discussions`,
            tone: "amber" as const,
          }
        : {
            value: formatK(itemsMined),
            label: "Sources mined",
            tone: "amber" as const,
          };
    return [
      { value: p.totalIdeas.toLocaleString(), label: "Ideas tracked" },
      { value: goCount.toLocaleString(), label: "Verdict: GO", tone: "go" as const },
      { value: p.totalPainPoints.toLocaleString(), label: "Pain points" },
      fourth,
    ];
  });

  // Section 1 prose lede — see sub-category route for fallback rationale.
  const sectionOneLede = $derived(
    data.kind === "category"
      ? (data.payload.categorizationSummary ?? data.payload.painAnalysisSummary)
      : null,
  );
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
    qualitySignals={data.payload.qualitySignals}
  />

  <!-- Section 1: Themes -->
  {#if data.payload.themes && data.payload.themes.length > 0}
    <SectionDivider num={1} label="Themes & audience signals" />
    {#if sectionOneLede}
      <p class="section-lede">{sectionOneLede}</p>
    {/if}
    <div class="themes-list">
      {#each data.payload.themes as t, i}
        <ThemeCard theme={t} index={i + 1} />
      {/each}
    </div>
  {/if}

  <!-- Section 2: Audience segments -->
  {#if data.payload.audienceSegments && data.payload.audienceSegments.length > 0}
    {@const segments = data.payload.audienceSegments}
    {#snippet segCount()}
      <span>{segments.length} segments identified</span>
    {/snippet}
    <SectionDivider num={2} label="Audience segments" right={segCount} />
    <div class="segments-grid">
      {#each segments as s}
        <AudienceSegmentCard segment={s} />
      {/each}
    </div>
  {/if}

  <!-- Section 3: Audience signals (Phase 5.5) -->
  {#if data.payload.audienceSignals}
    <SectionDivider num={3} label="Audience signals" />
    <AudienceSignalsSection signals={data.payload.audienceSignals} />
  {/if}

  <!-- Section 4: Top pain points -->
  {#if data.payload.topPainPoints.length > 0}
    {#snippet painCount()}
      <span>ranked by mention volume × severity</span>
    {/snippet}
    <SectionDivider num={4} label="Top pain points" right={painCount} />
    <TopPainTable painPoints={data.payload.topPainPoints} />
  {/if}

  <!-- Section 5: Sub-niches -->
  {#if data.payload.children.length > 0}
    {#snippet subCount()}
      <span>{data.payload.children.length} sub-categories</span>
    {/snippet}
    <SectionDivider num={5} label="Sub-niches" right={subCount} />
    <div class="subniche-grid">
      {#each data.payload.children as sub}
        <SubNicheCell
          name={sub.name}
          href={categoryPath({ slug: sub.slug, parentSlug: data.payload.category.slug })}
          count={sub.ideaCount + sub.painPointCount}
        />
      {/each}
    </div>
  {/if}

  <!-- Section 6: Top ideas -->
  {#if data.payload.topIdeas.length > 0}
    {#snippet topIdeasRight()}
      <a href="#all-ideas" class="view-all-link">View all ↓</a>
    {/snippet}
    <SectionDivider num={6} label="Top ideas in this category" right={topIdeasRight} />
    <div class="ideas-grid">
      {#each data.payload.topIdeas as idea}
        <IdeaCardV2 {idea} />
      {/each}
    </div>
  {/if}

  <!-- Section 6: All ideas (filterable) -->
  <section id="all-ideas">
    {#snippet totalRight()}
      <span>{data.payload.totalIdeas} total</span>
    {/snippet}
    <SectionDivider label="Browse all ideas" right={totalRight} />
    <AllIdeasSection
      ideas={data.payload.topIdeas}
      subNiches={data.payload.children}
    />
  </section>

  <!-- Inline CTA close -->
  <section class="inline-close" aria-label="Commission a research file">
    <p>
      Don't see what you need?
      <a class="inline-cta" href={ctaHref} data-sveltekit-preload-data="hover">
        <span class="inline-cta-label">Commission a research file</span>
        <ArrowRight class="inline-arrow" aria-hidden="true" />
      </a>
    </p>
  </section>
{:else}
  <!-- Programmatic SEO landing-page variant (existing behavior, lighter render). -->
  <CategoryHeroV2
    name={data.pseo.title}
    slug={data.pseo.slug}
    description={data.pseo.seoDescription}
    parentChip={null}
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

  <section class="inline-close" aria-label="Commission a research file">
    <p>
      Don't see what you need?
      <a class="inline-cta" href={ctaHref} data-sveltekit-preload-data="hover">
        <span class="inline-cta-label">Commission a research file</span>
        <ArrowRight class="inline-arrow" aria-hidden="true" />
      </a>
    </p>
  </section>
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
  .themes-list {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1px;
    background: var(--color-border);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
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
  .view-all-link {
    color: var(--color-text-secondary, var(--color-text-primary));
    font-size: 12px;
    text-decoration: none;
    padding: 5px 10px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    transition: border-color 0.12s;
  }
  .view-all-link:hover {
    border-color: var(--color-border-emphasis);
  }

  .inline-close {
    margin-top: 4rem;
    padding: 2.5rem 0;
    border-top: 1px solid var(--color-border);
    text-align: center;
  }
  .inline-close p {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }
  .inline-cta {
    display: inline-flex;
    align-items: baseline;
    gap: 0.375rem;
    margin-left: 0.5rem;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    text-decoration: none;
    transition: color 140ms ease;
  }
  .inline-cta-label {
    background-image: linear-gradient(currentColor, currentColor);
    background-position: 0 100%;
    background-size: 0% 1px;
    background-repeat: no-repeat;
    transition: background-size 200ms ease;
  }
  .inline-cta:hover {
    color: var(--color-accent);
  }
  .inline-cta:hover .inline-cta-label {
    background-size: 100% 1px;
  }
  :global(.inline-arrow) {
    width: 0.875rem;
    height: 0.875rem;
    align-self: center;
  }

  @media (prefers-reduced-motion: reduce) {
    .inline-cta,
    .inline-cta-label {
      transition: none;
    }
  }
</style>
