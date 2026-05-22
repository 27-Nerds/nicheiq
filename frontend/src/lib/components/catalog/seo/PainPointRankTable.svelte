<script lang="ts">
  import type { PainPointPreview } from "$lib/types/catalog-landing.js";
  import type { Theme } from "$lib/types/publicCatalog.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";
  import SeverityBar from "./SeverityBar.svelte";
  import CatalogTable from "./CatalogTable.svelte";
  import LockedListSkeleton from "./LockedListSkeleton.svelte";
  import CatalogLockedSection from "./CatalogLockedSection.svelte";
  import { painPointPath } from "$lib/utils/urls";

  // Reusable ranked-pain-points table used on category and sub-category
  // landing pages. Wraps <CatalogTable> for shared chrome (border, header
  // bg, hairline rows, hover, tier rail).
  //
  // Row is a non-anchor <div> with a card-link `::after` overlay on the
  // title, so any inner anchors (e.g. theme chip → #theme-{id}) escape via
  // z-index without producing an invalid <a>-in-<a> structure.

  interface Props {
    painPoints: PainPointPreview[];
    /** Show ranked numeric prefix (01, 02…). Default true. */
    showRank?: boolean;
    /** Render each row as a clickable surface (title is real <a>). When false,
     *  title is plain text, no card-link overlay. Default true. */
    hrefs?: boolean;
    /** Optional themes list — when supplied, an extra Theme column is
     *  rendered with a mono-uppercase chip per row. The chip resolves
     *  pp.themeId → theme.title via this list and anchors to
     *  `#theme-{themeId}`. Falls back to a static label for unresolvable
     *  IDs and an em-dash for null IDs. Sub-niche page passes this; the
     *  category-page caller leaves it undefined. */
    themes?: Theme[];
    /** When > 0, render the public teaser: the visible row(s) + N blurred,
     *  content-free skeleton rows + an unlock CTA. The locked rows' data is
     *  never passed in — the loader trims it server-side. */
    lockedCount?: number;
    /** Uniform unlock destination (a per-request redirect endpoint) — must not
     *  be session-derived so the public-cached page stays identical for all. */
    unlockHref?: string;
  }

  let {
    painPoints,
    showRank = true,
    hrefs = true,
    themes,
    lockedCount = 0,
    unlockHref = "/unlock-catalog",
  }: Props = $props();

  const lockedTotal = $derived(painPoints.length + lockedCount);

  const themeTitleById = $derived.by(() => {
    const map = new Map<string, string>();
    if (!themes) return map;
    for (const t of themes) {
      if (t.id) map.set(t.id, t.title);
    }
    return map;
  });

  const showTheme = $derived(themes != null);

  function severityTier(scaledScore: number | null): "high" | "med" | "low" {
    if (scaledScore == null) return "low";
    if (scaledScore >= 75) return "high";
    if (scaledScore >= 60) return "med";
    return "low";
  }
</script>

{#if painPoints.length > 0}
  <CatalogTable>
    <div
      class="ct-head ppr-head"
      class:with-rank={showRank}
      class:with-theme={showTheme}
    >
      {#if showRank}<span class="head-rank">#</span>{/if}
      <span class="head-title">Pain point</span>
      {#if showTheme}<span class="head-theme">Theme</span>{/if}
      <span class="head-mentions ar">Mentions</span>
      <span class="head-severity ar">Severity</span>
    </div>
    {#each painPoints as pp, i}
      {@const sev = scaleSeverity(pp.severityScore, "pain")}
      {@const tier = severityTier(sev)}
      {@const themeTitle = pp.themeId ? themeTitleById.get(pp.themeId) : undefined}
      <div
        class="ct-row ppr-row"
        class:with-rank={showRank}
        class:with-theme={showTheme}
        data-tier={tier}
      >
        {#if showRank}<span class="cell-rank">{String(i + 1).padStart(2, "0")}</span>{/if}
        {#if hrefs && pp.slug}
          <a class="title-link" href={painPointPath(pp.slug)}>{pp.title}</a>
        {:else}
          <span class="title-link static">{pp.title}</span>
        {/if}
        {#if showTheme}
          <span class="cell-theme">
            {#if pp.themeId == null}
              <span class="theme-empty">—</span>
            {:else if themeTitle}
              <a class="theme-link" href={`#theme-${pp.themeId}`} title={themeTitle}>{themeTitle.toUpperCase()}</a>
            {:else}
              <span class="theme-static" title={pp.themeId}>{pp.themeId.toUpperCase()}</span>
            {/if}
          </span>
        {/if}
        <span class="mentions">{pp.mentionCount.toLocaleString()}</span>
        <span class="severity">
          <SeverityBar value={sev} showTier={false} />
        </span>
      </div>
    {/each}
    {#if lockedCount > 0}
      <LockedListSkeleton variant="pain" count={lockedCount} />
    {/if}
  </CatalogTable>
{/if}

{#if lockedCount > 0}
  <div class="ppr-unlock">
    <CatalogLockedSection
      title="The full pain-point ranking is members-only"
      summary={`We ranked ${lockedTotal} validated pain points in this niche by mention volume and severity. Subscribe to see the complete ranking.`}
      ctaHref={unlockHref}
      ctaLabel={`Unlock all ${lockedTotal} pain points`}
    />
  </div>
{/if}

<style>
  /* Grid templates — explicit gap: 14px per mock (ideas-v2/styles.css:194).
     Both .ct-head and .ct-row share the same template so columns align. */
  .ct-head,
  .ct-row {
    grid-template-columns: 1fr 110px 170px;
    gap: 14px;
  }
  .ct-head.with-rank,
  .ct-row.with-rank {
    grid-template-columns: 44px 1fr 110px 170px;
  }
  .ct-head.with-theme,
  .ct-row.with-theme {
    grid-template-columns: 1fr 140px 110px 170px;
  }
  .ct-head.with-rank.with-theme,
  .ct-row.with-rank.with-theme {
    grid-template-columns: 44px 1fr 140px 110px 170px;
  }

  .ct-head .ar {
    text-align: right;
  }

  .cell-rank {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 600;
  }

  /* Card-link pattern: title's ::after overlay makes the whole row clickable
     while preserving theme-chip as a separately-clickable inner link via
     z-index. */
  .title-link {
    font-size: 13.5px;
    color: var(--color-text-primary);
    font-weight: 500;
    line-height: 1.4;
    text-decoration: none;
  }
  a.title-link::after {
    content: "";
    position: absolute;
    inset: 0;
  }
  a.title-link:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .title-link.static {
    cursor: default;
  }

  /* Theme chip — escapes the title-link overlay via position+z-index. */
  .cell-theme {
    position: relative;
    z-index: 1;
    min-width: 0;
  }
  .theme-link,
  .theme-static,
  .theme-empty {
    display: inline-block;
    max-width: 100%;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    font-weight: 600;
    padding: 3px 7px;
    border-radius: 4px;
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: background 0.12s, color 0.12s;
  }
  .theme-link {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface, #f5f5f5);
  }
  .theme-link:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-elevated, #fff);
  }
  .theme-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 1px;
  }
  .theme-static {
    color: var(--color-text-muted);
    background: var(--color-bg-surface, #f5f5f5);
    cursor: default;
  }
  .theme-empty {
    color: var(--color-text-muted);
    padding: 0;
  }

  .mentions {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    text-align: right;
  }
  .severity {
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }

  .ppr-unlock {
    margin-top: 20px;
  }

  /* Mobile (≤900px): keep rank + title + severity; hide theme + mentions.
     Severity is critical scanning context for pain points. */
  @media (max-width: 900px) {
    .ct-head,
    .ct-row,
    .ct-head.with-theme,
    .ct-row.with-theme {
      grid-template-columns: 1fr 100px;
    }
    .ct-head.with-rank,
    .ct-row.with-rank,
    .ct-head.with-rank.with-theme,
    .ct-row.with-rank.with-theme {
      grid-template-columns: 36px 1fr 100px;
    }
    .cell-theme,
    .head-theme,
    .mentions,
    .head-mentions {
      display: none;
    }
  }
</style>
