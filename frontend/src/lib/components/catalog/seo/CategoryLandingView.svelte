<script lang="ts">
  import { ideaPath, painPointPath, categoryPath } from "$lib/utils/urls";
  import type {
    CategoryLandingPayload,
    CatalogResearchContext,
    IdeaPreview,
    PainPointPreview,
    FaqEntry,
  } from "$lib/types/catalog-landing";

  import CategoryFAQ from "./CategoryFAQ.svelte";
  import RelatedCategories from "./RelatedCategories.svelte";
  import EmptyResearchState from "./EmptyResearchState.svelte";
  import CatalogThemesAndSegments from "./CatalogThemesAndSegments.svelte";

  // Phase 5.2 editorial rebuild + Phase 5.3 Overview enrichment. Single
  // shell-level root containing the editorial Overview content. Hero and
  // close are hoisted to the page template.
  interface Props {
    longDescription: string;
    /** Direct children categories (only present for real categories with kids). */
    children?: CategoryLandingPayload["children"];
    topIdeas: IdeaPreview[];
    topPainPoints?: PainPointPreview[];
    /** Total counts used in section-H2 "X of Y" labels. */
    totalIdeas?: number;
    totalPainPoints?: number;
    faq?: FaqEntry[] | null;
    siblings?: Array<{ name: string; slug: string; parentSlug?: string | null }>;
    /** Slug used for "View all" deep links. Defaults to no link. */
    viewAllSlug?: string | null;
    /** Phase 5.3: research context for the Overview metric strip + Market Segments. */
    researchContext?: CatalogResearchContext | null;
  }

  let {
    longDescription,
    children = [],
    topIdeas,
    topPainPoints = [],
    totalIdeas = 0,
    totalPainPoints = 0,
    faq = null,
    siblings = [],
    viewAllSlug = null,
    researchContext = null,
  }: Props = $props();

  const showSubcategories = $derived(children.length > 0);
  const showSolutions = $derived(topIdeas.length > 0);
  const showPainPoints = $derived(topPainPoints.length > 0);
  const showFaq = $derived((faq?.length ?? 0) > 0);
  const showRelated = $derived(siblings.length > 0);
  const isEmpty = $derived(
    totalIdeas + totalPainPoints === 0 && children.length === 0,
  );

  // Hub-style "hide count column when every cell is zero" — the em-dash
  // stripe was the loudest UX bug on the niche grid. Apply same logic to
  // subcategories: while every child has 0 items, hide the count slot
  // entirely. Once any child has data, show counts (em-dash for empties).
  const anyChildHasData = $derived(
    children.some((c) => (c.ideaCount ?? 0) + (c.painPointCount ?? 0) > 0),
  );

  // Score normalization helper. Confirmed by live DOM inspection:
  //   - severityScore is 0–1 native (the legacy <ProgressRing> multiplied by 100
  //     internally for display, which fooled an earlier review).
  //   - willingnessToPayScore is 0–1 native.
  //   - market_fit_score, novelty_score are 0–1 native.
  // All score fields use the same helper.
  function pct01(value: number | null | undefined): string | null {
    if (typeof value !== "number" || !Number.isFinite(value)) return null;
    return `${Math.round(value * 100)}`;
  }

  // ============================================================
  // Phase 5.3 Overview enrichment derivations
  // ============================================================

  function fmt(value: number | null | undefined): string {
    if (typeof value !== "number" || !Number.isFinite(value)) return "—";
    if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}k`;
    return String(value);
  }

  // Show metric strip whenever we have meaningful catalog signal — counts
  // alone (subcategories / pain points / solutions) are enough; researchContext
  // is bonus for POSTS + TOP SIGNAL cells which gate individually below.
  const hasMetricData = $derived(
    children.length > 0 ||
      totalPainPoints > 0 ||
      totalIdeas > 0 ||
      (!!researchContext &&
        (typeof researchContext.redditPostsAnalyzed === "number" ||
          !!researchContext.goNoGoVerdict)),
  );

  // Audience segments come from researchContext.audienceMapping.audience_segments.
  // The Json shape is loosely typed; cast at the boundary to keep TS happy.
  const marketSegments = $derived.by(() => {
    const am = researchContext?.audienceMapping as
      | { audience_segments?: Array<{ segment_name?: string; size_estimate?: string }> }
      | null
      | undefined;
    return (am?.audience_segments ?? []).filter((s) => s?.segment_name);
  });

  const verdictTone = $derived(
    researchContext?.goNoGoVerdict === "GO"
      ? "go"
      : researchContext?.goNoGoVerdict === "MAYBE"
        ? "maybe"
        : researchContext?.goNoGoVerdict === "NO_GO"
          ? "nogo"
          : "empty",
  );

  // Completion footnote: only when there's actually content to scroll to
  // (metric strip + segments + at least one of the body sections).
  const showCompletionFootnote = $derived(
    hasMetricData &&
      marketSegments.length > 0 &&
      (children.length > 0 ||
        topIdeas.length > 0 ||
        topPainPoints.length > 0),
  );
</script>

<section id="overview" class="section-anchor category-landing">
  <div class="cat-block cat-overview">
    <h2 class="cat-block-title">Overview</h2>
    <p class="cat-overview-prose">{longDescription}</p>

    {#if hasMetricData}
      <div class="cat-overview-metrics" aria-label="Niche metrics">
        {#if typeof researchContext?.redditPostsAnalyzed === "number"}
          <div class="metric-cell">
            <div class="metric-value tabular-nums">
              {fmt(researchContext.redditPostsAnalyzed)}
            </div>
            <div class="metric-label">Posts</div>
          </div>
        {/if}
        <div class="metric-cell">
          <div class="metric-value tabular-nums">{totalPainPoints}</div>
          <div class="metric-label">Pain points</div>
        </div>
        <!-- Subcategories — category-specific signal (NOT "Total mentions"
             like IdeaHero; that label belongs to per-niche detail pages.
             Differentiation here breaks the "every page has the same strip"
             tic flagged in anti-slop review. -->
        <div class="metric-cell">
          <div class="metric-value tabular-nums">{children.length}</div>
          <div class="metric-label">Subcategories</div>
        </div>
        <div class="metric-cell">
          <div class="metric-value tabular-nums">{totalIdeas}</div>
          <div class="metric-label">Solutions</div>
        </div>
        {#if researchContext?.goNoGoVerdict}
          <div class="metric-cell metric-cell--signal">
            <div class="metric-value verdict-{verdictTone}">
              {researchContext.goNoGoVerdict === "NO_GO"
                ? "NO-GO"
                : researchContext.goNoGoVerdict}
            </div>
            <div class="metric-label">Top signal</div>
          </div>
        {/if}
      </div>
    {/if}

    {#if marketSegments.length > 0}
      <div class="cat-overview-segments">
        <h3 class="cat-overview-segments-title">Market segments</h3>
        <dl class="cat-overview-segments-list">
          {#each marketSegments as segment, i}
            <div class="cat-overview-segment">
              <dt class="cat-overview-segment-num">
                {String(i + 1).padStart(2, "0")} —
              </dt>
              <dd class="cat-overview-segment-name">{segment.segment_name}</dd>
              {#if segment.size_estimate}
                <dd class="cat-overview-segment-size">
                  {segment.size_estimate}
                </dd>
              {/if}
            </div>
          {/each}
        </dl>
      </div>
    {/if}

    {#if showCompletionFootnote}
      <p class="cat-overview-complete">Findings continue below.</p>
    {/if}
  </div>

  {#if isEmpty}
    <EmptyResearchState />
  {/if}

  <CatalogThemesAndSegments
    contentCategorization={researchContext?.contentCategorization}
  />

  {#if showSubcategories}
    <div class="cat-block cat-subcategories">
      <header class="cat-block-header">
        <h2 class="cat-block-title">Subcategories</h2>
        <span class="cat-block-count">{children.length} items</span>
      </header>
      <ul class="subcategory-list">
        {#each children as child}
          {@const total = (child.ideaCount ?? 0) + (child.painPointCount ?? 0)}
          <li class="subcategory-row">
            <a
              class="subcategory-link"
              href={categoryPath({ slug: child.slug, parentSlug: viewAllSlug })}
              data-sveltekit-preload-data="hover"
              title={child.name}
            >
              <span class="subcategory-name">{child.name}</span>
              {#if anyChildHasData}
                <span class="subcategory-count tabular-nums">
                  {total > 0 ? total : "—"}
                </span>
              {/if}
            </a>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if showSolutions}
    <div class="cat-block cat-solutions">
      <header class="cat-block-header">
        <h2 class="cat-block-title">Top solutions</h2>
        <span class="cat-block-count">{topIdeas.length} of {totalIdeas}</span>
      </header>
      <ul class="painpoint-list">
        {#each topIdeas as idea}
          {@const fit = pct01(idea.market_fit_score)}
          {@const nov = pct01(idea.novelty_score)}
          {@const segments = [
            fit && `fit ${fit}`,
            idea.format && idea.format,
            nov && `novelty ${nov}`,
          ].filter((s): s is string => Boolean(s))}
          <li class="painpoint-row">
            <a
              class="painpoint-link"
              href={ideaPath(idea.slug)}
              data-sveltekit-preload-data="hover"
            >
              <h3 class="painpoint-title">{idea.solution_name}</h3>
              {#if idea.value_proposition || idea.description}
                <p class="painpoint-description">
                  {idea.value_proposition ?? idea.description}
                </p>
              {/if}
              {#if segments.length > 0}
                <p class="painpoint-meta">
                  {#each segments as seg, i}
                    {#if i > 0}<span class="meta-sep">·</span>{/if}
                    <span>{seg}</span>
                  {/each}
                </p>
              {/if}
            </a>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if showPainPoints}
    <div class="cat-block cat-painpoints">
      <header class="cat-block-header">
        <h2 class="cat-block-title">Top pain points</h2>
        <span class="cat-block-count">
          {topPainPoints.length} of {totalPainPoints}
        </span>
      </header>
      <ul class="painpoint-list">
        {#each topPainPoints as pp}
          {@const sev = pct01(pp.severityScore)}
          {@const wtp = pct01(pp.willingnessToPayScore)}
          {@const segments = [
            sev && `severity ${sev}`,
            wtp && `WTP ${wtp}%`,
            pp.mentionCount ? `${pp.mentionCount} mentions` : null,
          ].filter((s): s is string => Boolean(s))}
          <li class="painpoint-row">
            <a
              class="painpoint-link"
              href={painPointPath(pp.slug)}
              data-sveltekit-preload-data="hover"
            >
              <h3 class="painpoint-title">{pp.title}</h3>
              <p class="painpoint-description">{pp.description}</p>
              {#if segments.length > 0}
                <p class="painpoint-meta">
                  {#each segments as seg, i}
                    {#if i > 0}<span class="meta-sep">·</span>{/if}
                    <span>{seg}</span>
                  {/each}
                </p>
              {/if}
            </a>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#if showFaq && faq}
    <div class="cat-block cat-faq">
      <h2 class="cat-block-title">Frequently asked</h2>
      <CategoryFAQ items={faq} />
    </div>
  {/if}

  {#if showRelated}
    <div class="cat-block cat-related">
      <h2 class="cat-block-title">Related niches</h2>
      <RelatedCategories items={siblings} />
    </div>
  {/if}
</section>

<style>
  /* ============================================================
     Single-root layout — CategoryLandingView owns its own internal
     vertical rhythm via flex gap so the shell's gap doesn't apply
     to internal blocks (they aren't flex children of the shell).
     ============================================================ */
  .category-landing {
    display: flex;
    flex-direction: column;
    gap: var(--space-10);
  }

  /* ============================================================
     cat-block — internal block scaffolding
     ============================================================ */
  .cat-block-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 1rem;
    padding-bottom: 0.5rem;
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--color-border);
  }

  .cat-block-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    letter-spacing: -0.01em;
  }

  .cat-block-count {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1;
    letter-spacing: 0.04em;
  }

  /* ============================================================
     Overview — H2 + paragraph, no card chrome
     ============================================================ */
  .cat-overview .cat-block-title {
    margin-bottom: 0.625rem;
  }

  .cat-overview-prose {
    margin: 0;
    font-size: 1rem;
    line-height: 1.7;
    color: var(--color-text-secondary);
    max-width: 65ch;
    text-wrap: pretty;
    white-space: pre-line;
  }

  /* ============================================================
     Phase 5.3 Overview enrichment — metric strip + segments
     ============================================================ */

  /* Hairline-ledger metric strip. Cell count is data-dependent (3–5 cells)
     so we auto-distribute via grid-auto-flow. Same chrome as IdeaHero;
     differentiated by category-specific labels (SUBCATEGORIES vs MENTIONS). */
  .cat-overview-metrics {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    margin-top: 1.75rem;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }

  @media (max-width: 640px) {
    .cat-overview-metrics {
      grid-auto-flow: row;
      grid-template-columns: repeat(2, 1fr);
    }
    .metric-cell--signal {
      grid-column: 1 / -1;
    }
  }

  .metric-cell {
    padding: 1.125rem 1rem;
    border-left: 1px solid var(--color-border);
    text-align: center;
  }

  .metric-cell:first-child {
    border-left: none;
  }

  @media (max-width: 640px) {
    .metric-cell:nth-child(odd) {
      border-left: none;
    }
    .metric-cell:nth-child(n + 3) {
      border-top: 1px solid var(--color-border);
    }
  }

  .metric-value {
    font-family: var(--font-display);
    font-size: 1.625rem;
    font-weight: 700;
    line-height: 1.1;
    color: var(--color-text-primary);
  }

  .metric-label {
    margin-top: 0.375rem;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  /* Verdict tonal text-color — NO fill, NO pill, matches IdeaHero. */
  .verdict-go {
    color: var(--color-accent);
  }
  .verdict-maybe {
    color: var(--color-warning);
  }
  .verdict-nogo,
  .verdict-empty {
    color: var(--color-text-muted);
  }

  /* Market Segments — manual mono `01 —` prefix dl list. */
  .cat-overview-segments {
    margin-top: 1.75rem;
  }

  .cat-overview-segments-title {
    margin: 0 0 0.75rem;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .cat-overview-segments-list {
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
  }

  .cat-overview-segment {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .cat-overview-segment-num {
    flex-shrink: 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1;
  }

  .cat-overview-segment-name {
    margin: 0;
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--color-text-primary);
    flex: 1;
    min-width: 0;
  }

  .cat-overview-segment-size {
    margin: 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  /* Completion footnote — editorial wayfinding, NOT SaaS completion confetti.
     Top hairline only; the next section's top hairline supplies continuity. */
  .cat-overview-complete {
    margin: 1.75rem 0 0;
    padding: 1rem 0 0;
    border-top: 1px solid var(--color-border);
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.75rem;
    letter-spacing: 0.04em;
    text-align: center;
    color: var(--color-text-muted);
  }

  /* ============================================================
     Subcategories — editorial ToC mirroring hub niche grid
     ============================================================ */
  .subcategory-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: 1fr;
    column-gap: 2rem;
  }

  @media (min-width: 640px) {
    .subcategory-list {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (min-width: 1024px) {
    .subcategory-list {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .subcategory-row {
    list-style: none;
  }

  .subcategory-link {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.75rem;
    padding: 0.5rem 0;
    min-height: 2rem;
    text-decoration: none;
    color: var(--color-text-primary);
    font-size: 0.9375rem;
    font-weight: 500;
    transition: color 140ms ease;
  }

  .subcategory-name {
    flex: 1;
    min-width: 0;
    /* Underline-from-left via background-gradient. Same trick as the hub
       — survives `min-width: 0` without overflow:hidden conflicts and
       stops at the name's box (NOT the count column). */
    background-image: linear-gradient(currentColor, currentColor);
    background-position: 0 100%;
    background-size: 0% 1px;
    background-repeat: no-repeat;
    transition: background-size 200ms ease;
  }

  .subcategory-link:hover {
    color: var(--color-accent);
  }

  .subcategory-link:hover .subcategory-name {
    background-size: 100% 1px;
  }

  .subcategory-count {
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  /* ============================================================
     Pain-point / Top-solutions editorial list — shared structure.
     Per-row top hairline gives visual chunking against the wall-
     of-text risk three text rows would otherwise create.
     ============================================================ */
  .painpoint-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: 1fr;
    gap: 0;
  }

  @media (min-width: 768px) {
    .painpoint-list {
      grid-template-columns: repeat(2, 1fr);
      column-gap: 2rem;
    }
  }

  .painpoint-row {
    list-style: none;
  }

  .painpoint-link {
    display: block;
    padding: 1rem 0;
    border-top: 1px solid var(--color-border);
    text-decoration: none;
    color: inherit;
    transition: color 140ms ease;
  }

  .painpoint-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.3;
    letter-spacing: -0.005em;
    /* Underline-from-left on title, same trick as subcategory-name. */
    background-image: linear-gradient(currentColor, currentColor);
    background-position: 0 100%;
    background-size: 0% 1px;
    background-repeat: no-repeat;
    transition: background-size 200ms ease;
    /* Inline-block so background-size:100% sizes to the text width, not
       the link's full width. */
    display: inline;
  }

  .painpoint-link:hover .painpoint-title {
    background-size: 100% 1px;
  }

  .painpoint-description {
    margin: 0.25rem 0 0;
    font-size: 0.875rem;
    line-height: 1.55;
    color: var(--color-text-muted);
    max-width: 65ch;
    text-wrap: pretty;
    /* line-clamp 2 for tidy two-line previews */
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .painpoint-meta {
    margin: 0.375rem 0 0;
    font-family:
      ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-feature-settings: "tnum" 1;
    letter-spacing: 0.04em;
  }

  .meta-sep {
    color: var(--color-border);
    margin: 0 0.25rem;
  }

  /* ============================================================
     Reduced motion
     ============================================================ */
  @media (prefers-reduced-motion: reduce) {
    .subcategory-link,
    .subcategory-name,
    .painpoint-link,
    .painpoint-title {
      transition: none;
    }
  }
</style>
