<script lang="ts">
  import type { IdeaPreview } from "$lib/types/catalog-landing.js";
  import { mapVerdict } from "$lib/types/publicCatalog.js";
  import { solutionDisplayTitle, originalityMetric } from "$lib/utils/solution-utils.js";
  import { page } from "$app/state";
  import IdeaHeroAside from "./IdeaHeroAside.svelte";
  import Chip from "./Chip.svelte";
  import Rocket from "lucide-svelte/icons/rocket";
  import { IDEA_ICON as IdeaIcon } from "$lib/config/entity-icons";
  import SaveButton from "../SaveButton.svelte";

  // Two-column hero for the idea detail page.
  // Left: H1 + codename + long-form description + tag chips +
  //       primary CTA + Save button + source-count line.
  // Right: IdeaHeroAside niche-score panel.
  // Breadcrumb above carries category context — no duplicate eyebrow row.
  // Verdict context lives lower on the page (e.g. inside theme/build cards) —
  // the hero leads with narrative, not adjudication.

  interface Props {
    idea: IdeaPreview;
    /** Hero primary CTA href — same target as the bottom-of-page BuildCTA. */
    ctaHref?: string | null;
    /** Sourced-from line content (e.g. "Sourced from 432 discussions"). */
    sourceCount?: number | null;
    /** ISO date string used in the visible byline. Should match the schema's
     *  `dateModified` (`updated_at ?? created_at`) so visible-vs-schema
     *  match holds for the Article block. */
    updatedAt?: string | null;
    /** Author label rendered in the byline. Should match the schema's
     *  `Article.author.name`. */
    authorName?: string;
  }

  let {
    idea,
    ctaHref = null,
    sourceCount = null,
    updatedAt = null,
    authorName = "NicheIQ Research Team",
  }: Props = $props();

  const updatedDisplay = $derived.by(() => {
    if (!updatedAt) return null;
    try {
      return new Intl.DateTimeFormat("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      }).format(new Date(updatedAt));
    } catch {
      return null;
    }
  });

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
  // the composite + tier label. Originality + solo-dev render as a secondary
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
    originality: (() => {
      const m = originalityMetric(idea);
      return m.value == null ? null : m.value * 100;
    })(),
    originalityLabel: originalityMetric(idea).label,
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
    <p class="entity-eyebrow">
      <IdeaIcon size={14} aria-hidden="true" />
      <span>Idea</span>
    </p>
    <h1>{displayTitle}</h1>
    {#if showCodename}
      <p class="codename">{idea.solution_name}</p>
    {/if}
    {#if updatedDisplay}
      <!-- Byline anchors the Article schema's author + dateModified visibly
           on the page — required by Google's Article guidelines and verified
           by the visible-vs-schema match contract. -->
      <p class="byline">
        <span class="byline-author">By {authorName}</span>
        <span class="byline-sep" aria-hidden="true">·</span>
        <span class="byline-updated">
          Updated <time datetime={updatedAt!}>{updatedDisplay}</time>
        </span>
      </p>
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
          <span>Research your niche</span>
        </a>
      {/if}
      <SaveButton itemType="idea" itemId={idea.id} returnTo={page.url.pathname} />
    </div>
    {#if sourceCount != null && sourceCount > 0}
      <p class="source-line">Sourced from {sourceCount.toLocaleString()} discussions</p>
    {/if}
    {#if (idea.researchCount ?? 0) > 0}
      <p class="source-line">
        🔬 {idea.researchCount!.toLocaleString()}
        {idea.researchCount === 1 ? "founder has" : "founders have"} researched this idea
      </p>
    {/if}
  </div>
  <IdeaHeroAside {scores} {verdict} />
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
  .entity-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 10px;
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
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
  .byline {
    display: flex;
    flex-wrap: wrap;
    gap: 0 0.5rem;
    margin: 0 0 18px;
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.5;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
  }
  .byline-author {
    color: var(--color-text-secondary);
  }
  .byline-sep {
    color: var(--color-border);
  }
  .byline-updated time {
    font-feature-settings: "tnum";
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
  /* Hero CTA cluster — strong primary in accent + Save (ghost) adjacent.
     The Save button is provided by SaveButton.svelte and matches this
     cluster's btn-cta-ghost vocabulary internally. */
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
