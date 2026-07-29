<script lang="ts">
  import { AlertCircle, ArrowLeft, Check, RefreshCw } from "lucide-svelte";
  import { ApiError, getFinalDecision, recordFinalDecision } from "$lib/api";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import DecisionHandoffPanel from "./DecisionHandoffPanel.svelte";
  import type {
    FinalDecisionDisposition,
    FinalDecisionInput,
    FinalDecisionLoadResponse,
    FinalDecisionLockedTestBrief,
    FinalDecisionPreMortemEntryInput,
    FinalDecisionRiskPrompt,
    SelectionFinalDecision,
  } from "$lib/types/finalDecision";
  import {
    SELECTION_CHALLENGE_ASSUMPTIONS,
    SELECTION_CHALLENGE_LENSES,
    SELECTION_CHALLENGE_QUESTION_LABELS,
    selectionChallengeConsensusLabel,
  } from "$lib/utils/selectionRisk";

  interface Props {
    jobId: string;
    open?: boolean;
  }

  interface PreMortemDraft extends FinalDecisionPreMortemEntryInput {
    id: number;
  }

  let { jobId, open = $bindable(false) }: Props = $props();

  const DISPOSITIONS: Array<{
    value: FinalDecisionDisposition;
    label: string;
    description: string;
  }> = [
    { value: "PROCEED", label: "Proceed", description: "Commit this idea to implementation planning." },
    { value: "TEST_FIRST", label: "Test first", description: "Keep this idea, but resolve a critical assumption before building." },
    { value: "PARK", label: "Park", description: "Keep the research, with no active commitment." },
    { value: "STOP", label: "Stop", description: "Reject the researched paths for now." },
  ];

  const OUTCOME_LABELS: Record<string, string> = {
    PASS: "Pass rule met",
    FAIL: "Fail rule met",
    AMBIGUOUS: "Neither rule met",
    INVALID: "Test could not answer the question",
  };

  let sources = $state<FinalDecisionLoadResponse | null>(null);
  let loading = $state(false);
  let saving = $state(false);
  let error = $state("");
  let disposition = $state<FinalDecisionDisposition>("PROCEED");
  let selectedKey = $state("");
  let selectedTestExperimentId = $state("");
  let testBriefStatus = $state("");
  let rationale = $state("");
  let acceptedRisks = $state("");
  let changeCriterion = $state("");
  let overrideReason = $state("");
  let preMortemEntries = $state<PreMortemDraft[]>([emptyPreMortemEntry(1)]);
  let preMortemSequence = 1;
  let preMortemStatus = $state("");
  let stage = $state<"decision" | "premortem" | "review" | "handoff">("decision");
  let draftDirty = $state(false);
  let closeWarning = $state(false);
  let focusHandoffAfterConfirm = $state(false);
  let confirmationHeadingEl = $state<HTMLParagraphElement>();
  let loadRequested = false;

  const selectedFinalist = $derived(
    sources?.finalists.find((finalist) => finalistKey(finalist) === selectedKey) ?? null,
  );
  const otherFinalists = $derived(
    sources
      ? sources.finalists.filter((item) =>
          item.ideaId !== sources!.recommendation.ideaId
          || item.ideaRevision !== sources!.recommendation.ideaRevision
        )
      : [],
  );
  const targetRequired = $derived(disposition === "PROCEED" || disposition === "TEST_FIRST");
  const matchingTestBriefs = $derived(
    sources && selectedFinalist
      ? sources.lockedTestBriefs.filter((brief) =>
          brief.idea.ideaId === selectedFinalist.ideaId
          && brief.idea.ideaRevision === selectedFinalist.ideaRevision
        )
      : [],
  );
  const selectedTestBrief = $derived(
    matchingTestBriefs.find((brief) => brief.experimentId === selectedTestExperimentId) ?? null,
  );
  const selectedRiskPrompts = $derived(
    sources && selectedFinalist
      ? sources.riskPrompts.filter((prompt) =>
          prompt.ideaId === selectedFinalist.ideaId
          && prompt.ideaRevision === selectedFinalist.ideaRevision
        )
      : [],
  );
  const activePreMortemEntries = $derived(
    preMortemEntries.filter(entry =>
      !!entry.failureMode.trim()
      || !!entry.earlyWarningSignal.trim()
      || !!entry.mitigation.trim()
      || !!entry.origin
    ),
  );
  const preMortemValid = $derived(
    !targetRequired
      || (
        activePreMortemEntries.length >= 1
        && activePreMortemEntries.length <= 3
        && activePreMortemEntries.every(entry =>
          entry.failureMode.trim().length >= 10
          && entry.earlyWarningSignal.trim().length >= 10
          && entry.mitigation.trim().length >= 10
        )
      ),
  );
  const isOverride = $derived(
    targetRequired
      && !!selectedFinalist
      && !!sources
      && (
        selectedFinalist.ideaId !== sources.recommendation.ideaId
        || selectedFinalist.ideaRevision !== sources.recommendation.ideaRevision
      ),
  );
  const formValid = $derived(
    rationale.trim().length >= 10
      && changeCriterion.trim().length >= 10
      && (!targetRequired || !!selectedFinalist)
      && (disposition !== "TEST_FIRST" || !!selectedTestBrief)
      && preMortemValid
      && (!isOverride || overrideReason.trim().length >= 10),
  );
  const decisionStepValid = $derived(
    rationale.trim().length >= 10
      && changeCriterion.trim().length >= 10
      && (!targetRequired || !!selectedFinalist)
      && (disposition !== "TEST_FIRST" || !!selectedTestBrief)
      && (!isOverride || overrideReason.trim().length >= 10),
  );

  $effect(() => {
    if (disposition !== "TEST_FIRST") {
      if (selectedTestExperimentId) selectedTestExperimentId = "";
      return;
    }
    const eligibleIds = matchingTestBriefs.map((brief) => brief.experimentId);
    if (matchingTestBriefs.length === 1) {
      if (selectedTestExperimentId !== matchingTestBriefs[0].experimentId) {
        selectedTestExperimentId = matchingTestBriefs[0].experimentId;
        testBriefStatus = "The only matching locked test brief was selected.";
      }
    } else if (selectedTestExperimentId && !eligibleIds.includes(selectedTestExperimentId)) {
      selectedTestExperimentId = "";
      testBriefStatus = "The previous test brief does not match this idea revision and was cleared.";
    }
  });

  $effect(() => {
    if (!open || loadRequested) return;
    loadRequested = true;
    void load();
  });

  function finalistKey(finalist: { ideaId: string; ideaRevision: number }): string {
    return `${finalist.ideaId}:${finalist.ideaRevision}`;
  }

  function emptyPreMortemEntry(id: number): PreMortemDraft {
    return {
      id,
      failureMode: "",
      earlyWarningSignal: "",
      mitigation: "",
    };
  }

  function preMortemInput(): FinalDecisionPreMortemEntryInput[] {
    return activePreMortemEntries.map(({ id: _id, ...entry }) => ({
      failureMode: entry.failureMode.trim(),
      earlyWarningSignal: entry.earlyWarningSignal.trim(),
      mitigation: entry.mitigation.trim(),
      ...(entry.origin ? { origin: entry.origin } : {}),
    }));
  }

  function markDirty(): void {
    draftDirty = true;
    closeWarning = false;
  }

  function resetPreMortem(message: string): void {
    preMortemSequence += 1;
    preMortemEntries = [emptyPreMortemEntry(preMortemSequence)];
    preMortemStatus = message;
    markDirty();
  }

  function addPreMortemEntry(): void {
    if (preMortemEntries.length >= 3) return;
    preMortemSequence += 1;
    const entry = emptyPreMortemEntry(preMortemSequence);
    preMortemEntries = [...preMortemEntries, entry];
    preMortemStatus = `Failure mode ${preMortemEntries.length} added.`;
    markDirty();
    requestAnimationFrame(() => document.getElementById(`failure-mode-${entry.id}`)?.focus());
  }

  function removePreMortemEntry(id: number): void {
    const index = preMortemEntries.findIndex(entry => entry.id === id);
    preMortemEntries = preMortemEntries.filter(entry => entry.id !== id);
    if (preMortemEntries.length === 0) {
      preMortemSequence += 1;
      preMortemEntries = [emptyPreMortemEntry(preMortemSequence)];
    }
    preMortemStatus = `Failure mode ${index + 1} removed.`;
    markDirty();
  }

  function promptKey(prompt: Pick<FinalDecisionRiskPrompt, "challengeId" | "questionId">): string {
    return `${prompt.challengeId}:${prompt.questionId}`;
  }

  function selectedPromptKey(entry: PreMortemDraft): string {
    return entry.origin ? `${entry.origin.challengeId}:${entry.origin.questionId}` : "";
  }

  function riskPromptFor(entry: PreMortemDraft): FinalDecisionRiskPrompt | null {
    const key = selectedPromptKey(entry);
    return key ? selectedRiskPrompts.find(item => promptKey(item) === key) ?? null : null;
  }

  function riskPromptLabel(entry: PreMortemDraft): string | null {
    const prompt = riskPromptFor(entry);
    return prompt
      ? `${lensLabel(prompt)} · ${selectionChallengeConsensusLabel(prompt.consensus)}`
      : null;
  }

  function applyRiskPrompt(entry: PreMortemDraft, value: string): void {
    const prompt = selectedRiskPrompts.find(item => promptKey(item) === value);
    if (!prompt) {
      entry.origin = undefined;
      preMortemStatus = "Evidence anchor removed.";
      markDirty();
      return;
    }
    entry.origin = { challengeId: prompt.challengeId, questionId: prompt.questionId };
    if (!entry.failureMode.trim()) {
      entry.failureMode = `The assumption failed: ${SELECTION_CHALLENGE_ASSUMPTIONS[prompt.questionId] ?? prompt.questionId}`;
    }
    preMortemStatus = "Saved risk attached. The failure statement remains editable.";
    markDirty();
  }

  function lensLabel(prompt: Pick<FinalDecisionRiskPrompt, "lens">): string {
    return SELECTION_CHALLENGE_LENSES.find(item => item.value === prompt.lens)?.label ?? prompt.lens;
  }

  function firstInvalidPreMortemId(): string | null {
    if (!targetRequired) return null;
    const entry = activePreMortemEntries[0] ?? preMortemEntries[0];
    if (!entry || entry.failureMode.trim().length < 10) return entry ? `failure-mode-${entry.id}` : null;
    if (entry.earlyWarningSignal.trim().length < 10) return `early-warning-${entry.id}`;
    if (entry.mitigation.trim().length < 10) return `mitigation-${entry.id}`;
    for (const candidate of activePreMortemEntries.slice(1)) {
      if (candidate.failureMode.trim().length < 10) return `failure-mode-${candidate.id}`;
      if (candidate.earlyWarningSignal.trim().length < 10) return `early-warning-${candidate.id}`;
      if (candidate.mitigation.trim().length < 10) return `mitigation-${candidate.id}`;
    }
    return null;
  }

  function displayDate(value: string | null | undefined): string {
    if (!value) return "Date unavailable";
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
  }

  function selectedDecisionName(decision: SelectionFinalDecision): string | null {
    const snapshot = decision.selectedIdeaSnapshot;
    const value = snapshot?.solution_name ?? snapshot?.name;
    return typeof value === "string" ? value : null;
  }

  function dispositionLabel(value: FinalDecisionDisposition): string {
    return DISPOSITIONS.find((item) => item.value === value)?.label ?? value;
  }

  function readableEnum(value: string): string {
    return value.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
  }

  function testBriefRunState(brief: FinalDecisionLockedTestBrief): string {
    if (brief.runStatus === "ACTIVE") return "Collecting";
    if (brief.runStatus === "CLOSED") return "Awaiting conclusion";
    return "Ready to run";
  }

  async function load(): Promise<void> {
    loading = true;
    error = "";
    try {
      sources = await getFinalDecision(jobId);
      if (!sources.decision) {
        selectedKey = finalistKey(sources.recommendation);
        selectedTestExperimentId = "";
        stage = "decision";
      } else {
        stage = "handoff";
      }
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not load the owner decision memo.";
    } finally {
      loading = false;
    }
  }

  function review(): void {
    error = "";
    if (!preMortemValid) {
      error = "Describe the failure, its earliest observable warning, and what you will do.";
      const invalidId = firstInvalidPreMortemId();
      requestAnimationFrame(() => invalidId && document.getElementById(invalidId)?.focus());
      return;
    }
    if (!formValid) {
      error = "Complete the required decision, rationale, and change criterion before reviewing.";
      return;
    }
    stage = "review";
    requestAnimationFrame(() => confirmationHeadingEl?.focus());
  }

  function submitDecisionStep(): void {
    error = "";
    if (!decisionStepValid) {
      error = "Complete the required direction, rationale, and change criterion before continuing.";
      return;
    }
    stage = targetRequired ? "premortem" : "review";
  }

  function resetDraft(): void {
    disposition = "PROCEED";
    selectedKey = sources ? finalistKey(sources.recommendation) : "";
    selectedTestExperimentId = "";
    rationale = "";
    acceptedRisks = "";
    changeCriterion = "";
    overrideReason = "";
    preMortemSequence += 1;
    preMortemEntries = [emptyPreMortemEntry(preMortemSequence)];
    error = "";
    draftDirty = false;
    closeWarning = false;
    stage = "decision";
  }

  function openLab(): void {
    closeWarning = false;
    stage = sources?.decision ? "handoff" : "decision";
    if (!sources) loading = true;
    open = true;
  }

  function requestClose(): void {
    if (saving) return;
    if (!sources?.decision && draftDirty && !closeWarning) {
      closeWarning = true;
      return;
    }
    if (!sources?.decision && draftDirty) resetDraft();
    open = false;
  }

  function continueEditing(): void {
    closeWarning = false;
  }

  function input(): FinalDecisionInput {
    if (disposition === "TEST_FIRST" && selectedFinalist && selectedTestBrief) {
      return {
        disposition,
        ideaId: selectedFinalist.ideaId,
        ideaRevision: selectedFinalist.ideaRevision,
        testExperimentId: selectedTestBrief.experimentId,
        preMortem: preMortemInput(),
        rationale: rationale.trim(),
        acceptedRisks: acceptedRisks.trim(),
        changeCriterion: changeCriterion.trim(),
        sourceFingerprint: sources!.sourceFingerprint,
        ...(isOverride ? { overrideReason: overrideReason.trim() } : {}),
      };
    }
    if (disposition === "PROCEED" && selectedFinalist) {
      return {
        disposition,
        ideaId: selectedFinalist.ideaId,
        ideaRevision: selectedFinalist.ideaRevision,
        preMortem: preMortemInput(),
        rationale: rationale.trim(),
        acceptedRisks: acceptedRisks.trim(),
        changeCriterion: changeCriterion.trim(),
        sourceFingerprint: sources!.sourceFingerprint,
        ...(isOverride ? { overrideReason: overrideReason.trim() } : {}),
      };
    }
    return {
      disposition: disposition === "STOP" ? "STOP" : "PARK",
      rationale: rationale.trim(),
      acceptedRisks: acceptedRisks.trim(),
      changeCriterion: changeCriterion.trim(),
      sourceFingerprint: sources!.sourceFingerprint,
    };
  }

  async function confirm(): Promise<void> {
    if (!sources || !formValid) return;
    saving = true;
    error = "";
    try {
      const decision = await recordFinalDecision(jobId, input());
      sources = { ...sources, decision };
      focusHandoffAfterConfirm = true;
      draftDirty = false;
      closeWarning = false;
      stage = "handoff";
    } catch (cause) {
      error = cause instanceof ApiError && cause.status === 409
        ? cause.message
        : cause instanceof Error
          ? cause.message
          : "Could not record the owner decision.";
    } finally {
      saving = false;
    }
  }

</script>

<section id="owner-decision" class="decision-launcher" aria-labelledby="decision-launcher-title" aria-busy={loading} data-annotation-anchor="report:decision-lab-launcher">
  <div>
    <p class="launcher-kicker">Decision Lab</p>
    <h2 id="decision-launcher-title">
      {sources
        ? sources.decision
          ? "Decision recorded"
          : "Choose the next move"
        : "Record or review your decision"}
    </h2>
    <p>
      {sources
        ? sources.decision
          ? `${dispositionLabel(sources.decision.disposition)} is frozen as the owner record. Review its handoff and delivery status.`
          : "Review the recommendation, name failure conditions, and freeze an owner decision."
        : "Open the owner-only workspace to record a next move or review an existing decision."}
    </p>
  </div>
  <SubmitButton
    type="button"
    class=""
    disabled={loading}
    loadingText=""
    label={sources?.decision ? "Review decision and handoff" : "Open Decision Lab"}
    onclick={openLab}
  />
</section>

<FormOverlay
  {open}
  size="wizard"
  eyebrow="Owner-only Decision Lab"
  title={loading && !sources
    ? "Decision Lab"
    : sources?.decision
      ? "Review the frozen decision"
      : "Commit to the next move"}
  description={loading && !sources
    ? "Loading the owner record and its exact research context."
    : sources?.decision
      ? "Inspect the owner record, prepare its deterministic handoff, and choose whether to send it to GitHub."
      : "Research is an input. Record what you will do, why, and the observable evidence that would change your mind."}
  annotationAnchor="report:decision-lab"
  onRequestClose={requestClose}
>
<section class="decision-memo" aria-label="Decision Lab workspace" aria-busy={loading}>
  {#if loading || (!sources && !error)}
    <div class="memo-state">Loading decision sources…</div>
  {:else if error && !sources}
    <div class="memo-state memo-state-error" role="alert">
      <AlertCircle size={18} />
      <span>{error}</span>
      <button type="button" onclick={load}><RefreshCw size={15} /> Retry</button>
    </div>
  {:else if sources}
    <div class="evidence-overview" aria-label="Research context for this decision">
    <div class="memo-row">
      <h3>Research recommendation</h3>
      <div class="row-content">
        <p class="idea-name">{sources.recommendation.solutionName}</p>
        {#if sources.recommendation.verdict}
          <p class="verdict-line">
            <span>{sources.recommendation.verdict.verdict ?? "Research verdict"}</span>
            {sources.recommendation.verdict.rationale ?? sources.recommendation.selectionRationale}
          </p>
        {:else if sources.recommendation.selectionRationale}
          <p>{sources.recommendation.selectionRationale}</p>
        {/if}
        <p class="meta-line">
          Report generated {displayDate(sources.recommendation.generatedAt)} ·
          <a href="#solution">Review solution</a>
        </p>
      </div>
    </div>

    <div class="memo-row">
      <h3>Other paths considered</h3>
      <div class="row-content">
        {#if sources.finalists.length > 1}
          <details>
            <summary>{sources.finalists.length - 1} other Deep Research finalist{sources.finalists.length === 2 ? "" : "s"}</summary>
            <ul class="compact-list">
              {#each otherFinalists as finalist}
                <li>
                  <strong>{finalist.solutionName}</strong>
                  <span>Idea revision {finalist.ideaRevision}</span>
                </li>
              {/each}
            </ul>
          </details>
        {:else}
          <p class="neutral-copy">No other idea was sent through Deep Research.</p>
        {/if}
      </div>
    </div>

    <div class="memo-row">
      <h3>Still unresolved</h3>
      <div class="row-content">
        {#if sources.recommendation.verdict?.primary_concern}
          <p class="concern">{sources.recommendation.verdict.primary_concern}</p>
        {:else}
          <p class="neutral-copy">The report did not name a primary concern. That is not proof that risk is absent.</p>
        {/if}
      </div>
    </div>

    <div class="memo-row">
      <h3>Concluded tests</h3>
      <div class="row-content">
        {#if sources.conclusions.length}
          <details>
            <summary>{sources.conclusions.length} recorded test conclusion{sources.conclusions.length === 1 ? "" : "s"}</summary>
            <ul class="conclusion-list">
              {#each sources.conclusions as conclusion}
                <li>
                  <span class="outcome">{OUTCOME_LABELS[conclusion.outcome]}</span>
                  <p>{conclusion.ownerRationale}</p>
                  <p class="meta-line">Next action recorded: {conclusion.nextAction} · {displayDate(conclusion.createdAt)}</p>
                </li>
              {/each}
            </ul>
          </details>
        {:else}
          <p class="neutral-copy">No test conclusion was recorded. This does not mean the idea was tested.</p>
        {/if}
      </div>
    </div>

    </div>

    {#if sources.decision}
      <p class="frozen-status"><Check size={14} aria-hidden="true" /> <span>Read-only</span> owner record</p>
      <div class="memo-row decision-receipt" aria-live="polite">
        <h3>Your commitment</h3>
        <div class="row-content">
          <p class="decision-title">
            {dispositionLabel(sources.decision.disposition)}
            {#if selectedDecisionName(sources.decision)}
              · {selectedDecisionName(sources.decision)}
            {/if}
          </p>
          <dl>
            <div><dt>Why now</dt><dd>{sources.decision.rationale}</dd></div>
            {#if sources.decision.acceptedRisks}
              <div><dt>Accepted or open risks</dt><dd>{sources.decision.acceptedRisks}</dd></div>
            {/if}
            {#if sources.decision.overrideReason}
              <div><dt>Why the recommendation was overridden</dt><dd>{sources.decision.overrideReason}</dd></div>
            {/if}
            {#if sources.decision.testExperimentSnapshot}
              <div>
                <dt>Locked test brief</dt>
                <dd>
                  <strong>{sources.decision.testExperimentSnapshot.assumption.statement}</strong>
                  <span>
                    {readableEnum(sources.decision.testExperimentSnapshot.testDesign.method)} ·
                    {readableEnum(sources.decision.testExperimentSnapshot.testDesign.evidenceSignal)}
                  </span>
                </dd>
              </div>
            {/if}
            {#if sources.decision.preMortemSnapshot}
              <div>
                <dt>Pre-mortem</dt>
                <dd>
                  <ol class="pre-mortem-receipt">
                    {#each sources.decision.preMortemSnapshot.entries as entry, index}
                      <li>
                        <strong>{index + 1}. {entry.failureMode}</strong>
                        <span>Earliest warning: {entry.earlyWarningSignal}</span>
                        <span>Response: {entry.mitigation}</span>
                        {#if entry.origin}
                          <small>
                            Evidence anchor · {lensLabel(entry.origin)} ·
                            {selectionChallengeConsensusLabel(entry.origin.consensus)}
                          </small>
                        {/if}
                      </li>
                    {/each}
                  </ol>
                </dd>
              </div>
            {/if}
            <div><dt>Change or stop if</dt><dd>{sources.decision.changeCriterion}</dd></div>
            <div><dt>Recorded</dt><dd>{displayDate(sources.decision.createdAt)}</dd></div>
          </dl>
          <p class="receipt-note">This records the owner's next move. It does not label the idea validated.</p>
        </div>
      </div>
      <DecisionHandoffPanel
        {jobId}
        decision={sources.decision}
        focusOnMount={focusHandoffAfterConfirm}
      />
    {:else}
      <div class="memo-row owner-form">
        <h3>Owner decision</h3>
        <div class="row-content">
          <nav class="decision-steps" aria-label="Owner decision progress">
            <span class:active={stage === "decision"} class:complete={stage !== "decision"}>1 <strong>Decision</strong></span>
            {#if targetRequired}<span class:active={stage === "premortem"} class:complete={stage === "review"}>2 <strong>Pre-mortem</strong></span>{/if}
            <span class:active={stage === "review"}>{targetRequired ? "3" : "2"} <strong>Review</strong></span>
          </nav>

          {#if stage === "decision"}
          <form id="owner-decision-step" class="decision-step-form" onsubmit={(event) => { event.preventDefault(); submitDecisionStep(); }}>
          <DecisionHelp title="Your call, on the record" label="About the owner decision">
            Commit to a next move and name the evidence that would change it, while the reasoning is fresh. NicheIQ writes the decision once, permanently, beside a snapshot of the research it rests on. The report recommendation stays intact, and the call stays yours.
          </DecisionHelp>
          <fieldset>
            <legend>What will you do next?</legend>
            <SegmentControl
              density="card"
              label="What will you do next?"
              options={DISPOSITIONS}
              value={disposition}
              onChange={(value) => {
                disposition = value as FinalDecisionDisposition;
                markDirty();
              }}
            />
          </fieldset>

          {#if targetRequired}
            <label for="decision-idea">Idea to carry forward</label>
            <select id="decision-idea" bind:value={selectedKey} onchange={() => {
              markDirty();
              selectedTestExperimentId = "";
              resetPreMortem("The candidate changed. Its pre-mortem was cleared.");
            }}>
              {#each sources.finalists as finalist}
                <option value={finalistKey(finalist)}>
                  {finalist.solutionName}{finalistKey(finalist) === finalistKey(sources.recommendation) ? " (recommended)" : ""}
                </option>
              {/each}
            </select>
          {/if}

          {#if disposition === "TEST_FIRST" && selectedFinalist}
            <div class="test-brief-field" aria-describedby="test-brief-help">
              <label for={matchingTestBriefs.length > 1 ? "decision-test-brief" : undefined}>Locked test brief</label>
              <p id="test-brief-help" class="field-help">
                Choose the exact precommitted test this decision will carry forward.
              </p>
              {#if matchingTestBriefs.length === 0}
                <div class="test-brief-empty" role="status">
                  <strong>No locked test brief matches {selectedFinalist.solutionName} · revision {selectedFinalist.ideaRevision}.</strong>
                  <span>Test first cannot be recorded without one. Choose another finalist with a locked brief, or choose Proceed, Park, or Stop.</span>
                </div>
              {:else}
                {#if matchingTestBriefs.length > 1}
                  <select
                    id="decision-test-brief"
                    bind:value={selectedTestExperimentId}
                    required
                    aria-describedby="test-brief-help"
                    onchange={() => {
                      markDirty();
                      testBriefStatus = "Locked test brief selected.";
                    }}
                  >
                    <option value="">Choose a locked test brief</option>
                    {#each matchingTestBriefs as brief}
                      <option value={brief.experimentId}>{brief.assumption.statement}</option>
                    {/each}
                  </select>
                {/if}
                {#if selectedTestBrief}
                  <div class="test-brief-summary">
                    <div>
                      <strong>{readableEnum(selectedTestBrief.assumption.type)} · {selectedTestBrief.assumption.statement}</strong>
                      <span>{testBriefRunState(selectedTestBrief)}</span>
                    </div>
                    <p>
                      {readableEnum(selectedTestBrief.testDesign.method)} ·
                      {readableEnum(selectedTestBrief.testDesign.evidenceSignal)} ·
                      {selectedTestBrief.testDesign.measurementWindow}
                    </p>
                  </div>
                {/if}
              {/if}
              <span class="sr-status" role="status" aria-live="polite">{testBriefStatus}</span>
            </div>
          {/if}

          {#if isOverride}
            <label for="override-reason">Why are you overriding the research recommendation?</label>
            <textarea id="override-reason" bind:value={overrideReason} rows="3" required minlength="10" oninput={markDirty}></textarea>
          {/if}

          <label for="decision-rationale">Why is this the right next move now?</label>
          <textarea id="decision-rationale" bind:value={rationale} rows="4" required minlength="10" oninput={markDirty}></textarea>

          <label for="accepted-risks">Residual risk or context <span class="optional-label">Optional</span></label>
          <textarea
            id="accepted-risks"
            bind:value={acceptedRisks}
            rows="2"
            placeholder="Anything important that the structured pre-mortem does not capture."
            oninput={markDirty}
          ></textarea>

          <label for="change-criterion">I will change or stop this decision if…</label>
          <textarea
            id="change-criterion"
            bind:value={changeCriterion}
            rows="3"
            required
            minlength="10"
            placeholder="Write an observable condition, not a feeling."
            oninput={markDirty}
          ></textarea>

          {#if error}
            <p class="form-error" role="alert"><AlertCircle size={16} /> {error}</p>
          {/if}
          </form>

          {:else if stage === "premortem" && targetRequired && selectedFinalist}
            <form id="owner-premortem-step" class="decision-step-form" onsubmit={(event) => { event.preventDefault(); review(); }}>
            <fieldset class="pre-mortem" aria-describedby="pre-mortem-help">
              <legend>Pre-mortem</legend>
              <p id="pre-mortem-help" class="pre-mortem-intro">
                Imagine this path failed six months from now. Name what failed, the first signal you could observe, and the response you will take.
              </p>
              <div class="pre-mortem-list">
                {#each preMortemEntries as entry, index (entry.id)}
                  <fieldset class="pre-mortem-entry">
                    <legend><span>{index + 1}.</span> Failure mode {index + 1}</legend>

                    {#if selectedRiskPrompts.length}
                      <label for={`risk-prompt-${entry.id}`}>Start from a saved risk</label>
                      <select
                        id={`risk-prompt-${entry.id}`}
                        value={selectedPromptKey(entry)}
                        onchange={(event) => applyRiskPrompt(entry, event.currentTarget.value)}
                      >
                        <option value="">Write my own</option>
                        {#each selectedRiskPrompts as prompt}
                          <option value={promptKey(prompt)}>
                            {lensLabel(prompt)} · {selectionChallengeConsensusLabel(prompt.consensus)} ·
                            {SELECTION_CHALLENGE_QUESTION_LABELS[prompt.questionId] ?? prompt.questionId}
                          </option>
                        {/each}
                      </select>
                    {/if}

                    <label for={`failure-mode-${entry.id}`}>It failed because…</label>
                    <textarea
                      id={`failure-mode-${entry.id}`}
                      bind:value={entry.failureMode}
                      rows="2"
                      required
                      aria-invalid={entry.failureMode.trim().length > 0 && entry.failureMode.trim().length < 10}
                      oninput={markDirty}
                    ></textarea>

                    <div class="pre-mortem-fields">
                      <div>
                        <label for={`early-warning-${entry.id}`}>Earliest observable warning…</label>
                        <textarea
                          id={`early-warning-${entry.id}`}
                          bind:value={entry.earlyWarningSignal}
                          rows="3"
                          required
                          placeholder="Include a threshold or deadline when possible."
                          aria-invalid={entry.earlyWarningSignal.trim().length > 0 && entry.earlyWarningSignal.trim().length < 10}
                          oninput={markDirty}
                        ></textarea>
                      </div>
                      <div>
                        <label for={`mitigation-${entry.id}`}>If that appears, I will…</label>
                        <textarea
                          id={`mitigation-${entry.id}`}
                          bind:value={entry.mitigation}
                          rows="3"
                          required
                          aria-invalid={entry.mitigation.trim().length > 0 && entry.mitigation.trim().length < 10}
                          oninput={markDirty}
                        ></textarea>
                      </div>
                    </div>

                    <div class="pre-mortem-entry-footer">
                      {#if riskPromptLabel(entry)}
                        <span>
                          Evidence anchor · {riskPromptLabel(entry)}
                        </span>
                      {:else}
                        <span>Owner-authored</span>
                      {/if}
                      {#if preMortemEntries.length > 1}
                        <button
                          type="button"
                          class="text-button"
                          aria-label={`Remove failure mode ${index + 1}`}
                          onclick={() => removePreMortemEntry(entry.id)}
                        >Remove</button>
                      {/if}
                    </div>
                  </fieldset>
                {/each}
              </div>
              <div class="pre-mortem-actions">
                <button
                  type="button"
                  class="text-button"
                  onclick={addPreMortemEntry}
                  disabled={preMortemEntries.length >= 3}
                >+ Add another failure mode</button>
                <span>Up to three. Keep distinct failure paths.</span>
              </div>
              <span class="sr-status" role="status" aria-live="polite">{preMortemStatus}</span>
            </fieldset>
            {#if error}
              <p class="form-error" role="alert"><AlertCircle size={16} /> {error}</p>
            {/if}
            </form>
          {:else}
            <div class="confirmation" aria-live="polite">
              <p class="review-kicker">Final review</p>
              <h4 bind:this={confirmationHeadingEl} tabindex="-1">Review the owner record</h4>
              <p>
                You are recording <strong>{dispositionLabel(disposition)}</strong>
                {#if selectedFinalist} for <strong>{selectedFinalist.solutionName}</strong>{/if}.
                {#if disposition === "TEST_FIRST" && selectedTestBrief}
                  The locked brief is <strong>“{selectedTestBrief.assumption.statement}”</strong>.
                {/if}
                Future changes will need a separate amendment.
              </p>
              {#if targetRequired}
                <ol class="confirmation-risks">
                  {#each activePreMortemEntries as entry, index}
                    <li>
                      <strong>{index + 1}. {entry.failureMode}</strong>
                      <span>{entry.earlyWarningSignal} → {entry.mitigation}</span>
                    </li>
                {/each}
              </ol>
              {/if}
              <dl class="review-summary">
                <div><dt>Why now</dt><dd>{rationale}</dd></div>
                {#if acceptedRisks}<div><dt>Residual context</dt><dd>{acceptedRisks}</dd></div>{/if}
                <div><dt>Change or stop if</dt><dd>{changeCriterion}</dd></div>
              </dl>
              {#if error}<p class="form-error" role="alert"><AlertCircle size={16} /> {error}</p>{/if}
            </div>
          {/if}
        </div>
      </div>
    {/if}
  {/if}
</section>
  {#snippet footer()}
    <div class="overlay-footer">
      {#if closeWarning}
        <p role="status"><strong>Discard this draft?</strong><span>Your unsaved owner-decision changes will be cleared.</span></p>
        <button type="button" class="secondary" onclick={continueEditing}>Continue editing</button>
        <button type="button" class="danger-action" onclick={requestClose}>Discard draft</button>
      {:else if sources?.decision || loading || (error && !sources)}
        <span></span>
        <button type="button" class="secondary" onclick={requestClose}>Close Decision Lab</button>
      {:else if stage === "decision"}
        <span class="footer-progress">Step 1 of {targetRequired ? 3 : 2} · Decision</span>
        <button type="button" class="secondary" onclick={requestClose}>Cancel</button>
        <SubmitButton
          type="submit"
          form="owner-decision-step"
          class=""
          minWidth="11rem"
          disabled={!decisionStepValid}
          loadingText=""
          label={targetRequired ? "Continue to pre-mortem" : "Review decision"}
        />
      {:else if stage === "premortem"}
        <span class="footer-progress">Step 2 of 3 · Pre-mortem</span>
        <button type="button" class="secondary" onclick={() => (stage = "decision")}><ArrowLeft size={15} /> Back</button>
        <SubmitButton
          type="submit"
          form="owner-premortem-step"
          class=""
          minWidth="11rem"
          disabled={!preMortemValid}
          loadingText=""
          label="Review decision"
        />
      {:else}
        <span class="footer-progress">Final review · becomes read-only</span>
        <button type="button" class="secondary" onclick={() => (stage = targetRequired ? "premortem" : "decision")} disabled={saving}><ArrowLeft size={15} /> Edit</button>
        <SubmitButton
          type="button"
          class=""
          minWidth="11rem"
          loading={saving}
          loadingText="Recording…"
          label="Record decision"
          onclick={confirm}
        />
      {/if}
    </div>
  {/snippet}
</FormOverlay>

<style>
  .decision-launcher {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 2rem;
    margin: 2.5rem 0 1rem;
    padding: 1.4rem 0;
    border-block: 1px solid var(--color-border);
    color: var(--color-text-primary);
  }

  .decision-launcher h2 {
    margin: 0;
    font-size: clamp(1.35rem, 2.4vw, 1.8rem);
    letter-spacing: -0.025em;
    line-height: 1.12;
  }

  .decision-launcher > div > p:last-child {
    max-width: 62ch;
    margin: 0.45rem 0 0;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .launcher-kicker,
  .review-kicker {
    margin: 0 0 0.35rem;
    color: var(--color-accent-dark);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.11em;
    text-transform: uppercase;
  }

  .decision-memo {
    margin: 0;
    padding: 0;
    color: var(--color-text-primary);
  }

  .evidence-overview {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-bottom: 1.5rem;
    border-block: 1px solid var(--color-border);
  }

  .evidence-overview .memo-row {
    display: block;
    min-width: 0;
    padding: 1rem 1.1rem;
    border-bottom: 1px solid var(--color-border);
  }

  .evidence-overview .memo-row:nth-child(odd) {
    border-right: 1px solid var(--color-border);
  }

  .evidence-overview .memo-row h3 {
    margin-bottom: 0.55rem;
  }

  .decision-steps {
    display: flex;
    gap: 0;
    margin-bottom: 1.4rem;
    border-bottom: 1px solid var(--color-border);
  }

  .decision-steps span {
    position: relative;
    min-width: 8rem;
    padding: 0 1rem 0.75rem 0;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    letter-spacing: 0.03em;
  }

  .decision-steps strong {
    margin-left: 0.35rem;
    color: inherit;
    font-family: var(--font-body);
    font-size: var(--text-13);
    letter-spacing: 0;
  }

  .decision-steps span.active,
  .decision-steps span.complete {
    color: var(--color-text-primary);
  }

  .decision-steps span.active::after {
    position: absolute;
    right: 1rem;
    bottom: -1px;
    left: 0;
    height: 2px;
    content: "";
    background: var(--color-accent);
  }

  .decision-step-form {
    max-width: 52rem;
  }

  .frozen-status {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0 0 0.75rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 700;
    letter-spacing: 0.04em;
  }

  .overlay-footer {
    display: flex;
    min-width: 0;
    align-items: center;
    justify-content: flex-end;
    gap: 0.65rem;
  }

  .overlay-footer > p,
  .footer-progress {
    min-width: 0;
    margin: 0 auto 0 0;
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }

  .overlay-footer > p strong,
  .overlay-footer > p span {
    display: block;
  }

  .overlay-footer > p strong {
    color: var(--color-text-primary);
  }

  h2 {
    margin: 0;
    font-size: clamp(1.65rem, 3vw, 2.35rem);
    line-height: 1.08;
    letter-spacing: -0.035em;
  }

  .memo-row {
    display: grid;
    grid-template-columns: minmax(10rem, 3fr) minmax(0, 9fr);
    gap: 2rem;
    padding: 1.6rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  .memo-row h3 {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .row-content {
    min-width: 0;
  }

  .row-content > :first-child {
    margin-top: 0;
  }

  .idea-name, .decision-title {
    margin: 0 0 0.55rem;
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: -0.015em;
  }

  .verdict-line {
    color: var(--color-text-secondary);
  }

  .verdict-line span, .outcome {
    display: inline-block;
    margin-right: 0.55rem;
    color: var(--color-text-primary);
    font-weight: 700;
  }

  .meta-line, .neutral-copy, .receipt-note {
    color: var(--color-text-muted);
    font-size: var(--text-base);
  }

  a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  details {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  summary {
    min-height: 44px;
    padding: 0.7rem 0.85rem;
    cursor: pointer;
    font-weight: 600;
  }

  .compact-list, .conclusion-list {
    margin: 0;
    padding: 0 1rem 1rem 2rem;
  }

  .compact-list li {
    margin: 0.55rem 0;
  }

  .compact-list span {
    display: block;
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }

  .conclusion-list li + li {
    margin-top: 1rem;
  }

  .conclusion-list p {
    margin: 0.3rem 0;
  }

  .concern {
    color: var(--color-text-primary);
  }

  label, legend {
    display: block;
    margin: 1.15rem 0 0.45rem;
    font-size: var(--text-base);
    font-weight: 600;
  }

  fieldset {
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
  }

  legend {
    margin-top: 0;
  }

  textarea, select {
    width: 100%;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-13);
    transition:
      border-color var(--duration-fast) var(--ease-default),
      box-shadow var(--duration-fast) var(--ease-default);
  }

  textarea {
    resize: vertical;
    padding: 0.8rem;
    line-height: 1.5;
  }

  select {
    min-height: 44px;
    padding: 0 0.75rem;
  }

  textarea:hover:not(:focus), select:hover:not(:focus) {
    border-color: var(--color-input-border-hover);
  }

  textarea:focus, select:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }

  button:focus-visible, summary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .test-brief-field {
    margin-top: 1.15rem;
  }

  .test-brief-field > label {
    margin-top: 0;
  }

  .field-help {
    margin: -0.15rem 0 0.65rem;
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }

  .test-brief-summary,
  .test-brief-empty {
    margin-top: 0.65rem;
    padding: 0.8rem 0;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }

  .test-brief-summary > div {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
  }

  .test-brief-summary span,
  .test-brief-empty span {
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }

  .test-brief-summary p {
    margin: 0.4rem 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
  }

  .test-brief-empty {
    color: var(--color-error-text);
  }

  .test-brief-empty strong,
  .test-brief-empty span {
    display: block;
  }

  .test-brief-empty span {
    margin-top: 0.35rem;
  }

  .pre-mortem {
    margin-top: 1.6rem;
    border-top: 1px solid var(--color-text-primary);
  }

  .pre-mortem > legend {
    padding: 1rem 0 0;
    font-size: 1rem;
  }

  .pre-mortem-intro {
    max-width: 46rem;
    margin: 0.25rem 0 1rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .pre-mortem-list {
    border-top: 1px solid var(--color-border);
  }

  .pre-mortem-entry {
    padding: 1.15rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  .pre-mortem-entry > legend {
    margin: 0;
    padding: 0;
    font-size: var(--text-13);
  }

  .pre-mortem-entry > legend span {
    margin-right: 0.45rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm);
    letter-spacing: 0.08em;
  }

  .pre-mortem-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem;
  }

  .pre-mortem-entry-footer,
  .pre-mortem-actions {
    display: flex;
    min-height: 44px;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    color: var(--color-text-muted);
    font-size: var(--text-13);
  }

  .pre-mortem-actions {
    margin-top: 0.45rem;
  }

  button.text-button {
    min-height: 44px;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--color-text-primary);
    font-size: var(--text-13);
  }

  button.text-button:not(:disabled):hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  .optional-label {
    margin-left: 0.35rem;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    font-weight: 500;
  }

  .pre-mortem-receipt,
  .confirmation-risks {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .pre-mortem-receipt li + li,
  .confirmation-risks li + li {
    margin-top: 0.8rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--color-border);
  }

  .pre-mortem-receipt span,
  .pre-mortem-receipt small,
  .confirmation-risks span {
    display: block;
    margin-top: 0.28rem;
  }

  .pre-mortem-receipt small {
    color: var(--color-text-muted);
  }

  .confirmation-risks {
    margin-top: 0.85rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--color-border);
    font-size: var(--text-base);
  }

  .sr-status {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    clip-path: inset(50%);
  }

  .confirmation {
    margin-top: 1.25rem;
    padding: 1rem;
    border: 1px solid var(--color-text-primary);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
  }

  .confirmation p {
    margin: 0 0 0.5rem;
  }

  .confirmation h4 {
    margin: 0 0 0.65rem;
    font-size: 1.25rem;
    letter-spacing: -0.015em;
  }

  .confirmation [tabindex="-1"]:focus {
    outline: none;
  }

  button {
    display: inline-flex;
    min-height: 2.4rem;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  button:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  button.danger-action {
    border-color: var(--color-error-text);
    color: var(--color-error-text);
  }

  button.danger-action:hover:not(:disabled) {
    border-color: var(--color-error-text);
    color: var(--color-error-text);
    background: var(--color-error-subtle);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  .memo-state {
    display: flex;
    min-height: 6rem;
    align-items: center;
    gap: 0.65rem;
    border-top: 1px solid var(--color-border);
    color: var(--color-text-muted);
  }

  .memo-state-error, .form-error {
    color: var(--color-error-text);
  }

  .memo-state button {
    margin-left: auto;
    background: transparent;
    color: var(--color-text-primary);
  }

  .form-error {
    display: flex;
    align-items: flex-start;
    gap: 0.45rem;
    margin: 1rem 0 0;
    font-size: var(--text-base);
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

  @media (max-width: 720px) {
    .decision-launcher {
      display: block;
      margin-top: 2rem;
    }

    .decision-memo {
      margin: 0;
      padding: 0;
    }

    .memo-row {
      display: block;
    }

    .memo-row {
      padding: 1.3rem 0;
    }

    .memo-row h3 {
      margin-bottom: 0.85rem;
    }

    .evidence-overview {
      display: block;
    }

    .evidence-overview .memo-row {
      padding-inline: 0;
      border-right: 0;
    }

    .decision-steps {
      overflow-x: auto;
    }

    .decision-steps span {
      min-width: 7rem;
    }

    .pre-mortem-fields {
      grid-template-columns: 1fr;
      gap: 0;
    }

    .pre-mortem-actions {
      display: block;
    }

    .pre-mortem-actions span {
      display: block;
      margin-top: 0.15rem;
    }

    .overlay-footer {
      display: grid;
      grid-template-columns: 1fr;
    }

    .overlay-footer > p,
    .footer-progress {
      margin: 0 0 0.35rem;
    }

    .overlay-footer > span:empty {
      display: none;
    }

    button {
      width: 100%;
    }

    dl div {
      display: block;
    }

    dt {
      margin-bottom: 0.25rem;
    }
  }
</style>
