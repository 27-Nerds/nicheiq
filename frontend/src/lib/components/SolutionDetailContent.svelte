<script lang="ts">
  import {
    ChevronDown,
    ChevronUp,
  } from "lucide-svelte";
  import { renderTechnicalContent } from "$lib/utils/format";
  import { untrack } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { SolutionPreview } from "$lib/types/job";
  import FacetChips from "$lib/components/FacetChips.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { humanizeTag, tagDescription } from "$lib/utils/ideaTagLabels";
  import { angleLabel } from "$lib/utils/ideaAngleLabels";
  import { strengthEntry, SUPERPOWERS_DETAILED } from "$lib/utils/superpower";

  interface Props {
    solution: SolutionPreview;
  }

  let { solution }: Props = $props();

  let expandedSections = new SvelteSet<string>();
  let descExpanded = $state(false);

  // Grounded generation provenance: the (pain × segment) cell that produced this idea.
  const provenance = $derived.by(() => {
    const pain = solution.source_pain?.trim() || solution.pain_points_addressed?.[0]?.trim();
    if (!pain) return null;
    return { pain, seg: solution.source_segment?.trim() || null };
  });

  // Reset description expansion on solution change
  $effect(() => {
    solution;
    untrack(() => { descExpanded = false; });
  });

  // Closed-vocabulary tag facets, grouped for display (docs/IDEA_TAGS.md). Each chip carries a
  // one-line hover explanation (tagDescription).
  const strengthChips = $derived(
    (solution.tags?.strengths ?? [])
      .map((k) => {
        const entry = strengthEntry(k, SUPERPOWERS_DETAILED);
        return entry ? { ...entry, description: tagDescription(k) } : null;
      })
      .filter((e): e is NonNullable<typeof e> => e != null),
  );
  const chip = (v: string, label?: string) => ({ label: label ?? humanizeTag(v), description: tagDescription(v) });
  // data-access values that signal sourcing friction → surfaced as watch-outs
  const FRICTION_DATA = new Set(["paywalled", "unofficial", "restricted", "blocked", "unverified"]);

  // Model = identity only (what / who / how it earns) - always shown, neutral.
  const modelItems = $derived.by(() => {
    const t = solution.tags;
    if (!t) return [];
    const items: { label: string; description?: string }[] = [];
    if (t.project_type) items.push(chip(t.project_type));
    if (t.target_market) items.push(chip(t.target_market));
    if (t.monetization)
      items.push(
        chip(
          t.monetization,
          humanizeTag(t.monetization) +
            (t.monetization_secondary ? ` + ${humanizeTag(t.monetization_secondary)}` : ""),
        ),
      );
    if (t.usage_cadence) items.push(chip(t.usage_cadence));
    return items;
  });
  // Growth: show all channels - programmatic-SEO is a meaningful positive (scalable organic
  // growth), so keep it even though it's common in some niches.
  const growthItems = $derived(
    (solution.tags?.growth_channels ?? []).map((g) => ({ label: humanizeTag(g), description: tagDescription(g) })),
  );
  // Watch-outs = the standout NEGATIVES (warning-toned): hard-to-build, unoriginal, sourcing
  // friction, and risk flags. Positives live in Strengths; the neutral middle is hidden.
  const watchOutItems = $derived.by(() => {
    const t = solution.tags;
    if (!t) return [];
    const items: { label: string; description?: string }[] = [];
    if (t.build_complexity === "high") items.push(chip("high"));
    if (t.novelty_level === "conventional") items.push(chip("conventional"));
    if (t.data_access && FRICTION_DATA.has(t.data_access))
      // Prefer the verifier's per-idea, evidence-grounded note (LLM-generated) over the static
      // definition - it explains WHY *this* idea's data route is gated/unverified, citing the search.
      items.push({
        label: humanizeTag(t.data_access),
        description: solution.data_acquisition_notes?.trim() || tagDescription(t.data_access),
      });
    for (const r of t.risk_flags ?? []) items.push(chip(r));
    // Pricing-shape mismatch (code-derived): episodic/one-shot usage sold as a subscription —
    // the note explains the churn risk and the shape to consider instead.
    if (t.pricing_shape_mismatch)
      items.push({
        label: "Pricing-shape mismatch",
        description: t.pricing_shape_note?.trim() || tagDescription(t.usage_cadence ?? ""),
      });
    return items;
  });

  // Dev time parsing
  const devTimeParsed = $derived.by(() => {
    const devTime = solution.estimated_development_time;
    if (!devTime) return null;
    const match = devTime.match(/^[\d\-\+]+\s*(?:weeks?|months?|days?)/i);
    if (match) return { short: match[0], full: devTime };
    if (devTime.length <= 20) return { short: devTime, full: devTime };
    return { short: devTime.slice(0, 17) + "...", full: devTime };
  });

  const decisionFacts = $derived.by(() => {
    const facts: { label: string; value: string }[] = [];
    const pain = provenance?.pain;
    const audience = provenance?.seg || solution.tags?.target_market;
    const productShape = solution.tags?.project_type || solution.project_type;
    const revenue = solution.tags?.monetization;

    if (pain) facts.push({ label: "Pain signal", value: pain });
    if (audience) facts.push({ label: "Audience", value: humanizeTag(audience) });
    if (productShape) facts.push({ label: "Product shape", value: humanizeTag(productShape) });
    if (revenue) facts.push({ label: "Revenue model", value: humanizeTag(revenue) });
    if (devTimeParsed?.short) facts.push({ label: "Build range", value: devTimeParsed.short });

    return facts.slice(0, 4);
  });

  // Expandable sections config - why_it_works removed (surfaced inline instead)
  const detailSections = $derived.by(() => {
    const sections: { id: string; label: string; hasContent: boolean }[] = [];

    if (solution.pricing_strategy) sections.push({ id: 'pricing', label: 'Pricing Strategy', hasContent: true });
    if (solution.conventional_approach || solution.innovation_angle)
      sections.push({ id: 'innovation', label: 'Innovation Breakdown', hasContent: true });
    if (solution.core_features && solution.core_features.length > 0)
      sections.push({ id: 'features', label: 'Core Features', hasContent: true });
    if (solution.pain_points_addressed && solution.pain_points_addressed.length > 0)
      sections.push({ id: 'painpoints', label: 'Pain Points', hasContent: true });
    if (solution.differentiation_factors && solution.differentiation_factors.length > 0)
      sections.push({ id: 'differentiation', label: 'Differentiation', hasContent: true });
    if (solution.target_personas && solution.target_personas.length > 0)
      sections.push({ id: 'personas', label: 'Target Personas', hasContent: true });
    if (solution.programmatic_seo_opportunity)
      sections.push({ id: 'seo', label: 'SEO Opportunity', hasContent: true });
    if (solution.estimated_cac_organic)
      sections.push({ id: 'cac', label: 'Estimated CAC', hasContent: true });
    if (solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0)
      sections.push({ id: 'queries', label: 'Organic Queries', hasContent: true });

    return sections;
  });

  // Auto-expand features + painpoints on solution change (or first 2 available)
  $effect(() => {
    solution;
    untrack(() => {
      expandedSections.clear();
      const prioritized = ['features', 'painpoints'];
      let opened = 0;
      for (const id of prioritized) {
        if (detailSections.some(s => s.id === id) && opened < 2) {
          expandedSections.add(id);
          opened++;
        }
      }
      if (opened < 2) {
        for (const s of detailSections) {
          if (!expandedSections.has(s.id) && opened < 2) {
            expandedSections.add(s.id);
            opened++;
          }
        }
      }
    });
  });

  const allExpanded = $derived(
    detailSections.length > 0 && expandedSections.size >= detailSections.length
  );

  function toggleSection(id: string) {
    if (expandedSections.has(id)) {
      expandedSections.delete(id);
    } else {
      expandedSections.add(id);
    }
  }

  function toggleAll() {
    if (allExpanded) {
      expandedSections.clear();
    } else {
      for (const s of detailSections) {
        expandedSections.add(s.id);
      }
    }
  }
</script>

<!-- Single-column layout -->
<div class="solution-detail-content">
  <!-- Grounded decision facts for the shortlist decision. -->
  {#if decisionFacts.length}
    <dl class="decision-facts" aria-label="Candidate decision facts">
      {#each decisionFacts as fact}
        <div>
          <dt>{fact.label}</dt>
          <dd>{fact.value}</dd>
        </div>
      {/each}
    </dl>
  {/if}

  <!-- Closed-vocabulary tag facets: Strengths / Model / Signals & risks (docs/IDEA_TAGS.md) -->
  {#if solution.tags}
    <div class="facet-panel">
      {#if strengthChips.length > 0}
        <div class="facet-group">
          <span class="mono-label">Strengths</span>
          <div class="facet-chips">
            {#each strengthChips as s}
              <Tooltip content={s.description} class="cursor-help">
                {#snippet children()}
                  <span class="strength-chip strength-chip-{s.variant}">{s.label}</span>
                {/snippet}
              </Tooltip>
            {/each}
          </div>
        </div>
      {/if}
      <FacetChips label="Model" items={modelItems} tone="neutral" />
      <FacetChips label="Growth" items={growthItems} tone="neutral" />
      <FacetChips label="Watch-outs" items={watchOutItems} tone="neutral" />
    </div>
  {/if}

  <!-- Description (truncated to ~4 lines with expand) -->
  <div class="description-block">
    <p class="body-copy {descExpanded ? '' : 'truncate-4'}">
      {solution.description}
    </p>
    <button
      type="button"
      class="text-button"
      onclick={() => { descExpanded = !descExpanded; }}
    >
      {descExpanded ? 'Show less' : 'Read more'}
    </button>
  </div>

  <!-- Why it works - surfaced inline (was buried in Innovation Breakdown pill) -->
  {#if solution.why_it_works}
    <div class="insight-callout">
      <span class="mono-label">Why it works</span>
      <p>{solution.why_it_works}</p>
    </div>
  {/if}

  <!-- Angle - which GTM angle wins for this idea + where its differentiation lives -->
  {#if solution.winning_angle && solution.angle_rationale}
    <div class="insight-callout">
      <span class="mono-label">Angle / {angleLabel(solution.winning_angle)}</span>
      <p>{solution.angle_rationale}</p>
      {#if solution.differentiation_locus}
        <p class="subnote">
          <span class="font-medium text-text-secondary">Where the edge lives:</span>
          {solution.differentiation_locus}
        </p>
      {/if}
    </div>
  {/if}

  <div class="validation-strip">
    <span class="mono-label">Deep Research will check</span>
    <ul>
      <li>Demand evidence and search behavior</li>
      <li>Competitive alternatives and gaps</li>
      <li>Market sizing and acquisition routes</li>
      <li>MVP scope, data access, and go-to-market risk</li>
    </ul>
  </div>

  <!-- Expandable detail sections -->
  {#if detailSections.length > 0}
    <div class="detail-section-list">
      {#if detailSections.length > 2}
        <button
          type="button"
          class="section-toggle"
          onclick={toggleAll}
        >
          {allExpanded ? 'Collapse all' : 'Show all details'}
        </button>
      {/if}

      {#each detailSections as section}
        <section class="detail-section-card" class:is-open={expandedSections.has(section.id)}>
          <button
            type="button"
            class="section-trigger"
            onclick={() => toggleSection(section.id)}
            aria-expanded={expandedSections.has(section.id)}
          >
            <span>{section.label}</span>
            {#if expandedSections.has(section.id)}
              <ChevronUp class="w-3.5 h-3.5" aria-hidden="true" />
            {:else}
              <ChevronDown class="w-3.5 h-3.5" aria-hidden="true" />
            {/if}
          </button>

          {#if expandedSections.has(section.id)}
            <div class="detail-section-panel">
              {#if section.id === 'pricing' && solution.pricing_strategy}
                <p>{solution.pricing_strategy}</p>
              {/if}

              {#if section.id === 'innovation'}
                <div class="innovation-grid">
                  {#if solution.conventional_approach}
                    <div class="innovation-note">
                      <span class="mini-label">Conventional Path</span>
                      <p>{solution.conventional_approach}</p>
                    </div>
                  {/if}
                  {#if solution.innovation_angle}
                    <div class="innovation-note innovation-note--accent">
                      <span class="mini-label mini-label-accent">What's Different</span>
                      <p>{solution.innovation_angle}</p>
                    </div>
                  {/if}
                </div>
              {/if}

              {#if section.id === 'features' && solution.core_features}
                <ul class="detail-list">
                  {#each solution.core_features as feature}
                    <li>{feature}</li>
                  {/each}
                </ul>
              {/if}

              {#if section.id === 'painpoints' && solution.pain_points_addressed}
                <ul class="detail-list">
                  {#each solution.pain_points_addressed as point}
                    <li>{point}</li>
                  {/each}
                </ul>
              {/if}

              {#if section.id === 'differentiation' && solution.differentiation_factors}
                <ul class="detail-list">
                  {#each solution.differentiation_factors as factor}
                    <li>{factor}</li>
                  {/each}
                </ul>
              {/if}

              {#if section.id === 'personas' && solution.target_personas}
                <ul class="detail-list">
                  {#each solution.target_personas as persona}
                    <li>{persona}</li>
                  {/each}
                </ul>
              {/if}

              {#if section.id === 'seo' && solution.programmatic_seo_opportunity}
                <div class="markdown-content markdown-content-compact text-text-secondary text-sm">
                  {@html renderTechnicalContent(solution.programmatic_seo_opportunity)}
                </div>
              {/if}

              {#if section.id === 'cac' && solution.estimated_cac_organic}
                <p>
                  {solution.estimated_cac_organic}{#if solution.estimated_cac_paid} <span class="text-text-muted">(vs {solution.estimated_cac_paid} paid)</span>{/if}
                </p>
              {/if}

              {#if section.id === 'queries' && solution.organic_discovery_queries}
                <div class="query-tags">
                  {#each solution.organic_discovery_queries as query}
                    <span>{query}</span>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </section>
      {/each}
    </div>
  {/if}
</div>

<style>
  .solution-detail-content {
    display: grid;
    gap: 0.82rem;
    color: var(--color-text-secondary);
  }

  .decision-facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0;
    margin: 0;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 58%, transparent);
    border-radius: 0.62rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.36)),
      color-mix(in srgb, var(--color-bg-surface) 56%, var(--color-bg-elevated));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
  }

  .decision-facts div {
    position: relative;
    display: grid;
    gap: 0.22rem;
    min-width: 0;
    padding: 0.55rem 0.6rem;
  }

  .decision-facts div + div::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.56rem;
    bottom: 0.56rem;
    width: 1px;
    background: color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
  }

  .decision-facts dt {
    color: var(--color-text-muted);
    font-size: 0.57rem;
    font-weight: 760;
    letter-spacing: 0.01em;
  }

  .decision-facts dd {
    margin: 0;
    color: var(--color-text-primary);
    font-size: 0.74rem;
    font-weight: 700;
    line-height: 1.24;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .facet-panel {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 0.62rem 0.95rem;
    padding: 0.66rem 0.05rem;
    background: transparent;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
  }

  .description-block {
    display: grid;
    gap: 0.35rem;
  }

  .body-copy {
    margin: 0;
    max-width: 74ch;
    color: var(--color-text-secondary);
    font-size: 0.85rem;
    line-height: 1.52;
    text-wrap: pretty;
  }

  .text-button {
    width: fit-content;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-text-muted);
    font-size: 0.8rem;
    cursor: pointer;
    transition: color 180ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .text-button:hover {
    color: var(--color-text-secondary);
  }

  .validation-strip {
    display: grid;
    gap: 0.4rem;
    padding: 0.66rem 0.72rem;
    border: 1px solid color-mix(in srgb, var(--color-border) 76%, transparent);
    border-radius: 0.56rem;
    background: color-mix(in srgb, var(--color-bg-surface) 36%, transparent);
  }

  .validation-strip ul {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.28rem 0.85rem;
    margin: 0;
    padding: 0;
  }

  .validation-strip li {
    list-style: none;
    position: relative;
    padding-left: 0.7rem;
    color: var(--color-text-secondary);
    font-size: 0.74rem;
    line-height: 1.36;
  }

  .validation-strip li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.62em;
    width: 0.22rem;
    height: 0.22rem;
    border-radius: 50%;
    background: var(--color-text-muted);
  }

  .insight-callout {
    display: grid;
    gap: 0.34rem;
    max-width: 88ch;
    padding: 0.62rem 0.72rem;
    border: 1px solid color-mix(in srgb, var(--color-border) 78%, transparent);
    border-radius: 0.56rem;
    background: color-mix(in srgb, var(--color-bg-surface) 42%, transparent);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
  }

  .insight-callout p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.8rem;
    line-height: 1.5;
    text-wrap: pretty;
  }

  .insight-callout .subnote {
    color: var(--color-text-muted);
    font-size: 0.8rem;
  }

  .detail-section-list {
    display: grid;
    gap: 0;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 58%, transparent);
    border-radius: 0.62rem;
    background: color-mix(in srgb, var(--color-bg-surface) 50%, var(--color-bg-elevated));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
  }

  .detail-section-card {
    background: transparent;
    border: 0;
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
    overflow: hidden;
  }

  .detail-section-card.is-open {
    border-color: var(--color-border);
  }

  .detail-section-card:last-child {
    border-bottom: 0;
  }

  .section-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    width: 100%;
    padding: 0.62rem 0.72rem;
    border: 0;
    background: transparent;
    color: var(--color-text-primary);
    font-size: 0.76rem;
    font-weight: 720;
    text-align: left;
    cursor: pointer;
    transition:
      background 180ms cubic-bezier(0.32, 0.72, 0, 1),
      color 180ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .section-trigger:hover {
    color: var(--color-text-primary);
    background: color-mix(in srgb, var(--color-bg-surface) 76%, transparent);
  }

  .section-trigger:focus-visible,
  .section-toggle:focus-visible,
  .text-button:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .section-toggle {
    justify-self: end;
    margin: 0.38rem 0.45rem 0.25rem;
    padding: 0.22rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    font-size: 0.68rem;
    font-weight: 650;
    cursor: pointer;
  }

  .section-toggle:hover {
    color: var(--color-text-secondary);
  }

  .detail-section-panel {
    padding: 0.64rem 0.72rem 0.72rem;
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
    font-size: 0.78rem;
  }

  .detail-section-panel p {
    margin: 0;
    color: var(--color-text-secondary);
    line-height: 1.48;
  }

  .detail-section-panel ul {
    margin: 0;
    display: grid;
    gap: 0;
  }

  .detail-section-panel li {
    line-height: 1.42;
  }

  .detail-list {
    list-style: none;
    padding: 0;
  }

  .detail-list li {
    position: relative;
    padding: 0.42rem 0 0.42rem 0.9rem;
    color: var(--color-text-secondary);
    border-top: 1px solid color-mix(in srgb, var(--color-border) 72%, transparent);
  }

  .detail-list li:first-child {
    padding-top: 0;
    border-top: 0;
  }

  .detail-list li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.9rem;
    width: 0.26rem;
    height: 0.26rem;
    border-radius: 50%;
    background: var(--color-text-muted);
    opacity: 0.8;
  }

  .detail-list li:first-child::before {
    top: 0.48rem;
  }

  .innovation-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
  }

  .innovation-note {
    display: grid;
    gap: 0.28rem;
    min-width: 0;
    padding: 0.58rem 0.64rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 56%, transparent);
    border-radius: 0.5rem;
    background: color-mix(in srgb, var(--color-bg-surface) 64%, var(--color-bg-elevated));
  }

  .innovation-note--accent {
    border-color: color-mix(in srgb, var(--color-accent) 28%, var(--color-border));
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-elevated));
  }

  .query-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
  }

  .query-tags span {
    padding: 0.15rem 0.44rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: 0.68rem;
    line-height: 1.25;
  }

  .solution-detail-content :global(.mono-label),
  .mini-label {
    font-family: var(--font-body);
    font-size: 0.62rem;
    font-weight: 750;
    letter-spacing: 0.015em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .mini-label-accent {
    color: var(--color-accent);
  }

  .markdown-content-compact :global(h1),
  .markdown-content-compact :global(h2),
  .markdown-content-compact :global(h3),
  .markdown-content-compact :global(h4) {
    margin-top: 0.75rem;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
  }
  .markdown-content-compact :global(p) {
    margin-bottom: 0.5rem;
  }
  .markdown-content-compact :global(ul),
  .markdown-content-compact :global(ol) {
    margin-bottom: 0.5rem;
  }

  /* Idea-tag facet groups (display-only) */
  .facet-group {
    display: flex;
    flex-direction: column;
    gap: 0.32rem;
  }
  .facet-panel :global(.facet-group) {
    gap: 0.3rem;
  }
  .facet-panel :global(.mono-label) {
    font-family: var(--font-body);
    font-size: 0.67rem;
    font-weight: 750;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .facet-panel :global(.facet-chip) {
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    border-radius: 0.42rem;
    font-family: var(--font-body);
    font-size: 0.68rem;
    font-weight: 650;
  }
  .facet-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
  }
  .strength-chip {
    font-family: var(--font-body);
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    line-height: 1.2;
    padding: 0.16rem 0.46rem;
    border: 1px solid color-mix(in srgb, currentColor 62%, transparent);
    border-radius: 0.42rem;
  }
  .strength-chip-success { color: var(--color-success-dark); }
  .strength-chip-accent { color: var(--color-accent-dark); }
  .strength-chip-info { color: var(--color-secondary-dark); }
  .strength-chip-warning { color: var(--color-warning-dark); }

  @media (max-width: 720px) {
    .decision-facts {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .decision-facts div + div::before {
      display: none;
    }

    .decision-facts div:nth-child(even) {
      border-left: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    }

    .decision-facts div:nth-child(n + 3) {
      border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 52%, transparent);
    }

    .validation-strip ul {
      grid-template-columns: 1fr;
    }

    .innovation-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
