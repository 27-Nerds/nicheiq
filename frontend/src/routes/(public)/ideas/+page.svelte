<script lang="ts">
  import { ArrowRight, X } from "lucide-svelte";
  import { page } from "$app/state";
  import { goto } from "$app/navigation";
  import { SeoHead, JsonLd } from "$lib/components/seo";
  import { CategoryBreadcrumbs } from "$lib/components/catalog/seo";
  import CatalogIndexHero from "$lib/components/catalog/seo/CatalogIndexHero.svelte";
  import CategoryGrid from "$lib/components/catalog/seo/CategoryGrid.svelte";
  import CollectionCard from "$lib/components/catalog/seo/CollectionCard.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
  import TopPainsByDemand from "$lib/components/catalog/seo/TopPainsByDemand.svelte";
  import { isFallbackEdition } from "$lib/seo/edition";

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

  // Catalog search query — bound from CatalogIndexHero. URL-synced via ?q=
  // so search state survives reload and is shareable. Initialized once from
  // the URL; the $effect below mirrors changes back to the URL with debounce.
  let query = $state(page.url.searchParams.get("q") ?? "");

  let queryDebounce: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    // Reading `query` registers the dependency so this re-runs on input.
    const value = query;
    if (queryDebounce) clearTimeout(queryDebounce);
    queryDebounce = setTimeout(() => {
      const params = new URLSearchParams(page.url.searchParams);
      if (value.trim()) params.set("q", value);
      else params.delete("q");
      const qs = params.toString();
      const target = `/ideas${qs ? "?" + qs : ""}`;
      // Avoid pushing a no-op navigation when the URL hasn't changed (e.g. on
      // first paint where query already matches the URL).
      if (target !== page.url.pathname + page.url.search) {
        goto(target, {
          replaceState: true,
          keepFocus: true,
          noScroll: true,
        });
      }
    }, 200);
    return () => {
      if (queryDebounce) clearTimeout(queryDebounce);
    };
  });

  // Active-collection filter — driven by ?collection=<slug>. When set, the
  // accordion is restricted to categories whose slug (or any child's slug) is
  // in the collection's categorySlugs set. Backend B4 ensures parent slugs
  // are included, so a collection of sub-niche items still surfaces under the
  // parent category.
  const collectionCategorySet = $derived(
    data.activeCollection
      ? new Set(data.activeCollection.categorySlugs)
      : null,
  );

  function clearCollectionFilter() {
    const params = new URLSearchParams(page.url.searchParams);
    params.delete("collection");
    const qs = params.toString();
    goto(`/ideas${qs ? "?" + qs : ""}`, {
      replaceState: true,
      keepFocus: true,
      noScroll: true,
    });
  }

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

  // Filter the grouped niche tree by (a) the active collection filter and
  // (b) the text search query. Collection filter applies first, then query.
  // If a category name matches the query, keep all its children. If only some
  // children match, keep the category with just those children. Drop
  // categories with zero matches under either filter.
  const filteredGroups = $derived.by<NicheGroup[]>(() => {
    const collectionSet = collectionCategorySet;
    const q = query.trim().toLowerCase();

    // Step 1: apply collection filter (if active).
    const collectionFiltered: NicheGroup[] = collectionSet
      ? groupedNiches
          .map((g) => ({
            ...g,
            niches: g.niches
              .filter(
                (n) =>
                  collectionSet.has(n.slug) ||
                  (n.children ?? []).some((c) => collectionSet.has(c.slug)),
              )
              .map((n) =>
                collectionSet.has(n.slug)
                  ? n
                  : {
                      ...n,
                      children: (n.children ?? []).filter((c) =>
                        collectionSet.has(c.slug),
                      ),
                    },
              ),
          }))
          .filter((g) => g.niches.length > 0)
      : groupedNiches;

    // Step 2: apply text query filter.
    if (!q) return collectionFiltered;
    const out: NicheGroup[] = [];
    for (const g of collectionFiltered) {
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
  // Total niche count across all super-groups — distinct from
  // `filteredGroups.length` (which is the number of super-groups).
  const matchedNicheCount = $derived(
    filteredGroups.reduce((sum, g) => sum + g.niches.length, 0),
  );

  // All section numbers are derived from running counters — do NOT hardcode
  // literals here. Hidden sections leave numbering contiguous.
  function nextNum(prev: number, show: boolean): number {
    return show ? prev + 1 : prev;
  }
  const hasCollections = $derived(data.collections.length > 0);
  const hasCategoriesTree = $derived(data.categoriesTree.length > 0);
  const hasTopPains = $derived(data.topPainPoints.length > 0);
  const num1 = $derived(nextNum(0, hasCollections));
  const num2 = $derived(nextNum(num1, hasCategoriesTree));
  const num3 = $derived(nextNum(num2, hasTopPains));
  // Section label drops the month suffix when the freshness guardrail trips
  // ("Latest edition" stand-in), so we don't end up with the awkward
  // "Most In-Demand SaaS Niches — Latest edition" string.
  const topPainsLabel = $derived(
    isFallbackEdition(data.editionLabel)
      ? "Most In-Demand SaaS Niches"
      : `Most In-Demand SaaS Niches — ${data.editionLabel}`,
  );

  // Lightweight relative-time helper for the section-02 metaText. Reads the
  // largest unit that fits ("3 days ago", "2 hours ago"). Falls back gracefully
  // when the timestamp is null/unparseable.
  function formatRelative(iso: string | null): string {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const diffMs = Date.now() - d.getTime();
    const diffSec = Math.max(0, Math.floor(diffMs / 1000));
    if (diffSec < 60) return "just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? "" : "s"} ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? "" : "s"} ago`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 30) return `${diffDay} day${diffDay === 1 ? "" : "s"} ago`;
    const diffMo = Math.floor(diffDay / 30);
    if (diffMo < 12) return `${diffMo} month${diffMo === 1 ? "" : "s"} ago`;
    const diffYr = Math.floor(diffMo / 12);
    return `${diffYr} year${diffYr === 1 ? "" : "s"} ago`;
  }
  const browseMeta = $derived(
    data.totals.lastUpdated
      ? `last updated ${formatRelative(data.totals.lastUpdated)} · weekly cadence`
      : "weekly cadence",
  );
</script>

<SeoHead {...data.meta} />
<JsonLd data={data.jsonld} />

<CategoryBreadcrumbs
  trail={[{ label: "Home", href: "/" }, { label: "Ideas" }]}
/>

<CatalogIndexHero totals={data.totals} bind:query {ctaHref} />

{#if hasCollections}
  <SectionDivider num={num1} label="Featured collections" />
  <ul class="collections-grid">
    {#each data.collections as c (c.slug)}
      <li><CollectionCard collection={c} /></li>
    {/each}
  </ul>
{/if}

{#if hasCategoriesTree}
  <SectionDivider num={num2} label="Browse by category" metaText={browseMeta} />

  {#if data.activeCollection || query.trim()}
    <div class="filter-cluster">
      {#if data.activeCollection}
        <span class="filter-chip filter-chip--collection">
          <span class="chip-label">FILTERED</span>
          <span class="chip-name">{data.activeCollection.name}</span>
          <button
            type="button"
            class="chip-clear"
            onclick={clearCollectionFilter}
            aria-label="Clear collection filter"
          >
            <X size={12} aria-hidden="true" />
            Clear
          </button>
        </span>
      {/if}
      {#if query.trim()}
        <span class="filter-chip filter-chip--results">
          <span class="chip-label">RESULTS</span>
          <span class="chip-name">"{query.trim()}"</span>
          <span class="chip-count">{matchedNicheCount} {matchedNicheCount === 1 ? 'niche' : 'niches'}</span>
          <button
            type="button"
            class="chip-clear"
            onclick={() => (query = "")}
            aria-label="Clear search query"
          >
            <X size={12} aria-hidden="true" />
            Clear
          </button>
        </span>
      {/if}
    </div>
  {:else if data.collectionSlug && !data.activeCollection}
    <p class="no-matches">
      Collection "{data.collectionSlug}" not found.
      <a href="/ideas">Show all categories</a>.
    </p>
  {/if}

  {#if hasMatches}
    {#each filteredGroups as group}
      <div class="niche-group">
        <header class="group-header">
          <span class="group-label">{group.name}</span>
          <span class="group-count">{group.niches.length} niches</span>
        </header>
        <CategoryGrid categories={group.niches} />
      </div>
    {/each}
  {:else if data.activeCollection}
    <p class="no-matches">
      No categories in this collection match
      {query ? `"${query}"` : "the current view"}.
    </p>
  {:else}
    <p class="no-matches">No niches match "{query}". Try a broader term.</p>
  {/if}
{:else}
  <p class="hub-empty">Awaiting first findings. Re-checked weekly.</p>
{/if}

{#if hasTopPains}
  <SectionDivider num={num3} label={topPainsLabel} />
  <TopPainsByDemand
    painPoints={data.topPainPoints}
    editionLabel={data.editionLabel}
    totals={data.totals}
  />
{/if}

<section class="inline-close" aria-label="Run your own research">
  <p>
    Ready to explore a niche we haven't covered yet?
    <a class="inline-cta" href={ctaHref} data-sveltekit-preload-data="hover">
      <span class="inline-cta-label">Run your own research</span>
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
    font-size: 0.625rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent-muted);
    font-weight: 600;
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
  .no-matches a {
    color: var(--color-accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  /* Filter cluster — wrapper that holds active-collection and search-results
     chips above the niche groups. Both chips share shape; eyebrow color
     differentiates state (accent = destination filter, muted = search). */
  .filter-cluster {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0.5rem 0 1rem;
  }
  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.5rem 0.75rem 0.5rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-surface, #fff);
  }
  .filter-chip--collection {
    border: 1px solid var(--color-border-accent);
    border-left: 3px solid var(--color-accent);
    background: rgba(234, 88, 12, 0.04);
  }
  .filter-chip--collection .chip-label {
    color: var(--color-accent);
  }
  .filter-chip--results {
    border-left: 3px solid var(--color-text-muted);
  }
  .filter-chip--results .chip-label {
    color: var(--color-text-muted);
  }
  .chip-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .chip-name {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.005em;
  }
  .chip-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1, "calt" 1;
  }
  .chip-clear {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    margin-left: 4px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-surface);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition:
      color 0.12s ease,
      border-color 0.12s ease;
  }
  .chip-clear:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
  }
  .chip-clear:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
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
