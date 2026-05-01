<script lang="ts">
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import { solutionDisplayTitle, solutionCardDescription } from "$lib/utils/solution-utils.js";
  import Trifecta from "./Trifecta.svelte";
  import VerdictBadge from "./VerdictBadge.svelte";
  import ArrowRight from "lucide-svelte/icons/arrow-right";

  // Replaces CatalogIdeaCard. Mockup `.idea-card`: meta + title + Trifecta
  // + verdict badge + tags + arrow. Click → /idea/[slug].

  interface Props {
    idea: IdeaPreview;
    /** Optional sub-category label override; defaults to category.name. */
    subLabel?: string | null;
  }

  let { idea, subLabel = null }: Props = $props();

  const scores = $derived({
    demand: idea.market_fit_score == null ? null : idea.market_fit_score * 100,
    feasibility:
      idea.technical_feasibility_score == null ? null : idea.technical_feasibility_score * 100,
    opportunity: idea.seo_scalability_score == null ? null : idea.seo_scalability_score * 100,
  });

  const meta = $derived(subLabel ?? idea.category?.name ?? "");
  // Use the same headline/short_description fallbacks as job-page solution
  // sections — keeps catalog and report views consistent.
  const title = $derived(solutionDisplayTitle(idea));
  const blurb = $derived(solutionCardDescription(idea));
  // Dedupe — `format` and `project_type` frequently hold the same value
  // ("saas", "directory", "aggregator"), which would render as twin chips
  // on the card. Normalise + collapse case-insensitive duplicates.
  const tags = $derived.by(() => {
    const raw = [idea.format, idea.project_type].filter(
      (t): t is string => typeof t === "string" && t.trim() !== "",
    );
    const seen = new Set<string>();
    const out: string[] = [];
    for (const t of raw) {
      const key = t.trim().toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(t);
    }
    return out.slice(0, 2);
  });
</script>

<a class="idea-card" href={`/idea/${idea.slug}`}>
  {#if meta}
    <div class="ic-meta">{meta}</div>
  {/if}
  <div class="ic-head">
    <h3 class="ic-title">{title}</h3>
    <Trifecta {scores} size="md" />
  </div>
  <p class="ic-desc">{blurb}</p>
  <div class="ic-foot">
    <div class="ic-tags">
      <VerdictBadge verdict={idea.source_verdict} />
      {#each tags as t}
        <span class="badge">{t.replace(/-/g, " ")}</span>
      {/each}
    </div>
    <span class="ic-arrow"><ArrowRight size={14} /></span>
  </div>
</a>

<style>
  .idea-card {
    background: var(--color-surface, #fff);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
    color: inherit;
    text-decoration: none;
  }
  .idea-card:hover {
    border-color: var(--color-border-emphasis);
    background: var(--color-surface-elevated, var(--color-surface, #fafafa));
  }
  .ic-meta {
    font-size: 10px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 4px;
  }
  .ic-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }
  .ic-title {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.01em;
    line-height: 1.3;
    color: var(--color-text-primary);
    margin: 0;
  }
  .ic-desc {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .ic-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px solid var(--color-border);
    margin-top: auto;
  }
  .ic-tags {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    align-items: center;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary, var(--color-text-primary));
    background: var(--color-surface, #fff);
  }
  .ic-arrow {
    color: var(--color-text-muted);
    transition: transform 0.15s, color 0.15s;
    display: inline-flex;
  }
</style>
