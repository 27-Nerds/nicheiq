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
    IdeaCardV2,
    AllIdeasSection,
    EmptyResearchState,
  } from "$lib/components/catalog/seo";

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

  // Sub-category hero stats — narrower than the parent category.
  // Phase 5.5: when engagement metrics are present, the 4th tile shows
  // "Total engagement" (interactions across all discussions) — a richer
  // signal than raw post count. Falls back to "Sources mined" otherwise.
  const heroStats = $derived.by(() => {
    const p = data.payload;
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
      { value: p.totalPainPoints.toLocaleString(), label: "Pain points" },
      { value: (p.themes?.length ?? 0).toLocaleString(), label: "Themes" },
      fourth,
    ];
  });

  // Section 1 prose lede — categorization summary preferred over pain analysis
  // summary (the former is theme-focused, the latter is pain-focused; the
  // theme list reads better with theme-prose lead-in). Falls through gracefully.
  const sectionOneLede = $derived(
    data.payload.categorizationSummary ?? data.payload.painAnalysisSummary,
  );

  // Has-research-context gate determines whether the rich sections render.
  // When false, page renders the empty state + ideas list (sub-niche has
  // ideas but no aggregate context yet).
  const hasResearch = $derived(
    !!(
      (data.payload.themes && data.payload.themes.length > 0) ||
      (data.payload.audienceSegments && data.payload.audienceSegments.length > 0) ||
      data.payload.researchContext
    ),
  );
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

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

{#if !hasResearch}
  <EmptyResearchState
    headline={`No aggregate research yet for ${data.payload.category.name}.`}
    sub={`${data.payload.totalIdeas} ideas tracked. Themes & segments populate after the next research run.`}
  />
{/if}

{#if data.payload.themes && data.payload.themes.length > 0}
  <SectionDivider num={1} label="Key themes" />
  {#if sectionOneLede}
    <p class="section-lede">{sectionOneLede}</p>
  {/if}
  <div class="themes-list">
    {#each data.payload.themes as t, i}
      <ThemeCard theme={t} index={i + 1} />
    {/each}
  </div>
{/if}

{#if data.payload.audienceSegments && data.payload.audienceSegments.length > 0}
  <SectionDivider num={2} label="Audience segments" />
  <div class="segments-grid">
    {#each data.payload.audienceSegments as s}
      <AudienceSegmentCard segment={s} />
    {/each}
  </div>
{/if}

{#if data.payload.audienceSignals}
  <SectionDivider num={3} label="Audience signals" />
  <AudienceSignalsSection signals={data.payload.audienceSignals} />
{/if}

{#if data.payload.topPainPoints.length > 0}
  {#snippet painCount()}
    <span>{data.payload.topPainPoints.length} ranked</span>
  {/snippet}
  <SectionDivider num={4} label="Pain points" right={painCount} />
  <TopPainTable painPoints={data.payload.topPainPoints} />
{/if}

{#if data.payload.topIdeas.length > 0}
  {#snippet ideasCount()}
    <span>{data.payload.totalIdeas} tracked</span>
  {/snippet}
  <SectionDivider num={5} label={`Ideas in ${data.payload.category.name}`} right={ideasCount} />
  <div class="ideas-grid">
    {#each data.payload.topIdeas as idea}
      <IdeaCardV2 {idea} />
    {/each}
  </div>

  {#if data.payload.totalIdeas > data.payload.topIdeas.length}
    <section id="all-ideas" class="all-ideas-section">
      {#snippet totalRight()}
        <span>{data.payload.totalIdeas} total</span>
      {/snippet}
      <SectionDivider label="Browse all ideas" right={totalRight} />
      <AllIdeasSection ideas={data.payload.topIdeas} />
    </section>
  {/if}
{/if}

<section class="inline-close">
  <p>
    Don't see what you need?
    <a class="inline-cta" href={ctaHref} data-sveltekit-preload-data="hover">
      <span class="inline-cta-label">Commission a research file</span>
      <ArrowRight class="inline-arrow" aria-hidden="true" />
    </a>
  </p>
</section>

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
  /* Mockup uses fixed 3-col so 5 segments wrap as 3 + 2 with consistent
     card width. auto-fill let 5 cards collapse to a 4+1 orphan layout. */
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
  .ideas-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
  }
  .all-ideas-section {
    margin-top: 16px;
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
</style>
