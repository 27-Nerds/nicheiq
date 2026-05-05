<script lang="ts">
  import { untrack } from "svelte";
  import ChevronRight from "lucide-svelte/icons/chevron-right";
  import { categoryPath } from "$lib/utils/urls";
  import { categoryIcon } from "$lib/utils/categoryIcons";
  import IconBadge from "./IconBadge.svelte";
  import SubNicheCell from "./SubNicheCell.svelte";

  // Sub-niches inside the body use SubNicheCell in its default compact
  // single-line mode (name + count) — same shape the category page uses
  // for its top-level sub-niche grid, so the visual rhythm carries.

  // Accordion of categories with sub-niche grid inside each row.
  // Top-level (parentId IS NULL) categories are the accordion sections.
  // Click a header to toggle; sub-niches are SubNicheCell links.
  //
  // NOTE: Name collides with admin/CategoryAccordion.svelte. This one is
  // public-catalog only (sits under seo/) and has different behavior.

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
    /** When true, all categories are open by default. Default true. */
    defaultOpen?: boolean;
  }

  let { categories, defaultOpen = true }: Props = $props();

  // Track open state per category id. Initialized once from the initial
  // props snapshot — `categories` and `defaultOpen` should be stable for the
  // lifetime of the component on these pages. `untrack` makes the snapshot
  // semantics explicit (and silences the runes "captures initial value"
  // warning, which is the intended behavior here).
  let openIds = $state<Set<string>>(
    untrack(() => new Set(defaultOpen ? categories.map((c) => c.id) : [])),
  );

  function toggle(id: string) {
    const next = new Set(openIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    openIds = next;
  }

  function totalIdeasIn(c: NicheTreeNode): number {
    const own = c._count?.ideas ?? 0;
    const childSum = (c.children ?? []).reduce((s, k) => s + (k._count?.ideas ?? 0), 0);
    return own + childSum;
  }
</script>

<div class="cat-accordion">
  {#each categories as cat}
    {@const isOpen = openIds.has(cat.id)}
    {@const subs = cat.children ?? []}
    {@const subTotal = totalIdeasIn(cat)}
    {@const Icon = categoryIcon(cat.slug)}
    <section class="cat-section">
      <button
        class="cat-head"
        type="button"
        aria-expanded={isOpen}
        onclick={() => toggle(cat.id)}
      >
        <span class="cat-icon-slot">
          <IconBadge size={34}>
            <Icon size={16} />
          </IconBadge>
        </span>
        <div class="cat-name">
          <h3>{cat.name}</h3>
          {#if cat.description}
            <div class="desc">{cat.description}</div>
          {/if}
        </div>
        <div class="cat-counts">
          <div class="big">{subTotal.toLocaleString()}</div>
          <div>{subs.length} sub-niches</div>
        </div>
        <span class="cat-arrow" class:open={isOpen}><ChevronRight size={16} /></span>
      </button>
      {#if isOpen && subs.length > 0}
        <div class="cat-body">
          <div class="cat-subs">
            {#each subs as sub}
              <SubNicheCell
                name={sub.name}
                href={categoryPath({ slug: sub.slug, parentSlug: cat.slug })}
                count={sub._count?.ideas ?? 0}
              />
            {/each}
          </div>
        </div>
      {/if}
    </section>
  {/each}
</div>

<style>
  .cat-accordion {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .cat-section {
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface, #fff);
    overflow: hidden;
  }
  /* Header row — slightly tighter than the page-level hero strip and
     intentionally distinct from the body grid (which is white). The
     elevated bg reads as a "section banner". */
  .cat-head {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    gap: 14px;
    align-items: center;
    padding: 12px 18px;
    background: var(--color-surface-elevated, #fafafa);
    cursor: pointer;
    transition: background 0.12s;
    width: 100%;
    border: none;
    border-bottom: 1px solid transparent;
    text-align: left;
    font-family: inherit;
    color: inherit;
  }
  .cat-icon-slot {
    display: inline-flex;
    flex-shrink: 0;
  }
  .cat-head:hover {
    background: var(--color-surface, #fff);
  }
  /* Hairline separator between header and the open body. */
  .cat-section:has(.cat-body) .cat-head {
    border-bottom-color: var(--color-border);
  }
  .cat-name {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }
  .cat-name h3 {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
    margin: 0;
  }
  .desc {
    font-size: 12px;
    color: var(--color-text-muted);
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
  }
  .cat-counts {
    font-size: 11px;
    color: var(--color-text-muted);
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 1px;
  }
  .cat-counts .big {
    font-size: 18px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.01em;
    line-height: 1;
  }
  .cat-arrow {
    color: var(--color-text-muted);
    transition: transform 0.15s;
    display: inline-flex;
  }
  .cat-arrow.open {
    transform: rotate(90deg);
  }
  /* Sub-niche grid — 1px gap on a border-coloured background gives us
     hairline dividers between cells without a 4-direction border on each
     cell. Auto-fill at 200px so 4–5 columns fit on desktop, gracefully
     reflows on narrower viewports. */
  .cat-subs {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    background: var(--color-border);
    gap: 1px;
  }
</style>
