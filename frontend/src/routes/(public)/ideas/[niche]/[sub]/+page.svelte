<script lang="ts">
  import { ArrowRight, BarChart3, UserCheck, TrendingUp, FileText } from "lucide-svelte";
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import {
    CategoryBreadcrumbs,
    CategoryHero,
    CategoryLandingView,
    CatalogReportShell,
  } from "$lib/components/catalog/seo";
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";
  import MarketSizing from "$lib/components/sections/MarketSizing.svelte";
  import TrendSection from "$lib/components/sections/TrendSection.svelte";
  import type {
    AudienceMapping,
    MarketSizing as MarketSizingData,
    TrendLongevity,
  } from "$lib/types/report";

  let { data } = $props();

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  const trail = $derived.by(() => {
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
  });

  const r = $derived(data.payload.researchContext);

  const navSections = $derived.by(() => {
    const sections: Array<{ id: string; label: string; icon: typeof BarChart3 }> = [
      { id: "overview", label: "Overview", icon: FileText },
    ];
    if (r?.audienceMapping)
      sections.push({ id: "audience", label: "Audience", icon: UserCheck });
    if (r?.marketSizing)
      sections.push({ id: "market", label: "Market", icon: BarChart3 });
    if (r?.trendLongevity)
      sections.push({ id: "trend", label: "Trend", icon: TrendingUp });
    return sections;
  });
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs {trail} />

<CatalogReportShell sections={navSections} variant="catalog" railExpanded={true}>
  <CategoryHero
    name={data.payload.category.name}
    dek={data.payload.category.description}
    tags={data.payload.category.tags ?? []}
    sources={data.payload.sources}
    publishedAt={data.payload.category.createdAt}
    updatedAt={data.payload.category.updatedAt}
    totalIdeas={data.payload.totalIdeas}
    totalPainPoints={data.payload.totalPainPoints}
    subscribeHref={ctaHref}
  />

  <CategoryLandingView
    longDescription={data.longDescription}
    children={data.payload.children}
    topIdeas={data.payload.topIdeas}
    topPainPoints={data.payload.topPainPoints}
    totalIdeas={data.payload.totalIdeas}
    totalPainPoints={data.payload.totalPainPoints}
    faq={data.payload.category.faqJson}
    siblings={data.payload.siblings.map((s) => ({
      name: s.name,
      slug: s.slug,
      parentSlug: data.payload.parent?.slug ?? null,
    }))}
    viewAllSlug={data.payload.category.slug}
    researchContext={data.payload.researchContext}
  />

  {#if r?.audienceMapping}
    <section id="audience" class="section-anchor">
      <p class="research-disclaimer">
        Analysis from latest research published in this niche.
      </p>
      <AudienceSection data={r.audienceMapping as AudienceMapping} />
    </section>
  {/if}

  {#if r?.marketSizing}
    <section id="market" class="section-anchor">
      <MarketSizing data={r.marketSizing as MarketSizingData} />
    </section>
  {/if}

  {#if r?.trendLongevity}
    <section id="trend" class="section-anchor">
      <TrendSection data={r.trendLongevity as TrendLongevity} />
    </section>
  {/if}

  <section class="section-anchor cat-close" aria-label="Commission a research file">
    <p>
      Don't see what you need?
      <a class="inline-cta" href={ctaHref} data-sveltekit-preload-data="hover">
        <span class="inline-cta-label">Commission a research file</span>
        <ArrowRight class="inline-arrow" aria-hidden="true" />
      </a>
    </p>
  </section>
</CatalogReportShell>

<style>
  .research-disclaimer {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 1rem 0;
  }

  /* ============================================================
     Inline editorial close (page-bottom, last `.section-anchor`).
     CSS copied from /ideas/+page.svelte — Svelte component-scoped
     styles can't be reused cross-file. Identical to [niche]/+page.svelte.
     ============================================================ */
  .cat-close {
    padding-top: 0; /* handled by shell .section-anchor + .section-anchor rule */
    text-align: center;
  }

  .cat-close p {
    margin: 0;
    padding: 1.5rem 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    letter-spacing: 0.02em;
  }

  .inline-cta {
    display: inline-flex;
    align-items: baseline;
    gap: 0.375rem;
    margin-left: 0.5rem;
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    text-decoration: none;
    letter-spacing: -0.005em;
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
