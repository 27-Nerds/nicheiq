<script lang="ts">
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    PainPointHeroV2,
    SectionDivider,
    AudienceSegmentCard,
    SolutionsList,
    CompetitorTable,
    KeywordClusterPanel,
    SubredditChips,
    BuildCTA,
  } from "$lib/components/catalog/seo";
  import { categoryPath } from "$lib/utils/urls";

  let { data } = $props();

  const pp = $derived(data.painPoint);
  const r = $derived(pp.researchContext ?? null);
  const parent = $derived(pp.category.parent ?? null);

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
      label: pp.category.name,
      href: categoryPath({
        slug: pp.category.slug,
        parentSlug: parent?.slug ?? null,
      }),
    });
    stops.push({ label: pp.title });
    return stops;
  });

  const hasSolutions = $derived(
    !!(
      r?.selectedSolution ||
      (Array.isArray(r?.alternativeSolutions) && r!.alternativeSolutions.length > 0)
    ),
  );

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

<PainPointHeroV2
  title={pp.title}
  description={pp.description}
  severityScore={pp.severityScore}
  mentionCount={pp.mentionCount}
  categoryName={parent?.name ?? pp.category.name}
  subName={parent ? pp.category.name : null}
  idSuffix={`Pain #${pp.id.slice(0, 8)}`}
/>

<!-- Section 1: Audience segments -->
{#if data.painPoint.audienceSegments && data.painPoint.audienceSegments.length > 0}
  {@const segments = data.painPoint.audienceSegments}
  <SectionDivider num={1} label="Audience segments" />
  <div class="seg-grid">
    {#each segments as s}
      <AudienceSegmentCard segment={s} />
    {/each}
  </div>
{/if}

<!-- Section 2: Solution directions emerging from this pain -->
{#if hasSolutions}
  {#snippet solCount()}
    <span>{solutionsList.length} solution{solutionsList.length === 1 ? "" : "s"}</span>
  {/snippet}
  <SectionDivider num={2} label="Solution directions" right={solCount} />
  <SolutionsList solutions={solutionsList} markFirstAsSelected={!!r?.selectedSolution} />
{/if}

<!-- Section 3: Competitive landscape -->
{#if data.painPoint.competitors && data.painPoint.competitors.length > 0}
  {@const comps = data.painPoint.competitors}
  {#snippet compCount()}
    <span>{comps.length} tracked</span>
  {/snippet}
  <SectionDivider num={3} label="Competitive landscape" right={compCount} />
  <CompetitorTable competitors={comps} />
{/if}

<!-- Section 4: Keyword clusters -->
{#if data.painPoint.keywordClusters && data.painPoint.keywordClusters.length > 0}
  {@const clusters = data.painPoint.keywordClusters}
  <SectionDivider num={4} label="Keyword clusters & SEO opportunity" />
  <KeywordClusterPanel {clusters} />
{/if}

<!-- Section 5: Source signal -->
{#if data.painPoint.subredditSources && data.painPoint.subredditSources.length > 0}
  {@const sources = data.painPoint.subredditSources}
  <SectionDivider num={5} label="Source signal" />
  <SubredditChips {sources} />
{/if}

<BuildCTA
  {ctaHref}
  headline="Build a solution for this pain?"
  body="Generate a 30-day GTM plan, landing-page copy, and outbound list — tuned to the audience that's already complaining."
  secondaryLabel={`More in ${pp.category?.name ?? 'catalog'}`}
  secondaryHref={categoryPath({
    slug: pp.category.slug,
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
