<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import { CategoryBreadcrumbs } from "$lib/components/catalog/seo";
  import { categoryPath, programmaticPath } from "$lib/utils/urls";

  let { data } = $props();

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

  const totalNiches = $derived(data.categoriesTree.length);
  const totalCollections = $derived(data.programmaticPages.length);

  interface NicheTreeNode {
    id: string;
    name: string;
    slug: string;
    description?: string | null;
    superGroup?: { id: string; name: string; slug: string; sortOrder: number } | null;
    children?: NicheTreeNode[];
    _count?: { ideas: number; painPoints: number };
  }

  interface NicheGroup {
    id: string;
    name: string;
    sortOrder: number;
    niches: NicheTreeNode[];
  }

  // Group niches by superGroup, ordered by superGroup.sortOrder. Niches with no
  // super-group fall into "Uncategorized" with sortOrder=999. Niches inside each
  // group are sorted alphabetically — the hub is a research index, not a
  // sortOrder-ranked list.
  const groupedNiches = $derived.by<NicheGroup[]>(() => {
    const groups = new Map<string, NicheGroup>();
    for (const niche of data.categoriesTree as NicheTreeNode[]) {
      const sg = niche.superGroup;
      const key = sg?.id ?? "__uncategorized";
      if (!groups.has(key)) {
        groups.set(key, {
          id: key,
          name: sg?.name ?? "Uncategorized",
          sortOrder: sg?.sortOrder ?? 999,
          niches: [],
        });
      }
      groups.get(key)!.niches.push(niche);
    }
    const out = [...groups.values()];
    for (const g of out) {
      g.niches.sort((a, b) => a.name.localeCompare(b.name));
    }
    return out.sort((a, b) =>
      a.sortOrder !== b.sortOrder
        ? a.sortOrder - b.sortOrder
        : a.name.localeCompare(b.name),
    );
  });

  function nicheTotal(n: NicheTreeNode): number {
    return (n._count?.ideas ?? 0) + (n._count?.painPoints ?? 0);
  }

  // Phase 5.1 P1.1: while every niche has 0 items, hide the count column
  // entirely. The em-dash-everywhere stripe was reading as "disabled rows."
  // Once any niche has data, the column re-appears and uses em-dash for
  // empty rows again — at that point absence IS the signal.
  const anyHasData = $derived(
    (data.categoriesTree as NicheTreeNode[]).some((n) => nicheTotal(n) > 0),
  );
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs
  trail={[{ label: "Home", href: "/" }, { label: "Ideas" }]}
/>

<header class="hub-hero">
  <h1 class="hub-hero-title marker-rule">Startup Ideas & Pain Points</h1>
  <p class="hub-hero-dek">
    Hand-curated collections sourced from real Reddit and Hacker News
    discussions. Each idea is scored for market fit, technical feasibility,
    and SEO scalability.
  </p>
  <p class="hub-hero-provenance">
    <span>Research index</span>
    <span class="prov-sep">·</span>
    <span>{totalNiches} niches</span>
    <span class="prov-sep">·</span>
    <span>{totalCollections} collections</span>
    <span class="prov-sep">·</span>
    <span>Updated weekly</span>
  </p>
</header>

{#if data.programmaticPages.length > 0}
  <section class="hub-section">
    <h2 class="hub-section-title">Curated collections</h2>
    <ul class="programmatic-grid">
      {#each data.programmaticPages as p}
        <li class="programmatic-card">
          <a
            class="programmatic-link"
            href={programmaticPath(p.slug)}
            data-sveltekit-preload-data="hover"
          >
            <h3 class="programmatic-title">{p.title}</h3>
            <p class="programmatic-dek">{p.seoDescription}</p>
            <span class="programmatic-cta">
              <span class="programmatic-cta-label">Explore</span>
            </span>
          </a>
        </li>
      {/each}
    </ul>
  </section>
{/if}

{#if data.categoriesTree.length > 0}
  <section class="hub-section">
    <h2 class="hub-section-title">Browse by niche</h2>
    {#if !anyHasData}
      <p class="pre-launch-note">
        Counts populate as research files publish — start with the curated
        collections above.
      </p>
    {/if}
    {#each groupedNiches as group}
      <div class="niche-group">
        <header class="group-header">
          <h3 class="group-label">{group.name}</h3>
          <span class="group-count">{group.niches.length} niches</span>
        </header>
        <ul class="niche-list">
          {#each group.niches as n}
            {@const total = nicheTotal(n)}
            <li class="niche-row">
              <a
                class="niche-link"
                href={categoryPath({ slug: n.slug })}
                data-sveltekit-preload-data="viewport"
                title={n.name}
              >
                <span class="niche-name">{n.name}</span>
                {#if anyHasData}
                  <span class="niche-count tabular-nums">
                    {total > 0 ? total : "—"}
                  </span>
                {/if}
              </a>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </section>
{:else}
  <p class="hub-empty">Awaiting first findings. Re-checked weekly.</p>
{/if}

<section class="inline-close" aria-label="Commission a research file">
  <p>
    Don't see your niche?
    <a class="inline-cta" href={ctaHref} data-sveltekit-preload-data="hover">
      <span class="inline-cta-label">Commission a research file</span>
      <ArrowRight class="inline-arrow" aria-hidden="true" />
    </a>
  </p>
</section>

<style>
  /* ============================================================
     Hero
     ============================================================ */
  .hub-hero {
    margin-bottom: 3rem;
  }

  .hub-hero-title {
    font-family: var(--font-display);
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.03em;
    color: var(--color-text-primary);
    margin: 0;
  }

  .hub-hero-dek {
    margin: 1.5rem 0 0;
    max-width: 60ch;
    font-size: 1.0625rem;
    color: var(--color-text-muted);
    line-height: 1.6;
    text-wrap: pretty;
  }

  .hub-hero-provenance {
    margin: 1.25rem 0 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem 0.5rem;
    font-feature-settings: "tnum" 1, "ss01" 1;
  }

  .prov-sep {
    color: var(--color-border);
  }

  /* ============================================================
     Section scaffolding
     ============================================================ */
  .hub-section {
    margin-bottom: 3rem;
  }

  .hub-section-title {
    font-family: var(--font-display);
    font-size: 0.75rem;
    font-weight: 600;
    /* Align with .group-label and IdeaHero mono caps convention (0.08em). */
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 1.5rem 0;
  }

  /* ============================================================
     Curated Collections (programmatic SEO entry points) — unchanged
     ============================================================ */
  .programmatic-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: 1fr;
    list-style: none;
    padding: 0;
    margin: 0;
  }

  @media (min-width: 768px) {
    .programmatic-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .programmatic-card {
    list-style: none;
  }

  .programmatic-link {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 1.5rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    /* Phase 5.1 P1.3: squared corners harmonize with the now-flat niche
       index below. Cards stay distinct via background + border. */
    border-radius: 2px;
    text-decoration: none;
    color: inherit;
    transition: border-color 140ms ease;
  }

  .programmatic-link:hover {
    border-color: var(--color-border-emphasis);
  }

  .programmatic-link:active {
    transform: scale(0.998);
  }

  .programmatic-title {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.3;
    margin: 0;
    letter-spacing: -0.01em;
  }

  .programmatic-dek {
    margin: 0.75rem 0 0;
    font-size: 0.875rem;
    color: var(--color-text-muted);
    line-height: 1.55;
    flex: 1;
    text-wrap: pretty;
  }

  .programmatic-cta {
    display: inline-flex;
    align-items: baseline;
    margin-top: 1.25rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-accent);
  }

  /* Underline-from-left via background-gradient — matches the niche-link
     and inline-cta convention. Replaces the previous ArrowRight icon. */
  .programmatic-cta-label {
    background-image: linear-gradient(currentColor, currentColor);
    background-position: 0 100%;
    background-size: 0% 1px;
    background-repeat: no-repeat;
    transition: background-size 200ms ease;
  }

  .programmatic-link:hover .programmatic-cta-label {
    background-size: 100% 1px;
  }

  /* ============================================================
     Niche table-of-contents — editorial, no cell chrome
     ============================================================ */
  .niche-group {
    /* 3rem matches .hub-hero / .hub-section bottoms for shared vertical rhythm. */
    margin-bottom: 3rem;
  }

  .niche-group:last-child {
    margin-bottom: 0;
  }

  .group-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    padding-bottom: 0.5rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--color-border);
  }

  .group-label {
    /* h3 element — explicit margin reset to keep flex header layout intact */
    margin: 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .group-count {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1;
  }

  .niche-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: 1fr;
    column-gap: 2rem;
  }

  @media (min-width: 640px) {
    .niche-list {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (min-width: 1024px) {
    .niche-list {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .niche-row {
    list-style: none;
  }

  .niche-link {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.75rem;
    padding: 0.5rem 0;
    min-height: 2rem; /* ≥32px hit target */
    text-decoration: none;
    color: var(--color-text-primary);
    font-size: 0.9375rem;
    font-weight: 500;
    transition: color 140ms ease;
  }

  .niche-name {
    flex: 1;
    min-width: 0;
    /* Underline-from-left via background-gradient. background isn't
       clipped by overflow:hidden the way an absolutely-positioned ::after
       would be — and crucially it stops at the name's box, NOT the count
       column, so the count alignment stays clean per-the-spec. */
    background-image: linear-gradient(currentColor, currentColor);
    background-position: 0 100%;
    background-size: 0% 1px;
    background-repeat: no-repeat;
    transition: background-size 200ms ease;
  }

  .niche-link:hover {
    color: var(--color-accent);
  }

  .niche-link:hover .niche-name {
    background-size: 100% 1px;
  }

  .niche-count {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  /* ============================================================
     Pre-launch empty state (no categories at all)
     ============================================================ */
  .hub-empty {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    color: var(--color-text-muted);
    text-align: center;
    margin: 4rem 0;
  }

  /* ============================================================
     Inline editorial close — replaces the boxed PublicCatalogCta
     ============================================================ */
  .inline-close {
    margin-top: 4rem;
    padding: 2.5rem 0;
    border-top: 1px solid var(--color-border);
    text-align: center;
  }

  .inline-close p {
    margin: 0;
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

  /* Phase 5.1 P1.4: pre-launch reassurance copy. Renders only while every
     niche has 0 items. Self-cleaning — disappears once any niche has data. */
  .pre-launch-note {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: -0.5rem 0 1.5rem 0;
    letter-spacing: 0.02em;
    font-feature-settings: "tnum" 1;
  }

  @media (prefers-reduced-motion: reduce) {
    .programmatic-link,
    .programmatic-cta-label,
    .niche-link,
    .niche-name,
    .inline-cta,
    .inline-cta-label {
      transition: none;
    }
  }
</style>
