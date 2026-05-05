<script lang="ts">
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import ArrowRight from "lucide-svelte/icons/arrow-right";
  import CatalogTable from "./CatalogTable.svelte";
  import Trifecta from "./Trifecta.svelte";
  import VerdictBadge from "./VerdictBadge.svelte";
  import { ideaPath } from "$lib/utils/urls";
  import {
    solutionDisplayTitle,
    solutionCardDescription,
  } from "$lib/utils/solution-utils.js";

  // Ideas list-view table (image #11). Wraps <CatalogTable> for shared
  // chrome. Columns: optional rank, idea title + description, sub-niche,
  // 3 score circles (Trifecta), verdict pill, trailing arrow.
  //
  // Rows are full <a> tags — no inner anchors → no nested-anchor risk →
  // no card-link overlay needed.

  interface Props {
    ideas: IdeaPreview[];
    /** Render a numeric rank prefix (01, 02…) per visible position.
     *  Sub-niche routes pass true; category routes leave default false. */
    showRank?: boolean;
  }

  let { ideas, showRank = false }: Props = $props();

  function toScores(idea: IdeaPreview) {
    return {
      demand: idea.market_fit_score == null ? null : idea.market_fit_score * 100,
      feasibility:
        idea.technical_feasibility_score == null
          ? null
          : idea.technical_feasibility_score * 100,
      opportunity:
        idea.seo_scalability_score == null ? null : idea.seo_scalability_score * 100,
    };
  }
</script>

<div class="ideas-list-wrap">
  <CatalogTable>
    <div class="ct-head" class:with-rank={showRank}>
      {#if showRank}<span class="head-rank">#</span>{/if}
      <span class="head-idea">Idea</span>
      <span class="head-sub">Sub-niche</span>
      <span class="head-scores">Scores (D / F / O)</span>
      <span class="head-verdict">Verdict</span>
      <span class="head-arrow" aria-hidden="true"></span>
    </div>
    {#each ideas as idea, i}
      <a class="ct-row" class:with-rank={showRank} href={ideaPath(idea.slug)}>
        {#if showRank}
          <span class="cell-rank">{String(i + 1).padStart(2, "0")}</span>
        {/if}
        <div class="cell-idea">
          <h4 class="idea-title">{solutionDisplayTitle(idea)}</h4>
          <p class="idea-tagline">{solutionCardDescription(idea)}</p>
        </div>
        <span class="cell-sub">{idea.category?.name ?? "—"}</span>
        <span class="cell-scores"><Trifecta scores={toScores(idea)} /></span>
        <span class="cell-verdict"><VerdictBadge verdict={idea.source_verdict} /></span>
        <span class="cell-arrow" aria-hidden="true">
          <ArrowRight size={14} />
        </span>
      </a>
    {/each}
  </CatalogTable>
</div>

<style>
  .ideas-list-wrap {
    margin-bottom: 48px;
  }

  /* Grid templates per image #11 + 18px gap (mock spec). */
  .ct-head,
  .ct-row {
    grid-template-columns: 1fr 200px 200px 100px 24px;
    gap: 18px;
  }
  .ct-head.with-rank,
  .ct-row.with-rank {
    grid-template-columns: 36px 1fr 200px 200px 100px 24px;
  }

  .head-rank,
  .cell-rank {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    font-weight: 600;
    align-self: start;
    padding-top: 2px;
  }

  .cell-idea {
    min-width: 0;
  }
  .idea-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.005em;
    line-height: 1.35;
    margin: 0 0 3px;
  }
  .idea-tagline {
    font-size: 12.5px;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .cell-sub {
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .cell-arrow {
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    transition: transform 0.15s, color 0.15s;
  }
  /* Hover micro-animation per mock (ideas-v2/styles.css:752-755). */
  .ct-row:hover .cell-arrow {
    color: var(--color-text-primary);
    transform: translateX(2px);
  }

  /* Mobile (≤900px): keep idea + arrow visible per mock spec. Hide
     sub-niche, scores, verdict, and any rank. */
  @media (max-width: 900px) {
    .ct-head,
    .ct-row,
    .ct-head.with-rank,
    .ct-row.with-rank {
      grid-template-columns: 1fr auto;
      gap: 10px;
    }
    .head-sub,
    .cell-sub,
    .head-scores,
    .cell-scores,
    .head-verdict,
    .cell-verdict,
    .head-rank,
    .cell-rank {
      display: none;
    }
  }
</style>
