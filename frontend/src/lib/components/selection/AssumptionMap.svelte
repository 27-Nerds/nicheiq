<script lang="ts">
  import { tick } from "svelte";
  import {
    AlertTriangle,
    FlaskConical,
    Loader2,
    Pencil,
    Plus,
    RefreshCw,
  } from "lucide-svelte";
  import {
    ApiError,
    createSelectionAssumption,
    getSelectionAssumptions,
    getSelectionChallenges,
    updateSelectionAssumption,
  } from "$lib/api";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type {
    SelectionAssumption,
    SelectionAssumptionCreateInput,
    SelectionAssumptionImpact,
    SelectionAssumptionOwnerState,
  } from "$lib/types/selectionAssumption";
  import type { SolutionPreview } from "$lib/types/job";
  import type {
    SelectionChallenge,
    SelectionChallengeLens,
  } from "$lib/types/selectionChallenge";
  import type { SelectionExperimentDraftSeed } from "$lib/types/selectionExperiment";
  import type { SelectionAssumptionPrefill } from "$lib/types/selectionCopilot";
  import {
    SELECTION_CHALLENGE_LENSES,
    SELECTION_CHALLENGE_QUESTION_LABELS,
  } from "$lib/utils/selectionRisk";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface Props {
    jobId?: string;
    ideas: SolutionPreview[];
    onTestUnknown?: (draft: SelectionExperimentDraftSeed) => void;
    prefill?: SelectionAssumptionPrefill | null;
    onChanged?: () => void;
    /** When set, "Linked test" renders as a button that reveals the saved plan. */
    onOpenLinkedTest?: () => void;
  }

  type Editor = {
    mode: "create" | "edit";
    assumptionId: string | null;
    expectedVersion: number | null;
    ideaId: string;
    ideaRevision: number;
    ideaTitle: string;
    lens: SelectionChallengeLens;
    statement: string;
    impactIfFalse: string;
    falsificationQuestion: string;
    impact: SelectionAssumptionImpact | "";
    ownerState: SelectionAssumptionOwnerState;
    originChallengeId: string | null;
    originQuestionId: string | null;
  };

  let {
    jobId,
    ideas,
    onTestUnknown,
    prefill = null,
    onChanged,
    onOpenLinkedTest,
  }: Props = $props();
  let assumptions = $state<SelectionAssumption[]>([]);
  let challenges = $state<SelectionChallenge[]>([]);
  let loading = $state(false);
  let loadError = $state("");
  let saveError = $state("");
  let saveConflict = $state(false);
  let saving = $state(false);
  let loadedKey = "";
  let editor = $state<Editor | null>(null);
  let editorBaseline = $state("");
  let appliedPrefillId = "";
  let prefillFeedback = $state<{ failed: boolean; message: string } | null>(null);
  let activeCopilotDraft = $state<SelectionAssumptionPrefill | null>(null);
  /** Persistent, always-mounted status text for the assumption/challenge load
   *  (never unmounted with the loading spinner, so it actually announces). */
  let loadAnnouncement = $state("");
  /** Persistent, always-mounted status text set on a successful save (the
   *  overlay itself just closes, so nothing else announces the outcome). */
  let saveAnnouncement = $state("");

  const IMPACTS: Array<{ value: SelectionAssumptionImpact; label: string; description: string }> = [
    { value: "MEDIUM", label: "Medium", description: "Would change part of the plan." },
    { value: "HIGH", label: "High", description: "Would require a major reposition or new route." },
    { value: "DECISIVE", label: "Decision-changing", description: "Would stop this version from moving forward." },
  ];
  const OWNER_STATES: Array<{ value: SelectionAssumptionOwnerState; label: string }> = [
    { value: "OPEN", label: "Open" },
    { value: "ACCEPTED_RISK", label: "Accepted risk" },
    { value: "RETIRED", label: "Retired" },
  ];
  const GROUNDING_FIELDS = [
    { key: "statement", label: "What must be true" },
    { key: "impactIfFalse", label: "What changes if false" },
    { key: "falsificationQuestion", label: "What would prove it wrong" },
  ] as const;

  const editorDirty = $derived(Boolean(editor) && JSON.stringify(editor) !== editorBaseline);
  const canSave = $derived(Boolean(
    editor
      && editor.statement.trim().length >= 3
      && editor.impactIfFalse.trim().length >= 3
      && editor.falsificationQuestion.trim().length >= 3
      && editor.impact,
  ));

  // Inline validation: show a field's error once it has been touched (blurred)
  // or once a save was attempted while it was still invalid.
  type RequiredEditorField = "statement" | "impactIfFalse" | "falsificationQuestion" | "impact";
  let touchedEditorFields = $state<Set<RequiredEditorField>>(new Set());
  let editorSaveAttempted = $state(false);

  function touchEditorField(field: RequiredEditorField) {
    touchedEditorFields.add(field);
    touchedEditorFields = new Set(touchedEditorFields);
  }

  /** Per-field actionable copy plus the rendered control's DOM id, so a
   *  failed save can both explain and focus the first missing answer. */
  const EDITOR_FIELD_COPY: Record<Exclude<RequiredEditorField, "impact">, { id: string; message: string }> = {
    statement: { id: "assumption-statement", message: "Describe what must be true in at least 3 characters." },
    impactIfFalse: { id: "assumption-impact-if-false", message: "Say what you would change, stop, or investigate if this is false." },
    falsificationQuestion: { id: "assumption-falsification", message: "Write the observable result that would prove this wrong." },
  };

  function requiredEditorError(field: RequiredEditorField): string {
    if (!editor) return "";
    if (field === "impact") return editor.impact ? "" : "Choose how much this would change your decision.";
    return editor[field].trim().length < 3 ? EDITOR_FIELD_COPY[field].message : "";
  }

  function editorFieldError(field: RequiredEditorField): string {
    if (!editorSaveAttempted && !touchedEditorFields.has(field)) return "";
    return requiredEditorError(field);
  }

  function resetEditorValidation() {
    touchedEditorFields = new Set();
    editorSaveAttempted = false;
  }

  // SegmentControl (shared component) has no aria-describedby prop, so the
  // "Owner impact" error is wired onto its rendered radiogroup directly.
  let impactFieldEl = $state<HTMLDivElement>();
  $effect(() => {
    if (!impactFieldEl) return;
    const group = impactFieldEl.querySelector('[role="radiogroup"]');
    if (!group) return;
    if (editorFieldError("impact")) {
      group.setAttribute("aria-describedby", "assumption-impact-error");
    } else {
      group.removeAttribute("aria-describedby");
    }
  });

  function identity(idea: SolutionPreview): { id: string; revision: number } | null {
    if (!idea.idea_id || !Number.isInteger(idea.idea_revision) || Number(idea.idea_revision) < 1) return null;
    return { id: idea.idea_id, revision: Number(idea.idea_revision) };
  }

  function lensLabel(lens: SelectionChallengeLens): string {
    return {
      demand: "Do people want it?",
      distribution: "Can you reach buyers?",
      competition: "Can it stand out?",
      dependencies: "Can you build it?",
    }[lens];
  }

  function impactLabel(impact: SelectionAssumptionImpact): string {
    return IMPACTS.find((item) => item.value === impact)?.label ?? impact;
  }

  function ownerStateLabel(state: SelectionAssumptionOwnerState): string {
    return OWNER_STATES.find((item) => item.value === state)?.label ?? state;
  }

  function directionLabel(assumption: SelectionAssumption): string {
    return {
      UNKNOWN: "Direction unknown",
      SUPPORTING: "Leans supporting",
      MIXED: "Mixed direction",
      CONTRADICTING: "Leans contradicting",
    }[assumption.direction];
  }

  function evidenceClassLabel(assumption: SelectionAssumption): string {
    return {
      NONE: "No classified evidence",
      INFERENCE: "Inference",
      PROXY: "Proxy evidence",
      OBSERVED: "Observed evidence",
    }[assumption.evidenceClass];
  }

  function assumptionsFor(idea: SolutionPreview): SelectionAssumption[] {
    const current = identity(idea);
    if (!current) return [];
    return assumptions
      .filter((assumption) => assumption.ideaId === current.id)
      .sort((left, right) => Number(left.stale) - Number(right.stale)
        || right.updatedAt.localeCompare(left.updatedAt));
  }

  const displayedAssumptions = $derived.by(() => ideas.flatMap((idea) => assumptionsFor(idea)));
  const unresolvedCount = $derived(
    displayedAssumptions.filter((item) => !item.stale && item.ownerState === "OPEN").length,
  );

  function linkedTestLabel(assumption: SelectionAssumption): string {
    if (!assumption.experiments.length) return "No linked test";
    const concluded = assumption.experiments.find((experiment) => experiment.outcome);
    if (concluded?.outcome) {
      return {
        PASS: "Pass rule met",
        FAIL: "Fail rule met",
        AMBIGUOUS: "Result ambiguous",
        INVALID: "Test invalid",
      }[concluded.outcome];
    }
    if (assumption.experiments.some((experiment) => experiment.status === "LOCKED")) {
      return "Test plan locked";
    }
    return assumption.experiments.length === 1
      ? "Test draft linked"
      : `${assumption.experiments.length} test drafts linked`;
  }

  function nextAction(assumption: SelectionAssumption): string {
    if (assumption.stale) return "Revisit for the current idea revision";
    if (assumption.ownerState === "RETIRED") return "No further action";
    if (assumption.ownerState === "ACCEPTED_RISK") return "Carry this risk into the final decision";
    if (assumption.experiments.some((experiment) => experiment.outcome)) {
      return "Review the result against the falsification question";
    }
    if (assumption.experiments.length) return "Complete the linked test";
    return "Draft the cheapest decision-changing test";
  }

  function originLabel(assumption: SelectionAssumption): string {
    if (!assumption.originChallengeId || !assumption.originQuestionId) return "Added manually";
    return `Risk check · ${lensLabel(assumption.lens)} · ${SELECTION_CHALLENGE_QUESTION_LABELS[assumption.originQuestionId] ?? assumption.originQuestionId}`;
  }

  async function load() {
    if (!jobId) return;
    loading = true;
    loadError = "";
    loadAnnouncement = "Loading questions to resolve…";
    try {
      const [assumptionResponse, challengeResponse] = await Promise.all([
        getSelectionAssumptions(jobId),
        getSelectionChallenges(jobId),
      ]);
      assumptions = assumptionResponse.assumptions;
      challenges = challengeResponse.challenges;
      loadAnnouncement = "Questions to resolve loaded.";
    } catch (cause) {
      loadError = cause instanceof Error ? cause.message : "Could not load questions to resolve.";
      loadAnnouncement = loadError;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    const revisions = ideas.map((idea) => `${idea.idea_id ?? ""}:${idea.idea_revision ?? ""}`).join("|");
    const key = `${jobId ?? ""}:${revisions}`;
    if (!jobId || key === loadedKey) return;
    loadedKey = key;
    void load();
  });

  function reviewCopilotPrefill(request: SelectionAssumptionPrefill): void {
    if (request.requestId === appliedPrefillId) return;
    if (saving) {
      prefillFeedback = { failed: true, message: "Wait for the current save to finish." };
      return;
    }
    if (editor && editorDirty) {
      prefillFeedback = {
        failed: true,
        message: "This item has unsaved changes. Save or close it before reviewing another suggested draft.",
      };
      return;
    }
    const idea = ideas.find((candidate) => (
      candidate.idea_id === request.ideaId
      && Number(candidate.idea_revision) === request.ideaRevision
    ));
    if (!idea) {
      prefillFeedback = { failed: true, message: "This draft references an older idea revision." };
      return;
    }
    const draftedFields = GROUNDING_FIELDS.filter(({ key }) => request.values[key] !== undefined);
    if (
      draftedFields.length === 0
      || draftedFields.some(({ key }) => !request.grounding[key]?.length)
    ) {
      prefillFeedback = { failed: true, message: "This analyst draft is missing current evidence references." };
      return;
    }

    let baseline: Editor;
    if (request.record) {
      const existing = assumptions.find((item) => item.id === request.record?.id);
      if (
        !existing
        || existing.stale
        || existing.ideaId !== request.ideaId
        || existing.ideaRevision !== request.ideaRevision
        || existing.lens !== request.lens
        || request.record.version !== existing.version
        || (request.origin && (
          request.origin.challengeId !== existing.originChallengeId
          || request.origin.questionId !== existing.originQuestionId
        ))
      ) {
        prefillFeedback = {
          failed: true,
          message: "This item changed after the draft was prepared. Refresh and ask again.",
        };
        return;
      }
      baseline = {
        mode: "edit",
        assumptionId: existing.id,
        expectedVersion: existing.version,
        ideaId: existing.ideaId,
        ideaRevision: existing.ideaRevision,
        ideaTitle: solutionDisplayTitle(idea),
        lens: existing.lens,
        statement: existing.statement,
        impactIfFalse: existing.impactIfFalse,
        falsificationQuestion: existing.falsificationQuestion,
        impact: existing.impact,
        ownerState: existing.ownerState,
        originChallengeId: existing.originChallengeId,
        originQuestionId: existing.originQuestionId,
      };
    } else {
      if (request.origin) {
        const source = challenges.find((challenge) => (
          challenge.id === request.origin?.challengeId
          && challenge.ideaId === request.ideaId
          && challenge.ideaRevision === request.ideaRevision
          && challenge.lens === request.lens
          && challenge.questions.some((question) => question.questionId === request.origin?.questionId)
        ));
        if (!source) {
          prefillFeedback = {
            failed: true,
            message: "The risk-check question behind this draft is missing or no longer current.",
          };
          return;
        }
      }
      baseline = {
        mode: "create",
        assumptionId: null,
        expectedVersion: null,
        ideaId: request.ideaId,
        ideaRevision: request.ideaRevision,
        ideaTitle: solutionDisplayTitle(idea),
        lens: request.lens,
        statement: "",
        impactIfFalse: "",
        falsificationQuestion: "",
        impact: "",
        ownerState: "OPEN",
        originChallengeId: request.origin?.challengeId ?? null,
        originQuestionId: request.origin?.questionId ?? null,
      };
    }

    editor = {
      ...baseline,
      ...(request.values.statement !== undefined ? { statement: request.values.statement } : {}),
      ...(request.values.impactIfFalse !== undefined ? { impactIfFalse: request.values.impactIfFalse } : {}),
      ...(request.values.falsificationQuestion !== undefined ? { falsificationQuestion: request.values.falsificationQuestion } : {}),
      mode: baseline.mode,
      assumptionId: baseline.assumptionId,
      expectedVersion: baseline.expectedVersion,
      ideaId: baseline.ideaId,
      ideaRevision: baseline.ideaRevision,
      ideaTitle: baseline.ideaTitle,
      lens: baseline.lens,
      originChallengeId: baseline.originChallengeId,
      originQuestionId: baseline.originQuestionId,
    };
    editorBaseline = JSON.stringify(editor);
    saveError = "";
    saveConflict = false;
    resetEditorValidation();
    appliedPrefillId = request.requestId;
    activeCopilotDraft = request;
    prefillFeedback = { failed: false, message: "Suggested draft opened. Review it before saving." };
  }

  $effect(() => {
    if (!prefill || loading || prefill.requestId === appliedPrefillId) return;
    reviewCopilotPrefill(prefill);
  });

  function openManualCreate(idea: SolutionPreview) {
    const current = identity(idea);
    if (!current) return;
    activeCopilotDraft = null;
    editor = {
      mode: "create",
      assumptionId: null,
      expectedVersion: null,
      ideaId: current.id,
      ideaRevision: current.revision,
      ideaTitle: solutionDisplayTitle(idea),
      lens: "demand",
      statement: "",
      impactIfFalse: "",
      falsificationQuestion: "",
      impact: "",
      ownerState: "OPEN",
      originChallengeId: null,
      originQuestionId: null,
    };
    editorBaseline = JSON.stringify(editor);
    saveError = "";
    saveConflict = false;
    resetEditorValidation();
  }

  function openEdit(assumption: SelectionAssumption, idea: SolutionPreview) {
    if (assumption.stale) return;
    activeCopilotDraft = null;
    editor = {
      mode: "edit",
      assumptionId: assumption.id,
      expectedVersion: assumption.version,
      ideaId: assumption.ideaId,
      ideaRevision: assumption.ideaRevision,
      ideaTitle: solutionDisplayTitle(idea),
      lens: assumption.lens,
      statement: assumption.statement,
      impactIfFalse: assumption.impactIfFalse,
      falsificationQuestion: assumption.falsificationQuestion,
      impact: assumption.impact,
      ownerState: assumption.ownerState,
      originChallengeId: assumption.originChallengeId,
      originQuestionId: assumption.originQuestionId,
    };
    editorBaseline = JSON.stringify(editor);
    saveError = "";
    saveConflict = false;
    resetEditorValidation();
  }

  /** Confirmed close: FormOverlay owns the dirty two-press gate. */
  function closeEditor() {
    if (saving) return;
    editor = null;
    activeCopilotDraft = null;
    editorBaseline = "";
    saveError = "";
    saveConflict = false;
    resetEditorValidation();
  }

  /** Submit-attempt entry point: reveals every missing required field instead
   *  of relying on a silently disabled button, then focuses the first one. */
  async function attemptSaveEditor() {
    if (!canSave) {
      editorSaveAttempted = true;
      await tick();
      const order: RequiredEditorField[] = ["statement", "impactIfFalse", "falsificationQuestion", "impact"];
      const first = order.find((field) => requiredEditorError(field));
      if (first === "impact") {
        impactFieldEl?.querySelector<HTMLElement>('[role="radio"]')?.focus();
      } else if (first) {
        document.getElementById(EDITOR_FIELD_COPY[first].id)?.focus();
      }
      return;
    }
    void saveEditor();
  }

  async function saveEditor() {
    if (!jobId || !editor || !canSave || saving || !editor.impact) return;
    const editorMode = editor.mode;
    saving = true;
    saveError = "";
    saveConflict = false;
    try {
      if (editor.mode === "create") {
        const input: SelectionAssumptionCreateInput = {
          ideaId: editor.ideaId,
          ideaRevision: editor.ideaRevision,
          lens: editor.lens,
          statement: editor.statement.trim(),
          impactIfFalse: editor.impactIfFalse.trim(),
          falsificationQuestion: editor.falsificationQuestion.trim(),
          impact: editor.impact,
          ...(editor.originChallengeId && editor.originQuestionId ? {
            originChallengeId: editor.originChallengeId,
            originQuestionId: editor.originQuestionId,
          } : {}),
        };
        const response = await createSelectionAssumption(jobId, input);
        assumptions = [response.assumption, ...assumptions.filter((item) => item.id !== response.assumption.id)];
      } else if (editor.assumptionId && editor.expectedVersion != null) {
        const response = await updateSelectionAssumption(jobId, editor.assumptionId, {
          expectedVersion: editor.expectedVersion,
          ideaId: editor.ideaId,
          ideaRevision: editor.ideaRevision,
          statement: editor.statement.trim(),
          impactIfFalse: editor.impactIfFalse.trim(),
          falsificationQuestion: editor.falsificationQuestion.trim(),
          impact: editor.impact,
          ownerState: editor.ownerState,
        });
        assumptions = assumptions.map((item) => item.id === response.assumption.id ? response.assumption : item);
      }
      editor = null;
      activeCopilotDraft = null;
      editorBaseline = "";
      saveAnnouncement = "Question to resolve saved.";
      onChanged?.();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        saveConflict = true;
        saveError = editorMode === "create"
          ? "This question is already saved or its idea revision changed. Reload before continuing."
          : "This item changed or its idea revision is no longer current. Reload before editing it again.";
      } else {
        saveError = cause instanceof Error ? cause.message : "Could not save this item.";
      }
    } finally {
      saving = false;
    }
  }

  function reloadAfterConflict() {
    closeEditor();
    void load();
  }

  function draftTest(assumption: SelectionAssumption) {
    if (!onTestUnknown || assumption.stale || assumption.experiments.length) return;
    onTestUnknown({
      ideaId: assumption.ideaId,
      ideaRevision: assumption.ideaRevision,
      assumptionId: assumption.id,
      assumption: assumption.statement,
      whyCritical: assumption.impactIfFalse,
      originChallengeId: assumption.originChallengeId,
      originQuestionId: assumption.originQuestionId,
    });
  }
</script>

<section class="assumption-map" aria-labelledby="assumption-map-title">
  <header class="map-head">
    <div>
      <div class="title-row">
        <h3 id="assumption-map-title">Questions to resolve</h3>
        <DecisionHelp title="How to use this list" position="bottom">
          <p>You choose how much each belief matters. Evidence signals update from linked risk checks and completed tests, but they never become a confidence score. Start with decision-changing beliefs that still rely on inference.</p>
        </DecisionHelp>
      </div>
      <p>Keep only questions whose answer would change what you research or build.</p>
    </div>
    {#if !loading && !loadError}
      <div class="map-actions">
        {#if unresolvedCount > 0}
          <span class="map-count">{unresolvedCount} unresolved</span>
        {/if}
        {#if ideas.length === 1}
          <button
            type="button"
            class="add-action"
            aria-label={`Add a question to resolve for ${solutionDisplayTitle(ideas[0])}`}
            disabled={!identity(ideas[0]) || !jobId}
            onclick={() => openManualCreate(ideas[0])}
          >
            <Plus aria-hidden="true" /> Add question
          </button>
        {/if}
      </div>
    {/if}
  </header>

  <p class="sr-only" role="status">{loadAnnouncement}</p>
  <p class="sr-only" role="status">{saveAnnouncement}</p>

  {#if prefillFeedback && !editor}
    <p class="prefill-feedback" class:is-error={prefillFeedback.failed} role="alert">
      {prefillFeedback.message}
    </p>
  {/if}

  {#if loading}
    <div class="map-state"><Loader2 class="spin map-spin" aria-hidden="true" /> Loading questions to resolve…</div>
  {:else if loadError}
    <div class="map-state map-error" role="alert">
      <span>{loadError}</span>
      <button type="button" onclick={() => void load()}><RefreshCw aria-hidden="true" /> Retry</button>
    </div>
  {:else}
    <div class="idea-groups" class:is-single={ideas.length === 1}>
      {#each ideas as idea, ideaIndex (idea.idea_id ?? `${idea.solution_name}:${ideaIndex}`)}
        {@const current = identity(idea)}
        {@const tracked = assumptionsFor(idea)}
        <section
          class="idea-group"
          class:is-single={ideas.length === 1}
          aria-labelledby={ideas.length === 1 ? "assumption-map-title" : `assumption-idea-${ideaIndex}`}
        >
          {#if ideas.length > 1}
            <header class="idea-head">
              <div>
                <span>Idea {ideaIndex + 1}{current ? ` · rev ${current.revision}` : ""}</span>
                <h4 id={`assumption-idea-${ideaIndex}`}>{solutionDisplayTitle(idea)}</h4>
              </div>
              <button type="button" class="add-action" aria-label={`Add a question to resolve for ${solutionDisplayTitle(idea)}`} disabled={!current || !jobId} onclick={() => openManualCreate(idea)}>
                <Plus aria-hidden="true" /> Add question
              </button>
            </header>
          {/if}

          {#if tracked.length}
            <div class="assumption-list">
              {#each tracked as assumption (assumption.id)}
                <article class="assumption" class:is-stale={assumption.stale} data-annotation-anchor={`selection:assumption:${assumption.id}`}>
                  <h5>{assumption.statement}</h5>
                  <div class="assumption-top">
                    <div class="assumption-origin">
                      <span>{originLabel(assumption)}</span>
                      {#if assumption.stale}<strong>Older revision · rev {assumption.ideaRevision}</strong>{/if}
                    </div>
                    <div class="assumption-badges">
                      <span class="impact impact--{assumption.impact.toLowerCase()}">{impactLabel(assumption.impact)} impact</span>
                      <span>Status: {ownerStateLabel(assumption.ownerState)}</span>
                    </div>
                  </div>
                  <dl class="assumption-detail">
                    <div><dt>If this is false</dt><dd>{assumption.impactIfFalse}</dd></div>
                    <div><dt>What would prove it wrong?</dt><dd>{assumption.falsificationQuestion}</dd></div>
                    {#if assumption.direction !== "UNKNOWN"}
                      <div><dt>What the evidence suggests</dt><dd>{directionLabel(assumption)}</dd></div>
                    {/if}
                    {#if assumption.evidenceClass !== "NONE"}
                      <div><dt>Best evidence available</dt><dd>{evidenceClassLabel(assumption)}</dd></div>
                    {/if}
                    {#if assumption.experiments.length}
                      <div><dt>Linked test</dt><dd>
                        {#if onOpenLinkedTest && assumption.experiments.length}
                          <button type="button" class="linked-test-action" onclick={onOpenLinkedTest}>{linkedTestLabel(assumption)}</button>
                        {:else}
                          {linkedTestLabel(assumption)}
                        {/if}
                      </dd></div>
                    {/if}
                    <div><dt>Next action</dt><dd>{nextAction(assumption)}</dd></div>
                  </dl>
                  <footer class="assumption-actions">
                    {#if !assumption.stale}
                      <button type="button" class="text-action" onclick={() => openEdit(assumption, idea)}><Pencil aria-hidden="true" /> Edit</button>
                      {#if onTestUnknown && !assumption.experiments.length && assumption.ownerState === "OPEN"}
                        <button type="button" class="test-action" onclick={() => draftTest(assumption)}><FlaskConical aria-hidden="true" /> Draft test</button>
                      {/if}
                    {:else}
                      <span><AlertTriangle aria-hidden="true" /> Kept for history; create a current-revision assumption to act on it.</span>
                    {/if}
                  </footer>
                </article>
              {/each}
            </div>
          {:else}
            <p class="idea-empty">No questions saved yet.</p>
          {/if}
        </section>
      {/each}
    </div>
  {/if}

  {#if displayedAssumptions.length > 0}
    <footer class="map-note">Evidence signals can change when saved evidence or completed test results change. They summarize linked evidence; they are not confidence ratings.</footer>
  {/if}
</section>

<FormOverlay
  open={Boolean(editor)}
  size="form"
  eyebrow="Questions to resolve"
  title={editor?.mode === "edit" ? "Edit question to resolve" : "Save a question to resolve"}
  description={editor ? `${editor.ideaTitle} · rev ${editor.ideaRevision}` : ""}
  annotationAnchor={editor ? `selection:assumption-form:${editor.mode}:${editor.assumptionId ?? `${editor.ideaId}:${editor.ideaRevision}:${editor.originChallengeId ?? "manual"}`}` : undefined}
  onRequestClose={closeEditor}
  dirty={editorDirty}
  closeWarning="You have unsaved changes. Close again to discard them."
  footerMessage="Your wording and impact are saved. Evidence signals still come from linked sources and tests."
>
  {#snippet children()}
    {#if editor}
      {#if prefillFeedback?.failed}
        <p class="prefill-feedback is-error" role="alert">{prefillFeedback.message}</p>
      {/if}
      <form id="assumption-editor" class="editor" onsubmit={(event) => { event.preventDefault(); attemptSaveEditor(); }}>
        {#if activeCopilotDraft}
          <aside class="analyst-draft-note" aria-label="Analyst draft grounding">
            <div class="analyst-draft-heading">
              <strong>Suggested draft · not saved</strong>
              <span>Review and edit before saving.</span>
            </div>
            <p>{activeCopilotDraft.rationale}</p>
            <dl>
              {#each GROUNDING_FIELDS as field}
                {#if activeCopilotDraft.values[field.key] !== undefined}
                  <div>
                    <dt>{field.label}</dt>
                    <dd>
                      {#each activeCopilotDraft.grounding[field.key] ?? [] as source (source.ref)}
                        <span>{source.label}</span>
                      {/each}
                    </dd>
                  </div>
                {/if}
              {/each}
            </dl>
            {#if activeCopilotDraft.caveats.length}
              <p><strong>Caveat:</strong> {activeCopilotDraft.caveats.join(" ")}</p>
            {/if}
            <p class="owner-boundary">You still choose how much this matters and whether it remains open.</p>
          </aside>
        {:else if editor.originChallengeId && editor.originQuestionId}
          <div class="provenance-note">
            <strong>Suggested by the “{lensLabel(editor.lens)}” risk check</strong>
            <span>{SELECTION_CHALLENGE_QUESTION_LABELS[editor.originQuestionId] ?? editor.originQuestionId}</span>
            <p>The source reference stays attached. You still decide the impact and what would prove this wrong.</p>
          </div>
        {/if}

        <FormField
          id="assumption-lens"
          kind="select"
          label="Question area"
          value={editor.lens}
          disabled={editor.mode === "edit" || Boolean(editor.originChallengeId)}
          onchange={(event) => (editor!.lens = (event.currentTarget as HTMLSelectElement).value as SelectionChallengeLens)}
        >
          {#each SELECTION_CHALLENGE_LENSES as lens}<option value={lens.value}>{lensLabel(lens.value)}</option>{/each}
        </FormField>

        <FormField
          id="assumption-statement"
          kind="textarea"
          label="What must be true?"
          hint="Write one short, observable belief about this exact candidate."
          required
          bind:value={editor.statement}
          maxlength={800}
          rows={3}
          error={editorFieldError("statement")}
          onblur={() => touchEditorField("statement")}
        />

        <FormField
          id="assumption-impact-if-false"
          kind="textarea"
          label="What changes if this is false?"
          hint="Say what you would change, stop, or investigate if this belief is wrong."
          required
          bind:value={editor.impactIfFalse}
          maxlength={800}
          rows={3}
          error={editorFieldError("impactIfFalse")}
          onblur={() => touchEditorField("impactIfFalse")}
        />

        <FormField
          id="assumption-falsification"
          kind="textarea"
          label="What result would prove it wrong?"
          hint="Write the observable question a real-world test should answer."
          required
          bind:value={editor.falsificationQuestion}
          maxlength={800}
          rows={3}
          error={editorFieldError("falsificationQuestion")}
          onblur={() => touchEditorField("falsificationQuestion")}
        />

        <div class="field" bind:this={impactFieldEl}>
          <span class="field-label" id="assumption-impact-label">How much would this change your decision? <span class="req">Required</span></span>
          <SegmentControl
            density="card"
            label="How much would this change your decision?"
            labelledBy="assumption-impact-label"
            options={IMPACTS}
            value={editor.impact}
            onChange={(value) => {
              editor!.impact = value as SelectionAssumptionImpact;
              touchEditorField("impact");
            }}
          />
          {#if editorFieldError("impact")}
            <p class="field-error" id="assumption-impact-error" role="alert">{editorFieldError("impact")}</p>
          {/if}
        </div>

        {#if editor.mode === "edit"}
          <FormField
            id="assumption-owner-state"
            kind="select"
            label="Status"
            hint="Status records how you plan to handle this item. It does not change what the evidence suggests."
            value={editor.ownerState}
            onchange={(event) => (editor!.ownerState = (event.currentTarget as HTMLSelectElement).value as SelectionAssumptionOwnerState)}
          >
            {#each OWNER_STATES as state}<option value={state.value}>{state.label}</option>{/each}
          </FormField>
        {/if}

        {#if saveError}
          <div class="editor-error" role="alert">
            <span>{saveError}</span>
            {#if saveConflict}<button type="button" class="reload-action" onclick={reloadAfterConflict}>Reload map</button>{/if}
          </div>
        {/if}
      </form>
    {/if}
  {/snippet}
  {#snippet footerCancel(requestClose)}
    <button type="button" class="cancel-btn" disabled={saving} onclick={requestClose}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <SubmitButton
      type="button"
      label={editor?.mode === "edit" ? "Save changes" : "Save question"}
      loadingText="Saving…"
      loading={saving}
      onclick={attemptSaveEditor}
      class="submit-btn"
    />
  {/snippet}
</FormOverlay>

<style>
  .assumption-map { padding: 0; background: transparent; }
  .map-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-8); padding-bottom: var(--space-4); border-bottom: 1px solid var(--color-border-emphasis); }
  .title-row { display: flex; align-items: flex-start; gap: var(--space-2); }
  h3, h4, h5, p { margin: 0; }
  .map-head h3 { max-width: 38ch; font-size: var(--text-xl); line-height: var(--leading-tight); letter-spacing: var(--tracking-tight); text-wrap: balance; }
  .map-head > div > p:last-child { max-width: 65ch; margin-top: var(--space-2); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); text-wrap: pretty; }
  .map-actions { display: flex; flex: 0 0 auto; align-items: center; justify-content: flex-end; gap: var(--space-3); }
  .map-count { flex: 0 0 auto; color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-11); font-weight: 700; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
  .prefill-feedback { margin: var(--space-3) 0 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); }
  .prefill-feedback.is-error { color: var(--color-error-text); }
  .map-state { display: flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: calc(var(--space-16) * 4); color: var(--color-text-secondary); font-size: var(--text-13); }
  .map-state :global(svg) { width: var(--space-4); height: var(--space-4); }
  .map-error { flex-direction: column; color: var(--color-error-text); }
  .map-error button { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-1-5); min-height: var(--space-10); padding: var(--space-2) var(--space-3); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: var(--color-bg-elevated); color: var(--color-text-primary); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default); }
  .map-error button:hover { border-color: var(--color-text-secondary); }
  .map-error button:active { transform: scale(0.98); }
  .idea-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: var(--space-5) var(--space-8); padding-top: var(--space-4); }
  .idea-groups.is-single { grid-template-columns: minmax(0, 1fr); }
  .idea-group { min-width: 0; padding-top: var(--space-4); border-top: 1px solid var(--color-border-emphasis); }
  .idea-group.is-single { padding-top: 0; border-top: 0; }
  .idea-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: var(--space-4); padding-bottom: var(--space-3); }
  .idea-head span { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .idea-head h4 { max-width: 34ch; margin-top: var(--space-1); font-size: var(--text-md); line-height: var(--leading-snug); letter-spacing: var(--tracking-tight); text-wrap: pretty; }
  .add-action, .test-action, .text-action { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-1-5); min-height: var(--space-10); border: 0; background: transparent; color: var(--color-accent-dark); font: inherit; font-size: var(--text-13); font-weight: 700; white-space: nowrap; cursor: pointer; transition: transform var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .add-action:hover:not(:disabled), .test-action:hover, .text-action:hover:not(:disabled) { color: var(--color-accent-hover); }
  .linked-test-action { border: 0; background: transparent; padding: 0; font: inherit; color: var(--color-accent-dark); text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }
  .linked-test-action:hover { color: var(--color-accent-hover); }
  .linked-test-action:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: var(--radius-sm); }
  .add-action:active:not(:disabled), .test-action:active, .text-action:active:not(:disabled) { transform: scale(0.98); }
  .add-action :global(svg), .test-action :global(svg), .text-action :global(svg) { width: var(--text-base); height: var(--text-base); }
  .add-action:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); cursor: not-allowed; }
  .add-action { min-height: var(--space-8); padding: var(--space-1-5) var(--space-3); border: 1px solid var(--color-border-accent); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .add-action:hover:not(:disabled) { border-color: var(--color-input-border-hover); background: var(--color-bg-surface); }
  .idea-empty { max-width: 65ch; padding: var(--space-4) 0 var(--space-2); color: var(--color-text-secondary); font-size: var(--text-base); line-height: var(--leading-normal); text-wrap: pretty; }
  .assumption-list { display: grid; gap: var(--space-3); }
  .assumption { padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-elevated); }
  /* Staleness reads from the "Older revision" label plus a muted (but AA)
   *  body color — never opacity, which would wash out the whole card. */
  .assumption.is-stale h5, .assumption.is-stale .assumption-detail dd { color: var(--color-text-secondary); }
  .assumption-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-top: var(--space-2); }
  .assumption-origin { display: grid; gap: var(--space-1); min-width: 0; }
  .assumption-origin span, .assumption-origin strong { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); line-height: var(--leading-snug); }
  .assumption-origin strong { color: var(--color-error-text); }
  .assumption-badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-1-5); }
  .assumption-badges span { padding: var(--space-1) var(--space-1-5); border: 1px solid var(--color-border); border-radius: var(--radius-sm); color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; text-transform: uppercase; }
  .assumption-badges .impact--decisive { border-color: color-mix(in srgb, var(--color-error-text) 45%, var(--color-border)); color: var(--color-error-text); }
  .assumption h5 { max-width: 60ch; font-size: var(--text-lg); line-height: var(--leading-snug); letter-spacing: var(--tracking-tight); text-wrap: pretty; }
  .assumption-detail { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: var(--space-3) 0 0; border-top: 1px solid var(--color-border); }
  .assumption-detail div { min-width: 0; padding: var(--space-2) var(--space-3) var(--space-1) 0; }
  .assumption-detail dt { color: var(--color-text-secondary); font-size: var(--text-sm); font-weight: 700; }
  .assumption-detail dd { max-width: 65ch; margin: var(--space-1) 0 0; font-size: var(--text-13); line-height: var(--leading-normal); overflow-wrap: anywhere; text-wrap: pretty; }
  .assumption-actions { display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-3); padding-top: var(--space-2); border-top: 1px solid var(--color-border); }
  .assumption-actions span { display: inline-flex; align-items: center; gap: var(--space-1-5); color: var(--color-text-secondary); font-size: var(--text-sm); }
  .assumption-actions span :global(svg) { width: var(--text-13); height: var(--text-13); }
  .map-note { max-width: 65ch; padding-top: var(--space-4); color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); }

  /* ── Overlay form ── */
  /* 16px field rhythm, matching the test-plan wizard's fieldset gap. */
  .editor { display: grid; gap: var(--space-4); max-width: 65ch; }
  .field { display: grid; gap: var(--space-1-5); }
  .field-label { display: flex; align-items: baseline; gap: var(--space-2); font-size: var(--text-base); font-weight: 700; color: var(--color-text-primary); }
  .field-label .req { font-size: var(--text-11); font-weight: 500; color: var(--color-text-secondary); }
  .field-error { margin: 0; color: var(--color-error-text); font-size: var(--text-sm); line-height: var(--leading-normal); }
  .provenance-note { display: grid; gap: var(--space-1); padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .provenance-note strong { font-size: var(--text-sm); }
  .provenance-note span { color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); }
  .provenance-note p { max-width: 65ch; margin-top: var(--space-1); color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); text-wrap: pretty; }
  .analyst-draft-note { display: grid; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .analyst-draft-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--space-1) var(--space-4); }
  .analyst-draft-heading strong { font-size: var(--text-sm); }
  .analyst-draft-heading span, .analyst-draft-note > p { max-width: 65ch; color: var(--color-text-secondary); font-size: var(--text-13); line-height: var(--leading-normal); text-wrap: pretty; }
  .analyst-draft-note dl { display: grid; gap: var(--space-2); margin: 0; }
  .analyst-draft-note dl div { display: grid; grid-template-columns: minmax(8rem, 0.35fr) minmax(0, 1fr); gap: var(--space-2); }
  .analyst-draft-note dt { color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 600; }
  .analyst-draft-note dd { display: flex; flex-wrap: wrap; gap: var(--space-1); margin: 0; }
  .analyst-draft-note dd span { padding: var(--space-1) var(--space-1-5); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg-elevated); color: var(--color-text-secondary); font-size: var(--text-xs); }
  .analyst-draft-note .owner-boundary { color: var(--color-text-primary); font-weight: 700; }
  .editor-error { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin: 0; padding: var(--space-3); border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background: var(--color-error-subtle); color: var(--color-error-text); font-size: var(--text-sm); }
  .reload-action { display: inline-flex; align-items: center; flex: 0 0 auto; min-height: var(--space-8); border: 0; background: transparent; color: inherit; font: inherit; font-weight: 700; cursor: pointer; text-decoration: underline; text-underline-offset: var(--space-1); transition: opacity var(--duration-fast) var(--ease-default); }
  .reload-action:hover { opacity: 0.75; }
  .reload-action:active { transform: scale(0.98); }
  .cancel-btn { display: inline-flex; align-items: center; justify-content: center; min-height: var(--space-10); padding: var(--space-2) var(--space-4); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 700; white-space: nowrap; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .cancel-btn:hover:not(:disabled) { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .cancel-btn:active:not(:disabled) { transform: scale(0.98); }
  .cancel-btn:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: wait; }
  .cancel-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  button:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  :global(.map-spin) { animation: assumption-spin var(--duration-slowest) linear infinite; }
  @keyframes assumption-spin { to { transform: rotate(360deg); } }

  @media (prefers-reduced-motion: reduce) {
    .assumption-map *,
    .assumption-map *::before,
    .assumption-map *::after,
    .editor *,
    .editor *::before,
    .editor *::after {
      transition: none !important;
      animation: none !important;
    }
    .map-error button:active,
    .add-action:hover:not(:disabled),
    .test-action:hover,
    .text-action:hover:not(:disabled),
    .add-action:active:not(:disabled),
    .test-action:active,
    .text-action:active:not(:disabled),
    .reload-action:active,
    .cancel-btn:active:not(:disabled) {
      transform: none;
    }
  }

  @media (max-width: 860px) {
    .idea-groups { grid-template-columns: 1fr; }
  }

  @media (max-width: 720px) {
    .assumption-map { padding: 0; }
    .map-head { display: block; }
    .map-actions { justify-content: flex-start; margin-top: var(--space-3); }
    .idea-head { grid-template-columns: 1fr; }
    .add-action { width: fit-content; }
    .assumption-top { display: grid; }
    .assumption-badges { justify-content: flex-start; }
    .assumption-detail { grid-template-columns: 1fr; }
    .assumption-detail div { padding-right: 0; padding-bottom: var(--space-2); border-bottom: 1px solid var(--color-border); }
    .assumption-actions { flex-wrap: wrap; }
    .analyst-draft-note dl div { grid-template-columns: 1fr; }
  }
</style>
