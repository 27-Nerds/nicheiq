<script lang="ts">
  import { onMount } from "svelte";
  import {
    AlertCircle,
    Check,
    Clipboard,
    Download,
    FileJson,
    Loader2,
    RefreshCw,
  } from "lucide-svelte";
  import {
    getDecisionHandoff,
    materializeDecisionHandoff,
  } from "$lib/api";
  import GithubDispatchPanel from "./GithubDispatchPanel.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type { SelectionFinalDecision } from "$lib/types/finalDecision";
  import type {
    DecisionHandoffAction,
    SelectionDecisionHandoff,
  } from "$lib/types/decisionHandoff";

  interface Props {
    jobId: string;
    decision: SelectionFinalDecision;
    focusOnMount?: boolean;
  }

  let { jobId, decision, focusOnMount = false }: Props = $props();

  let handoff = $state<SelectionDecisionHandoff | null>(null);
  let loading = $state(true);
  let creating = $state(false);
  let error = $state("");
  let copyStatus = $state("");
  let headingEl = $state<HTMLHeadingElement>();

  const BRIEFS: Record<DecisionHandoffAction, {
    title: string;
    description: string;
  }> = {
    BUILD: {
      title: "Implementation brief",
      description: "Recorded inputs for implementation planning.",
    },
    VALIDATE_MORE: {
      title: "Test handoff",
      description: "Frozen owner decision and selected locked test brief.",
    },
    PARK: {
      title: "Parking note",
      description: "A durable record of why this path is paused.",
    },
    STOP: {
      title: "Stop record",
      description: "A durable record of why this researched path ended.",
    },
  };

  const CREATE_LABELS: Record<SelectionFinalDecision["disposition"], string> = {
    PROCEED: "Create implementation brief",
    TEST_FIRST: "Create test handoff",
    PARK: "Create parking note",
    STOP: "Create stop record",
  };

  const brief = $derived(handoff ? BRIEFS[handoff.action] : null);
  const selectedTestBrief = $derived(
    handoff?.artifact.testBrief ?? null,
  );
  const conclusions = $derived.by(() => {
    const value = handoff?.artifact.evidence.evidenceSnapshot.experimentConclusions;
    return Array.isArray(value) ? value : [];
  });

  function displayDate(value: string): string {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
  }

  function readableEnum(value: string): string {
    return value.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
  }

  function focusHeading(): void {
    requestAnimationFrame(() => {
      headingEl?.focus();
      const reduced = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      headingEl?.scrollIntoView?.({
        behavior: reduced ? "auto" : "smooth",
        block: "center",
      });
    });
  }

  async function load(): Promise<void> {
    loading = true;
    error = "";
    try {
      const response = await getDecisionHandoff(jobId);
      handoff = response.handoff;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not load the decision handoff.";
    } finally {
      loading = false;
    }
  }

  async function create(): Promise<void> {
    creating = true;
    error = "";
    try {
      handoff = await materializeDecisionHandoff(jobId, decision.id);
      focusHeading();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not create the decision handoff.";
    } finally {
      creating = false;
    }
  }

  async function copyMarkdown(): Promise<void> {
    copyStatus = "";
    try {
      const response = await fetch(`/api/jobs/${jobId}/decision-handoff/export/md`);
      if (!response.ok) throw new Error("Could not prepare the Markdown brief.");
      await navigator.clipboard.writeText(await response.text());
      copyStatus = "Markdown copied";
    } catch (cause) {
      copyStatus = cause instanceof Error ? cause.message : "Could not copy the brief.";
    }
  }

  onMount(() => {
    void load().then(() => {
      if (focusOnMount) focusHeading();
    });
  });
</script>

<div class="handoff-row" aria-busy={loading || creating}>
  <h3>Next-step handoff</h3>
  <div class="handoff-content">
    {#if loading}
      <p class="handoff-state"><Loader2 class="handoff-spin" size={16} /> Loading handoff…</p>
    {:else if error && !handoff}
      <div class="handoff-state handoff-error" role="alert">
        <AlertCircle size={17} />
        <span>{error}</span>
        <button type="button" class="text-action" onclick={load}>
          <RefreshCw size={14} /> Retry
        </button>
      </div>
    {:else if !handoff}
      <h4 bind:this={headingEl} id="decision-handoff-heading" tabindex="-1">
        Prepare the next-step record
      </h4>
      <p class="handoff-intro">
        Create a deterministic brief from this read-only owner decision. No new research
        or generated implementation tasks will be added.
      </p>
      <SubmitButton
        type="button"
        class=""
        loading={creating}
        loadingText="Creating…"
        label={CREATE_LABELS[decision.disposition]}
        onclick={create}
      />
    {:else if brief}
      <div class="handoff-heading">
        <div>
          <h4 bind:this={headingEl} id="decision-handoff-heading" tabindex="-1">{brief.title}</h4>
          <p>{brief.description}</p>
        </div>
        <span class="immutable-mark"><Check size={14} /> Frozen</span>
      </div>

      <dl>
        {#if handoff.artifact.target}
          <div>
            <dt>Exact target</dt>
            <dd>
              <strong>{handoff.artifact.target.title ?? "Untitled idea"}</strong>
              <span>{handoff.artifact.target.ideaId} · revision {handoff.artifact.target.ideaRevision}</span>
            </dd>
          </div>
        {/if}
        {#if selectedTestBrief}
          <div>
            <dt>Selected test brief</dt>
            <dd>
              <strong>{selectedTestBrief.assumption.statement}</strong>
              <span>{readableEnum(selectedTestBrief.assumption.type)}</span>
            </dd>
          </div>
          <div>
            <dt>Method and signal</dt>
            <dd>{readableEnum(selectedTestBrief.testDesign.method)} · {readableEnum(selectedTestBrief.testDesign.evidenceSignal)}</dd>
          </div>
          <div>
            <dt>Pass / fail rules</dt>
            <dd>
              <strong>Pass:</strong> {selectedTestBrief.testDesign.passThreshold}<br />
              <strong>Fail:</strong> {selectedTestBrief.testDesign.failThreshold}
            </dd>
          </div>
          <div><dt>Stopping rule</dt><dd>{selectedTestBrief.testDesign.measurementWindow}</dd></div>
          <div>
            <dt>Run state at decision</dt>
            <dd>{selectedTestBrief.runStatusAtDecision ? readableEnum(selectedTestBrief.runStatusAtDecision) : "Ready to run"}</dd>
          </div>
        {:else if handoff.action === "VALIDATE_MORE"}
          <div><dt>Selected test brief</dt><dd>Legacy decision · no locked test brief was recorded.</dd></div>
        {/if}
        <div><dt>Why now</dt><dd>{handoff.artifact.decision.rationale}</dd></div>
        {#if handoff.artifact.decision.acceptedRisks}
          <div><dt>Accepted or open risks</dt><dd>{handoff.artifact.decision.acceptedRisks}</dd></div>
        {/if}
        <div><dt>Change or stop if</dt><dd>{handoff.artifact.decision.changeCriterion}</dd></div>
        <div>
          <dt>Concluded evidence</dt>
          <dd>
            {#if conclusions.length}
              {conclusions.length} immutable test conclusion{conclusions.length === 1 ? "" : "s"} attached
            {:else}
              No test conclusion was recorded with this decision.
            {/if}
          </dd>
        </div>
        <div><dt>Recorded</dt><dd>{displayDate(handoff.createdAt)}</dd></div>
      </dl>

      <div class="handoff-actions">
        <button type="button" class="secondary-action" onclick={copyMarkdown}>
          <Clipboard size={15} /> Copy Markdown
        </button>
        <a href={`/api/jobs/${jobId}/decision-handoff/export/md`}>
          <Download size={15} /> Download .md
        </a>
        <a href={`/api/jobs/${jobId}/decision-handoff/export/json`}>
          <FileJson size={15} /> Download JSON
        </a>
      </div>
      <p class="handoff-note">
        This handoff preserves the owner's next move and does not claim validation.
        Creating external work requires a separate destination review and confirmation.
      </p>
      {#if handoff.artifact.executionPolicy.providerDispatchAllowed}
        <GithubDispatchPanel {jobId} />
      {/if}
      <span class="copy-status" role="status" aria-live="polite">{copyStatus}</span>
    {/if}
  </div>
</div>

<style>
  .handoff-row {
    display: grid;
    grid-template-columns: minmax(10rem, 3fr) minmax(0, 9fr);
    gap: 2rem;
    padding: 1.6rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  .handoff-row > h3 {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .handoff-content {
    min-width: 0;
  }

  h4 {
    margin: 0;
    font-size: 1.2rem;
    line-height: 1.25;
    letter-spacing: -0.015em;
  }

  h4:focus {
    outline: none;
  }

  .handoff-intro,
  .handoff-heading p,
  .handoff-note {
    color: var(--color-text-muted);
    font-size: var(--text-base);
    line-height: 1.5;
  }

  .handoff-intro {
    max-width: 62ch;
    margin: 0.55rem 0 1rem;
  }

  .handoff-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .handoff-heading p {
    margin: 0.35rem 0 0;
  }

  .immutable-mark {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    white-space: nowrap;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    font-weight: 600;
  }

  dl {
    margin: 1rem 0 0;
  }

  dl div {
    display: grid;
    grid-template-columns: minmax(9rem, 1fr) minmax(0, 3fr);
    gap: 1rem;
    padding: 0.75rem 0;
    border-top: 1px solid var(--color-border);
  }

  dt {
    color: var(--color-text-muted);
    font-size: var(--text-13);
    font-weight: 600;
  }

  dd {
    margin: 0;
  }

  dd span {
    display: block;
    margin-top: 0.18rem;
    color: var(--color-text-muted);
    font-size: var(--text-13);
    overflow-wrap: anywhere;
  }

  .secondary-action,
  .text-action,
  a {
    display: inline-flex;
    min-height: 2.4rem;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    padding: 0.5rem 0.85rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .secondary-action:hover,
  .text-action:hover,
  a:hover {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .secondary-action:active:not(:disabled),
  .text-action:active:not(:disabled),
  a:active {
    transform: scale(0.98);
  }

  .secondary-action:focus-visible,
  .text-action:focus-visible,
  a:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .secondary-action:disabled,
  .text-action:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .handoff-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin-top: 1rem;
  }

  .handoff-note {
    margin: 0.8rem 0 0;
  }

  .handoff-state {
    display: flex;
    min-height: 3rem;
    align-items: center;
    gap: 0.5rem;
    margin: 0;
    color: var(--color-text-muted);
  }

  .handoff-error {
    color: var(--color-error-text);
  }

  .handoff-error .text-action {
    margin-left: auto;
  }

  .copy-status {
    display: block;
    min-height: 1.2rem;
    margin-top: 0.4rem;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
  }

  :global(.handoff-spin) {
    animation: handoff-spin 800ms linear infinite;
  }

  @keyframes handoff-spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 720px) {
    .handoff-row {
      display: block;
      padding: 1.3rem 0;
    }

    .handoff-row > h3 {
      margin-bottom: 0.85rem;
    }

    .handoff-heading {
      display: block;
    }

    .immutable-mark {
      margin-top: 0.75rem;
    }

    dl div {
      display: block;
    }

    dt {
      display: block;
      margin-bottom: 0.3rem;
    }

    .handoff-actions {
      align-items: stretch;
      flex-direction: column;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .secondary-action:active:not(:disabled),
    .text-action:active:not(:disabled),
    a:active {
      transform: none;
    }
  }
</style>
