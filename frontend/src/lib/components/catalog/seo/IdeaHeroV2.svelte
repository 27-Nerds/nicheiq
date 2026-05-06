<script lang="ts">
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import { mapVerdict } from "$lib/types/publicCatalog.js";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils.js";
  import IdeaHeroAside from "./IdeaHeroAside.svelte";
  import Chip from "./Chip.svelte";
  import Rocket from "lucide-svelte/icons/rocket";
  import Bookmark from "lucide-svelte/icons/bookmark";

  // Two-column hero for the idea detail page.
  // Left: H1 + codename + long-form description + tag chips +
  //       primary CTA + Save button + source-count line.
  // Right: IdeaHeroAside niche-score panel.
  // Breadcrumb above carries category context — no duplicate eyebrow row.
  // Verdict context lives lower on the page (e.g. inside theme/build cards) —
  // the hero leads with narrative, not adjudication.

  interface Props {
    idea: IdeaPreview;
    /** Right-rail mini stats. Tile renders larger when `primary: true`.
     *  Null/empty values are filtered by IdeaHeroAside. */
    stats: Array<{
      value: string | number | null;
      label: string;
      primary?: boolean;
    }>;
    /** Hero primary CTA href — same target as the bottom-of-page BuildCTA. */
    ctaHref?: string | null;
    /** Sourced-from line content (e.g. "Sourced from 432 discussions"). */
    sourceCount?: number | null;
  }

  let { idea, stats, ctaHref = null, sourceCount = null }: Props = $props();

  const displayTitle = $derived(solutionDisplayTitle(idea));
  // Show codename only when it adds information — when headline differs from
  // solution_name (case-insensitive). Otherwise the codename is redundant.
  const showCodename = $derived(
    !!idea.headline?.trim() &&
      idea.headline.trim().toLowerCase() !== idea.solution_name.trim().toLowerCase(),
  );
  // Long-form description — Pydantic spec says 4-6 sentences detailing user
  // journey. `description` is non-null per the schema. Falls back through
  // value_proposition → short_description only if description is empty.
  const lede = $derived(
    idea.description?.trim() ||
      idea.value_proposition?.trim() ||
      idea.short_description?.trim() ||
      null,
  );

  // Niche score panel: 3 primary bars (demand/feasibility/opportunity) drive
  // the composite + tier label. Novelty + solo-dev render as a secondary
  // "Founder fit" pair beneath a hairline divider — surfaced but excluded
  // from composite math so the niche score stays comparable across ideas.
  const scores = $derived({
    demand: idea.market_fit_score == null ? null : idea.market_fit_score * 100,
    feasibility:
      idea.technical_feasibility_score == null
        ? null
        : idea.technical_feasibility_score * 100,
    opportunity:
      idea.seo_scalability_score == null ? null : idea.seo_scalability_score * 100,
    novelty: idea.novelty_score == null ? null : idea.novelty_score * 100,
    soloDev:
      idea.solo_dev_feasibility == null ? null : idea.solo_dev_feasibility * 100,
  });

  // GO / CONDITIONAL / NO-GO badge — pipeline-emitted source_verdict mapped
  // through the canonical helper. Null when the report didn't produce a verdict.
  const verdict = $derived(mapVerdict(idea.source_verdict));

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
    <h1>{displayTitle}</h1>
    {#if showCodename}
      <p class="codename">{idea.solution_name}</p>
    {/if}
    {#if lede}
      <p class="lede">{lede}</p>
    {/if}
    {#if tags.length > 0}
      <div class="badges">
        {#each tags as t}
          <Chip label={t} />
        {/each}
      </div>
    {/if}
    <div class="hero-actions">
      {#if ctaHref}
        <a class="btn-cta-primary" href={ctaHref} data-sveltekit-preload-data="hover">
          <Rocket size={16} />
          <span>Validate this idea</span>
        </a>
      {/if}
      <button class="btn-cta-ghost" type="button" aria-label="Save this idea">
        <Bookmark size={14} />
        <span>Save</span>
      </button>
    </div>
    {#if sourceCount != null && sourceCount > 0}
      <p class="source-line">Sourced from {sourceCount.toLocaleString()} discussions</p>
    {/if}
  </div>
  <IdeaHeroAside {scores} {stats} {verdict} />
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
    margin: 0 0 4px;
    color: var(--color-text-primary);
    text-wrap: balance;
    max-width: 720px;
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
    line-height: 1.65;
    max-width: 640px;
    margin: 0;
    text-wrap: pretty;
  }
  .lede::first-letter {
    font-weight: 500;
    color: var(--color-text-primary);
  }
  .badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 18px;
  }
  /* Hero CTA cluster — strong primary in accent + ghost Save adjacent.
     Save is intentionally non-functional (no backend bookmarking yet); the
     button renders for layout completeness. Export PDF deliberately omitted. */
  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 22px;
  }
  .btn-cta-primary {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 13px 22px;
    border-radius: 6px;
    font-size: 15px;
    font-weight: 600;
    background: var(--color-accent);
    color: var(--color-surface, #fff);
    text-decoration: none;
    border: 1px solid transparent;
    transition: background-color 140ms ease, box-shadow 140ms ease,
      transform 140ms ease;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.2),
      0 1px 2px rgba(154, 52, 18, 0.22),
      0 8px 18px rgba(154, 52, 18, 0.14);
  }
  .btn-cta-primary:hover {
    background: var(--color-accent-hover, var(--color-accent-dark));
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.22),
      0 2px 4px rgba(154, 52, 18, 0.26),
      0 10px 22px rgba(154, 52, 18, 0.16);
  }
  .btn-cta-primary:active {
    transform: scale(0.98);
  }
  .btn-cta-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .btn-cta-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 13px 18px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    background: var(--color-bg-elevated, #fff);
    color: var(--color-text-secondary, var(--color-text-primary));
    border: 1px solid var(--color-border-emphasis);
    cursor: pointer;
    font-family: inherit;
    transition: color 140ms ease, border-color 140ms ease, background 140ms ease;
  }
  .btn-cta-ghost:hover {
    color: var(--color-text-primary);
    border-color: var(--color-text-muted);
    background: var(--color-bg-base, #fafafa);
  }
  .btn-cta-ghost:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  /* Source provenance line — quiet mono row beneath the CTA, gives social
     proof in-flow without burying it in the right-rail tile. */
  .source-line {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--color-text-muted);
    margin: 14px 0 0;
  }
  @media (max-width: 900px) {
    .idea-hero {
      grid-template-columns: 1fr;
    }
  }
</style>
