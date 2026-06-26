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
  const FRICTION_DATA = new Set(["paywalled", "unofficial", "restricted", "blocked"]);

  // Model = identity only (what / who / how it earns) — always shown, neutral.
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
    return items;
  });
  // Growth: show all channels — programmatic-SEO is a meaningful positive (scalable organic
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
    if (t.data_access && FRICTION_DATA.has(t.data_access)) items.push(chip(t.data_access));
    for (const r of t.risk_flags ?? []) items.push(chip(r));
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

  // Expandable sections config — why_it_works removed (surfaced inline instead)
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
<div class="space-y-5">
  <!-- Grounded provenance: the pain × segment this idea was generated for -->
  {#if provenance}
    <p class="text-xs text-text-muted font-mono">
      Generated for <span class="text-text-secondary">{provenance.pain}</span>{#if provenance.seg} — {provenance.seg} audience{/if}
    </p>
  {/if}

  <!-- Closed-vocabulary tag facets: Strengths / Model / Signals & risks (docs/IDEA_TAGS.md) -->
  {#if solution.tags}
    <div class="space-y-3">
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
      <FacetChips label="Growth" items={growthItems} tone="info" />
      <FacetChips label="Watch-outs" items={watchOutItems} tone="warning" />
      {#if solution.tags.rationale}
        <p class="text-xs text-text-muted leading-relaxed">
          <span class="text-text-secondary">Why these tags:</span> {solution.tags.rationale}
        </p>
      {/if}
    </div>
  {/if}

  <!-- Description (truncated to ~4 lines with expand) -->
  <div>
    <p class="text-sm text-text-secondary leading-relaxed {descExpanded ? '' : 'truncate-4'}">
      {solution.description}
    </p>
    <button
      type="button"
      class="text-xs text-text-muted hover:text-text-secondary transition-colors mt-1"
      onclick={() => { descExpanded = !descExpanded; }}
    >
      {descExpanded ? 'Show less' : 'Read more'}
    </button>
  </div>

  <!-- Why it works — surfaced inline (was buried in Innovation Breakdown pill) -->
  {#if solution.why_it_works}
    <div class="pl-3 border-l-2 border-border-emphasis">
      <span class="mono-label">Why it works</span>
      <p class="mt-0.5 text-sm text-text-secondary leading-relaxed">{solution.why_it_works}</p>
    </div>
  {/if}

  <!-- Quick info row -->
  {#if devTimeParsed}
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs text-text-muted flex items-center gap-1" title={devTimeParsed.full}>
        <span>&#9201;</span> {devTimeParsed.short}
      </span>
    </div>
  {/if}

  <!-- Expandable section pills + Show all toggle -->
  {#if detailSections.length > 0}
    <div class="flex flex-wrap items-center gap-1.5 mt-1">
      {#each detailSections as section}
        <button
          type="button"
          class="text-xs px-2.5 py-1 rounded-md border transition-colors
            {expandedSections.has(section.id)
              ? 'bg-accent/10 border-accent/30 text-accent'
              : 'bg-bg-elevated border-border text-text-muted hover:border-accent/30 hover:text-text-secondary'}"
          onclick={() => toggleSection(section.id)}
        >
          {section.label}
          {#if expandedSections.has(section.id)}
            <ChevronUp class="w-3 h-3 inline ml-0.5" />
          {:else}
            <ChevronDown class="w-3 h-3 inline ml-0.5" />
          {/if}
        </button>
      {/each}
      {#if detailSections.length > 2}
        <button
          type="button"
          class="text-xs text-text-muted hover:text-text-secondary transition-colors ml-1"
          onclick={toggleAll}
        >
          {allExpanded ? 'Collapse' : 'Show all'}
        </button>
      {/if}
    </div>

    <!-- Expanded section content -->
    {#each detailSections as section}
      {#if expandedSections.has(section.id)}
        <div class="text-sm border-t border-border pt-3">
          {#if section.id === 'pricing' && solution.pricing_strategy}
            <h4 class="mono-label mb-1">Pricing Strategy</h4>
            <p class="text-text-secondary">{solution.pricing_strategy}</p>
          {/if}

          {#if section.id === 'innovation'}
            <h4 class="mono-label mb-2">Innovation Breakdown</h4>
            <div class="space-y-2">
              {#if solution.conventional_approach}
                <div class="rounded border border-border px-3 py-2">
                  <span class="text-xs font-medium uppercase tracking-wider text-text-muted">Conventional Path</span>
                  <p class="mt-0.5 text-text-secondary">{solution.conventional_approach}</p>
                </div>
              {/if}
              {#if solution.innovation_angle}
                <div class="rounded border border-accent/30 bg-accent/5 px-3 py-2">
                  <span class="text-xs font-medium uppercase tracking-wider text-accent">What's Different</span>
                  <p class="mt-0.5 text-text-secondary">{solution.innovation_angle}</p>
                </div>
              {/if}
            </div>
          {/if}

          {#if section.id === 'features' && solution.core_features}
            <h4 class="mono-label mb-1">Core Features</h4>
            <ul class="space-y-0.5">
              {#each solution.core_features as feature}
                <li class="text-text-secondary flex items-start gap-1.5">
                  <span class="text-accent mt-1 shrink-0">-</span>
                  {feature}
                </li>
              {/each}
            </ul>
          {/if}

          {#if section.id === 'painpoints' && solution.pain_points_addressed}
            <h4 class="mono-label mb-1">Pain Points Addressed</h4>
            <ul class="space-y-0.5">
              {#each solution.pain_points_addressed as point}
                <li class="text-text-secondary flex items-start gap-1.5">
                  <span class="text-accent mt-1 shrink-0">-</span>
                  {point}
                </li>
              {/each}
            </ul>
          {/if}

          {#if section.id === 'differentiation' && solution.differentiation_factors}
            <h4 class="mono-label mb-1">Differentiation</h4>
            <ul class="space-y-0.5">
              {#each solution.differentiation_factors as factor}
                <li class="text-text-secondary flex items-start gap-1.5">
                  <span class="text-accent mt-1 shrink-0">-</span>
                  {factor}
                </li>
              {/each}
            </ul>
          {/if}

          {#if section.id === 'personas' && solution.target_personas}
            <h4 class="mono-label mb-1">Target Personas</h4>
            <ul class="space-y-0.5">
              {#each solution.target_personas as persona}
                <li class="text-text-secondary flex items-start gap-1.5">
                  <span class="text-accent mt-1 shrink-0">-</span>
                  {persona}
                </li>
              {/each}
            </ul>
          {/if}

          {#if section.id === 'seo' && solution.programmatic_seo_opportunity}
            <h4 class="mono-label mb-1">Programmatic SEO Opportunity</h4>
            <div class="markdown-content markdown-content-compact text-text-secondary text-sm">
              {@html renderTechnicalContent(solution.programmatic_seo_opportunity)}
            </div>
          {/if}

          {#if section.id === 'cac' && solution.estimated_cac_organic}
            <h4 class="mono-label mb-1">Estimated CAC</h4>
            <p class="text-text-secondary">
              {solution.estimated_cac_organic}{#if solution.estimated_cac_paid} <span class="text-text-muted">(vs {solution.estimated_cac_paid} paid)</span>{/if}
            </p>
          {/if}

          {#if section.id === 'queries' && solution.organic_discovery_queries}
            <h4 class="mono-label mb-1">Organic Discovery Queries</h4>
            <div class="flex flex-wrap gap-1.5">
              {#each solution.organic_discovery_queries as query}
                <span class="text-xs px-2 py-0.5 rounded bg-bg-elevated border border-border text-text-secondary">
                  {query}
                </span>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    {/each}
  {/if}
</div>

<style>
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
    gap: 0.375rem;
  }
  .facet-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }
  .strength-chip {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    line-height: 1.2;
    padding-left: 0.5rem;
    border-left: 2px solid currentColor;
  }
  .strength-chip-success { color: var(--color-success-dark); }
  .strength-chip-accent { color: var(--color-accent-dark); }
  .strength-chip-info { color: var(--color-secondary-dark); }
  .strength-chip-warning { color: var(--color-warning-dark); }
</style>
