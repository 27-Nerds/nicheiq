<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import {
    ArrowRight,
    Plus,
    Sparkles,
    Loader2,
    Coins,
    ArrowUp,
    ArrowDown,
    X,
  } from "lucide-svelte";
  import { selectSolution, regenerateIdeas, ApiError } from "$lib/api";
  import { creditTopUp } from "$lib/stores/creditTopUp.svelte";
  import {
    DEFAULT_STAGE_COSTS,
    type SolutionPreview,
    type StageCosts,
  } from "$lib/types/job";
  import {
    computeCompositeScore,
    solutionDisplayTitle,
    solutionCardDescription,
    solutionStrengthBadge,
    fitLabel,
    opportunityShape,
  } from "$lib/utils/solution-utils";
  import { SCORE_DEFINITIONS } from "$lib/utils/scoreDefinitions";
  import { humanizeTag, tagDescription } from "$lib/utils/ideaTagLabels";
  import { angleLabel, angleDescription } from "$lib/utils/ideaAngleLabels";
  import Tooltip from "$lib/components/ui/Tooltip.svelte";
  import SelectSolutionModal from "$lib/components/SelectSolutionModal.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";

  const MAX_SELECTIONS = 3;

  interface Props {
    jobId: string;
    solutions: SolutionPreview[];
    creditBalance: number;
    stageCosts?: StageCosts;
    canRegenerate?: boolean;
    isRegenerating?: boolean;
    selectedSolutions?: string[];
    solutionVotes?: Record<string, number>;
    coverageNotes?: string[] | null;
    discussionCount?: number | null;
    painPointCount?: number | null;
    segmentCount?: number | null;
    onComplete?: () => void;
    onRegenerateStart?: () => void;
  }

  let {
    jobId,
    solutions,
    creditBalance,
    stageCosts = { ...DEFAULT_STAGE_COSTS },
    canRegenerate = false,
    isRegenerating = false,
    selectedSolutions,
    solutionVotes = {},
    coverageNotes = [],
    discussionCount = null,
    painPointCount = null,
    segmentCount = null,
    onComplete,
    onRegenerateStart,
  }: Props = $props();

  // ── Selection state ──
  let selectedNames = new SvelteSet<string>();
  let modalOpen = $state(false);
  let selectLoading = $state(false);
  let selectError = $state("");
  let modalIndex = $state<number | null>(null); // index into original `solutions`

  // Restore pre-existing selections (e.g. page reload mid-selection)
  $effect(() => {
    if (selectedSolutions?.length && selectedNames.size === 0) {
      for (const name of selectedSolutions) selectedNames.add(name);
    }
  });

  // ── Regeneration state ──
  let regenerating = $state(false);
  let regenerateError = $state("");
  const canAffordRegenerate = $derived(
    creditBalance >= stageCosts.regenerate_ideas,
  );
  const REGEN_FOCUSES = [
    { value: "auto", label: "Auto" },
    { value: "novelty", label: "Novelty" },
    { value: "distribution", label: "Distribution" },
  ] as const;
  let regenerateFocus = $state<"auto" | "novelty" | "distribution">("auto");
  $effect(() => {
    if (!isRegenerating && regenerating) regenerating = false;
  });

  async function handleRegenerate() {
    if (regenerating || isRegenerating) return;
    regenerating = true;
    regenerateError = "";
    try {
      await regenerateIdeas(
        jobId,
        regenerateFocus === "auto" ? undefined : regenerateFocus,
      );
      onRegenerateStart?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        creditTopUp.show({
          balance: creditBalance,
          required: stageCosts.regenerate_ideas,
          stageName: "idea regeneration",
        });
      } else {
        regenerateError =
          e instanceof Error ? e.message : "Failed to generate ideas";
      }
      regenerating = false;
    }
  }

  // ── Derived display values ──
  const shape = $derived(opportunityShape(solutions));
  const deepCost = $derived(stageCosts.deep_research);
  const canAffordDeep = $derived(creditBalance >= deepCost);
  const selectionCount = $derived(selectedNames.size);
  const canSubmit = $derived(selectionCount > 0);
  const showTray = $derived(selectionCount > 0 && !modalOpen && modalIndex === null);
  const statusCtaLabel = $derived(
    !canSubmit
      ? "Shortlist candidates to start"
      : canAffordDeep
        ? "Start Deep Research"
        : "Add credits to start",
  );
  const bestScore = $derived.by(() =>
    solutions.length
      ? Math.round(Math.max(...solutions.map((s) => computeCompositeScore(s))) * 100)
      : null,
  );
  const picks = $derived.by(() => {
    const out: { name: string; title: string }[] = [];
    for (const name of selectedNames) {
      const s = solutions.find((x) => x.solution_name === name);
      out.push({ name, title: s ? solutionDisplayTitle(s) : name });
    }
    return out;
  });

  // ── Sorting ──
  type SortKey = "score" | "fit" | "feas" | "build";
  let sortKey = $state<SortKey>("score");
  let sortDir = $state<"asc" | "desc">("desc");
  function setSort(k: SortKey) {
    if (sortKey === k) {
      sortDir = sortDir === "desc" ? "asc" : "desc";
    } else {
      sortKey = k;
      sortDir = k === "build" ? "asc" : "desc";
    }
  }
  function buildWeeks(s?: string | null): number {
    if (!s) return Infinity;
    const m = s.match(/(\d+(?:\.\d+)?)\s*(day|week|month|year)/i);
    if (!m) return Infinity;
    const n = parseFloat(m[1]);
    const u = m[2].toLowerCase();
    const mult = u.startsWith("day")
      ? 1 / 7
      : u.startsWith("week")
        ? 1
        : u.startsWith("month")
          ? 4.345
          : u.startsWith("year")
            ? 52
            : 1;
    return n * mult;
  }
  function sortValue(s: SolutionPreview, k: SortKey): number {
    if (k === "score") return computeCompositeScore(s);
    if (k === "fit") return s.market_fit_score ?? -1;
    if (k === "feas") return s.technical_feasibility_score ?? -1;
    return buildWeeks(s.estimated_development_time);
  }
  const sortedSolutions = $derived.by(() => {
    const arr = [...solutions];
    arr.sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      return sortDir === "desc" ? vb - va : va - vb;
    });
    return arr;
  });

  const SORT_COLS: { key: SortKey; label: string; tooltip?: string }[] = [
    { key: "score", label: "Score", tooltip: SCORE_DEFINITIONS.composite },
    { key: "fit", label: "Market fit", tooltip: SCORE_DEFINITIONS.market_fit },
    {
      key: "feas",
      label: "Feasibility",
      tooltip: SCORE_DEFINITIONS.technical_feasibility,
    },
    { key: "build", label: "Build time" },
  ];

  // ── Helpers ──
  function selectionIndexOf(name: string): number {
    let i = 1;
    for (const n of selectedNames) {
      if (n === name) return i;
      i++;
    }
    return 0;
  }
  function rankedIndexOf(name: string): number {
    return sortedSolutions.findIndex((s) => s.solution_name === name);
  }
  function toggle(name: string) {
    if (selectLoading) return;
    if (selectedNames.has(name)) selectedNames.delete(name);
    else if (selectedNames.size < MAX_SELECTIONS) selectedNames.add(name);
  }
  // Adapter so SolutionDetail's onSelect(name) matches our toggle(name)
  function handleToggleAdapter(name: string) {
    toggle(name);
  }
  function openDetail(name: string) {
    modalIndex = rankedIndexOf(name);
  }
  function handleNavigate(index: number) {
    modalIndex = index;
  }
  function handleCloseDetail() {
    modalIndex = null;
  }

  function handleValidate() {
    if (!canSubmit) return;
    if (!canAffordDeep) {
      creditTopUp.show({
        balance: creditBalance,
        required: deepCost,
        stageName: "deep research",
      });
      return;
    }
    selectError = "";
    modalOpen = true;
  }
  async function handleConfirmSelection(rationale: string) {
    selectLoading = true;
    selectError = "";
    try {
      await selectSolution(jobId, {
        solutionNames: Array.from(selectedNames),
        rationale: rationale || undefined,
      });
      modalOpen = false;
      onComplete?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        modalOpen = false;
        creditTopUp.show({
          balance: creditBalance,
          required: deepCost,
          stageName: "deep research",
        });
      } else {
        selectError =
          e instanceof Error ? e.message : "Failed to select solution";
      }
    } finally {
      selectLoading = false;
    }
  }
  function handleCancelModal() {
    if (!selectLoading) {
      modalOpen = false;
      selectError = "";
    }
  }

  function scoreColor(v: number): string {
    if (v >= 0.7) return "var(--color-success-dark)";
    if (v < 0.35) return "var(--color-text-muted)";
    return "var(--color-text-primary)";
  }
  function pct(v?: number | null): string {
    return v == null ? "--" : String(Math.round(v * 100));
  }

  // Per-row derived helpers (called in snippet to keep markup lean)
  function rowMeta(s: SolutionPreview) {
    const sourcePain = s.source_pain?.trim() || s.pain_points_addressed?.[0]?.trim() || null;
    const risk =
      s.tags?.risk_flags?.[0]
        ? humanizeTag(s.tags.risk_flags[0])
        : s.tags?.build_complexity === "high"
          ? "Hard to build"
          : s.tags?.novelty_level === "conventional"
            ? "Conventional"
            : null;
    return {
      title: solutionDisplayTitle(s),
      summary: solutionCardDescription(s),
      score: computeCompositeScore(s),
      fit: fitLabel(s.market_fit_score),
      feasPct: pct(s.technical_feasibility_score),
      build: s.estimated_development_time ?? "--",
      strength: solutionStrengthBadge(s),
      angle: s.winning_angle && angleLabel(s.winning_angle),
      strengthWhy: s.tags?.primary_strength
        ? tagDescription(s.tags.primary_strength)
        : null,
      angleWhy:
        s.angle_rationale ||
        (s.winning_angle ? angleDescription(s.winning_angle) : null),
      provenance: sourcePain,
      risk,
    };
  }
</script>

<div class="workbench" class:has-tray={showTray} id="opportunities">
  <span id="solution-selector" class="workbench-anchor" aria-hidden="true"></span>
  <!-- ── Command header ── -->
  <header class="cmd">
    <div class="cmd-main">
      <h2 class="cmd-title">Ranked candidates</h2>
      <p class="cmd-sub">
        Choose up to 3 candidates for paid validation. Deep Research checks demand,
        competition, market size, and go-to-market risk.
      </p>
      <!-- Ranking-focused stats only. Evidence counts (discussions, pain points, sources)
           live in the discovery-dossier ledger below — kept distinct to avoid repeating numbers. -->
      <dl class="cmd-proof" aria-label="Candidate summary">
        <div>
          <dt>Candidates</dt>
          <dd>{solutions.length}</dd>
        </div>
        <div>
          <dt>Top score</dt>
          <dd>{bestScore ?? "--"}</dd>
        </div>
        <div>
          <dt>Segments</dt>
          <dd>{segmentCount ?? "--"}</dd>
        </div>
      </dl>
    </div>
    <aside class="cmd-status" class:is-empty={selectionCount === 0} aria-label="Selection status">
      <div class="cmd-status-top">
        <strong>{selectionCount}/{MAX_SELECTIONS}</strong>
        <span>selected</span>
      </div>
      {#if selectionCount > 0}
        <div
          class="cmd-status-track"
          aria-hidden="true"
          style={`--selection-progress:${(selectionCount / MAX_SELECTIONS) * 100}%`}
        >
          <span></span>
        </div>
        <p>Ready to validate {selectionCount} idea{selectionCount === 1 ? "" : "s"}.</p>
        {#if !canAffordDeep}
          <p class="cmd-status-warning">{deepCost - creditBalance} more credits needed.</p>
        {/if}
      {:else}
        <p class="cmd-status-empty">Pick at least one candidate.</p>
      {/if}
      <span class="cmd-status-cost">
        <Coins class="w-3 h-3" aria-hidden="true" />{deepCost} credits / one-time
      </span>
      {#if selectionCount === 0}
        <button
          type="button"
          class="cmd-status-cta"
          onclick={handleValidate}
          disabled={!canSubmit || selectLoading}
        >
          {statusCtaLabel}
        </button>
      {/if}
    </aside>
  </header>

  {#if regenerateError}
    <p class="regen-error">{regenerateError}</p>
  {/if}

  {#if shape || (coverageNotes && coverageNotes.length)}
    <div class="context-notes">
      {#if shape}
        <div class="shape-line">
          <span class="shape-label">Opportunity shape</span>
          <span>{shape.line}</span>
        </div>
      {/if}
      {#if coverageNotes && coverageNotes.length}
        <details class="coverage-disclosure">
          <summary>
            <span>Data caveats</span>
            <strong>{coverageNotes.length}</strong>
          </summary>
          <ul>
            {#each coverageNotes as note}
              {#if note?.trim()}
                <li>{note}</li>
              {/if}
            {/each}
          </ul>
        </details>
      {/if}
    </div>
  {/if}

  <!-- ── Ranked opportunity list ── -->
  <div class="opp-list">
    <!-- Column header (desktop) -->
    <div class="row row-head">
      <span class="cell-rank">#</span>
      <span class="cell-select-label">Pick</span>
      <span class="cell-title-label">Opportunity</span>
      {#each SORT_COLS as col}
        <button
          type="button"
          class="cell-metric-head"
          class:active={sortKey === col.key}
          onclick={() => setSort(col.key)}
          aria-label="Sort by {col.label}"
          aria-pressed={sortKey === col.key}
          title={col.tooltip}
        >
          <span>{col.label}</span>
          {#if sortKey === col.key}
            {#if sortDir === "asc"}<ArrowUp class="w-3 h-3" aria-hidden="true" />{:else}<ArrowDown class="w-3 h-3" aria-hidden="true" />{/if}
          {/if}
        </button>
      {/each}
    </div>

    {#each sortedSolutions as s, i (s.solution_name)}
      {@const m = rowMeta(s)}
      {@const isSel = selectedNames.has(s.solution_name)}
      {@const order = selectionIndexOf(s.solution_name)}
      {@const maxed = !isSel && selectedNames.size >= MAX_SELECTIONS}
      <div
        class="row"
        class:row-sel={isSel}
        class:row-maxed={maxed}
      >
        <span class="cell-rank">{i + 1}</span>

        <label
          class="cell-select select-control"
          class:sel={isSel}
          class:maxed
          title={maxed ? "Deselect one to add this" : undefined}
        >
          <input
            type="checkbox"
            class="sr-only"
            checked={isSel}
            disabled={maxed || selectLoading}
            onchange={() => toggle(s.solution_name)}
            aria-label={isSel ? `Deselect ${m.title}` : `Select ${m.title}`}
          />
          {#if isSel}
            <span class="select-marker"><span class="select-order">{order}</span></span>
            <span class="select-copy">Picked</span>
          {:else if maxed}
            <span class="select-marker"><span class="select-dash" aria-hidden="true">-</span></span>
            <span class="select-copy">Full</span>
          {:else}
            <span class="select-marker"><Plus class="select-plus w-3.5 h-3.5" aria-hidden="true" /></span>
            <span class="select-copy">Shortlist</span>
          {/if}
        </label>

        <button
          type="button"
          class="cell-title"
          onclick={() => openDetail(s.solution_name)}
          aria-label="Review details for {m.title}. Score {Math.round(m.score * 100)} of 100, market fit {pct(s.market_fit_score)} percent, feasibility {m.feasPct} percent, build time {m.build}."
        >
          <span class="title-block">
            <span class="opp-title">{m.title}</span>
            <span class="opp-summary">{m.summary}</span>
            <span class="mobile-metrics" aria-hidden="true">
              <span>Market <strong>{pct(s.market_fit_score)}{#if s.market_fit_score != null}%{/if}</strong></span>
              <span>Feas <strong>{m.feasPct}{#if s.technical_feasibility_score != null}%{/if}</strong></span>
              <span>Build <strong>{m.build}</strong></span>
            </span>
            {#if m.provenance}
              <span class="opp-evidence"><strong>Pain</strong><span>{m.provenance}</span></span>
            {/if}
            <span class="opp-tags">
              {#if m.strength}
                {@const strength = m.strength}
                {#if m.strengthWhy}
                  <Tooltip content={m.strengthWhy} position="bottom">
                    {#snippet children()}<span class="tag tag-strength tag-{strength.variant}">{strength.label}</span>{/snippet}
                  </Tooltip>
                {:else}
                  <span class="tag tag-strength tag-{strength.variant}">{strength.label}</span>
                {/if}
              {/if}
              {#if m.angle}
                {@const angle = m.angle}
                <Tooltip content={m.angleWhy ?? ""} position="bottom">
                  {#snippet children()}<span class="tag tag-angle">{angle}</span>{/snippet}
                </Tooltip>
              {/if}
              {#if m.risk}
                <span class="tag tag-risk">{m.risk}</span>
              {/if}
            </span>
          </span>
        </button>

        <!-- Score -->
        <span class="cell-metric metric-score" aria-label="Score {Math.round(m.score * 100)}">
          <span class="metric-num" style:color={scoreColor(m.score)}>{Math.round(m.score * 100)}</span>
        </span>

        <span class="cell-metric metric-fit" aria-label="Fit {m.fit.text}">
          <span class="metric-num fit-{m.fit.variant}">{pct(s.market_fit_score)}<span class="metric-unit">%</span></span>
        </span>

        <span class="cell-metric" aria-label="Feasibility {m.feasPct}">
          <span class="metric-num">{m.feasPct}{#if s.technical_feasibility_score != null}<span class="metric-unit">%</span>{/if}</span>
        </span>

        <span class="cell-metric metric-build" aria-label="Build time {m.build}">
          <span class="metric-num metric-build-num">{m.build}</span>
        </span>
      </div>

    {/each}
  </div>

  {#if canRegenerate}
    <div class="secondary-actions">
      <div class="secondary-copy">
        <span class="secondary-title">Need another angle?</span>
        <span class="secondary-text">Generate a small extra batch after reviewing this ranked set.</span>
      </div>
      <div class="regen-group">
        <div class="regen-focus" role="group" aria-label="Idea focus for the next batch">
          {#each REGEN_FOCUSES as focus}
            <button
              type="button"
              onclick={() => (regenerateFocus = focus.value)}
              disabled={regenerating || isRegenerating}
              class="regen-focus-btn"
              class:is-active={regenerateFocus === focus.value}
              aria-pressed={regenerateFocus === focus.value}
            >
              {focus.label}
            </button>
          {/each}
        </div>
        <button
          type="button"
          onclick={handleRegenerate}
          disabled={regenerating || isRegenerating || !canAffordRegenerate}
          class="regen-btn"
        >
          {#if regenerating || isRegenerating}
            <Loader2 class="w-3.5 h-3.5 animate-spin" />
            <span>Exploring new angles...</span>
          {:else}
            <Sparkles class="w-3.5 h-3.5" />
            <span>Generate more ideas</span>
            {#if stageCosts.regenerate_ideas > 0}
              <span class="regen-cost"><Coins class="w-3 h-3" aria-hidden="true" />{stageCosts.regenerate_ideas}</span>
            {/if}
          {/if}
        </button>
      </div>
    </div>
  {/if}

  <!-- ── Selection tray (fixed) ── -->
  {#if showTray}
  <div class="tray" role="region" aria-label="Your selection">
    <div class="tray-inner">
      <div class="tray-picks">
        <span class="tray-count"><strong>{selectionCount}</strong><span class="tray-sep">/</span>{MAX_SELECTIONS}</span>
        {#if selectionCount > 0}
          <div class="tray-chips">
            {#each picks as p}
              <span class="tray-chip">
                <span class="tray-chip-label">{p.title}</span>
                <button
                  type="button"
                  class="tray-x"
                  aria-label="Remove {p.title}"
                  disabled={selectLoading}
                  onclick={() => toggle(p.name)}
                >
                  <X class="w-3 h-3" aria-hidden="true" />
                </button>
              </span>
            {/each}
          </div>
        {/if}
      </div>
      <div class="tray-action">
        {#if !canAffordDeep}
          <span class="tray-warn">{deepCost - creditBalance} more credits needed</span>
        {:else}
          <span class="tray-cost"><Coins class="w-3 h-3" aria-hidden="true" />{deepCost} credits / one-time</span>
        {/if}
        <button
          type="button"
          class="tray-cta"
          disabled={!canSubmit || selectLoading}
          onclick={handleValidate}
        >
          {#if selectLoading}
            <Loader2 class="w-4 h-4 animate-spin" /> Validating...
          {:else if selectionCount === 0}
            Select ideas to start
          {:else if !canAffordDeep}
            Add credits to start
          {:else}
            Start Deep Research
            <span class="tray-cta-icon"><ArrowRight class="w-4 h-4" aria-hidden="true" /></span>
          {/if}
        </button>
      </div>
    </div>
  </div>
  {/if}
</div>

<!-- Confirmation modal -->
<SelectSolutionModal
  bind:open={modalOpen}
  solutionNames={Array.from(selectedNames)}
  {solutions}
  loading={selectLoading}
  error={selectError}
  creditCost={deepCost}
  onConfirm={handleConfirmSelection}
  onCancel={handleCancelModal}
/>

<!-- Detail modal -->
{#if modalIndex !== null && sortedSolutions[modalIndex]}
  <SolutionDetail
    open={modalIndex !== null}
    solution={sortedSolutions[modalIndex]}
    solutions={sortedSolutions}
    currentIndex={modalIndex}
    isSelected={selectedNames.has(sortedSolutions[modalIndex].solution_name)}
    selectionIndex={selectionIndexOf(sortedSolutions[modalIndex].solution_name)}
    selectedCount={selectionCount}
    maxSelections={MAX_SELECTIONS}
    maxReached={selectedNames.size >= MAX_SELECTIONS}
    disabled={selectLoading}
    canStart={canSubmit}
    canAffordStart={canAffordDeep}
    startCost={deepCost}
    onSelect={handleToggleAdapter}
    onStartValidation={handleValidate}
    onNavigate={handleNavigate}
    onClose={handleCloseDetail}
    voteCount={solutionVotes[sortedSolutions[modalIndex].solution_name] ?? 0}
  />
{/if}

<style>
  .workbench {
    --selection-motion: cubic-bezier(0.32, 0.72, 0, 1);
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.68rem;
    padding: 1rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0.38)),
      var(--color-bg-elevated);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 58%, transparent);
    border-radius: 0.75rem;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.84),
      0 18px 54px rgba(24, 24, 27, 0.045);
  }
  .workbench.has-tray {
    padding-bottom: 6.2rem;
  }
  .workbench-anchor {
    position: absolute;
    top: -5.5rem;
    left: 0;
    width: 1px;
    height: 1px;
    pointer-events: none;
  }

  /* ── Command header ── */
  .cmd {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(12rem, 15rem);
    align-items: center;
    gap: 1rem;
    padding: 0 0.1rem 0.72rem;
    background: transparent;
    border: 0;
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
  }
  .cmd-title {
    margin: 0;
    max-width: 42ch;
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: 0;
    color: var(--color-text-primary);
    text-wrap: balance;
  }
  .cmd-sub {
    margin: 0.14rem 0 0;
    max-width: 68ch;
    font-size: 0.75rem;
    line-height: 1.48;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }
  /* Bordered stat cells — mirrors the discovery dossier's ledger so both
     summaries read as the same designed element, not one strip run-on. */
  .cmd-proof {
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
    width: fit-content;
    max-width: 100%;
    margin: 0.72rem 0 0;
    padding: 0.28rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
    border-radius: 0.75rem;
    background: color-mix(in srgb, var(--color-bg-elevated) 74%, transparent);
  }
  .cmd-proof div {
    flex: 0 0 auto;
    display: grid;
    gap: 0.1rem;
    min-width: 4.4rem;
    padding: 0.4rem 0.5rem;
    border-radius: 0.5rem;
    background: color-mix(in srgb, white 58%, transparent);
  }
  .cmd-proof dt {
    color: var(--color-text-muted);
    font-size: 0.5625rem;
    font-weight: 700;
    line-height: 1;
  }
  .cmd-proof dd {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.875rem;
    font-weight: 800;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
  }
  .cmd-status {
    display: grid;
    gap: 0.3rem;
    align-self: start;
    justify-self: end;
    width: 100%;
    padding: 0.06rem 0 0.06rem 0.95rem;
    border-left: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }
  .cmd-status-top {
    display: flex;
    align-items: baseline;
    justify-content: flex-end;
    gap: 0.3rem;
  }
  .cmd-status-top span {
    font-size: 0.6875rem;
    font-weight: 700;
  }
  .cmd-status-top strong {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }
  .cmd-status-track {
    position: relative;
    height: 0.22rem;
    overflow: hidden;
    border-radius: 999px;
    background: var(--color-border);
  }
  .cmd-status-track span {
    display: block;
    width: var(--selection-progress);
    height: 100%;
    border-radius: inherit;
    background: var(--color-accent);
    transition: width 260ms var(--selection-motion);
  }
  .cmd-status p {
    margin: 0;
    font-size: 0.6875rem;
    line-height: 1.32;
    text-align: right;
    color: var(--color-text-muted);
  }
  .cmd-status-warning {
    color: var(--color-warning-dark) !important;
  }
  .cmd-status-cost {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    white-space: nowrap;
    justify-self: end;
  }
  .cmd-status-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2rem;
    padding: 0.34rem 0.7rem;
    border: 1px solid var(--color-accent-hover);
    border-radius: 0.5rem;
    background: var(--color-accent-hover);
    color: white;
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 800;
    cursor: pointer;
    justify-self: end;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      background 220ms var(--selection-motion),
      color 220ms var(--selection-motion);
  }
  .cmd-status-cta:hover:not(:disabled) {    border-color: var(--color-accent-hover);
    background: var(--color-accent-hover);
  }
  .cmd-status-cta:disabled {
    border-color: var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 82%, var(--color-bg-elevated));
    color: var(--color-text-muted);
    cursor: not-allowed;
  }
  .cmd-status-empty {
    max-width: 12rem;
  }

  .regen-group {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
  }
  .regen-focus {
    display: inline-flex;
    gap: 0.18rem;
    padding: 0.18rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
  }
  .regen-focus-btn {
    padding: 0.32rem 0.55rem;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 0.375rem;
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      color 220ms var(--selection-motion),
      background 220ms var(--selection-motion);
  }
  .regen-focus-btn:hover:not(:disabled) {    color: var(--color-text-secondary);
  }
  .regen-focus-btn.is-active {
    background: var(--color-bg-elevated);
    border-color: color-mix(in srgb, var(--color-accent) 24%, transparent);
    color: var(--color-accent);
  }
  .regen-focus-btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .regen-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 2.35rem;
    padding: 0.45rem 0.8rem;
    background: var(--color-bg-elevated);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 76%, transparent);
    border-radius: 0.625rem;
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      color 220ms var(--selection-motion),
      background 220ms var(--selection-motion);
  }
  .regen-btn:hover:not(:disabled) {    border-color: var(--color-accent);
    color: var(--color-accent);
  }
  .regen-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .regen-cost {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: var(--color-text-muted);
  }
  .secondary-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.62rem 0.1rem 0.1rem;
    border-top: 1px solid var(--color-border);
  }
  .secondary-copy {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    min-width: 0;
    color: var(--color-text-muted);
  }
  .secondary-title {
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .secondary-text {
    font-size: 0.75rem;
    line-height: 1.35;
    text-wrap: pretty;
  }
  .regen-error {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-error);
    text-align: right;
  }

  .cell-metric-head:focus-visible,
  .cmd-status-cta:focus-visible,
  .regen-focus-btn:focus-visible,
  .regen-btn:focus-visible,
  .coverage-disclosure summary:focus-visible,
  .tray-cta:focus-visible,
  .tray-x:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ── Context notes ── */
  .context-notes {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.02rem 0.05rem 0.18rem;
  }
  .shape-line {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 0.62rem;
    align-items: baseline;
    margin: 0;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.42;
    min-width: 0;
  }
  .shape-label {
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .coverage-disclosure {
    position: relative;
    flex-shrink: 0;
    min-width: 11rem;
  }
  .coverage-disclosure summary {
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.55rem;
    width: 100%;
    padding: 0.34rem 0.54rem;
    list-style: none;
    cursor: pointer;
    color: var(--color-text-muted);
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      color 220ms var(--selection-motion),
      background 220ms var(--selection-motion);
  }
  .coverage-disclosure summary::-webkit-details-marker { display: none; }
  .coverage-disclosure summary:hover {    color: var(--color-text-secondary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
  }
  .coverage-disclosure summary strong {
    display: grid;
    place-items: center;
    min-width: 1.2rem;
    height: 1.2rem;
    padding: 0 0.25rem;
    border-radius: 999px;
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: 0.625rem;
  }
  .coverage-disclosure[open] summary {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
  }
  .coverage-disclosure ul {
    position: absolute;
    right: 0;
    z-index: 3;
    display: grid;
    gap: 0.58rem;
    width: min(42rem, 72vw);
    margin: 0.45rem 0 0;
    padding: 0.85rem 0.95rem;
    background: color-mix(in srgb, var(--color-bg-elevated) 98%, transparent);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 1rem;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.86),
      0 18px 48px rgba(24, 24, 27, 0.08);
  }
  .coverage-disclosure li {
    list-style: none;
    margin: 0;
    padding-left: 0.7rem;
    border-left: 1px solid var(--color-border-emphasis);
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    line-height: 1.42;
  }

  /* ── Opportunity list ── */
  .opp-list {
    display: grid;
    gap: 0;
    overflow: hidden;
    background: var(--color-bg-surface);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 56%, transparent);
    border-radius: 0.5rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.68);
  }
  .row {
    display: grid;
    grid-template-columns: 1.35rem 5.65rem minmax(0, 1fr) 4rem 4.55rem 4.7rem 5.2rem;
    align-items: center;
    gap: 0.56rem;
    padding: 0.56rem 0.68rem;
    border: 0;
    border-top: 1px solid var(--color-border);
    border-radius: 0;
    background: var(--color-bg-elevated);
    box-shadow: none;
    transition:
      background 280ms var(--selection-motion),
      box-shadow 280ms var(--selection-motion);
  }
  .row-head {
    min-height: 1.75rem;
    padding: 0.32rem 0.7rem;
    border: 0;
    border-radius: 0;
    background: var(--color-bg-surface);
    box-shadow: none;
  }
  .row:not(.row-head):hover {
    background: color-mix(in srgb, var(--color-bg-surface) 48%, var(--color-bg-elevated));
  }
  .row-sel {
    background: color-mix(in srgb, var(--color-accent) 3%, var(--color-bg-elevated));
    box-shadow: inset 2px 0 0 color-mix(in srgb, var(--color-accent) 74%, var(--color-border-emphasis));
  }
  .row-maxed { opacity: 1; }

  .cell-rank {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
    text-align: center;
  }
  .row-head .cell-rank,
  .row-head .cell-select-label,
  .row-head .cell-title-label {
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    color: var(--color-text-muted);
  }
  .row-head .cell-title-label { padding-left: 0; }

  /* select control */
  .cell-select-label {
    text-align: center;
  }
  .select-control {
    position: relative;
    justify-self: center;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.34rem;
    width: 100%;
    min-height: 2rem;
    padding: 0 0.44rem;
    border-radius: 0.375rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 86%, transparent);
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    transition:
      transform 220ms var(--selection-motion),
      border-color 220ms var(--selection-motion),
      background 220ms var(--selection-motion),
      color 220ms var(--selection-motion);
  }
  .select-control:hover:not(.maxed) {    border-color: var(--color-accent);
    color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated));
  }
  .select-control.sel {
    border-color: color-mix(in srgb, var(--color-accent) 54%, var(--color-border-emphasis));
    background: color-mix(in srgb, var(--color-accent) 7%, var(--color-bg-elevated));
    color: var(--color-accent-dark);
    box-shadow: none;
  }
  .select-control.sel .select-marker {
    border-color: var(--color-accent);
    background: var(--color-accent);
    color: white;
  }
  .select-control.maxed {
    border-color: var(--color-border);
    color: var(--color-text-muted);
    cursor: not-allowed;
    opacity: 0.55;
  }
  .select-control:active:not(.maxed) { transform: scale(0.96); }
  .select-marker {
    display: grid;
    place-items: center;
    width: 0.94rem;
    height: 0.94rem;
    border-radius: 0.25rem;
    border: 1.25px solid currentColor;
    flex-shrink: 0;
  }
  .select-copy {
    position: static;
    width: auto;
    height: auto;
    overflow: visible;
    clip: auto;
    white-space: nowrap;
  }
  .select-order {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 800;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .row:has(.cell-select input:focus-visible) .select-control {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .select-control:focus-within {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* title cell */
  .cell-title {
    display: flex;
    align-items: center;
    gap: 0;
    min-width: 0;
    background: transparent;
    border: none;
    padding: 0;
    text-align: left;
    cursor: pointer;
    color: inherit;
  }
  .cell-title:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
    border-radius: 0.5rem;
  }
  /* The title IS the button that opens the detail view — give it a clear affordance. */
  .cell-title:hover .opp-title {
    color: var(--color-accent-dark);
    text-decoration: underline;
    text-underline-offset: 2px;
    text-decoration-thickness: 1px;
  }
  .title-block {
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
    min-width: 0;
  }
  .opp-title {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-text-primary);
    transition: color 0.15s ease;
    text-wrap: pretty;
  }
  .opp-summary {
    max-width: 72ch;
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
    display: -webkit-box;
    -webkit-line-clamp: 1;
    line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .opp-evidence {
    display: flex;
    gap: 0.32rem;
    align-items: baseline;
    max-width: 78ch;
    font-size: 0.6875rem;
    line-height: 1.36;
    color: var(--color-text-muted);
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
  }
  .opp-evidence strong {
    flex-shrink: 0;
    color: var(--color-text-secondary);
    font-weight: 700;
  }
  .opp-evidence span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .mobile-metrics {
    display: none;
  }
  .opp-tags {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.28rem;
    margin-top: 0.12rem;
  }
  .tag {
    display: inline-flex;
    align-items: center;
    max-width: 22rem;
    padding: 0.09rem 0.34rem;
    border-radius: 0.375rem;
    font-family: var(--font-body);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 0;
    line-height: 1.18;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tag-strength { border: 1px solid currentColor; }
  .tag-success {
    background: color-mix(in srgb, var(--color-success) 9%, transparent);
    color: var(--color-success-dark);
  }
  .tag-accent {
    background: var(--color-accent-subtle);
    color: var(--color-accent-dark);
  }
  .tag-info {
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
  }
  .tag-warning {
    background: color-mix(in srgb, var(--color-warning) 11%, transparent);
    color: var(--color-warning-dark);
  }
  .tag-angle {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }
  .tag-risk {
    background: var(--color-error-subtle);
    border: 1px solid color-mix(in srgb, var(--color-error) 30%, transparent);
    color: var(--color-error-dark);
  }

  /* metric cells */
  .cell-metric,
  .cell-metric-head {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.34rem;
    font-variant-numeric: tabular-nums;
  }
  .cell-metric-head {
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
    color: var(--color-text-muted);
    background: transparent;
    border: none;
    cursor: pointer;
    min-height: 1.5rem;
    padding: 0.16rem 0;
    border-radius: 0.375rem;
    transition:
      color 180ms var(--selection-motion),
      transform 180ms var(--selection-motion);
  }
  .cell-metric-head:hover {    color: var(--color-text-secondary);
  }
  .cell-metric-head.active { color: var(--color-accent-dark); }
  .metric-num {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 800;
    color: var(--color-text-primary);
    line-height: 1;
  }
  .metric-unit {
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-left: 0.05rem;
  }
  .fit-success { color: var(--color-success-dark); }
  .fit-warning { color: var(--color-text-primary); }
  .fit-muted { color: var(--color-text-muted); }
  .metric-score { align-items: flex-end; }
  .metric-score .metric-num { font-size: 0.9375rem; }
  .metric-build-num {
    max-width: 5.8rem;
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-text-secondary);
    line-height: 1.08;
    text-align: right;
  }

  /* ── Selection tray ── */
  .tray {
    position: fixed;
    left: clamp(0.75rem, 3vw, 2rem);
    right: clamp(0.75rem, 3vw, 2rem);
    bottom: clamp(0.8rem, 2vw, 1.2rem);
    background: transparent;
    border: 0;
    z-index: var(--z-overlay, 30);
    pointer-events: none;
  }
  .tray-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: min(58rem, calc(100vw - 2rem));
    margin: 0 auto;
    padding: 0.56rem 0.6rem 0.56rem 0.82rem;
    pointer-events: auto;
    background: var(--color-bg-elevated);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 78%, transparent);
    border-radius: 0.75rem;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.9),
      0 18px 48px rgba(24, 24, 27, 0.11);
  }
  .tray-picks {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    min-width: 0;
    flex: 1;
  }
  .tray-count {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .tray-count strong {
    font-size: 1.125rem;
    color: var(--color-text-primary);
    font-weight: 800;
  }
  .tray-sep {
    opacity: 0.5;
    margin: 0 0.1rem;
  }
  .tray-chips {
    display: flex;
    gap: 0.42rem;
    overflow: hidden;
    flex-wrap: wrap;
  }
  .tray-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.34rem;
    max-width: 14rem;
    padding: 0.28rem 0.36rem 0.28rem 0.66rem;
    background: var(--color-bg-elevated);
    border: 1px solid color-mix(in srgb, var(--color-accent) 28%, var(--color-border));
    border-radius: 0.75rem;
    color: var(--color-accent-dark);
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
  }
  .tray-chip-label {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tray-x {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    border: none;
    background: color-mix(in srgb, var(--color-accent) 12%, transparent);
    color: var(--color-accent);
    cursor: pointer;
    transition: transform 200ms var(--selection-motion), background 200ms var(--selection-motion), color 200ms var(--selection-motion);
  }
  .tray-x:hover {
    transform: scale(1.06);
    background: var(--color-accent);
    color: white;
  }
  .tray-x:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .tray-cost {
    display: inline-flex;
    align-items: center;
    gap: 0.34rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .tray-action {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    flex-shrink: 0;
  }
  .tray-warn {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-warning-dark);
    white-space: nowrap;
  }
  .tray-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    min-height: 2.35rem;
    padding: 0.42rem 0.48rem 0.42rem 0.86rem;
    background: var(--color-accent-hover);
    color: white;
    border: none;
    border-radius: 0.625rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 800;
    cursor: pointer;
    transition:
      transform 220ms var(--selection-motion),
      background 220ms var(--selection-motion),
      color 220ms var(--selection-motion);
  }
  .tray-cta:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .tray-cta:active:not(:disabled) { transform: scale(0.985); }
  .tray-cta:disabled {
    background: color-mix(in srgb, var(--color-bg-surface) 82%, var(--color-bg-elevated));
    border: 1px solid var(--color-border);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }
  .tray-cta-icon {
    display: grid;
    place-items: center;
    width: 1.55rem;
    height: 1.55rem;
    border-radius: 0.5rem;
    background: rgba(255, 255, 255, 0.18);
    transition: transform 220ms var(--selection-motion), background 220ms var(--selection-motion);
  }
  .tray-cta:hover:not(:disabled) .tray-cta-icon {
    transform: translateX(2px);
    background: rgba(255, 255, 255, 0.24);
  }
  .tray-cta:disabled .tray-cta-icon {
    background: color-mix(in srgb, var(--color-text-muted) 12%, transparent);
  }

  /* ── Responsive ── */
  @media (max-width: 859px) {
    .workbench { padding: 0.88rem 0.88rem 1.25rem; }
    .workbench.has-tray { padding-bottom: 6rem; }
    .cmd {
      grid-template-columns: 1fr;
      align-items: flex-start;
    }
    .cmd-title { max-width: none; }
    .cmd-status {
      width: 100%;
      padding: 0.65rem 0 0;
      border-left: 0;
      border-top: 1px solid var(--color-border);
    }
    .cmd-status-cost {
      justify-self: start;
    }
    .cmd-status-cta {
      width: 100%;
      justify-self: stretch;
    }
    .context-notes {
      display: grid;
      gap: 0.55rem;
    }
    .shape-line {
      grid-template-columns: 1fr;
      gap: 0.2rem;
    }
    .coverage-disclosure {
      width: 100%;
      min-width: 0;
    }
    .coverage-disclosure ul {
      position: static;
      width: 100%;
    }
    .regen-group {
      flex-wrap: wrap;
    }
    .secondary-actions {
      display: grid;
      gap: 0.55rem;
    }
    .secondary-copy {
      display: grid;
      gap: 0.18rem;
    }
    .row {
      grid-template-columns: 2rem minmax(0, 1fr) 4.5rem;
      grid-template-areas:
        "rank title score"
        "pick pick pick";
      gap: 0.7rem 0.75rem;
      padding: 0.92rem;
      border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 54%, transparent);
      border-radius: var(--radius-lg, 0.875rem);
      background: var(--color-bg-elevated);
    }
    .opp-list {
      gap: 0.55rem;
      overflow: visible;
      background: transparent;
      border: 0;
      border-radius: 0;
    }
    .row-head { display: none; }
    .cell-metric.metric-fit,
    .cell-metric:not(.metric-score):not(.metric-fit),
    .cell-metric.metric-build {
      display: none;
    }
    .cell-rank {
      grid-area: rank;
      align-self: start;
      padding-top: 0.1rem;
      text-align: left;
    }
    .cell-select {
      grid-area: pick;
    }
    .cell-title {
      grid-area: title;
    }
    .metric-score {
      grid-area: score;
      align-self: start;
    }
    .metric-score { align-items: flex-end; }
    .opp-summary {
      -webkit-line-clamp: 2;
      line-clamp: 2;
    }
    .mobile-metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 0.28rem 0.56rem;
      margin-top: 0.08rem;
      color: var(--color-text-muted);
      font-size: 0.6875rem;
      line-height: 1.2;
    }
    .mobile-metrics strong {
      color: var(--color-text-secondary);
      font-family: var(--font-mono);
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .tag { max-width: 13rem; }
    .select-control {
      width: 100%;
      min-height: 2.25rem;
      font-size: 0.75rem;
    }
    .tray {
      position: fixed;
      left: 0.75rem;
      right: 0.75rem;
      bottom: calc(0.75rem + env(safe-area-inset-bottom, 0px));
      margin-top: 0;
    }
    .tray-inner { width: 100%; }
    .tray-inner {
      flex-direction: column;
      align-items: stretch;
      gap: 0.65rem;
    }
    .tray-picks {
      align-items: flex-start;
    }
    .tray-action {
      justify-content: space-between;
    }
    .tray-cta {
      flex: 1;
      justify-content: center;
    }
  }

  @media (max-width: 480px) {
    .cmd-sub { font-size: 0.8125rem; }
    .regen-focus-btn {
      padding: 0.3rem 0.46rem;
      font-size: 0.6875rem;
    }
    .regen-btn {
      width: 100%;
      justify-content: center;
    }
    .tray { bottom: 0.6rem; }
    .tray-picks {
      flex-direction: column;
      gap: 0.35rem;
    }
    .tray-cta {
      width: 100%;
      font-size: 0.875rem;
    }
  }
</style>
