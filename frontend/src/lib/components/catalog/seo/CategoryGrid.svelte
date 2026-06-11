<script lang="ts">
  import ChevronRight from "lucide-svelte/icons/chevron-right";
  import { categoryPath } from "$lib/utils/urls";
  import { categoryIcon } from "$lib/utils/categoryIcons";
  import IconBadge from "./IconBadge.svelte";

  // Compact card grid — replaces the always-open accordion-by-super-group
  // pattern. Each card surfaces:
  //   1. Category identity      (icon + name + chevron, links to niche page)
  //   2. Quantity meta          (idea count + sub-niche count)
  //   3. Sub-niche peek         (always present when there are sub-niches)
  //   4. Foot link              ("+N more →" when there's overflow)
  //
  // Two-path strategy by sub-niche count:
  //   ≤ 8        → unclamped full peek, no foot (card is self-contained)
  //   > 8        → 2-line-clamped peek of top 6 + "+N more →" foot link
  //
  // Earlier iteration had a third "no peek" path for >25 sub-niches, but
  // live testing showed it creates jarring visual inconsistency across the
  // grid — half the cards had peeks, half didn't. Two paths keep every
  // card on the same rhythm regardless of whether the overflow is +4 or +49.

  interface NicheTreeNode {
    id: string;
    name: string;
    slug: string;
    description?: string | null;
    children?: NicheTreeNode[];
    _count?: { ideas: number; painPoints: number };
  }

  interface Props {
    categories: NicheTreeNode[];
  }

  let { categories }: Props = $props();

  // Peek thresholds — module-level constants. Tuned for ~320px-wide cards
  // and the catalog's typical sub-niche name lengths (~15–35 chars).
  const PEEK_FULL_MAX = 8;       // ≤ this → full unclamped peek, no foot
  const PEEK_PARTIAL_LIMIT = 6;  // > 8 → clamped peek of up to this many + foot

  type PeekKind = "full" | "partial";

  // Pure helpers — invoked per-card via {@const} inside {#each}.

  function sortSubsByDensity(subs: NicheTreeNode[]): NicheTreeNode[] {
    // Hero copy frames the catalog as "Startup Ideas & Validated Pain Points",
    // so sort by total content density (ideas + pain points), not ideas alone.
    // Alphabetical secondary sort stabilizes order when density ties.
    return [...subs].sort((a, b) => {
      const aDensity = (a._count?.ideas ?? 0) + (a._count?.painPoints ?? 0);
      const bDensity = (b._count?.ideas ?? 0) + (b._count?.painPoints ?? 0);
      if (aDensity !== bDensity) return bDensity - aDensity;
      return a.name.localeCompare(b.name);
    });
  }

  function classifyPeek(count: number): PeekKind {
    return count <= PEEK_FULL_MAX ? "full" : "partial";
  }

  function selectVisible(
    sorted: NicheTreeNode[],
    kind: PeekKind,
  ): NicheTreeNode[] {
    return kind === "full" ? sorted : sorted.slice(0, PEEK_PARTIAL_LIMIT);
  }

  function totalIdeasIn(c: NicheTreeNode): number {
    const own = c._count?.ideas ?? 0;
    const childSum = (c.children ?? []).reduce(
      (s, k) => s + (k._count?.ideas ?? 0),
      0,
    );
    return own + childSum;
  }

  function totalPainsIn(c: NicheTreeNode): number {
    const own = c._count?.painPoints ?? 0;
    const childSum = (c.children ?? []).reduce(
      (s, k) => s + (k._count?.painPoints ?? 0),
      0,
    );
    return own + childSum;
  }
</script>

<div class="cat-grid">
  {#each categories as cat (cat.id)}
    {@const sortedSubs = sortSubsByDensity(cat.children ?? [])}
    {@const peekKind = classifyPeek(sortedSubs.length)}
    {@const visibleSubs = selectVisible(sortedSubs, peekKind)}
    {@const overflow = sortedSubs.length - visibleSubs.length}
    {@const subTotalIdeas = totalIdeasIn(cat)}
    {@const subTotalPains = totalPainsIn(cat)}
    {@const Icon = categoryIcon(cat.slug)}
    <article class="grid-card">
      <a
        class="card-head"
        href={categoryPath({ slug: cat.slug, parentSlug: null })}
        data-sveltekit-preload-data="hover"
      >
        <span class="card-icon-slot">
          <IconBadge size={26}>
            <Icon size={14} />
          </IconBadge>
        </span>
        <h3>{cat.name}</h3>
        <span class="card-arrow"><ChevronRight size={14} /></span>
      </a>
      <!-- Lead stat falls back to pain points when a category has no ideas
           yet — leading with a bold "0" reads as an empty catalog. When both
           counts are zero, only the sub-niche count renders. -->
      <div class="card-meta">
        {#if subTotalIdeas > 0}
          <span class="meta-num">{subTotalIdeas.toLocaleString()}</span>
          <span class="meta-label">ideas</span>
          <span class="meta-dot" aria-hidden="true">·</span>
        {:else if subTotalPains > 0}
          <span class="meta-num">{subTotalPains.toLocaleString()}</span>
          <span class="meta-label">pain points</span>
          <span class="meta-dot" aria-hidden="true">·</span>
        {/if}
        <span class="meta-num">{sortedSubs.length}</span>
        <span class="meta-label">sub-niches</span>
      </div>
      {#if visibleSubs.length > 0}
        <ul
          class="card-peek"
          class:card-peek--full={peekKind === "full"}
        >
          {#each visibleSubs as sub, i (sub.id)}
            <li>
              <a href={categoryPath({ slug: sub.slug, parentSlug: cat.slug })}
                >{sub.name}</a
              >{#if i < visibleSubs.length - 1}<span
                  class="peek-sep"
                  aria-hidden="true">·</span
                >{/if}
            </li>
          {/each}
        </ul>
      {/if}
      {#if overflow > 0}
        <div class="card-foot">
          <a
            class="foot-link"
            href={categoryPath({ slug: cat.slug, parentSlug: null })}
            aria-label={`View ${overflow} more sub-niches in ${cat.name}`}
          >
            +{overflow} more →
          </a>
        </div>
      {/if}
    </article>
  {/each}
</div>

<style>
  .cat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
  }

  .grid-card {
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 14px 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.12s ease;
  }
  .grid-card:hover {
    border-color: var(--color-border-emphasis);
  }

  /* Card head — clickable row containing icon, title, and trailing arrow.
     Title shifts to accent on hover anywhere in this row. */
  .card-head {
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    color: inherit;
  }
  .card-icon-slot {
    display: inline-flex;
    flex-shrink: 0;
  }
  .card-head h3 {
    flex: 1;
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
    transition: color 0.12s ease;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card-head:hover h3 {
    color: var(--color-accent);
  }
  .card-arrow {
    color: var(--color-text-muted);
    flex-shrink: 0;
    display: inline-flex;
    transition: transform 0.12s ease, color 0.12s ease;
  }
  .card-head:hover .card-arrow {
    color: var(--color-accent);
    transform: translateX(2px);
  }
  .card-head:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 3px;
  }

  /* Two-fact dateline — idea count + sub-niche count, mono numerals,
     muted labels. Reads as a single line of editorial bookkeeping. */
  .card-meta {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px;
  }
  .meta-num {
    color: var(--color-text-primary);
    font-weight: 700;
    font-feature-settings: "tnum" 1, "calt" 1;
  }
  .meta-label {
    color: var(--color-text-muted);
  }
  .meta-dot {
    color: var(--color-text-muted);
    opacity: 0.55;
    margin: 0 2px;
  }

  /* Sub-niche peek — medium-path default. Inline-flowing list of links,
     line-clamped at 2 lines so cards stay compact even with 6 long names. */
  .card-peek {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--color-text-secondary, var(--color-text-primary));
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  /* Small-path modifier — drops the 2-line clamp so all sub-niches render
     regardless of name length. The full-path "card shows everything"
     contract requires no truncation. */
  .card-peek--full {
    display: block;
    -webkit-line-clamp: unset;
    line-clamp: unset;
    overflow: visible;
  }
  .card-peek li {
    display: inline;
  }
  .card-peek a {
    color: inherit;
    text-decoration: none;
    transition: color 0.12s ease;
  }
  .card-peek a:hover {
    color: var(--color-accent);
  }
  .card-peek a:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 3px;
  }
  .peek-sep {
    margin: 0 6px;
    color: var(--color-text-muted);
  }

  /* Card foot — sibling of .card-peek (NOT a child). Always visible when
     overflow > 0 or peekKind === 'none' so line-clamp can never hide it.
     Adaptive copy: "+N more →" (medium) or "Browse all N sub-niches →" (large). */
  .card-foot {
    /* auto top margin bottom-aligns feet across a grid row — cards stretch
       to the tallest sibling, so a fixed margin left feet ragged. */
    margin-top: auto;
    padding-top: 4px;
  }
  .foot-link {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: color 0.12s ease;
    display: inline-block;
    letter-spacing: 0.02em;
    /* Tap target — vertical padding gives ~28px effective hit area on
       touch devices. Negative margin cancels it for layout rhythm so
       surrounding spacing isn't disturbed. */
    padding: 6px 0;
    margin: -6px 0;
  }
  .foot-link:hover {
    color: var(--color-accent);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .foot-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    .grid-card,
    .card-head h3,
    .card-arrow,
    .card-peek a,
    .foot-link {
      transition: none;
    }
  }
</style>
