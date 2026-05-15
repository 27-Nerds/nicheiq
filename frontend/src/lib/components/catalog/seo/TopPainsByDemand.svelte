<script lang="ts">
  import { categoryPath } from "$lib/utils/urls";
  import { formatCompact } from "$lib/utils/format-numbers";
  import { isFallbackEdition } from "$lib/seo/edition";
  import {
    scaleSeverity,
    type CatalogTotals,
    type CatalogTopPainPoint,
  } from "$lib/types/publicCatalog.js";
  import CatalogTable from "./CatalogTable.svelte";
  import OpportunityBadge from "./OpportunityBadge.svelte";

  // Bottom-of-page SEO surface for /ideas. Renders an editorial intro
  // paragraph (capped to a 65ch reading window) followed by a 10-row table
  // of the highest-severity pain points across the entire catalog. The
  // Niche cell is the row's primary link; pain titles stay as plain text
  // so they act as a citation anchor for AI Overviews. Mobile stacks each
  // row vertically and hides the secondary numeric columns.

  interface Props {
    painPoints: CatalogTopPainPoint[];
    editionLabel: string;
    totals: CatalogTotals;
  }

  let { painPoints, editionLabel, totals }: Props = $props();

  const editionPhrase = $derived(
    isFallbackEdition(editionLabel)
      ? "The latest edition"
      : `The ${editionLabel} edition`,
  );
</script>

<section class="top-pains" aria-labelledby="top-pains-heading">
  <p class="intro">
    Every month we analyze thousands of real founder and developer discussions
    to surface the most validated startup opportunities. {editionPhrase} covers
    {totals.totalIdeas.toLocaleString()} hand-curated ideas across {totals.totalCategories.toLocaleString()}
    categories, sourced from {formatCompact(totals.contentItemsMined)}+ community
    discussions — ranked by demand, pain point severity, and SEO opportunity.
  </p>

  {#if painPoints.length > 0}
    <CatalogTable>
      <div class="ct-head" role="row" id="top-pains-heading">
        <span role="columnheader">Pain Point</span>
        <span class="col-niche" role="columnheader">Niche</span>
        <span class="col-num" role="columnheader">Mentions</span>
        <span class="col-num" role="columnheader">Severity</span>
        <span class="col-opp" role="columnheader">Opportunity</span>
      </div>
      {#each painPoints as pp (pp.id)}
        {@const href = categoryPath({
          slug: pp.category.slug,
          parentSlug: pp.category.parent?.slug ?? null,
        })}
        <div class="ct-row" role="row">
          <span class="cell-title" role="cell">{pp.title}</span>
          <span class="cell-niche" role="cell">
            <a
              class="niche-link"
              {href}
              data-sveltekit-preload-data="hover"
            >
              {pp.category.name}
            </a>
          </span>
          <span class="cell-num cell-mentions" role="cell">
            {pp.mentionCount.toLocaleString()}
          </span>
          <span class="cell-num cell-severity" role="cell">
            {scaleSeverity(pp.severityScore, "pain") ?? "—"}
          </span>
          <span class="cell-opp" role="cell">
            <OpportunityBadge level={pp.opportunityLevel} />
          </span>
        </div>
      {/each}
    </CatalogTable>
  {/if}
</section>

<style>
  /* SectionDivider above already provides 40px top + 16px bottom padding,
     so no extra `margin-top` here — it would double-space the intro and
     drift away from the sibling sub-niche §03 "What people are talking
     about" rhythm. */

  /* Canonical "intro prose under section title" — mirrors
     `.theme-deck-note` on /ideas/[niche]/[sub] §03 "What people are
     talking about." Smaller, muted body so it reads as section meta
     rather than lede prose. 720px cap (rather than 65ch) keeps the
     block compact and consistent with sibling catalog sections. */
  .intro {
    display: block;
    max-width: 720px;
    margin: 0 0 18px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-muted);
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }

  /* Desktop column rhythm. Pain Point fills available space; the
     remaining columns are fixed so the right edge stays predictable. */
  .ct-head,
  .ct-row {
    grid-template-columns: minmax(0, 1fr) 200px 80px 100px 100px;
    gap: 14px;
  }

  /* Header cell alignment — numeric + opportunity columns right-align so
     the numerals line up under each header. */
  .ct-head .col-num,
  .ct-head .col-opp {
    text-align: right;
  }
  .ct-head .col-niche {
    text-align: left;
  }

  /* Pain Point title — plain text, 2-line clamp prevents tall rows when
     a single title is unusually long. */
  .cell-title {
    font-size: 13.5px;
    color: var(--color-text-primary);
    font-weight: 500;
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-width: 0;
  }

  .cell-niche {
    min-width: 0;
  }
  .niche-link {
    font-size: 13px;
    color: var(--color-text-secondary);
    text-decoration: none;
    transition: color 0.12s ease;
    display: inline-block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .niche-link:hover {
    color: var(--color-accent);
  }
  .niche-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 3px;
  }

  .cell-num {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    text-align: right;
    font-feature-settings: "tnum" 1;
  }

  .cell-opp {
    text-align: right;
  }

  /* Mobile (≤640px) — collapse the 5-column table into a stacked layout.
     Pain Point title gets its own row, Niche + Opportunity share the row
     below. Mentions + Severity drop out (secondary signals). The header
     row hides entirely (touch users don't benefit from column labels on
     a stack). `!important` on .ct-head display because CatalogTable's
     parent `:global(.ct-head)` rule sets display:grid at equal CSS
     specificity, and source order is not guaranteed by Vite. */
  @media (max-width: 640px) {
    .ct-head {
      display: none !important;
    }
    .ct-row {
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-areas:
        "title title"
        "niche opp";
      column-gap: 12px;
      row-gap: 6px;
      padding: 14px 16px;
    }
    .cell-title {
      grid-area: title;
      -webkit-line-clamp: unset;
      line-clamp: unset;
      display: block;
    }
    .cell-niche {
      grid-area: niche;
      align-self: center;
      min-width: 0;
    }
    .cell-opp {
      grid-area: opp;
      align-self: center;
      justify-self: end;
      text-align: right;
    }
    .cell-mentions,
    .cell-severity {
      display: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .niche-link {
      transition: none;
    }
  }
</style>
