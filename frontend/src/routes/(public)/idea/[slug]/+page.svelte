<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    IdeaHeroV2,
    SectionDivider,
    PainPointsList,
    SolutionsList,
    CompetitorTable,
    KeywordClusterPanel,
    SubredditChips,
    AudienceSegmentCard,
    BuildCTA,
  } from "$lib/components/catalog/seo";
  import { categoryPath } from "$lib/utils/urls";

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

  // 4-tile right-rail mini-stats.
  const heroStats = $derived([
    { value: tam ?? "—", label: "TAM" },
    {
      value: Array.isArray(r?.detailedPainPoints) ? r!.detailedPainPoints.length : 0,
      label: "Pain points",
    },
    {
      value: Array.isArray(r?.alternativeSolutions)
        ? r!.alternativeSolutions.length + (r!.selectedSolution ? 1 : 0)
        : 0,
      label: "Solutions",
    },
    { value: data.idea.contentItemsMined, label: "Sources" },
  ]);

  const hasPains = $derived(
    Array.isArray(r?.detailedPainPoints) && r!.detailedPainPoints.length > 0,
  );
  const hasSolutions = $derived(
    !!(
      r?.selectedSolution ||
      (Array.isArray(r?.alternativeSolutions) && r!.alternativeSolutions.length > 0)
    ),
  );

  // Combined solutions list: selected first, then alternatives.
  const solutionsList = $derived.by(() => {
    const out: unknown[] = [];
    if (r?.selectedSolution) out.push(r.selectedSolution);
    if (Array.isArray(r?.alternativeSolutions)) out.push(...r!.alternativeSolutions);
    return out;
  });
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<IdeaHeroV2 {idea} stats={heroStats} />

<!-- Section 1: Audience segments -->
{#if data.idea.audienceSegments && data.idea.audienceSegments.length > 0}
  {@const segments = data.idea.audienceSegments}
  <SectionDivider num={1} label="Audience segments" />
  <div class="seg-grid">
    {#each segments as s}
      <AudienceSegmentCard segment={s} />
    {/each}
  </div>
{/if}

<!-- Section 2: Pain points -->
{#if hasPains}
  {#snippet painCount()}
    <span>{(r?.detailedPainPoints as unknown[])?.length ?? 0} ranked</span>
  {/snippet}
  <SectionDivider num={2} label="Pain points addressed" right={painCount} />
  <PainPointsList pains={r?.detailedPainPoints} />
{/if}

<!-- Section 3: Solution directions (separate from pains per scope) -->
{#if hasSolutions}
  {#snippet solCount()}
    <span>{solutionsList.length} solution{solutionsList.length === 1 ? "" : "s"}</span>
  {/snippet}
  <SectionDivider num={3} label="Solution directions" right={solCount} />
  <SolutionsList solutions={solutionsList} markFirstAsSelected={!!r?.selectedSolution} />
{/if}

<!-- Section 4: Competitive landscape -->
{#if data.idea.competitors && data.idea.competitors.length > 0}
  {@const comps = data.idea.competitors}
  {#snippet compCount()}
    <span>{comps.length} tracked</span>
  {/snippet}
  <SectionDivider num={4} label="Competitive landscape" right={compCount} />
  <CompetitorTable competitors={comps} />
{/if}

<!-- Section 5: Keyword clusters -->
{#if data.idea.keywordClusters && data.idea.keywordClusters.length > 0}
  {@const clusters = data.idea.keywordClusters}
  <SectionDivider num={5} label="Keyword clusters & SEO opportunity" />
  <KeywordClusterPanel {clusters} />
{/if}

<!-- Section 6: Source signal (subreddit chips) -->
{#if data.idea.subredditSources && data.idea.subredditSources.length > 0}
  {@const sources = data.idea.subredditSources}
  <SectionDivider num={6} label="Source signal" />
  <SubredditChips {sources} />
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
  }
  @media (max-width: 768px) {
    .seg-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
