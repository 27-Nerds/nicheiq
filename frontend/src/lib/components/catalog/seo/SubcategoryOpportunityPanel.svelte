<script lang="ts">
  import type { IdeaPreview, PainPointPreview } from "$lib/types/catalog-landing.js";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";
  import Trifecta from "./Trifecta.svelte";
  import VerdictBadge from "./VerdictBadge.svelte";
  import { painPointPath, ideaPath } from "$lib/utils/urls";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils.js";
  import ArrowDown from "lucide-svelte/icons/arrow-down";

  // Sub-category hero right rail. Replaces the generic CategoryHeroAside on
  // sub-niche routes with a more focused "where the room is" panel:
  // top pain → highest-opportunity idea → GO count anchor.

  interface Props {
    topPainPoint: PainPointPreview | null;
    /** Sorted by seo_scalability_score desc; component picks idx 0. */
    topIdea: IdeaPreview | null;
    goCount: number;
    totalIdeas: number;
    /** Anchor scroll target, defaults to "#sub-ideas" matching route convention. */
    seeAllHref?: string;
  }

  let {
    topPainPoint,
    topIdea,
    goCount,
    totalIdeas,
    seeAllHref = "#sub-ideas",
  }: Props = $props();

  const topPainSeverity = $derived(
    topPainPoint ? scaleSeverity(topPainPoint.severityScore, "pain") : null,
  );

  const topIdeaScores = $derived.by(() => {
    if (!topIdea) return null;
    return {
      demand:
        topIdea.market_fit_score == null
          ? null
          : topIdea.market_fit_score * 100,
      feasibility:
        topIdea.technical_feasibility_score == null
          ? null
          : topIdea.technical_feasibility_score * 100,
      opportunity:
        topIdea.seo_scalability_score == null
          ? null
          : topIdea.seo_scalability_score * 100,
    };
  });

  const hasContent = $derived(
    !!topPainPoint || !!topIdea || (totalIdeas > 0 && goCount > 0),
  );
</script>

{#if hasContent}
  <aside class="op-panel">
    {#if topPainPoint}
      <a class="op-top" href={painPointPath(topPainPoint.slug)}>
        <span class="op-label">Where the room is</span>
        <h3>{topPainPoint.title}</h3>
        <div class="op-meta">
          {#if topPainSeverity != null}
            <span class="op-sev">Severity {topPainSeverity}</span>
          {/if}
          <span class="op-mentions">{topPainPoint.mentionCount.toLocaleString()} mentions</span>
        </div>
      </a>
    {/if}

    {#if topIdea && topIdeaScores}
      <a class="op-idea" href={ideaPath(topIdea.slug)}>
        <span class="op-idea-label">Featured idea</span>
        <div class="op-idea-name">{solutionDisplayTitle(topIdea)}</div>
        <div class="op-idea-foot">
          <Trifecta scores={topIdeaScores} size="md" />
          <VerdictBadge verdict={topIdea.source_verdict} />
        </div>
      </a>
    {/if}

    {#if totalIdeas > 0}
      <div class="op-go-row" class:no-verdicts={goCount === 0}>
        {#if goCount > 0}
          <span>
            <b>{goCount}</b> of {totalIdeas} ideas verdict
            <span class="go-pill">GO</span>
          </span>
        {:else}
          <!-- Most sub-niches don't have GO/NO-GO verdicts yet (those come from
               commissioning a research file). Suppressing the "0 of N verdict GO"
               line removes the empty zero-state; "See all" link still useful. -->
          <span class="op-tracked"><b>{totalIdeas}</b> {totalIdeas === 1 ? 'idea' : 'ideas'} tracked</span>
        {/if}
        <a class="see-all" href={seeAllHref}>
          See all
          <ArrowDown size={11} />
        </a>
      </div>
    {/if}
  </aside>
{/if}

<style>
  .op-panel {
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-surface, #fff);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .op-top {
    padding: 18px 20px;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-accent-glow, rgba(234, 88, 12, 0.04));
    color: inherit;
    text-decoration: none;
    transition: background 0.12s;
  }
  .op-top:hover {
    background: var(--color-accent-subtle, rgba(234, 88, 12, 0.08));
  }
  .op-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-accent);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .op-top h3 {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1.3;
    color: var(--color-text-primary);
    text-wrap: balance;
    margin: 0;
  }
  .op-meta {
    display: flex;
    gap: 10px;
    margin-top: 10px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
  }
  .op-sev {
    color: var(--color-error);
    font-weight: 600;
  }
  .op-mentions {
    color: var(--color-text-secondary, var(--color-text-primary));
  }

  .op-idea {
    padding: 14px 20px;
    border-bottom: 1px solid var(--color-border);
    color: inherit;
    text-decoration: none;
    transition: background 0.12s;
  }
  .op-idea:hover {
    background: var(--color-bg-elevated, #fafafa);
  }
  .op-idea-label {
    display: block;
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .op-idea-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
    letter-spacing: -0.005em;
    line-height: 1.35;
    margin-bottom: 10px;
  }
  .op-idea-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .op-go-row {
    padding: 11px 20px;
    background: var(--color-bg-elevated, #fafafa);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .op-go-row b {
    color: var(--color-text-primary);
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .op-tracked {
    color: var(--color-text-secondary, var(--color-text-primary));
  }
  .go-pill {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    background: var(--color-success-subtle, rgba(34, 197, 94, 0.1));
    color: var(--color-success-dark);
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
    margin-left: 2px;
  }
  .see-all {
    color: var(--color-text-primary);
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    text-decoration: none;
    transition: color 0.12s;
  }
  .see-all:hover {
    color: var(--color-accent);
  }
</style>
