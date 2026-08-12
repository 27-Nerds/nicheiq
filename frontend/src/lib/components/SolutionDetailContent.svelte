<script lang="ts">
  import { Telescope, TriangleAlert } from "lucide-svelte";
  import { humanizeInternalJargon, renderTechnicalContent } from "$lib/utils/format";
  import type { SolutionPreview } from "$lib/types/job";
  import type { OverlapGroup } from "$lib/types/report";
  import FacetChips from "$lib/components/FacetChips.svelte";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import { humanizeTag, tagDescription, normalizeDataAccess } from "$lib/utils/ideaTagLabels";
  import { angleLabel } from "$lib/utils/ideaAngleLabels";
  import { sourceFrameLabel } from "$lib/utils/sourceFrameLabels";
  import { strengthEntry, SUPERPOWERS_DETAILED } from "$lib/utils/superpower";
  import { scoreRationale, type ScoreKey } from "$lib/utils/scoreRationale";
  import { SvelteSet } from "svelte/reactivity";
  import {
    adversarialReviewFinding,
    adversarialReviewCoda,
    adversarialReviewSummary,
    directIncumbentParity,
    incumbentParityPhrase,
    noDirectIncumbentFound,
  } from "$lib/utils/adversarialReview";
  import {
    originalityMetric,
    validatedBuildComplexity,
    validatedNoveltyLevel,
    validatedStrengthKeys,
  } from "$lib/utils/solution-utils";
  import { normalizePainSignal } from "$lib/utils/painSignal";
  import { buyerFacingSolutionPreview } from "$lib/selection/buyerFacingResearchProse";
  import { deliveryFormatLabel } from "$lib/utils/deliveryFormatLabels";

  interface Props {
    solution: SolutionPreview;
    /** overview = the shortlist-decision snapshot; detail = the 7-card deep reference. */
    view?: "overview" | "detail";
    /** Decision summary only: jump to the All details tab. */
    onViewFull?: () => void;
    /** Overview only: the overlap group this candidate belongs to, if any. */
    overlapGroup?: OverlapGroup | null;
    /** Overview only: the overlap group's OTHER candidates resolved against the pool —
     *  display title plus the pool index (null when the name isn't in the current pool). */
    overlapPeers?: { title: string; index: number | null }[] | null;
    /** Overview only: pages the host overlay to another pool candidate. */
    onOpenPeer?: (index: number) => void;
    lifecycle?: "selection" | "reference" | "running" | "completed";
    evidenceLinks?: { href: string; label: string }[];
    onOpenEvidence?: (href: string) => void;
  }

  let {
    solution: rawSolution,
    view = "overview",
    onViewFull,
    overlapGroup = null,
    overlapPeers = null,
    onOpenPeer,
    lifecycle = "reference",
    evidenceLinks = [],
    onOpenEvidence,
  }: Props = $props();

  // THE PIPELINE VOCABULARY IS SANITISED HERE, NOT AT THE CALLER. This component prints
  // `angle_rationale`, `data_acquisition_notes`, `critic_concern` and
  // `refine_binding_constraint`, and it is mounted (through SolutionDetail) from four
  // places — SelectionWorkbench, /selection/review, and SelectedSolutionsSummary on both
  // the job page and the research-progress screen. Only the first of those sanitised, so
  // "cold-start corpus", "paid wedge" and "build_feas" printed verbatim on the other three.
  // Shadowing the prop makes every reference below — including the `scoreRationale` calls,
  // which read `data_acquisition_notes` — read the buyer-facing text by construction.
  // `buyerFacingSolutionPreview` returns the SAME object when nothing changed and is
  // idempotent, so a caller that already sanitised loses nothing.
  const solution = $derived(buyerFacingSolutionPreview(rawSolution));

  function handleEvidenceClick(event: MouseEvent, href: string) {
    if (!onOpenEvidence) return;
    event.preventDefault();
    onOpenEvidence(href);
  }

  // Prefer host-resolved peers (display titles + pool indices for paging); fall back to
  // the group's raw internal names for callers that don't resolve against a pool.
  const overlapDisplay = $derived(
    overlapPeers
      ?? (overlapGroup
        ? overlapGroup.idea_names
            .filter((n) => n !== solution.solution_name)
            .map((name) => ({ title: name, index: null as number | null }))
        : []),
  );

  // Deterministic weak-signal note: a 'restored' candidate was demoted for thin market signal,
  // then brought back so its pain stays represented on the shortlist. Framed as a property of
  // the opportunity, not a flaw in the concept or a limit of the analysis.
  const isWeakSignal = $derived(solution.candidate_status === "restored");
  const deepResearchCopy = $derived.by(() => {
    if (lifecycle === "running") {
      return {
        title: "Deep Research is checking this idea",
        incumbent: "Deep Research is validating this signal.",
        estimate: "Discovery estimate · Deep Research in progress",
        parity: "Deep Research is mapping the direct incumbents and adjacent players.",
      };
    }
    if (lifecycle === "completed") {
      return {
        title: "Deep Research checked this idea",
        incumbent: "Deep Research evaluated this signal.",
        estimate: "Discovery estimate · compare with completed research",
        parity: "See the completed research for the final incumbent and adjacent-player map.",
      };
    }
    if (lifecycle === "selection") {
      return {
        title: "Deep Research would check this idea",
        incumbent: "Deep Research would validate this signal.",
        estimate: "Discovery estimate · Deep Research can verify this",
        parity: "Deep Research would map the direct incumbents and adjacent players.",
      };
    }
    return {
      title: "What deeper research should check",
      incumbent: "This signal still needs deeper validation.",
      estimate: "Discovery estimate · requires deeper research",
      parity: "Deeper research should map the direct incumbents and adjacent players.",
    };
  });

  // Grounded generation provenance: the (pain × segment) cell that produced this idea.
  // The legacy fallback carries the raw ranked-list entry ("1. … (Severity 8.0/10, …): …"),
  // so it's normalized down to the pain title for the fact display.
  const provenance = $derived.by(() => {
    const raw = solution.pain_points_addressed?.[0];
    const pain = solution.source_pain?.trim() || (raw ? normalizePainSignal(raw) : "");
    if (!pain) return null;
    return { pain, seg: solution.source_segment?.trim() || null };
  });

  // Closed-vocabulary tag facets, grouped for display (docs/IDEA_TAGS.md). Each chip carries a
  // one-line hover explanation (tagDescription).
  const strengthChips = $derived(
    validatedStrengthKeys(solution)
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
    const frameLabel = sourceFrameLabel(solution.source_frame);
    if (frameLabel) items.push({ label: frameLabel, description: "Where this idea came from." });
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
    if (validatedBuildComplexity(solution) === "high") items.push(chip("high"));
    if (validatedNoveltyLevel(solution) === "conventional") items.push(chip("conventional"));
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
    const deliveryFormat = solution.delivery_format;
    const revenue = solution.tags?.monetization;

    if (pain) facts.push({ label: "Pain signal", value: pain });
    if (audience) facts.push({ label: "Audience", value: humanizeTag(audience) });
    if (deliveryFormat) {
      facts.push({ label: "Delivered as", value: deliveryFormatLabel(deliveryFormat) });
    } else if (productShape) {
      facts.push({ label: "Product shape", value: humanizeTag(productShape) });
    }
    if (revenue) facts.push({ label: "Revenue model", value: humanizeTag(revenue) });
    if (devTimeShort) facts.push({ label: "Build range", value: devTimeShort });

    return facts.slice(0, 4);
  });

  // Full-detail helpers. Red-team evidence is deliberately separate from actual incumbent parity:
  // the pipeline can encode a mechanism objection as "shipped by evidence: ...".
  const journeyTag = $derived(solution.journey_tag ? humanizeTag(solution.journey_tag) : null);
  const mechanismTag = $derived(solution.mechanism_tag ? humanizeTag(solution.mechanism_tag) : null);
  // Rendered as prose in three places, so the stored class prefix is turned into words here
  // rather than at each site (matches the analyst's wording — see adversarialReview.ts).
  const overviewIncumbentNote = $derived(
    incumbentParityPhrase(directIncumbentParity(solution)) || null,
  );
  const adjacentParityNote = $derived(
    incumbentParityPhrase(solution.adjacent_market_parity) || null,
  );
  const noIncumbentFound = $derived(noDirectIncumbentFound(solution));
  const adversarialReview = $derived(adversarialReviewFinding(solution));

  // Red-team caveats arrive as "Short label: long evidence prose". Split on the first
  // colon only when the prefix reads like a label, so each finding gets a bold lead-in.
  function splitAdversarialDetail(detail: string): { label: string | null; body: string } {
    const idx = detail.indexOf(": ");
    if (idx > 0 && idx < 60 && !detail.slice(0, idx).includes(".")) {
      return { label: detail.slice(0, idx + 1), body: detail.slice(idx + 2) };
    }
    return { label: null, body: detail };
  }
  const hasParity = $derived(
    !!(overviewIncumbentNote || noIncumbentFound || adjacentParityNote),
  );

  // Final card — the per-criterion scoring rationale (same user-facing text as the Overview
  // score-detail popovers; NOT the not-user-facing calibration_notes).
  // `scoreRationale` clamps to 240 chars for popovers, so every reason on this list
  // ended in "…" with no way to read the rest — the reasoning behind each number was
  // simply unavailable. Carry the full text too and let each row expand to it.
  const scoreCriteria = $derived.by(() => {
    const om = originalityMetric(solution);
    return [
      { key: "market_fit", label: "Market fit", value: solution.market_fit_score },
      { key: "technical_feasibility", label: "Feasibility", value: solution.technical_feasibility_score },
      { key: "seo", label: "SEO", value: solution.seo_scalability_score },
      { key: "novelty", label: om.short ?? "Distinct", value: om.value },
      { key: "solo_dev", label: "Solo-dev", value: solution.solo_dev_feasibility },
    ].map((c) => ({
      ...c,
      why: scoreRationale(solution, c.key as ScoreKey),
      whyFull: scoreRationale(solution, c.key as ScoreKey, { full: true }),
    })).filter((c) => c.value != null);
  });
  const expandedScoreKeys = new SvelteSet<string>();
  function toggleScoreWhy(key: string): void {
    if (expandedScoreKeys.has(key)) expandedScoreKeys.delete(key);
    else expandedScoreKeys.add(key);
  }

  function critColor(v: number | null | undefined): string {
    if (v == null) return "var(--color-text-muted)";
    if (v >= 0.7) return "var(--color-success-text)";
    if (v >= 0.45) return "var(--color-text-primary)";
    return "var(--color-text-muted)";
  }

  const hasEconomics = $derived(
    !!(solution.pricing_strategy || solution.estimated_cac_organic || solution.programmatic_seo_opportunity)
      || growthItems.length > 0
      || (solution.organic_discovery_queries?.length ?? 0) > 0,
  );
  const dataAccess = $derived(normalizeDataAccess(solution.data_access_model));
  const hasBuild = $derived(
    !!(solution.estimated_development_time || solution.technical_approach || dataAccess || solution.data_acquisition_notes)
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

    {#if solution.idea_tier === "merged" && solution.merged_from?.length}
      <p class="merged-note">
        Synthesized from {solution.merged_from.length} variant{solution.merged_from.length === 1 ? "" : "s"}: {solution.merged_from.join(", ")}
      </p>
    {/if}

    {#if solution.idea_tier === "bundle" && solution.pain_points_addressed?.length}
      <div class="bundle-note">
        <span class="mono-label">
          Bundle · {solution.pain_points_addressed.length} Discovery pain
          signal{solution.pain_points_addressed.length === 1 ? "" : "s"}
        </span>
        <ul class="bundle-signals">
          {#each solution.pain_points_addressed as signal}
            <li>{normalizePainSignal(signal)}</li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if overlapGroup && overlapDisplay.length}
      <p class="merged-note">
        Overlaps with {overlapDisplay.length} other
        candidate{overlapDisplay.length === 1 ? "" : "s"}
        {overlapGroup.shared_product?.trim() ? `on "${overlapGroup.shared_product.trim()}"` : "as one product direction"}:
        {#each overlapDisplay as peer, i}{#if i > 0}{", "}{/if}{#if peer.index !== null && onOpenPeer}{@const idx = peer.index}<button
            type="button"
            class="overlap-peer"
            onclick={() => onOpenPeer(idx)}
          >{peer.title}</button>{:else}{peer.title}{/if}{/each}
      </p>
    {/if}

    {#if evidenceLinks.length > 0}
      <nav class="evidence-links" aria-label="Related Discovery evidence">
        <span class="mono-label">Open the underlying evidence</span>
        <div>
          {#each evidenceLinks as link}
            <a href={link.href} onclick={(event) => handleEvidenceClick(event, link.href)}>
              {link.label}
            </a>
          {/each}
        </div>
      </nav>
    {/if}

    {#if strengthChips.length > 0 || modelItems.length > 0 || watchOutItems.length > 0 || adversarialReview}
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
        {#if adversarialReview}
          <FacetChips
            label="Adversarial review"
            items={[
              {
                label: adversarialReview.chipLabel,
                description: adversarialReviewSummary(adversarialReview, { inIdeaDetail: true }),
              },
            ]}
            tone={adversarialReview.severity === "weakened" ? "warning" : "risk"}
          />
        {/if}
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
        {#if overviewIncumbentNote}
          <p class="subnote">
            <span class="font-medium text-text-secondary">Web-verified incumbent:</span>
            {overviewIncumbentNote} — thin early signal. {deepResearchCopy.incumbent}
          </p>
        {/if}
      </div>
    {/if}

    {#if adversarialReview}
      <div class="weak-note {adversarialReview.severity === 'weakened' ? 'weak-note--caution' : 'weak-note--critical'}">
        <TriangleAlert class="weak-note-icon" aria-hidden="true" />
        <div class="weak-note-body">
          <span class="weak-note-title">{adversarialReview.label}</span>
          {#each adversarialReview.details as detail}
            <p>{detail}</p>
          {/each}
          <p>{adversarialReviewCoda(adversarialReview, "decision")}</p>
        </div>
      </div>
    {/if}

    {#if isWeakSignal}
      <div class="weak-note">
        <TriangleAlert class="weak-note-icon" aria-hidden="true" />
        <div class="weak-note-body">
          <span class="weak-note-title">Thin market signal</span>
          <p>
            This is the strongest concept we found for its pain, but the market signal is thin —
            we're showing it so the pain stays represented. Treat it as a lower-confidence bet.
          </p>
        </div>
      </div>
    {/if}

    <!-- The value-unlock panel — the payoff of shortlisting/starting research. Given accent
         chrome so it reads as the action anchor of the Overview, not another flat section. -->
    <div class="validation-strip">
      <div class="validation-head">
        <Telescope class="validation-icon" aria-hidden="true" />
        <span class="validation-title">{deepResearchCopy.title}</span>
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
        <dl class="fd-reftags">
          {#if journeyTag}
            <div>
              <dt class="mini-label">How users reach value</dt>
              <dd>{journeyTag}</dd>
            </div>
          {/if}
          {#if mechanismTag}
            <div>
              <dt class="mini-label">Core mechanism</dt>
              <dd>{mechanismTag}</dd>
            </div>
          {/if}
        </dl>
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
          <p class="fd-note"><span class="mini-label">Why it differs</span>{solution.novelty_rationale}</p>
        {/if}
      </section>
    {/if}

    <!-- 4 · Distribution & economics -->
    {#if hasEconomics}
      <section class="fd-card fd-card--ledger">
        <div class="fd-card-head">
          <h3 class="fd-card-title">Distribution &amp; economics</h3>
          <span class="fd-est-tag">{deepResearchCopy.estimate}</span>
        </div>
        <dl class="fd-ledger">
          {#if solution.pricing_strategy}
            <div class="fd-ledger-row">
              <dt class="mini-label">Pricing</dt>
              <dd class="fd-ledger-value"><p>{solution.pricing_strategy}</p></dd>
            </div>
          {/if}
          {#if solution.estimated_cac_organic}
            <div class="fd-ledger-row">
              <dt class="mini-label">Acquisition cost</dt>
              <dd class="fd-ledger-value">
                <p>{solution.estimated_cac_organic}{#if solution.estimated_cac_paid} <span class="fd-muted">(vs {solution.estimated_cac_paid} paid)</span>{/if}</p>
              </dd>
            </div>
          {/if}
          {#if solution.programmatic_seo_opportunity}
            <div class="fd-ledger-row">
              <dt class="mini-label">SEO reach</dt>
              <dd class="fd-ledger-value">
                <div class="markdown-content markdown-content-compact fd-md">
                  {@html renderTechnicalContent(solution.programmatic_seo_opportunity)}
                </div>
              </dd>
            </div>
          {/if}
          {#if growthItems.length > 0}
            <div class="fd-ledger-row">
              <dt class="mini-label">Growth channels</dt>
              <dd class="fd-ledger-value fd-ledger-value--facet">
                <FacetChips label="Growth channels" items={growthItems} tone="neutral" />
              </dd>
            </div>
          {/if}
          {#if solution.organic_discovery_queries && solution.organic_discovery_queries.length > 0}
            <div class="fd-ledger-row">
              <dt class="mini-label">Organic queries users search</dt>
              <dd class="fd-ledger-value">
                <div class="query-tags">
                  {#each solution.organic_discovery_queries as query}
                    <span>{query}</span>
                  {/each}
                </div>
              </dd>
            </div>
          {/if}
        </dl>
      </section>
    {/if}

    <!-- 5 · How it's built -->
    {#if hasBuild}
      <section class="fd-card fd-card--ledger">
        <h3 class="fd-card-title">How it's built</h3>
        <dl class="fd-ledger">
          {#if solution.estimated_development_time}
            <div class="fd-ledger-row">
              <dt class="mini-label">Build time</dt>
              <dd class="fd-ledger-value">
                <p>{solution.estimated_development_time}</p>
                {#if solution.dev_time_rationale}
                  <p class="fd-subnote">{solution.dev_time_rationale}</p>
                {/if}
              </dd>
            </div>
          {/if}
          {#if dataAccess || solution.data_acquisition_notes || (solution.data_sources?.length ?? 0) > 0}
            <div class="fd-ledger-row">
              <dt class="mini-label">Data</dt>
              <dd class="fd-ledger-value">
                {#if dataAccess}
                  <p>{humanizeTag(dataAccess)}</p>
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
              </dd>
            </div>
          {/if}
          {#if solution.technical_approach}
            <div class="fd-ledger-row">
              <dt class="mini-label">Technical approach</dt>
              <dd class="fd-ledger-value">
                <p>{solution.technical_approach}</p>
              </dd>
            </div>
          {/if}
        </dl>
      </section>
    {/if}

    {#if adversarialReview}
      <section class="fd-card {adversarialReview.severity === 'weakened' ? 'fd-card--caution' : 'fd-card--critical'}">
        <h3 class="fd-card-title">{adversarialReview.label}</h3>
        {#if adversarialReview.details.length > 0}
          <ul class="fd-finding-list">
            {#each adversarialReview.details as detail}
              {@const finding = splitAdversarialDetail(detail)}
              <li class="fd-finding">
                {#if finding.label}<strong>{finding.label}</strong> {finding.body}{:else}{finding.body}{/if}
              </li>
            {/each}
          </ul>
        {/if}
        <p class="fd-finding-coda">{adversarialReviewCoda(adversarialReview, "decision")}</p>
      </section>
    {/if}

    <!-- 6 · Competitive parity -->
    {#if hasParity}
      <section class="fd-card fd-card--ledger">
        <h3 class="fd-card-title">Competitive parity</h3>
        <dl class="fd-ledger">
          {#if overviewIncumbentNote}
            <div class="fd-ledger-row">
              <dt class="mini-label">Direct incumbents</dt>
              <dd class="fd-ledger-value">
                <p>{overviewIncumbentNote}</p>
              </dd>
            </div>
          {:else if noIncumbentFound}
            <div class="fd-ledger-row">
              <dt class="mini-label">Direct incumbent check</dt>
              <dd class="fd-ledger-value">
                <p>No incumbent was found shipping this idea's core mechanism.</p>
              </dd>
            </div>
          {/if}
          {#if adjacentParityNote}
            <div class="fd-ledger-row">
              <dt class="mini-label">Adjacent players</dt>
              <dd class="fd-ledger-value">
                <p>{adjacentParityNote}</p>
              </dd>
            </div>
          {/if}
        </dl>
      </section>
    {:else}
      <section class="fd-card fd-card--locked">
        <h3 class="fd-card-title">Competitive parity</h3>
        <p class="fd-locked-note">{deepResearchCopy.parity}</p>
      </section>
    {/if}

    <!-- 7 · How we scored it -->
    {#if scoreCriteria.length > 0}
      <section class="fd-card">
        <h3 class="fd-card-title">How we scored it</h3>
        <!-- Every criterion below is conditional on the premise. Say so here, where the
             numbers are, rather than leaving a high score next to an unproven premise. -->
        {#if adversarialReview?.severity === "killed"}
          <p class="fd-finding-coda">{adversarialReviewCoda(adversarialReview, "scores")}</p>
        {/if}
        <dl class="fd-score-list">
          {#each scoreCriteria as c}
            {@const open = expandedScoreKeys.has(c.key)}
            {@const clipped = !!c.whyFull && c.whyFull !== c.why}
            <div class="fd-score-row">
              <dt>
                <span class="fd-score-name">{c.label}</span>
                <span class="fd-score-val" style:color={critColor(c.value)}>{Math.round((c.value ?? 0) * 100)}</span>
              </dt>
              {#if c.why}
                <dd>
                  <span id={`score-why-${c.key}`}>{open ? c.whyFull : c.why}</span>
                  {#if clipped}
                    <button
                      type="button"
                      class="fd-score-more"
                      aria-expanded={open}
                      aria-controls={`score-why-${c.key}`}
                      onclick={() => toggleScoreWhy(c.key)}
                    >
                      {open ? "Show less" : "Show full reasoning"}
                    </button>
                  {/if}
                </dd>
              {/if}
            </div>
          {/each}
        </dl>
        <!-- Independent calibration note — this durable field can be positive,
             mixed, or critical. Never relabel it as a guaranteed bear case. -->
        {#if solution.critic_concern?.trim()}
          <div class="fd-critic">
            <span class="mini-label">Independent critic's take</span>
            <p>{humanizeInternalJargon(solution.critic_concern)}</p>
          </div>
        {/if}
        {#if solution.refine_binding_constraint?.trim()}
          <div class="fd-critic">
            <span class="mini-label">Tournament bear case</span>
            <p>{solution.refine_binding_constraint}</p>
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
    min-width: 0;
    color: var(--color-text-secondary);
    overflow-wrap: anywhere;
  }

  /* ── Overview ── */
  .decision-facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0;
    margin: 0;
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 58%, transparent);
    border-radius: var(--radius-md);
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
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .decision-facts dd {
    margin: 0;
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    line-height: 1.24;
    overflow-wrap: anywhere;
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

  .merged-note {
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    color: var(--color-text-muted);
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }

  /* Inline candidate reference inside the overlap note — pages the overlay to the peer. */
  .overlap-peer {
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font: inherit;
    text-decoration: underline;
    text-underline-offset: 0.2em;
    cursor: pointer;
  }

  .overlap-peer:hover {
    color: var(--color-accent-hover);
  }

  .overlap-peer:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 0.25rem;
  }

  /* Bundle provenance — mono kicker + one line per composed pain signal. */
  .bundle-note {
    display: grid;
    gap: 0.375rem;
    padding: 0.5rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    background: var(--color-bg-surface);
  }

  .bundle-signals {
    display: grid;
    gap: 0.25rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .bundle-signals li {
    position: relative;
    padding-left: 0.75rem;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.4;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }

  .bundle-signals li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.55em;
    width: 0.22rem;
    height: 0.22rem;
    border-radius: 50%;
    background: var(--color-text-muted);
  }

  .evidence-links {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }

  .evidence-links > div {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.75rem;
  }

  .evidence-links a {
    min-height: 1.5rem;
    color: var(--color-accent-dark);
    font-size: var(--text-sm);
    font-weight: 700;
    line-height: 1.5rem;
    text-decoration: none;
  }

  .evidence-links a:hover {
    color: var(--color-accent-hover);
    text-decoration: underline;
    text-underline-offset: 0.2em;
  }

  .evidence-links a:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 0.25rem;
  }

  .body-copy {
    margin: 0;
    max-width: 74ch;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: 1.52;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }

  /* Accent-tinted value panel — the one framed, action-colored element in the flat Overview,
     signposting the payoff of the primary CTA (Start Deep Research). */
  .validation-strip {
    display: grid;
    gap: 0.5rem;
    margin-top: 0.25rem;
    padding: 0.75rem 0.875rem;
    border: 1px solid color-mix(in srgb, var(--color-accent) 26%, var(--color-border));
    border-radius: var(--radius-md);
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
    font-size: var(--text-13);
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
    font-size: var(--text-sm);
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
    font-size: var(--text-13);
    line-height: 1.5;
    text-wrap: pretty;
    overflow-wrap: anywhere;
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
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
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
    font-size: var(--text-13);
  }

  /* Weak-signal note — a calm, neutral aside (not an error): a LOW-FIT candidate is honest about
     the thin market for its pain, framed as an opportunity property, not a flaw. */
  .weak-note {
    display: flex;
    gap: 0.55rem;
    align-items: flex-start;
    margin-top: 0.75rem;
    padding: 0.6rem 0.7rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    background: var(--color-bg-surface);
  }
  .weak-note :global(.weak-note-icon) {
    width: 15px;
    height: 15px;
    flex-shrink: 0;
    margin-top: 1px;
    color: var(--color-text-muted);
  }
  .weak-note-body {
    display: grid;
    gap: 0.12rem;
    min-width: 0;
  }
  .weak-note-title {
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 700;
    color: var(--color-text-secondary);
  }
  .weak-note p {
    margin: 0;
    max-width: 72ch;
    color: var(--color-text-muted);
    font-size: var(--text-13);
    line-height: 1.5;
    text-wrap: pretty;
  }

  .weak-note--critical {
    border-color: color-mix(in srgb, var(--color-error) 32%, var(--color-border));
    background: color-mix(in srgb, var(--color-error) 5%, var(--color-bg-surface));
  }

  .weak-note--critical :global(.weak-note-icon),
  .weak-note--critical .weak-note-title {
    color: var(--color-error-text);
  }

  .weak-note--caution {
    border-color: color-mix(in srgb, var(--color-warning) 32%, var(--color-border));
    background: color-mix(in srgb, var(--color-warning) 5%, var(--color-bg-surface));
  }

  .weak-note--caution :global(.weak-note-icon),
  .weak-note--caution .weak-note-title {
    color: var(--color-warning-text);
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

  /* Severity variants must follow the base .fd-card rule — equal specificity,
     source order decides which border/background wins. */
  .fd-card--critical {
    border-color: color-mix(in srgb, var(--color-error) 32%, var(--color-border));
    background: color-mix(in srgb, var(--color-error) 5%, var(--color-bg-surface));
  }

  .fd-card--caution {
    border-color: color-mix(in srgb, var(--color-warning) 32%, var(--color-border));
    background: color-mix(in srgb, var(--color-warning) 5%, var(--color-bg-surface));
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
    font-size: var(--text-md);
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.01em;
  }

  .fd-est-tag {
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }

  .fd-lead {
    margin: 0;
    max-width: 74ch;
    color: var(--color-text-primary);
    font-size: var(--text-base);
    font-weight: 600;
    line-height: 1.45;
    text-wrap: pretty;
  }

  .fd-reftags {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    margin: 0;
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  .fd-reftags > div {
    display: grid;
    gap: var(--space-1);
    min-width: 0;
  }

  .fd-reftags > div + div {
    padding-left: var(--space-5);
    border-left: 1px solid var(--color-border);
  }

  .fd-reftags dt,
  .fd-reftags dd {
    margin: 0;
  }

  .fd-reftags dd {
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    font-weight: 600;
    line-height: var(--leading-snug);
    text-wrap: pretty;
    overflow-wrap: anywhere;
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
    font-size: var(--text-base);
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
    font-size: var(--text-13);
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
    font-size: var(--text-base);
    line-height: 1.45;
  }

  .fd-check-list li::before {
    content: "✓";
    position: absolute;
    left: 0;
    top: 0;
    color: var(--color-success-text);
    font-weight: 800;
    font-size: var(--text-13);
  }

  .fd-note {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.48;
  }

  .fd-note .mini-label {
    margin-right: 0.375rem;
  }

  .fd-card--ledger {
    gap: var(--space-4);
    padding: var(--space-5);
  }

  .fd-card--ledger .fd-card-head {
    align-items: flex-start;
  }

  .fd-card--ledger .fd-card-title {
    font-size: var(--text-lg);
  }

  .fd-card--ledger .fd-est-tag {
    max-width: 40ch;
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0;
    line-height: var(--leading-snug);
    text-align: right;
    text-transform: none;
  }

  .fd-ledger {
    display: grid;
    margin: 0;
  }

  .fd-ledger-row {
    display: grid;
    grid-template-columns: minmax(8rem, 11rem) minmax(0, 1fr);
    gap: var(--space-6);
    padding: var(--space-4) 0;
    border-top: 1px solid var(--color-border);
  }

  .fd-ledger-row:first-child {
    padding-top: var(--space-2);
    border-top: 0;
  }

  .fd-ledger-row:last-child {
    padding-bottom: 0;
  }

  .fd-ledger-row dt {
    margin: 0;
  }

  .fd-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.5rem 0.875rem;
  }

  .fd-ledger-value {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
    max-width: 72ch;
    margin: 0;
  }

  .fd-ledger-value p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: var(--leading-normal);
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }

  .fd-finding-list {
    display: grid;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .fd-finding {
    max-width: 74ch;
    padding: var(--space-3) 0;
    border-top: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.5;
    text-wrap: pretty;
    overflow-wrap: anywhere;
  }

  .fd-finding:first-child {
    padding-top: 0;
    border-top: 0;
  }

  .fd-finding:last-child {
    padding-bottom: 0;
  }

  .fd-finding strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .fd-finding-coda {
    margin: 0;
    max-width: 74ch;
    color: var(--color-text-muted);
    font-size: var(--text-13);
    line-height: 1.5;
    text-wrap: pretty;
  }

  .fd-subnote {
    color: var(--color-text-muted) !important;
    font-size: var(--text-sm) !important;
    line-height: 1.42 !important;
  }

  .fd-muted {
    color: var(--color-text-muted);
  }

  .fd-md {
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .fd-ledger-value .fd-md {
    font-size: var(--text-base);
    line-height: var(--leading-normal);
  }

  .fd-ledger-value .markdown-content-compact :global(p:first-child) {
    margin-top: 0;
  }

  .fd-ledger-value .markdown-content-compact :global(p:last-child) {
    margin-bottom: 0;
  }

  .fd-ledger-value--facet :global(.mono-label) {
    display: none;
  }

  .query-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .query-tags span {
    padding: 0.125rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-11);
    line-height: 1.25;
  }

  .fd-card--locked {
    background: color-mix(in srgb, var(--color-bg-surface) 55%, transparent);
    border-style: dashed;
  }

  .fd-locked-note {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-13);
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
    font-size: var(--text-13);
    font-weight: 700;
  }

  .fd-score-val {
    font-family: var(--font-mono);
    font-size: var(--text-base);
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .fd-score-row dd {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.45;
    text-wrap: pretty;
  }

  .fd-score-more {
    margin-left: 0.35rem;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }

  .fd-score-more:hover {
    color: var(--color-accent-hover);
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
    font-size: var(--text-13);
    line-height: 1.45;
    text-wrap: pretty;
  }

  /* ── Shared labels ── */
  .solution-detail-content :global(.mono-label),
  .mini-label {
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0;
    text-transform: none;
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
    font-size: var(--text-base);
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
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0;
    text-transform: none;
    color: var(--color-text-muted);
  }
  .facet-panel :global(.facet-chip),
  .fd-ledger-value--facet :global(.facet-chip) {
    background: color-mix(in srgb, var(--color-bg-surface) 74%, var(--color-bg-elevated));
    border-radius: var(--radius-sm);
    font-family: var(--font-body);
    font-size: var(--text-11);
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
    font-size: var(--text-11);
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    line-height: 1.2;
    padding: 0.125rem 0.5rem;
    background: color-mix(in srgb, currentColor 9%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 55%, transparent);
    border-radius: var(--radius-sm);
  }
  .strength-chip-success { color: var(--color-success-text); }

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
    .fd-card--ledger {
      padding: var(--space-4);
    }
    .fd-card--ledger .fd-card-head {
      display: grid;
    }
    .fd-card--ledger .fd-est-tag {
      text-align: left;
    }
    .fd-ledger-row {
      grid-template-columns: minmax(0, 1fr);
      gap: var(--space-2);
    }
    .fd-reftags > div + div {
      margin-top: var(--space-3);
      padding-top: var(--space-3);
      padding-left: 0;
      border-top: 1px solid var(--color-border);
      border-left: 0;
    }
  }
</style>
