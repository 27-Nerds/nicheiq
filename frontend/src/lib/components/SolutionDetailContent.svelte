<script lang="ts">
  import { Telescope } from "lucide-svelte";
  import { renderTechnicalContent } from "$lib/utils/format";
  import type { SolutionPreview } from "$lib/types/job";
  import FacetChips from "$lib/components/FacetChips.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { humanizeTag, tagDescription } from "$lib/utils/ideaTagLabels";
  import { angleLabel } from "$lib/utils/ideaAngleLabels";
  import { strengthEntry, SUPERPOWERS_DETAILED } from "$lib/utils/superpower";
  import { scoreRationale } from "$lib/utils/scoreRationale";
  import { originalityMetric } from "$lib/utils/solution-utils";

  interface Props {
    solution: SolutionPreview;
    /** overview = the shortlist-decision snapshot; detail = the 7-card deep reference. */
    view?: "overview" | "detail";
    /** Overview only: jump to the Full detail tab (from the "Read full detail" link). */
    onViewFull?: () => void;
  }

  let { solution, view = "overview", onViewFull }: Props = $props();

  // Grounded generation provenance: the (pain × segment) cell that produced this idea.
  const provenance = $derived.by(() => {
    const pain = solution.source_pain?.trim() || solution.pain_points_addressed?.[0]?.trim();
    if (!pain) return null;
    return { pain, seg: solution.source_segment?.trim() || null };
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
  // Growth channels — a distribution facet, so it lives in the Full-detail economics card.
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
      // Prefer the verifier's per-idea, evidence-grounded note over the static definition.
      items.push({
        label: humanizeTag(t.data_access),
        description: solution.data_acquisition_notes?.trim() || tagDescription(t.data_access),
      });
    for (const r of t.risk_flags ?? []) items.push(chip(r));
    if (t.pricing_shape_mismatch)
      items.push({
        label: "Pricing-shape mismatch",
        description: t.pricing_shape_note?.trim() || tagDescription(t.usage_cadence ?? ""),
      });
    return items;
  });

  // Dev time short form (feasibility)
  const devTimeShort = $derived.by(() => {
    const devTime = solution.estimated_development_time;
    if (!devTime) return null;
    const match = devTime.match(/^[\d\-\+]+\s*(?:weeks?|months?|days?)/i);
    return match ? match[0] : devTime;
  });

  // Overview grounding facts (condensed — the shortlist read).
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
    if (devTimeShort) facts.push({ label: "Build range", value: devTimeShort });

    return facts.slice(0, 4);
  });

  // Full-detail helpers
  const journeyTag = $derived(solution.journey_tag ? humanizeTag(solution.journey_tag) : null);
  const mechanismTag = $derived(solution.mechanism_tag ? humanizeTag(solution.mechanism_tag) : null);
  const hasParity = $derived(!!(solution.incumbent_parity?.trim() || solution.adjacent_market_parity?.trim()));

  // Card 7 — the per-criterion scoring rationale (same user-facing text as the Overview
  // score-detail popovers; NOT the not-user-facing calibration_notes).
  const scoreCriteria = $derived.by(() => {
    const om = originalityMetric(solution);
    return [
      { label: "Market fit", value: solution.market_fit_score, why: scoreRationale(solution, "market_fit") },
      { label: "Feasibility", value: solution.technical_feasibility_score, why: scoreRationale(solution, "technical_feasibility") },
      { label: "SEO", value: solution.seo_scalability_score, why: scoreRationale(solution, "seo") },
      { label: om.short === "Orig" ? "Originality" : (om.short ?? "Originality"), value: om.value, why: scoreRationale(solution, "novelty") },
      { label: "Solo-dev", value: solution.solo_dev_feasibility, why: scoreRationale(solution, "solo_dev") },
    ].filter((c) => c.value != null);
  });

  function critColor(v: number | null | undefined): string {
    if (v == null) return "var(--color-text-muted)";
    if (v >= 0.7) return "var(--color-success-dark)";
    if (v >= 0.45) return "var(--color-text-primary)";
    return "var(--color-text-muted)";
  }

  const hasEconomics = $derived(
    !!(solution.pricing_strategy || solution.estimated_cac_organic || solution.programmatic_seo_opportunity)
      || growthItems.length > 0
      || (solution.organic_discovery_queries?.length ?? 0) > 0,
  );
  const hasBuild = $derived(
    !!(solution.estimated_development_time || solution.technical_approach || solution.data_access_model || solution.data_acquisition_notes)
      || (solution.data_sources?.length ?? 0) > 0,
  );
  const hasWedge = $derived(
    !!(solution.conventional_approach || solution.innovation_angle || solution.novelty_rationale)
      || (solution.differentiation_factors?.length ?? 0) > 0,
  );
</script>

{#if view === "overview"}
  <!-- ═══ OVERVIEW — the shortlist-decision snapshot ═══ -->
  <!-- "What it does" is a chrome-less callout paired above "Why it works" below. -->
  <div class="solution-detail-content">
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

    {#if strengthChips.length > 0 || modelItems.length > 0 || watchOutItems.length > 0}
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
        <FacetChips label="Watch-outs" items={watchOutItems} tone="risk" />
      </div>
    {/if}

    {#if solution.short_description || solution.description}
      <div class="insight-callout">
        <span class="mono-label">What it does</span>
        <p class:is-clamped={!solution.short_description}>{solution.short_description || solution.description}</p>
        {#if onViewFull}
          <button type="button" class="callout-toggle" onclick={onViewFull}>Read full detail →</button>
        {/if}
      </div>
    {/if}

    {#if solution.why_it_works}
      <div class="insight-callout">
        <span class="mono-label">Why it works</span>
        <p>{solution.why_it_works}</p>
      </div>
    {/if}

    {#if solution.winning_angle && solution.angle_rationale}
      <div class="insight-callout">
        <span class="mono-label">The read / {angleLabel(solution.winning_angle)}</span>
        <p>{solution.angle_rationale}</p>
        {#if solution.differentiation_locus}
          <p class="subnote">
            <span class="font-medium text-text-secondary">Where the edge lives:</span>
            {solution.differentiation_locus}
          </p>
        {/if}
      </div>
    {/if}

    <!-- The value-unlock panel — the payoff of shortlisting/starting research. Given accent
         chrome so it reads as the action anchor of the Overview, not another flat section. -->
    <div class="validation-strip">
      <div class="validation-head">
        <Telescope class="validation-icon" aria-hidden="true" />
        <span class="validation-title">Deep Research validates this idea</span>
      </div>
      <ul>
        <li>Demand evidence and search behavior</li>
        <li>Competitive alternatives and gaps</li>
        <li>Market sizing and acquisition routes</li>
        <li>MVP scope, data access, and go-to-market risk</li>
      </ul>
    </div>
  </div>
{:else}
  <!-- ═══ FULL DETAIL — the everything-about-this-idea reference ═══ -->
  <div class="solution-detail-content detail-view">
    <!-- 1 · What it is -->
    <section class="fd-card">
      <h3 class="fd-card-title">What it is</h3>
      {#if solution.value_proposition}
        <p class="fd-lead">{solution.value_proposition}</p>
      {/if}
      <p class="body-copy">{solution.description}</p>
      {#if journeyTag || mechanismTag}
        <div class="fd-reftags">
          {#if journeyTag}
            <span><span class="mini-label">How users reach value</span>{journeyTag}</span>
          {/if}
          {#if mechanismTag}
            <span><span class="mini-label">Core mechanism</span>{mechanismTag}</span>
          {/if}
        </div>
      {/if}
    </section>

    <!-- 2 · Who it's for -->
    {#if solution.target_personas && solution.target_personas.length > 0}
      <section class="fd-card">
        <h3 class="fd-card-title">Who it's for</h3>
        <ul class="fd-persona-grid">
          {#each solution.target_personas as persona}
            <li>{persona}</li>
          {/each}
        </ul>
      </section>
    {/if}

    <!-- 3 · What's different -->
    {#if hasWedge}
      <section class="fd-card">
        <h3 class="fd-card-title">What's different</h3>
        {#if solution.conventional_approach || solution.innovation_angle}
          <div class="innovation-grid">
            {#if solution.conventional_approach}
              <div class="innovation-note">
                <span class="mini-label">The usual way</span>
                <p>{solution.conventional_approach}</p>
              </div>
            {/if}
            {#if solution.innovation_angle}
              <div class="innovation-note innovation-note--accent">
                <span class="mini-label mini-label-accent">This idea's angle</span>
                <p>{solution.innovation_angle}</p>
              </div>
            {/if}
          </div>
        {/if}
        {#if solution.differentiation_factors && solution.differentiation_factors.length > 0}
          <ul class="fd-check-list">
            {#each solution.differentiation_factors as factor}
              <li>{factor}</li>
            {/each}
          </ul>
        {/if}
        {#if solution.novelty_rationale}
          <p class="fd-note"><span class="mini-label">On novelty</span>{solution.novelty_rationale}</p>
        {/if}
      </section>
    {/if}

    <!-- 4 · Distribution & economics -->
    {#if hasEconomics}
      <section class="fd-card">
        <div class="fd-card-head">
          <h3 class="fd-card-title">Distribution &amp; economics</h3>
          <span class="fd-est-tag">Estimated · refined by Deep Research</span>
        </div>
        <div class="fd-grid">
          {#if solution.pricing_strategy}
            <div class="fd-col">
              <span class="mini-label">Pricing</span>
              <p>{solution.pricing_strategy}</p>
            </div>
          {/if}
          {#if solution.estimated_cac_organic}
            <div class="fd-col">
              <span class="mini-label">Acquisition cost</span>
              <p>{solution.estimated_cac_organic}{#if solution.estimated_cac_paid} <span class="fd-muted">(vs {solution.estimated_cac_paid} paid)</span>{/if}</p>
            </div>
          {/if}
          {#if solution.programmatic_seo_opportunity}
            <div class="fd-col">
              <span class="mini-label">SEO reach</span>
              <div class="markdown-content markdown-content-compact fd-md">
                {@html renderTechnicalContent(solution.programmatic_seo_opportunity)}
              </div>
            </div>
          {/if}
        </div>
        {#if growthItems.length > 0}
          <div class="fd-chip-row">
            <FacetChips label="Growth channels" items={growthItems} tone="neutral" />
          </div>
        {/if}
        {#if solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0}
          <div class="fd-chip-row">
            <span class="mini-label">Organic queries users search</span>
            <div class="query-tags">
              {#each solution.organic_discovery_queries as query}
                <span>{query}</span>
              {/each}
            </div>
          </div>
        {/if}
      </section>
    {/if}

    <!-- 5 · How it's built -->
    {#if hasBuild}
      <section class="fd-card">
        <h3 class="fd-card-title">How it's built</h3>
        <div class="fd-grid">
          {#if solution.estimated_development_time}
            <div class="fd-col">
              <span class="mini-label">Build time</span>
              <p>{solution.estimated_development_time}</p>
              {#if solution.dev_time_rationale}
                <p class="fd-subnote">{solution.dev_time_rationale}</p>
              {/if}
            </div>
          {/if}
          {#if solution.technical_approach}
            <div class="fd-col">
              <span class="mini-label">Technical approach</span>
              <p>{solution.technical_approach}</p>
            </div>
          {/if}
          {#if solution.data_access_model || solution.data_acquisition_notes || (solution.data_sources?.length ?? 0) > 0}
            <div class="fd-col">
              <span class="mini-label">Data</span>
              {#if solution.data_access_model}
                <p>{humanizeTag(solution.data_access_model)}</p>
              {/if}
              {#if solution.data_acquisition_notes}
                <p class="fd-subnote">{solution.data_acquisition_notes}</p>
              {/if}
              {#if solution.data_sources && solution.data_sources.length > 0}
                <div class="query-tags">
                  {#each solution.data_sources as src}
                    <span>{src}</span>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </section>
    {/if}

    <!-- 6 · Competitive parity -->
    {#if hasParity}
      <section class="fd-card">
        <h3 class="fd-card-title">Competitive parity</h3>
        <div class="innovation-grid">
          {#if solution.incumbent_parity?.trim()}
            <div class="innovation-note">
              <span class="mini-label">Direct incumbents</span>
              <p>{solution.incumbent_parity}</p>
            </div>
          {/if}
          {#if solution.adjacent_market_parity?.trim()}
            <div class="innovation-note">
              <span class="mini-label">Adjacent players</span>
              <p>{solution.adjacent_market_parity}</p>
            </div>
          {/if}
        </div>
      </section>
    {:else}
      <section class="fd-card fd-card--locked">
        <h3 class="fd-card-title">Competitive parity</h3>
        <p class="fd-locked-note">Deep Research maps the direct incumbents and adjacent players this idea would compete with.</p>
      </section>
    {/if}

    <!-- 7 · How we scored it -->
    {#if scoreCriteria.length > 0}
      <section class="fd-card">
        <h3 class="fd-card-title">How we scored it</h3>
        <dl class="fd-score-list">
          {#each scoreCriteria as c}
            <div class="fd-score-row">
              <dt>
                <span class="fd-score-name">{c.label}</span>
                <span class="fd-score-val" style:color={critColor(c.value)}>{Math.round((c.value ?? 0) * 100)}</span>
              </dt>
              {#if c.why}
                <dd>{c.why}</dd>
              {/if}
            </div>
          {/each}
        </dl>
        <!-- Distilled bear case — the counterpoint to the per-criterion rationale
             above. Uses the pre-distilled critic_concern (one note), never the raw
             calibration_notes. None-safe: most ideas without a critique show nothing. -->
        {#if solution.critic_concern?.trim()}
          <div class="fd-critic">
            <span class="mini-label">Independent critic's take</span>
            <p>{solution.critic_concern}</p>
          </div>
        {/if}
      </section>
    {/if}
  </div>
{/if}

<style>
  .solution-detail-content {
    display: grid;
    gap: 0.875rem;
    color: var(--color-text-secondary);
  }

  /* ── Overview ── */
  .decision-facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0;
    margin: 0;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 58%, transparent);
    border-radius: 0.625rem;
    background: color-mix(in srgb, var(--color-bg-surface) 56%, var(--color-bg-elevated));
  }

  .decision-facts div {
    position: relative;
    display: grid;
    gap: 0.25rem;
    min-width: 0;
    padding: 0.5rem 0.625rem;
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
    color: var(--color-text-secondary);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .decision-facts dd {
    margin: 0;
    color: var(--color-text-primary);
    font-size: 0.75rem;
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
    gap: 0.625rem 1rem;
    padding: 0.625rem 0.125rem;
    background: transparent;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
  }

  .body-copy {
    margin: 0;
    max-width: 74ch;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.52;
    text-wrap: pretty;
  }

  /* Accent-tinted value panel — the one framed, action-colored element in the flat Overview,
     signposting the payoff of the primary CTA (Start Deep Research). */
  .validation-strip {
    display: grid;
    gap: 0.5rem;
    margin-top: 0.25rem;
    padding: 0.75rem 0.875rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 26%, var(--color-border));
    border-radius: 0.625rem;
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated));
  }

  .validation-head {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .validation-strip :global(.validation-icon) {
    flex-shrink: 0;
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent-dark);
  }

  .validation-title {
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .validation-strip ul {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.25rem 0.875rem;
    margin: 0;
    padding: 0;
  }

  .validation-strip li {
    list-style: none;
    position: relative;
    padding-left: 0.75rem;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
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

  /* Chrome-less labeled sections (What it does / Why it works / The read) — the mono
     eyebrow + spacing carry the structure; only the score panel + facts stay framed. */
  .insight-callout {
    display: grid;
    gap: 0.25rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
  }

  .insight-callout p {
    margin: 0;
    max-width: 72ch;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.5;
    text-wrap: pretty;
  }

  /* "What it does" shows a condensed description; the reader can expand it inline. */
  .insight-callout p.is-clamped {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .callout-toggle {
    justify-self: start;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: color 0.15s ease;
  }

  .callout-toggle:hover {
    color: var(--color-accent-hover);
  }

  .callout-toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 0.25rem;
  }

  .insight-callout .subnote {
    color: var(--color-text-muted);
    font-size: 0.8125rem;
  }

  /* ── Full detail cards ── */
  .detail-view {
    gap: 0.75rem;
  }

  .fd-card {
    display: grid;
    gap: 0.625rem;
    padding: 0.875rem 0.875rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 46%, transparent);
    border-radius: 0.75rem;
    background: color-mix(in srgb, var(--color-bg-surface) 40%, var(--color-bg-elevated));
  }

  .fd-card-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.375rem 0.75rem;
  }

  .fd-card-title {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.01em;
  }

  .fd-est-tag {
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }

  .fd-lead {
    margin: 0;
    max-width: 74ch;
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-weight: 600;
    line-height: 1.45;
    text-wrap: pretty;
  }

  .fd-reftags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem 1.375rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .fd-reftags > span {
    display: inline-flex;
    align-items: baseline;
    gap: 0.375rem;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    font-weight: 600;
  }

  .fd-persona-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.375rem 1.125rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .fd-persona-grid li {
    position: relative;
    padding-left: 0.875rem;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.4;
  }

  .fd-persona-grid li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.6em;
    width: 0.28rem;
    height: 0.28rem;
    border-radius: 50%;
    background: var(--color-text-muted);
  }

  .innovation-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
  }

  .innovation-note {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
    padding: 0.625rem 0.625rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 56%, transparent);
    border-radius: 0.5rem;
    background: color-mix(in srgb, var(--color-bg-surface) 64%, var(--color-bg-elevated));
  }

  .innovation-note--accent {
    border-color: color-mix(in srgb, var(--color-accent) 28%, var(--color-border));
    background: color-mix(in srgb, var(--color-accent) 4%, var(--color-bg-elevated));
  }

  .innovation-note p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.48;
    text-wrap: pretty;
  }

  .fd-check-list {
    display: grid;
    gap: 0.375rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .fd-check-list li {
    position: relative;
    padding-left: 1.25rem;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.45;
  }

  .fd-check-list li::before {
    content: "✓";
    position: absolute;
    left: 0;
    top: 0;
    color: var(--color-success-dark);
    font-weight: 800;
    font-size: 0.8125rem;
  }

  .fd-note {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.48;
  }

  .fd-note .mini-label {
    margin-right: 0.375rem;
  }

  /* auto-fit so a card with only 1-2 populated columns fills the row instead of
     leaving a ragged empty third. */
  .fd-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.5rem 0.875rem;
  }

  .fd-col {
    display: grid;
    gap: 0.25rem;
    align-content: start;
    min-width: 0;
  }

  .fd-col p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.45;
    text-wrap: pretty;
  }

  .fd-subnote {
    color: var(--color-text-muted) !important;
    font-size: 0.75rem !important;
    line-height: 1.42 !important;
  }

  .fd-muted {
    color: var(--color-text-muted);
  }

  .fd-md {
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.45;
  }

  .fd-chip-row {
    display: grid;
    gap: 0.375rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .query-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .query-tags span {
    padding: 0.125rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    line-height: 1.25;
  }

  .fd-card--locked {
    background: color-mix(in srgb, var(--color-bg-surface) 55%, transparent);
    border-style: dashed;
  }

  .fd-locked-note {
    margin: 0;
    color: var(--color-text-muted);
    font-size: 0.8125rem;
    line-height: 1.45;
  }

  /* Card 7 — scoring transparency */
  .fd-score-list {
    display: grid;
    gap: 0;
    margin: 0;
  }

  .fd-score-row {
    display: grid;
    gap: 0.125rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--color-border);
  }

  .fd-score-row:first-child {
    padding-top: 0;
    border-top: 0;
  }

  .fd-score-row dt {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .fd-score-name {
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-weight: 700;
  }

  .fd-score-val {
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .fd-score-row dd {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.45;
    text-wrap: pretty;
  }

  /* Distilled bear case — hairline-separated counterpoint under the score list. */
  .fd-critic {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
    display: grid;
    gap: 0.25rem;
  }
  .fd-critic p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.45;
    text-wrap: pretty;
  }

  /* ── Shared labels ── */
  .solution-detail-content :global(.mono-label),
  .mini-label {
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .mini-label-accent {
    color: var(--color-accent-dark);
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
    gap: 0.375rem;
  }
  .facet-panel :global(.facet-group) {
    gap: 0.25rem;
  }
  .facet-panel :global(.mono-label) {
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .facet-panel :global(.facet-chip),
  .fd-chip-row :global(.facet-chip) {
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    border-radius: 0.375rem;
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 600;
  }
  .facet-panel :global(.facet-chip-risk) {
    background: var(--color-error-subtle);
  }
  .facet-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }
  .strength-chip {
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    line-height: 1.2;
    padding: 0.125rem 0.5rem;
    background: color-mix(in srgb, currentColor 9%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 55%, transparent);
    border-radius: 0.375rem;
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
    .innovation-grid,
    .fd-grid,
    .fd-persona-grid,
    .validation-strip ul {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
