<script lang="ts">
  import { tick } from "svelte";
  import { ArrowRight, Loader2, RefreshCw } from "lucide-svelte";
  import {
    createSelectionConceptSet,
    getSelectionConceptSets,
    prepareSelectionConceptOption,
    type IdeaSynthesisPatch,
  } from "$lib/api";
  import ChipGroup from "$lib/components/ui/ChipGroup.svelte";
  import ConfirmGate from "$lib/components/ui/ConfirmGate.svelte";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import type { SelectionConceptForgePrefill } from "$lib/types/selectionCopilot";
  import type {
    SelectionConceptOption,
    SelectionConceptPurpose,
    SelectionConceptSet,
  } from "$lib/types/selectionConceptSet";
  import {
    GENERATE_DIRECTIONS_LABEL,
    GENERATING_DIRECTIONS_LABEL,
    SHAPE_PANEL_EYEBROW,
    SHAPE_PANEL_INTRO,
    SHAPE_PANEL_TITLE,
    SHAPE_PURPOSE_LABEL,
    STILL_GENERATING_NOTE,
    costLine,
    shapeCostNote,
  } from "$lib/selection/labels";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface Props {
    open: boolean;
    jobId: string;
    parents: SolutionPreview[];
    prefill?: SelectionConceptForgePrefill | null;
    seedCost?: number | null;
    disabled?: boolean;
    /** Owner-page error from the last onEvaluate attempt (e.g. the 409
     *  PRICE_CHANGED message after the price re-fetch). Shown inline here so a
     *  failed evaluation is never explained only behind the overlay. */
    evaluateError?: string;
    onEvaluate: (patch: IdeaSynthesisPatch, sourceMessageId: string) => Promise<boolean>;
    onClose: () => void;
  }

  let {
    open,
    jobId,
    parents,
    prefill = null,
    seedCost = null,
    disabled = false,
    evaluateError = "",
    onEvaluate,
    onClose,
  }: Props = $props();

  let purpose = $state<SelectionConceptPurpose>("diverge");
  let targetTradeoff = $state("");
  /** Last programmatic/persisted tension value. Dirty compares against this so
   *  a prefilled or saved note never counts as unsaved owner input. */
  let tradeoffBaseline = $state("");
  let conceptSet = $state<SelectionConceptSet | null>(null);
  let loading = $state(false);
  let generating = $state(false);
  let error = $state("");
  let loadFailed = $state(false);
  let loadedKey = $state("");
  let evaluatingOptionId = $state<string | null>(null);
  let actionMessage = $state("");
  /** Announces generation completion to assistive tech (persistent region;
   *  only the text changes). */
  let generationAnnouncement = $state("");
  /** True once the owner has explicitly picked a purpose (via the segment
   *  control, an analyst prefill, or a saved set). Blocks the pickedCount
   *  default effect from silently overwriting that choice. */
  let purposeTouched = $state(false);
  let briefHeadingEl = $state<HTMLHeadingElement>();
  let optionsHeadingEl = $state<HTMLHeadingElement>();

  // Elapsed-aware generation copy: after ~20s of an in-flight run the busy
  // state adds a static "long runs are normal" line. Timer torn down with the
  // effect; no animation involved, so reduced motion needs no special case.
  const SLOW_GENERATE_MS = 20_000;
  let generateSlow = $state(false);
  $effect(() => {
    if (!generating) {
      generateSlow = false;
      return;
    }
    const timer = setTimeout(() => {
      generateSlow = true;
    }, SLOW_GENERATE_MS);
    return () => clearTimeout(timer);
  });

  function parentRefKey(parent: SolutionPreview): string {
    return `${parent.idea_id}:${parent.idea_revision ?? 1}`;
  }

  // The forge always branches 1-2 exact parent revisions (backend contract),
  // but the workbench may pass the whole shortlist (up to 3). `selectedParentKeys`
  // is the source of truth for the PICKED parents: with <=2 passed all are
  // auto-selected and no picker renders; with >2 a ChipGroup (cap 2) does.
  let selectedParentKeys = $state<string[]>([]);
  let parentInitKey = $state("");

  const eligibleParents = $derived.by(() => parents
    .filter((parent) => parent.idea_id && Number.isInteger(parent.idea_revision ?? 1)));
  const usesPicker = $derived(parents.length > 2);
  const allPassedEligible = $derived(eligibleParents.length === parents.length);
  const passedKey = $derived(eligibleParents.map(parentRefKey).sort().join("|"));

  $effect(() => {
    if (!open) {
      parentInitKey = "";
      return;
    }
    const key = `${usesPicker}:${passedKey}`;
    if (key === parentInitKey) return;
    parentInitKey = key;
    selectedParentKeys = usesPicker ? [] : eligibleParents.map(parentRefKey);
  });

  const stableParents = $derived.by(() => eligibleParents
    .filter((parent) => selectedParentKeys.includes(parentRefKey(parent)))
    .sort((left, right) => parentRefKey(left).localeCompare(parentRefKey(right))));
  const pickedCount = $derived(stableParents.length);
  const parentKey = $derived(stableParents.map(parentRefKey).join("|"));
  const conceptForgeSurfaceKey = $derived(`selection:concept-forge:${parentKey}`);
  const hasExactParents = $derived(
    (usesPicker || allPassedEligible) && pickedCount >= 1 && pickedCount <= 2,
  );
  const purposeOrder = $derived.by((): SelectionConceptPurpose[] => pickedCount === 2
    ? ["diverge", "resolve_tradeoff", "reshape"]
    : ["diverge", "reshape"]);

  // Purpose picker copy: card-density SegmentControl options (label + description).
  const PURPOSE_META: Record<SelectionConceptPurpose, { label: string; description: string }> = {
    diverge: { label: "Explore directions", description: "Push buyer, workflow, and scope apart." },
    resolve_tradeoff: { label: "Resolve the trade-off", description: "Keep, combine, or deliberately give up strengths." },
    reshape: { label: "Find a viable shape", description: "Reduce risk without pretending it disappeared." },
  };
  const purposeOptions = $derived(purposeOrder.map((value) => ({ value, ...PURPOSE_META[value] })));
  const pickerOptions = $derived(eligibleParents.map((parent) => ({
    value: parentRefKey(parent),
    label: solutionDisplayTitle(parent),
  })));

  const showBrief = $derived(!loading && !loadFailed && !conceptSet && (usesPicker || hasExactParents));
  // Only an unsent tension note is at risk on close; generated sets are
  // persisted. Dirty means the note diverged from its baseline (empty, the
  // analyst prefill, or the last sent/saved value) — never merely non-empty.
  const forgeDirty = $derived(!conceptSet && targetTradeoff.trim() !== tradeoffBaseline.trim());
  const footerMessage = $derived(
    conceptSet
      ? "Only the option you explicitly confirm enters paid evaluation."
      : shapeCostNote(seedCost),
  );

  $effect(() => {
    if (!open || purposeTouched) return;
    purpose = pickedCount === 2 ? "resolve_tradeoff" : "diverge";
  });

  $effect(() => {
    const key = open ? `${jobId}:${parentKey}:${prefill?.requestId ?? "saved"}` : "";
    if (!key || key === loadedKey) return;
    loadedKey = key;
    conceptSet = null;
    actionMessage = "";
    error = "";
    loadFailed = false;
    if (prefill) {
      purpose = prefill.purpose;
      purposeTouched = true;
      targetTradeoff = prefill.targetTradeoff;
      tradeoffBaseline = prefill.targetTradeoff;
      return;
    }
    purposeTouched = false;
    void loadSavedSet();
  });

  function exactRefs() {
    return stableParents.flatMap((parent) => parent.idea_id ? [{
      ideaId: parent.idea_id,
      ideaRevision: parent.idea_revision ?? 1,
    }] : []);
  }

  function setMatchesParents(set: SelectionConceptSet): boolean {
    const refs = set.artifact.parents
      .map((parent) => `${parent.ideaId}:${parent.ideaRevision}`)
      .sort()
      .join("|");
    return !set.stale && refs === parentKey;
  }

  function forgeError(cause: unknown, fallback: string): string {
    const message = cause instanceof Error ? cause.message.trim() : "";
    if (/candidate|shortlist|temporarily unavailable|evidence changed|could not be verified|price is not available/i.test(message)) {
      return message;
    }
    console.error("Shape request failed:", cause);
    return fallback;
  }

  async function loadSavedSet() {
    if (!hasExactParents) return;
    loading = true;
    loadFailed = false;
    error = "";
    try {
      const sets = await getSelectionConceptSets(jobId);
      conceptSet = sets.find(setMatchesParents) ?? null;
      if (conceptSet) {
        purpose = conceptSet.artifact.purpose;
        purposeTouched = true;
        targetTradeoff = conceptSet.artifact.targetTradeoff ?? "";
        tradeoffBaseline = targetTradeoff;
      }
    } catch (cause) {
      loadFailed = true;
      error = forgeError(cause, "Could not load saved concept directions. Please try again.");
    } finally {
      loading = false;
    }
  }

  async function generate() {
    if (!hasExactParents || generating || disabled) return;
    generating = true;
    error = "";
    actionMessage = "";
    try {
      const response = await createSelectionConceptSet(jobId, {
        purpose,
        parents: exactRefs(),
        ...(targetTradeoff.trim() ? { targetTradeoff: targetTradeoff.trim() } : {}),
      });
      conceptSet = response.set;
      // The note is now part of the persisted set: no longer at risk on close.
      tradeoffBaseline = targetTradeoff;
      const optionCount = response.set.artifact.options.length;
      generationAnnouncement = `${optionCount} concept direction${optionCount === 1 ? "" : "s"} ready.`;
      // The footer Submit button (focused when the click landed) unmounts as
      // showBrief flips: move focus to the new heading instead of losing it.
      await tick();
      optionsHeadingEl?.focus();
    } catch (cause) {
      error = forgeError(cause, "Could not prepare concept directions. Your shortlist is unchanged; please try again.");
    } finally {
      generating = false;
    }
  }

  async function resetQuestion() {
    conceptSet = null;
    actionMessage = "";
    error = "";
    await tick();
    briefHeadingEl?.focus();
  }

  async function evaluate(option: SelectionConceptOption) {
    if (!conceptSet || evaluatingOptionId || disabled || seedCost == null) return;
    evaluatingOptionId = option.optionId;
    actionMessage = "";
    error = "";
    try {
      const prepared = await prepareSelectionConceptOption(
        jobId,
        conceptSet.id,
        option.optionId,
        conceptSet.artifact.inputFingerprint,
      );
      const started = await onEvaluate(prepared.patch, prepared.sourceMessageId);
      if (started) {
        actionMessage = `Evaluation started for “${option.title}”. The source candidates and other directions remain unchanged.`;
      } else if (evaluateError) {
        // The owner page already handled the failure (409 PRICE_CHANGED
        // re-fetches the price into `seedCost`; 402 opens the top-up modal).
        // Surface its message inline so the explanation is not hidden behind
        // the overlay. The refreshed price shows on the Evaluate buttons.
        error = evaluateError;
      } else {
        actionMessage = "Evaluation did not start. Review the message on the selection page and try again.";
      }
    } catch (cause) {
      error = forgeError(cause, "Could not prepare this option for evaluation. Nothing was charged or changed.");
    } finally {
      evaluatingOptionId = null;
    }
  }

  const COUNT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];

  function countWord(count: number): string {
    return COUNT_WORDS[count] ?? String(count);
  }

  const operationLabel: Record<SelectionConceptOption["operation"], string> = {
    narrow: "Focused slice",
    reposition: "New position",
    combine: "Combined direction",
    adjacent: "Adjacent opportunity",
  };

  const methodLabel: Record<string, string> = {
    CUSTOMER_INTERVIEWS: "Customer interviews",
    SURVEY: "Survey",
    CTA_SMOKE_TEST: "CTA smoke test",
    BOOKED_CALL: "Booked-call test",
    PREORDER: "Preorder / deposit",
    CONCIERGE: "Concierge test",
    PROTOTYPE: "Prototype test",
    TECHNICAL_SPIKE: "Technical spike",
    OTHER: "Custom test",
  };
</script>

<FormOverlay
  {open}
  size="wizard"
  eyebrow={SHAPE_PANEL_EYEBROW}
  title={SHAPE_PANEL_TITLE}
  description="Deliberately different options branched from exact candidate revisions. Scores and conclusions never transfer."
  annotationAnchor={conceptForgeSurfaceKey}
  onRequestClose={onClose}
  dirty={forgeDirty}
  closeWarning="You have an unsent tension note. Close again to discard it."
  {footerMessage}
>
  <p class="sr-only" role="status">{generationAnnouncement}</p>

  <!-- Picked-parent chips: commit-bar chip recipe (accent border, ellipsized).
       With >2 parents the ChipGroup below stays the selection surface; these
       chips only reflect the picked state. -->
  {#if stableParents.length}
    <div class="parent-line" role="list" aria-label="Concept sources">
      {#each stableParents as parent}
        <span role="listitem">{solutionDisplayTitle(parent)} · rev {parent.idea_revision ?? 1}</span>
      {/each}
    </div>
  {/if}

  {#if !usesPicker && !hasExactParents}
    <div class="state state--error" role="alert">Select one or two current candidates with stable revisions.</div>
  {:else if loading}
    <div class="state" role="status"><Loader2 class="spin forge-spin" aria-hidden="true" /> Loading saved directions…</div>
  {:else if loadFailed}
    <div class="state state--error" role="alert">
      <p>{error}</p>
      <button type="button" class="ghost" onclick={() => void loadSavedSet()}>
        <RefreshCw aria-hidden="true" /> Try again
      </button>
    </div>
  {:else if !conceptSet}
    <section
      class="forge-brief"
      aria-labelledby="forge-brief-title"
      data-annotation-anchor={`selection:concept-forge:brief:${purpose}`}
    >
      <div class="brief-head-row">
        <div>
          <p class="section-label">Branching brief</p>
          <h3 id="forge-brief-title" tabindex="-1" bind:this={briefHeadingEl}>What should these options help you resolve?</h3>
        </div>
        <DecisionHelp title="How concept directions work" label="How directions work" position="bottom">
          {SHAPE_PANEL_INTRO}
        </DecisionHelp>
      </div>

      {#if usesPicker}
        <div class="field">
          <span class="field-label">Branch from <span class="opt">Pick up to 2</span></span>
          <p class="field-hint">Pick up to 2 ideas to branch from.</p>
          <ChipGroup
            label="Branch from, pick up to 2 ideas"
            options={pickerOptions}
            max={2}
            bind:values={selectedParentKeys}
          />
        </div>
      {/if}

      {#if prefill}
        <aside class="analyst-brief" aria-label="Analyst-prepared directions brief">
          <div><strong>Analyst brief</strong><span>Not generated</span></div>
          <p>{prefill.rationale}</p>
          {#if prefill.caveats.length}
            <ul>{#each prefill.caveats as caveat}<li>{caveat}</li>{/each}</ul>
          {/if}
        </aside>
      {/if}

      <div class="field">
        <span class="field-label" id="forge-purpose-label">Purpose of the branch</span>
        <SegmentControl
          density="card"
          label={SHAPE_PURPOSE_LABEL}
          labelledBy="forge-purpose-label"
          options={purposeOptions}
          value={purpose}
          onChange={(value) => {
            purpose = value as SelectionConceptPurpose;
            purposeTouched = true;
          }}
        />
      </div>

      <FormField
        id="forge-tradeoff"
        kind="textarea"
        label="Specific tension to explore"
        optional
        bind:value={targetTradeoff}
        maxlength={500}
        rows={3}
        placeholder={pickedCount === 2
          ? "For example: speed to launch versus a stronger competitive wedge"
          : "For example: keep the pain, but fit a solo founder’s first month"}
      />

      <p class="slow-note" role="status">{generateSlow ? STILL_GENERATING_NOTE : ""}</p>
    </section>
  {:else}
    {@const optionCount = conceptSet.artifact.options.length}
    <section
      class="option-section"
      aria-labelledby="forge-options-title"
      data-annotation-anchor="selection:concept-forge:options"
    >
      <div class="option-head">
        <div>
          <p class="section-label">{countWord(optionCount)} unevaluated {optionCount === 1 ? "option" : "options"}</p>
          <h3 id="forge-options-title" tabindex="-1" bind:this={optionsHeadingEl}>Compare what changes and what becomes newly uncertain</h3>
        </div>
        <button type="button" class="change-brief" disabled={evaluatingOptionId != null} onclick={() => void resetQuestion()}>
          <RefreshCw aria-hidden="true" /> Change the question
        </button>
      </div>

      {#if seedCost == null}
        <p class="price-note" role="status">
          An evaluation price is not available yet, so paid evaluation stays disabled. You can still compare every direction.
        </p>
      {/if}

      <div class="option-grid">
        {#each conceptSet.artifact.options as option (option.optionId)}
          {@const testedAssumption = option.assumptions.find((assumption) => assumption.assumptionId === option.suggestedTest.assumptionId)}
          <article class="option-card">
            <div class="option-kicker">
              <strong>{operationLabel[option.operation]}</strong>
            </div>
            <h4>{option.title}</h4>
            <p class="option-brief">{option.brief}</p>

            <dl class="axis-list">
              {#each option.changedAxes as change}
                <div>
                  <dt>{change.axis.replace("_", " ")}</dt>
                  <dd><span>{change.from}</span><ArrowRight aria-hidden="true" /><strong>{change.to}</strong></dd>
                </div>
              {/each}
            </dl>

            <div class="option-block">
              <span class="block-label">Decision-changing assumptions</span>
              <ul>
                {#each option.assumptions as assumption}
                  <li>
                    <strong>{assumption.type.replace("_", " ")}</strong>
                    <span>{assumption.statement}</span>
                  </li>
                {/each}
              </ul>
            </div>

            <details>
              <summary>Evidence transfer and disqualifiers</summary>
              <div class="evidence-columns">
                <div>
                  <strong>May still apply</strong>
                  <ul>{#each option.retainedEvidence as item}<li>{item}</li>{/each}</ul>
                </div>
                <div>
                  <strong>Must be re-checked</strong>
                  <ul>{#each option.evidenceToRecheck as item}<li>{item}</li>{/each}</ul>
                </div>
                <div>
                  <strong>Stop if</strong>
                  <ul>{#each option.disqualifiers as item}<li>{item}</li>{/each}</ul>
                </div>
              </div>
            </details>

            <div class="test-block">
              <span class="block-label">Cheapest useful test</span>
              <strong>{methodLabel[option.suggestedTest.method] ?? option.suggestedTest.method}</strong>
              <p>{option.suggestedTest.hypothesis}</p>
              {#if testedAssumption}<small>Tests: {testedAssumption.statement}</small>{/if}
              <dl>
                <div><dt>Pass</dt><dd>{option.suggestedTest.passThreshold}</dd></div>
                <div><dt>Fail</dt><dd>{option.suggestedTest.failThreshold}</dd></div>
              </dl>
            </div>

            <div class="evaluate-gate">
              <ConfirmGate
                variant="paid"
                label="Evaluate this option"
                confirmLabel="Confirm evaluation"
                costLine={costLine(seedCost)}
                busy={evaluatingOptionId === option.optionId}
                disabled={disabled || evaluatingOptionId != null || seedCost == null}
                onConfirm={() => void evaluate(option)}
              />
            </div>
          </article>
        {/each}
      </div>
    </section>
  {/if}

  {#if error && !loadFailed}<p class="feedback feedback--error" role="alert">{error}</p>{/if}
  <p class="feedback" class:is-empty={!actionMessage} role="status">{actionMessage}</p>

  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={generating || evaluatingOptionId != null} onclick={onClose}>Close</button>
  {/snippet}
  {#snippet footer()}
    {#if showBrief}
      <SubmitButton
        type="button"
        label={GENERATE_DIRECTIONS_LABEL}
        loadingText={GENERATING_DIRECTIONS_LABEL}
        loading={generating}
        disabled={disabled || !hasExactParents}
        icon={ArrowRight}
        iconPosition="end"
        onclick={() => void generate()}
        class="submit-btn"
      />
    {/if}
  {/snippet}
</FormOverlay>

<style>
  .section-label {
    margin: 0 0 0.35rem;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  h3, h4, p { margin: 0; }

  /* Picked-parent chips: commit-bar chip recipe. */
  .parent-line { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .parent-line span {
    display: inline-block;
    max-width: 14rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 600;
  }

  .state {
    display: flex;
    min-height: 9rem;
    max-width: 34rem;
    margin: 1.5rem auto;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    color: var(--color-text-secondary);
    text-align: center;
  }
  .state p { max-width: 52ch; line-height: 1.5; }
  .state--error, .feedback--error { color: var(--color-error-text); }

  .forge-brief { display: grid; gap: 1.3rem; max-width: 52rem; }
  .brief-head-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
  .forge-brief h3, .option-head h3 { font-size: var(--text-md); line-height: 1.3; }

  .field { display: grid; gap: 0.4rem; }
  .field-label {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    font-size: var(--text-13);
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .field-label .opt { font-size: var(--text-11); font-weight: 500; color: var(--color-text-secondary); }
  .field-hint { margin: -0.1rem 0 0; font-size: var(--text-sm); line-height: 1.45; color: var(--color-text-muted); }

  /* Analyst brief: plain bordered card (no accent stripe, no phantom token). */
  .analyst-brief {
    display: grid;
    gap: 0.45rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }
  .analyst-brief > div { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
  .analyst-brief strong { font-size: var(--text-13); font-weight: 600; }
  .analyst-brief span {
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .analyst-brief p, .analyst-brief li { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.5; }
  .analyst-brief ul { margin: 0; padding-left: 1rem; }

  .slow-note { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.4; }

  /* Ghost button (retry / secondary). */
  .ghost {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-height: 2.1rem;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }
  .ghost:hover { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .ghost:active { transform: scale(0.98); }
  .ghost :global(svg) { width: 0.9rem; height: 0.9rem; }

  .cancel-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.4rem;
    padding: 0.5rem 0.9rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }
  .cancel-btn:hover { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .cancel-btn:active:not(:disabled) { transform: scale(0.98); }

  /* ── Options view ── */
  .option-head { display: flex; align-items: end; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
  .change-brief {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2.1rem;
    border: 0;
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }
  .change-brief:hover:not(:disabled) { color: var(--color-text-primary); }
  .change-brief:active:not(:disabled) { transform: scale(0.98); }
  .change-brief:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); cursor: not-allowed; }
  .change-brief :global(svg) { width: 0.85rem; height: 0.85rem; }

  /* Price note: plain bordered card (no warning stripe, no phantom token). */
  .price-note {
    margin: -0.35rem 0 1rem;
    padding: 0.7rem 0.8rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.45;
  }

  .option-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-lg); overflow: hidden; }
  .option-card { display: flex; flex-direction: column; min-width: 0; padding: 1rem; border-right: 1px solid var(--color-border); background: var(--color-bg-surface); }
  .option-card:last-child { border-right: 0; }
  .option-kicker { color: var(--color-accent-dark); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
  .option-card h4 { margin-top: 0.65rem; font-size: var(--text-md); line-height: 1.25; }
  .option-brief { min-height: 4.5rem; margin-top: 0.4rem; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.5; }
  .axis-list { margin: 0.8rem 0 0; padding: 0.7rem 0; border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
  .axis-list > div + div { margin-top: 0.5rem; }
  .axis-list dt, .test-block dt { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); text-transform: uppercase; }
  .axis-list dd { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 0.3rem; margin: 0.2rem 0 0; font-size: var(--text-xs); line-height: 1.35; }
  .axis-list dd span { color: var(--color-text-secondary); text-decoration: line-through; }
  .axis-list dd :global(svg) { width: 0.7rem; height: 0.7rem; color: var(--color-text-muted); }
  .option-block, .test-block { margin-top: 0.8rem; }
  .block-label { display: block; margin-bottom: 0.35rem; color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
  ul { margin: 0; padding-left: 1rem; }
  li { color: var(--color-text-secondary); font-size: var(--text-xs); line-height: 1.45; }
  .option-block li { margin-bottom: 0.4rem; }
  .option-block li strong { display: block; color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); text-transform: uppercase; }
  details { margin-top: 0.75rem; border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
  summary { padding: 0.65rem 0; color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 700; cursor: pointer; }
  summary:active { transform: scale(0.98); }
  .evidence-columns { display: grid; gap: 0.65rem; padding: 0 0 0.75rem; }
  .evidence-columns strong { display: block; margin-bottom: 0.2rem; font-size: var(--text-xs); }
  .test-block { padding: 0.75rem; border-radius: var(--radius-md); background: var(--color-bg-subtle); }
  .test-block > strong { font-size: var(--text-sm); }
  .test-block > p { margin-top: 0.25rem; font-size: var(--text-xs); line-height: 1.45; }
  .test-block > small { display: block; margin-top: 0.3rem; color: var(--color-text-secondary); font-size: var(--text-xs); line-height: 1.4; }
  .test-block dl { display: grid; gap: 0.35rem; margin: 0.6rem 0 0; }
  .test-block dl > div { display: grid; grid-template-columns: 2.5rem 1fr; gap: 0.3rem; }
  .test-block dd { margin: 0; color: var(--color-text-secondary); font-size: var(--text-xs); line-height: 1.35; }

  /* Evaluate: shared paid ConfirmGate, stretched to the card's full width. */
  .evaluate-gate { margin-top: 0.9rem; }
  .evaluate-gate :global(.gate-trigger) { width: 100%; min-width: 0; }
  .evaluate-gate :global(.confirm-gate) { width: 100%; }
  .evaluate-gate :global(.gate-cancel),
  .evaluate-gate :global(.gate-confirm) { flex: 1; min-width: 0; }

  .feedback { margin: 0.85rem 0 0; padding: 0.65rem 0.75rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-subtle); color: var(--color-text-secondary); font-size: var(--text-sm); }
  .feedback.is-empty { margin: 0; padding: 0; border: 0; background: none; }

  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }

  :global(.forge-spin) { animation: forge-spin 800ms linear infinite; }
  @keyframes forge-spin { to { transform: rotate(360deg); } }
  button:focus-visible, summary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  #forge-brief-title:focus, #forge-options-title:focus { outline: 2px solid var(--color-accent); outline-offset: 3px; border-radius: var(--radius-sm); }

  @media (max-width: 900px) {
    .option-grid { grid-template-columns: 1fr; }
    .option-card { border-right: 0; border-bottom: 1px solid var(--color-border); }
    .option-card:last-child { border-bottom: 0; }
    .option-brief { min-height: 0; }
  }
  @media (max-width: 640px) {
    .brief-head-row { flex-direction: column; }
    .option-head { align-items: stretch; flex-direction: column; }
  }

  @media (prefers-reduced-motion: reduce) {
    .ghost:active,
    .cancel-btn:active:not(:disabled),
    .change-brief:active:not(:disabled),
    summary:active {
      transform: none;
    }
  }
</style>
