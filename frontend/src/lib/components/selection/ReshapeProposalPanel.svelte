<script lang="ts">
  import { Check, Loader2, Wand2 } from "lucide-svelte";
  import type {
    ExperimentNarrowingProposalResponse,
    IdeaSynthesisPatch,
    SeedResultSummary,
  } from "$lib/api";
  import type { FounderFitArtifact, FounderFitResult } from "$lib/types/founderFit";
  import type { SolutionPreview } from "$lib/types/job";
  import type { SelectionExperiment } from "$lib/types/selectionExperiment";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import ConfirmGate from "$lib/components/ui/ConfirmGate.svelte";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import { EVALUATED_ACCEPTED_LABEL, EVALUATED_DEMOTED_LABEL } from "$lib/selection/labels";

  /** Discriminated origin: founder-fit reshape vs experiment-conclusion narrowing.
   *  Both variants render one unevaluated child from an exact parent revision. */
  export type ReshapeSource =
    | {
        kind: "founderFit";
        idea: SolutionPreview;
        artifact: FounderFitArtifact;
        result: FounderFitResult;
      }
    | { kind: "experiment"; experiment: SelectionExperiment };

  type ProposalResponse = ExperimentNarrowingProposalResponse;

  interface Props {
    source: ReshapeSource;
    seedCost: number | null;
    disabled?: boolean;
    /** Injected origin-specific API calls (identity args captured by the caller). */
    createProposal: () => Promise<ProposalResponse>;
    fetchProposal: () => Promise<ProposalResponse>;
    onEvaluate: (patch: IdeaSynthesisPatch, sourceMessageId: string) => Promise<boolean>;
    onReview?: (
      patch: IdeaSynthesisPatch,
      child: SeedResultSummary,
      sourceMessageId: string,
    ) => { ok: boolean; message?: string };
    onUse?: (
      patch: IdeaSynthesisPatch,
      child: SeedResultSummary,
      sourceMessageId: string,
    ) => { ok: boolean; message?: string };
  }

  let {
    source,
    seedCost,
    disabled = false,
    createProposal,
    fetchProposal,
    onEvaluate,
    onReview,
    onUse,
  }: Props = $props();

  let open = $state(false);
  let loading = $state(false);
  let evaluating = $state(false);
  let response = $state<ProposalResponse | null>(null);
  let error = $state("");
  let actionMessage = $state("");
  let actionFailed = $state(false);
  let pollFailed = $state(false);
  let lastCheckedAt = $state<number | null>(null);

  const proposal = $derived(response?.proposalMessage ?? null);
  const settlement = $derived(response?.settlement ?? null);

  function snapshotText(experiment: SelectionExperiment, key: string): string {
    const value = experiment.ideaSnapshot[key];
    return typeof value === "string" ? value.trim() : "";
  }

  /** Exact-parent identity used to validate the accepted child links to this origin. */
  const identity = $derived(
    source.kind === "founderFit"
      ? { ideaId: source.result.ideaId, ideaRevision: source.result.ideaRevision }
      : { ideaId: source.experiment.ideaId, ideaRevision: source.experiment.ideaRevision },
  );

  /** Per-origin copy and provenance. */
  const config = $derived.by(() => {
    if (source.kind === "founderFit") {
      return {
        triggerLabel: "Reshape to fit",
        eyebrow: "Constraint-led variant",
        title: "Make the product shape smaller, not the evidence stronger",
        description: "The parent, score, and founder-fit finding stay unchanged.",
        annotationAnchor: `selection:founder-fit-reshape:${source.result.ideaId}:${source.result.ideaRevision}`,
        helpTitle: "Before you evaluate",
        helpBody:
          "Turn the recorded conflict into one smaller variant, scored from scratch as its own idea. Review the recheck list first: those items are the child’s fresh burden of proof; parent evidence stays with the parent. Clear the market-fit bar and the variant joins your ranked ideas.",
        loadingText: "Preparing one smaller variant…",
        createError: "Could not prepare a constraint-led variant.",
        beforeLabel: "Before · parent",
        retainedLabel: "What remains useful",
        scopeNote:
          "Designed around your constraint, not proven to fit it. Parent evidence and scores do not transfer automatically.",
        footNote: "Review the exact change and recheck list before evaluation.",
        reviewFailMessage:
          "The exact revisions are no longer available. Refresh and try again.",
      };
    }
    return {
      triggerLabel: "Narrow this idea",
      eyebrow: "Narrowed variant",
      title: "Turn this result into one sharper candidate",
      description: "This creates a new candidate. The parent and its conclusion stay unchanged.",
      annotationAnchor: `selection:experiment:${source.experiment.id}:narrowing`,
      helpTitle: "Vet what the child inherits",
      helpBody:
        "Check the ledger before you spend credits: the child keeps only the parent contribution named there, and every new assumption lands on the recheck list. Evaluation then scores the variant from scratch, so its rank reflects the narrower idea itself: earned, not borrowed.",
      loadingText: "Preparing one evidence-grounded variant…",
      createError: "Could not prepare a narrowed variant.",
      beforeLabel: `Before · parent rev ${source.experiment.ideaRevision}`,
      retainedLabel: "Evidence retained",
      scopeNote:
        "The source idea keeps its history. Its conclusion and scores do not transfer to this child.",
      footNote: "Review the exact change and recheck list before evaluation.",
      reviewFailMessage:
        "The current idea revisions are not available. Refresh and try again.",
    };
  });

  /** Founder-fit only: the recorded conflicts surfaced above the comparison. */
  const conflicts = $derived(
    source.kind === "founderFit"
      ? source.result.dimensions.filter((dimension) => dimension.status === "conflict")
      : [],
  );

  const parentTitle = $derived.by(() => {
    if (source.kind === "founderFit") return solutionDisplayTitle(source.idea);
    return snapshotText(source.experiment, "solution_name") || source.experiment.ideaId;
  });

  const parentBrief = $derived.by(() => {
    if (source.kind === "founderFit") {
      const idea = source.idea;
      return (
        idea.short_description?.trim() ||
        idea.description?.trim() ||
        idea.value_proposition?.trim() ||
        "The exact candidate revision from this comparison."
      );
    }
    return (
      snapshotText(source.experiment, "value_proposition") ||
      snapshotText(source.experiment, "headline") ||
      "The exact parent snapshot attached to this experiment."
    );
  });

  const acceptedChild = $derived.by(() => {
    const child = settlement?.state === "accepted" ? settlement.idea : null;
    if (
      !proposal ||
      !child?.idea_id ||
      !child.idea_revision ||
      child.synthesis_operation !== "narrow" ||
      child.synthesis_source_message_id !== proposal.id
    )
      return null;
    const exactParent = child.synthesized_from?.some(
      (parent) =>
        parent.idea_id === identity.ideaId && parent.idea_revision === identity.ideaRevision,
    );
    return exactParent ? child : null;
  });

  const costLine = $derived(
    seedCost != null ? `${seedCost} credit${seedCost === 1 ? "" : "s"}` : undefined,
  );

  $effect(() => {
    if (response?.settlement?.state !== "pending") return;
    const timer = window.setInterval(() => void refresh(), 6000);
    return () => window.clearInterval(timer);
  });

  async function reveal() {
    open = true;
    if (response?.proposalMessage || loading) return;
    loading = true;
    error = "";
    try {
      response = await createProposal();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : config.createError;
    } finally {
      loading = false;
    }
  }

  async function refresh() {
    try {
      const latest = await fetchProposal();
      if (latest.proposalMessage) response = latest;
      pollFailed = false;
      lastCheckedAt = Date.now();
    } catch {
      // Polling is only a backstop; the saved proposal is restored on the next open.
      pollFailed = true;
    }
  }

  async function evaluate() {
    if (evaluating) return;
    if (!proposal || seedCost == null || disabled) return;
    if (settlement?.state !== "ready" && settlement?.state !== "failed" && settlement?.state !== "refunded") return;
    evaluating = true;
    error = "";
    try {
      const accepted = await onEvaluate(proposal.patchJson, proposal.id);
      if (accepted) {
        response = { ...response!, settlement: { state: "pending", idea: null } };
      }
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not submit the variant for evaluation.";
    } finally {
      evaluating = false;
    }
  }

  function runAcceptedAction(kind: "review" | "use") {
    if (!proposal || !acceptedChild) return;
    const action = kind === "review" ? onReview : onUse;
    if (!action) return;
    const outcome = action(proposal.patchJson, acceptedChild, proposal.id);
    actionFailed = !outcome.ok;
    actionMessage =
      outcome.message ??
      (outcome.ok
        ? kind === "review"
          ? "Comparison opened."
          : "Variant is now in your shortlist."
        : config.reviewFailMessage);
    if (kind === "review" && outcome.ok) {
      open = false;
      error = "";
    }
  }

  function requestClose() {
    if (loading || evaluating) return;
    open = false;
    error = "";
  }
</script>

<div class="reshape-entry">
  <button type="button" class="reshape-trigger" {disabled} onclick={() => void reveal()}>
    <Wand2 aria-hidden="true" /> {config.triggerLabel}
  </button>
</div>

<FormOverlay
  {open}
  size="wizard"
  eyebrow={config.eyebrow}
  title={config.title}
  description={config.description}
  annotationAnchor={config.annotationAnchor}
  onRequestClose={requestClose}
>
  <section class="reshape-sheet" aria-label={config.eyebrow} aria-busy={loading || evaluating}>
    <DecisionHelp title={config.helpTitle} label="Variant scope">
      {config.helpBody}
    </DecisionHelp>

    {#if loading}
      <p class="status" aria-live="polite"><Loader2 class="spin reshape-spin" aria-hidden="true" /> {config.loadingText}</p>
    {:else if error && !proposal}
      <p class="error" role="alert">{error}</p>
    {:else if proposal && settlement}
      {@const patch = proposal.patchJson}
      {#if source.kind === "founderFit"}
        <dl class="origin">
          <div>
            <dt>Constraint addressed</dt>
            <dd>{conflicts.map((conflict) => conflict.summary).join(" ")}</dd>
          </div>
          <div>
            <dt>Frozen from</dt>
            <dd>Founder fit · {source.artifact.inputFingerprint.slice(0, 10)} · parent rev {source.result.ideaRevision}</dd>
          </div>
        </dl>
      {/if}

      <div class="comparison" aria-label="Parent and proposed child comparison">
        <article>
          <span>{config.beforeLabel}</span>
          <strong>{parentTitle}</strong>
          <p>{parentBrief}</p>
        </article>
        <article class="after">
          <span>After · unevaluated child</span>
          <strong>{patch.proposedTitle}</strong>
          <p>{patch.proposedBrief}</p>
        </article>
      </div>

      <dl class="ledger">
        <div><dt>What changes</dt><dd>{patch.changeSummary}</dd></div>
        <div><dt>{config.retainedLabel}</dt><dd>{patch.parents[0]?.contribution}</dd></div>
        <div>
          <dt>Must be rechecked</dt>
          <dd><ul>{#each patch.evidence.requiresValidation as item}<li>{item}</li>{/each}</ul></dd>
        </div>
      </dl>
      <p class="scope">{config.scopeNote}</p>

      {#if settlement.state === "accepted"}
        <p class="receipt accepted" aria-live="polite">
          <Check aria-hidden="true" />
          <span><strong>{EVALUATED_ACCEPTED_LABEL}</strong>{settlement.idea?.solution_name ?? patch.proposedTitle}</span>
        </p>
        {#if actionMessage}<p class:error={actionFailed} class="action-message" role={actionFailed ? "alert" : "status"}>{actionMessage}</p>{/if}
      {:else if settlement.state === "demoted"}
        <p class="receipt" aria-live="polite"><strong>{EVALUATED_DEMOTED_LABEL}</strong></p>
      {:else if settlement.state === "pending"}
        <p class="receipt" aria-live="polite"><Loader2 class="spin reshape-spin" aria-hidden="true" /><strong>Evaluating independently…</strong></p>
        {#if pollFailed}<p class="poll-hint" role="status">Could not refresh the latest status{lastCheckedAt ? ` · last confirmed ${new Date(lastCheckedAt).toLocaleTimeString()}` : ""}. Still retrying.</p>{/if}
      {:else if settlement.state === "failed" || settlement.state === "refunded"}
        <p class="receipt error" role="alert"><strong>Evaluation failed. Any charged credits were refunded. Retry below.</strong></p>
      {/if}
      {#if error}<p class="error" role="alert">{error}</p>{/if}
    {/if}
  </section>

  {#snippet footer()}
    <div class="reshape-footer">
      {#if error && !proposal}
        <button type="button" class="btn-ghost" onclick={requestClose}>Close</button>
        <span class="foot-spacer"></span>
        <button type="button" class="btn-ghost" onclick={() => { response = null; void reveal(); }}>Try again</button>
      {:else if settlement?.state === "accepted" && acceptedChild && (onReview || onUse)}
        <button type="button" class="btn-ghost" onclick={requestClose}>Close</button>
        <span class="foot-spacer"></span>
        {#if onReview}<button type="button" class="btn-ghost" onclick={() => runAcceptedAction("review")}>Compare with parent</button>{/if}
        {#if onUse}
          <SubmitButton
            type="button"
            class="btn-primary"
            minWidth="12rem"
            label="Use variant in shortlist"
            loadingText=""
            onclick={() => runAcceptedAction("use")}
          />
        {/if}
      {:else if settlement?.state === "ready"}
        <button type="button" class="btn-ghost" disabled={evaluating} onclick={requestClose}>Close</button>
        <p class="foot-msg">{seedCost == null ? "The evaluation price has not loaded yet." : config.footNote}</p>
        <ConfirmGate
          label="Evaluate variant"
          confirmLabel="Confirm independent evaluation"
          variant="paid"
          {costLine}
          onConfirm={() => void evaluate()}
          busy={evaluating}
          disabled={disabled || seedCost == null}
        />
      {:else if settlement?.state === "failed" || settlement?.state === "refunded"}
        <button type="button" class="btn-ghost" disabled={evaluating} onclick={requestClose}>Close</button>
        <p class="foot-msg">{seedCost == null ? "The evaluation price has not loaded yet." : "Credits were refunded. Retry when you're ready."}</p>
        <ConfirmGate
          label="Retry evaluation"
          confirmLabel="Confirm independent evaluation"
          variant="paid"
          {costLine}
          onConfirm={() => void evaluate()}
          busy={evaluating}
          disabled={disabled || seedCost == null}
        />
      {:else}
        <button type="button" class="btn-ghost" disabled={loading || evaluating} onclick={requestClose}>Close</button>
      {/if}
    </div>
  {/snippet}
</FormOverlay>

<style>
  .reshape-entry {
    margin-top: 0.9rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--color-border);
  }

  .reshape-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    min-height: 2.4rem;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent-dark);
    font-weight: 700;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default);
  }

  .reshape-trigger:hover:not(:disabled) {
    color: var(--color-accent-hover);
    text-decoration: underline;
  }

  .reshape-trigger:active:not(:disabled) {
    transform: scale(0.98);
  }

  .reshape-trigger:disabled {
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  .reshape-trigger :global(svg),
  .receipt :global(svg),
  .status :global(svg) {
    width: 1rem;
    height: 1rem;
    flex: 0 0 auto;
  }

  .reshape-trigger:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .reshape-sheet {
    padding: 0;
  }

  .origin,
  .ledger {
    margin: 0;
  }

  .origin {
    display: grid;
    gap: 0.65rem;
    padding: 0.75rem 0;
    border-block: 1px solid var(--color-border);
  }

  .comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    border-bottom: 1px solid var(--color-border);
  }

  .comparison article {
    min-width: 0;
    padding: 0.8rem 0.8rem 0.8rem 0;
  }

  .comparison .after {
    padding-inline: 0.8rem 0;
    border-left: 1px solid var(--color-border);
  }

  .comparison span,
  dt {
    display: block;
    margin-bottom: 0.25rem;
    color: var(--color-text-secondary);
    font-size: var(--text-11);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .comparison strong {
    display: block;
    font-size: var(--text-sm);
  }

  .comparison p,
  dd {
    margin: 0.25rem 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.5;
  }

  .ledger > div {
    padding: 0.7rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  ul {
    margin: 0.3rem 0 0;
    padding-left: 1rem;
  }

  li + li {
    margin-top: 0.25rem;
  }

  .scope,
  .action-message {
    margin: 0.65rem 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .reshape-footer {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
  }

  .foot-spacer {
    flex: 1;
  }

  .foot-msg {
    flex: 1;
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.45;
  }

  .btn-ghost {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.1rem;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .btn-ghost:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .btn-ghost:active:not(:disabled) {
    transform: scale(0.98);
  }

  .btn-ghost:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .btn-ghost:disabled {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  .receipt,
  .status {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    margin: 0.8rem 0 0;
    padding: 0.7rem;
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    font-size: var(--text-13);
  }

  .receipt span {
    display: grid;
    gap: 0.15rem;
  }

  .receipt.accepted {
    color: var(--color-success-text);
  }

  .poll-hint {
    margin: 0.5rem 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-11);
    line-height: 1.45;
  }

  .error {
    color: var(--color-error-text);
  }

  :global(.reshape-spin) {
    animation: reshape-spin 900ms linear infinite;
  }

  @keyframes reshape-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 760px) {
    .comparison {
      display: block;
    }

    .comparison .after {
      border-left: 0;
      border-top: 1px solid var(--color-border);
      padding-left: 0;
    }

    .reshape-footer {
      flex-wrap: wrap;
    }

    .foot-msg {
      flex-basis: 100%;
      order: -1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .reshape-trigger:active:not(:disabled),
    .btn-ghost:active:not(:disabled) {
      transform: none;
    }
  }

</style>
