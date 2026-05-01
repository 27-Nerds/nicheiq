<script lang="ts">
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils.js";
  import IdeaTagRow from "./IdeaTagRow.svelte";
  import VerdictBadge from "./VerdictBadge.svelte";
  import IdeaHeroAside from "./IdeaHeroAside.svelte";

  // Two-column hero for the idea detail page.
  // Left: tag row + H1 + lede + verdict + tag chips + actions.
  // Right: IdeaHeroAside with Trifecta + 4 mini-stats.

  interface Props {
    idea: IdeaPreview;
    /** Right-rail mini stats (TAM / pain points / sub-ideas / sources). */
    stats: Array<{ value: string | number | null; label: string }>;
  }

  let { idea, stats }: Props = $props();

  const scores = $derived({
    demand: idea.market_fit_score == null ? null : idea.market_fit_score * 100,
    feasibility:
      idea.technical_feasibility_score == null
        ? null
        : idea.technical_feasibility_score * 100,
    opportunity:
      idea.seo_scalability_score == null ? null : idea.seo_scalability_score * 100,
  });

  // Dedupe (case-insensitive) — `format` and `project_type` frequently hold
  // the same value, producing duplicate chips on the hero.
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
      out.push(t.replace(/-/g, " "));
    }
    return out;
  });
</script>

<header class="idea-hero">
  <div class="left">
    <IdeaTagRow
      categoryName={idea.category?.parent?.name ?? idea.category?.name ?? "Catalog"}
      subName={idea.category?.parent ? idea.category?.name : null}
      suffix={`Idea #${idea.id.slice(0, 8)}`}
    />
    <h1>{solutionDisplayTitle(idea)}</h1>
    <p class="codename">{idea.solution_name}</p>
    {#if idea.value_proposition || idea.description}
      <p class="lede">{idea.value_proposition ?? idea.description}</p>
    {/if}
    <div class="badges">
      <VerdictBadge verdict={idea.source_verdict} />
      {#each tags as t}
        <span class="badge">{t}</span>
      {/each}
    </div>
  </div>
  <IdeaHeroAside {scores} {stats} />
</header>

<style>
  .idea-hero {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 40px;
    align-items: flex-start;
    padding: 32px 0;
  }
  .left {
    min-width: 0;
  }
  h1 {
    font-size: 32px;
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.1;
    margin: 10px 0 4px;
    color: var(--color-text-primary);
  }
  .codename {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-text-muted);
    letter-spacing: 0.04em;
    margin: 0 0 14px;
  }
  .lede {
    font-size: 15px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 600px;
    margin: 0;
  }
  .badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 18px;
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

  @media (max-width: 900px) {
    .idea-hero {
      grid-template-columns: 1fr;
    }
  }
</style>
