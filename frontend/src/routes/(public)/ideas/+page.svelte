<script lang="ts">
  import { ArrowRight } from "lucide-svelte";
  import { page } from "$app/state";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import { CategoryBreadcrumbs } from "$lib/components/catalog/seo";
  import CatalogIndexHero from "$lib/components/catalog/seo/CatalogIndexHero.svelte";
  import CategoryAccordion from "$lib/components/catalog/seo/CategoryAccordion.svelte";
  import CollectionCard from "$lib/components/catalog/seo/CollectionCard.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";

  let { data } = $props();

  const session = $derived(page.data.session);
  const ctaHref = $derived(session?.user ? "/new" : "/register?ref=catalog");

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

  // Local catalog search query — bound from CatalogIndexHero. v1 is client-only;
  // no URL sync. Filters category and sub-niche names case-insensitively.
  let query = $state("");

  // Group top-level niches by their superGroup (e.g. "Software", "Industry").
  // Niches without a super-group fall into "Uncategorized" (sortOrder=999).
  // Sub-niches inside each top-level node remain attached to that node — the
  // accordion renders them in the body when the user expands.
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

  // Filter the grouped niche tree by the search query. If a category name
  // matches, keep all its children. If only some children match, keep the
  // category with just those children. Drop categories with zero matches.
  const filteredGroups = $derived.by<NicheGroup[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q) return groupedNiches;
    const out: NicheGroup[] = [];
    for (const g of groupedNiches) {
      const niches: NicheTreeNode[] = [];
      for (const niche of g.niches) {
        const nameMatch = niche.name.toLowerCase().includes(q);
        if (nameMatch) {
          niches.push(niche);
          continue;
        }
        const matchedChildren = (niche.children ?? []).filter((c) =>
          c.name.toLowerCase().includes(q),
        );
        if (matchedChildren.length > 0) {
          niches.push({ ...niche, children: matchedChildren });
        }
      }
      if (niches.length > 0) {
        out.push({ ...g, niches });
      }
    }
    return out;
  });
  const hasMatches = $derived(filteredGroups.length > 0);

  // All section numbers are derived from running counters — do NOT hardcode
  // literals here. Hidden sections leave numbering contiguous.
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const hasCollections = $derived(data.collections.length > 0);
  const hasCategoriesTree = $derived(data.categoriesTree.length > 0);
  const num1 = $derived(nextNum(0, hasCollections));
  const num2 = $derived(nextNum(num1, hasCategoriesTree));
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs
  trail={[{ label: "Home", href: "/" }, { label: "Ideas" }]}
/>

<CatalogIndexHero totals={data.totals} bind:query />

{#if hasCollections}
  <SectionDivider num={num1} label="Featured collections" />
  <ul class="collections-grid">
    {#each data.collections as c (c.slug)}
      <li><CollectionCard collection={c} /></li>
    {/each}
  </ul>
{/if}

{#if hasCategoriesTree}
  <SectionDivider
    num={num2}
    label="Browse by category"
    metaText={`${data.totals.totalCategories} categories · ${data.totals.totalSubcategories} sub-niches`}
  />

  {#if hasMatches}
    {#each filteredGroups as group}
      <div class="niche-group">
        <header class="group-header">
          <span class="group-label">{group.name}</span>
          <span class="group-count">{group.niches.length} niches</span>
        </header>
        <CategoryAccordion categories={group.niches} defaultOpen={true} />
      </div>
    {/each}
  {:else}
    <p class="no-matches">No niches match "{query}". Try a broader term.</p>
  {/if}
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
  /* Featured collections grid — admin-curated CatalogCollection rows.
     Card markup lives in CollectionCard.svelte; this is just the layout. */
  .collections-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: 1fr;
    list-style: none;
    padding: 0;
    margin: 0;
  }
  @media (min-width: 768px) {
    .collections-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }
  .collections-grid > li {
    list-style: none;
  }

  /* Niche group rail — preserves super-group taxonomy as a quiet sub-divider
     so the user can still read groups, without competing visually with
     SectionDivider above. Reduced weight + padding per the v2 audit. */
  .niche-group {
    margin-bottom: 16px;
  }
  .niche-group:last-child {
    margin-bottom: 0;
  }
  .group-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    padding: 8px 0 4px;
  }
  .group-label {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    font-weight: 500;
  }
  .group-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .hub-empty,
  .no-matches {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    text-align: center;
    margin: 4rem 0;
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
