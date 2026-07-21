<script lang="ts">
  import {
    AlertTriangle,
    ArrowRight,
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
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
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
    SelectionChallengeQuestion,
  } from "$lib/types/selectionChallenge";
  import type { SelectionExperimentDraftSeed } from "$lib/types/selectionExperiment";
  import type { SelectionAssumptionPrefill } from "$lib/types/selectionCopilot";
  import {
    SELECTION_CHALLENGE_ASSUMPTIONS,
    SELECTION_CHALLENGE_LENSES,
    SELECTION_CHALLENGE_QUESTION_LABELS,
    SELECTION_RISK_PRIORITY,
    actionableSelectionQuestion,
  } from "$lib/utils/selectionRisk";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface Props {
    jobId?: string;
    ideas: SolutionPreview[];
    onTestUnknown?: (draft: SelectionExperimentDraftSeed) => void;
    prefill?: SelectionAssumptionPrefill | null;
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

  type GapSuggestion = {
    idea: SolutionPreview;
    challenge: SelectionChallenge;
    question: SelectionChallengeQuestion;
    statement: string;
  };

  let { jobId, ideas, onTestUnknown, prefill = null }: Props = $props();
  let assumptions = $state<SelectionAssumption[]>([]);
  let challenges = $state<SelectionChallenge[]>([]);
  let loading = $state(false);
  let loadError = $state("");
  let saveError = $state("");
  let saveConflict = $state(false);
  let saving = $state(false);
  let loadedKey = $state("");
  let editor = $state<Editor | null>(null);
  let editorBaseline = $state("");
  let appliedPrefillId = $state("");
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
    { key: "falsificationQuestion", label: "Falsification question" },
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

  function requiredTextError(value: string): string {
    if (value.trim().length === 0) return "Required.";
    return value.trim().length < 3 ? "Enter at least 3 characters." : "";
  }

  function editorFieldError(field: RequiredEditorField): string {
    if (!editorSaveAttempted && !touchedEditorFields.has(field)) return "";
    if (!editor) return "";
    if (field === "impact") return editor.impact ? "" : "Choose an impact.";
    return requiredTextError(editor[field]);
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
    return SELECTION_CHALLENGE_LENSES.find((item) => item.value === lens)?.label ?? lens;
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

  function suggestionsFor(idea: SolutionPreview): GapSuggestion[] {
    const current = identity(idea);
    if (!current) return [];
    return challenges
      .filter((challenge) => (
        challenge.ideaId === current.id
        && challenge.ideaRevision === current.revision
      ))
      .flatMap((challenge): GapSuggestion[] => {
        const question = actionableSelectionQuestion(challenge);
        if (!question) return [];
        if (assumptions.some((assumption) => (
          assumption.originChallengeId === challenge.id
          && assumption.originQuestionId === question.questionId
        ))) return [];
        const statement = SELECTION_CHALLENGE_ASSUMPTIONS[question.questionId];
        return statement ? [{ idea, challenge, question, statement }] : [];
      })
      .sort((left, right) => (
        SELECTION_RISK_PRIORITY[left.question.consensus]
        - SELECTION_RISK_PRIORITY[right.question.consensus]
      ));
  }

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
    return `Evidence review · ${lensLabel(assumption.lens)} · ${SELECTION_CHALLENGE_QUESTION_LABELS[assumption.originQuestionId] ?? assumption.originQuestionId}`;
  }

  async function load() {
    if (!jobId) return;
    loading = true;
    loadError = "";
    loadAnnouncement = "Loading assumptions and evidence gaps…";
    try {
      const [assumptionResponse, challengeResponse] = await Promise.all([
        getSelectionAssumptions(jobId),
        getSelectionChallenges(jobId),
      ]);
      assumptions = assumptionResponse.assumptions;
      challenges = challengeResponse.challenges;
      loadAnnouncement = "Assumptions and evidence gaps loaded.";
    } catch (cause) {
      loadError = cause instanceof Error ? cause.message : "Could not load the assumption map.";
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
      prefillFeedback = { failed: true, message: "Wait for the current assumption save to finish." };
      return;
    }
    if (editor && editorDirty) {
      prefillFeedback = {
        failed: true,
        message: "Your assumption has unsaved changes. Save or close it before reviewing another analyst draft.",
      };
      return;
    }
    const idea = ideas.find((candidate) => (
      candidate.idea_id === request.ideaId
      && Number(candidate.idea_revision) === request.ideaRevision
    ));
    if (!idea) {
      prefillFeedback = { failed: true, message: "This assumption draft references an older candidate revision." };
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
          message: "This assumption changed after the analyst prepared the draft. Refresh and ask again.",
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
            message: "The evidence-check question behind this draft is missing or no longer current.",
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
    prefillFeedback = { failed: false, message: "Analyst draft opened. Review the owner fields before saving." };
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

  function trackSuggestion(suggestion: GapSuggestion) {
    const current = identity(suggestion.idea);
    if (!current) return;
    activeCopilotDraft = null;
    editor = {
      mode: "create",
      assumptionId: null,
      expectedVersion: null,
      ideaId: current.id,
      ideaRevision: current.revision,
      ideaTitle: solutionDisplayTitle(suggestion.idea),
      lens: suggestion.challenge.lens,
      statement: suggestion.statement,
      impactIfFalse: "",
      falsificationQuestion: "",
      impact: "",
      ownerState: "OPEN",
      originChallengeId: suggestion.challenge.id,
      originQuestionId: suggestion.question.questionId,
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
   *  of relying on a silently disabled button. */
  function attemptSaveEditor() {
    if (!canSave) {
      editorSaveAttempted = true;
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
      saveAnnouncement = "Assumption saved.";
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        saveConflict = true;
        saveError = editorMode === "create"
          ? "This evidence-check gap is already tracked or its idea revision changed. Reload the map before continuing."
          : "This assumption changed or its idea revision is no longer current. Reload the map before editing it again.";
      } else {
        saveError = cause instanceof Error ? cause.message : "Could not save the assumption.";
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
      <p class="kicker">Tracked assumptions</p>
      <div class="title-row">
        <h3 id="assumption-map-title">Make the decision hinge visible</h3>
        <DecisionHelp title="Set impact, read the signals" position="bottom">
          <p>Rate each assumption’s impact yourself; evidence direction and class fill in from the linked evidence-check question and concluded experiment outcomes. Test high-impact claims that still read Inference first. Each readout traces one claim’s evidence, not a confidence score. The whole-idea call stays yours.</p>
        </DecisionHelp>
      </div>
      <p>Write what must be true, what failure would change, and the question that could falsify it. No composite score is created.</p>
    </div>
    {#if !loading && !loadError}
      <span class="map-count">{assumptions.filter((item) => !item.stale && item.ownerState === "OPEN").length} open</span>
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
    <div class="map-state"><Loader2 class="spin map-spin" aria-hidden="true" /> Loading assumptions and evidence gaps…</div>
  {:else if loadError}
    <div class="map-state map-error" role="alert">
      <span>{loadError}</span>
      <button type="button" onclick={() => void load()}><RefreshCw aria-hidden="true" /> Retry</button>
    </div>
  {:else}
    <div class="idea-groups">
      {#each ideas as idea, ideaIndex (idea.idea_id ?? `${idea.solution_name}:${ideaIndex}`)}
        {@const current = identity(idea)}
        {@const tracked = assumptionsFor(idea)}
        {@const suggestions = suggestionsFor(idea)}
        <section class="idea-group" aria-labelledby={`assumption-idea-${ideaIndex}`}>
          <header class="idea-head">
            <div>
              <span>Candidate {ideaIndex + 1}{current ? ` · rev ${current.revision}` : ""}</span>
              <h4 id={`assumption-idea-${ideaIndex}`}>{solutionDisplayTitle(idea)}</h4>
            </div>
            <button type="button" class="add-action" disabled={!current || !jobId} onclick={() => openManualCreate(idea)}>
              <Plus aria-hidden="true" /> Track an assumption
            </button>
          </header>

          {#if suggestions.length}
            <aside class="gap-suggestions" aria-label={`Untracked evidence gaps for ${solutionDisplayTitle(idea)}`}>
              <div class="suggestion-heading">
                <strong>Untracked gaps from evidence checks</strong>
                <span>Review before adding; agents do not set owner impact.</span>
              </div>
              {#each suggestions as suggestion (`${suggestion.challenge.id}:${suggestion.question.questionId}`)}
                <article class="suggestion">
                  <div>
                    <span>{lensLabel(suggestion.challenge.lens)} · {SELECTION_CHALLENGE_QUESTION_LABELS[suggestion.question.questionId] ?? suggestion.question.questionId}</span>
                    <p>{suggestion.statement}</p>
                  </div>
                  <button type="button" onclick={() => trackSuggestion(suggestion)}>Track this assumption <ArrowRight aria-hidden="true" /></button>
                </article>
              {/each}
            </aside>
          {/if}

          {#if tracked.length}
            <div class="assumption-list">
              {#each tracked as assumption (assumption.id)}
                <article class="assumption" class:is-stale={assumption.stale} data-annotation-anchor={`selection:assumption:${assumption.id}`}>
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
                  <h5>{assumption.statement}</h5>
                  <dl class="assumption-detail">
                    <div><dt>Impact if false</dt><dd>{assumption.impactIfFalse}</dd></div>
                    <div><dt>Falsification question</dt><dd>{assumption.falsificationQuestion}</dd></div>
                    {#if assumption.direction !== "UNKNOWN"}
                      <div><dt>Evidence direction</dt><dd>{directionLabel(assumption)}</dd></div>
                    {/if}
                    {#if assumption.evidenceClass !== "NONE"}
                      <div><dt>Evidence class</dt><dd>{evidenceClassLabel(assumption)}</dd></div>
                    {/if}
                    {#if assumption.experiments.length}
                      <div><dt>Linked test</dt><dd>{linkedTestLabel(assumption)}</dd></div>
                    {/if}
                    <div><dt>Next action</dt><dd>{nextAction(assumption)}</dd></div>
                  </dl>
                  <footer class="assumption-actions">
                    {#if !assumption.stale}
                      <button type="button" class="text-action" onclick={() => openEdit(assumption, idea)}><Pencil aria-hidden="true" /> Edit owner fields</button>
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
          {:else if !suggestions.length}
            <EmptyState inline title="No assumptions are tracked for this exact candidate yet." />
          {/if}
        </section>
      {/each}
    </div>
  {/if}

  <footer class="map-note">Derived evidence direction can change as immutable evidence is added. It is not an owner-entered confidence rating.</footer>
</section>

<FormOverlay
  open={Boolean(editor)}
  size="form"
  eyebrow={editor?.mode === "edit" ? "Owner judgment" : "Decision hinge"}
  title={editor?.mode === "edit" ? "Edit key assumption" : "Track a key assumption"}
  description={editor ? `${editor.ideaTitle} · rev ${editor.ideaRevision}` : ""}
  annotationAnchor={editor ? `selection:assumption-form:${editor.mode}:${editor.assumptionId ?? `${editor.ideaId}:${editor.ideaRevision}:${editor.originChallengeId ?? "manual"}`}` : undefined}
  onRequestClose={closeEditor}
  dirty={editorDirty}
  closeWarning="You have unsaved changes. Close again to discard them."
  footerMessage="Only your owner fields are saved. Evidence direction stays derived."
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
              <strong>Analyst draft · not saved</strong>
              <span>Review and edit before owner confirmation.</span>
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
            <p class="owner-boundary">The analyst did not choose impact or owner state. Those remain your judgment.</p>
          </aside>
        {:else if editor.originChallengeId && editor.originQuestionId}
          <div class="provenance-note">
            <strong>Suggested by the {lensLabel(editor.lens)} evidence review</strong>
            <span>{SELECTION_CHALLENGE_QUESTION_LABELS[editor.originQuestionId] ?? editor.originQuestionId}</span>
            <p>The source reference is preserved. You still decide the impact and falsification question.</p>
          </div>
        {/if}

        <FormField
          id="assumption-lens"
          kind="select"
          label="Area of uncertainty"
          value={editor.lens}
          disabled={editor.mode === "edit" || Boolean(editor.originChallengeId)}
          onchange={(event) => (editor!.lens = (event.currentTarget as HTMLSelectElement).value as SelectionChallengeLens)}
        >
          {#each SELECTION_CHALLENGE_LENSES as lens}<option value={lens.value}>{lens.label}</option>{/each}
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
          <span class="field-label" id="assumption-impact-label">Owner impact <span class="req">Required</span></span>
          <SegmentControl
            density="card"
            label="Owner impact"
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
            label="Owner state"
            hint="State records your decision handling. It does not change derived evidence direction."
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
  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={saving} onclick={closeEditor}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <SubmitButton
      type="button"
      label={editor?.mode === "edit" ? "Save changes" : "Track key assumption"}
      loadingText="Saving…"
      loading={saving}
      onclick={attemptSaveEditor}
      class="submit-btn"
    />
  {/snippet}
</FormOverlay>

<style>
  .assumption-map { padding: 1.15rem 1.5rem 1rem; background: var(--color-bg-surface); }
  .map-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--color-border-emphasis); }
  .kicker { margin: 0 0 0.28rem; color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
  .title-row { display: flex; align-items: center; gap: 0.55rem; }
  h3, h4, h5, p { margin: 0; }
  .map-head h3 { font-size: 1rem; line-height: 1.3; }
  .map-head > div > p:last-child { max-width: 52rem; margin-top: 0.32rem; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.5; }
  .map-count { flex: 0 0 auto; color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-11); font-weight: 700; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
  .prefill-feedback { margin: 0.75rem 0 0; color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.45; }
  .prefill-feedback.is-error { color: var(--color-error-text); }
  .map-state { display: flex; align-items: center; justify-content: center; gap: 0.5rem; min-height: 16rem; color: var(--color-text-secondary); font-size: var(--text-13); }
  .map-state :global(svg) { width: 0.95rem; height: 0.95rem; }
  .map-error { flex-direction: column; color: var(--color-error-text); }
  .map-error button { display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem; min-height: 2.4rem; padding: 0.45rem 0.75rem; border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: var(--color-bg-elevated); color: var(--color-text-primary); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default); }
  .map-error button:hover { border-color: var(--color-text-secondary); }
  .map-error button:active { transform: scale(0.98); }
  .idea-groups { display: grid; gap: 1.4rem; padding-top: 1rem; }
  .idea-group { min-width: 0; }
  .idea-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; padding-bottom: 0.7rem; }
  .idea-head span { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.06em; }
  .idea-head h4 { margin-top: 0.22rem; font-size: 0.95rem; line-height: 1.35; }
  .add-action, .suggestion button, .test-action, .text-action { display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem; min-height: 2.4rem; border: 0; background: transparent; color: var(--color-accent-dark); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: color var(--duration-fast) var(--ease-default); }
  .add-action:hover:not(:disabled), .suggestion button:hover, .test-action:hover, .text-action:hover:not(:disabled) { color: var(--color-accent-hover); }
  .add-action:active:not(:disabled), .suggestion button:active, .test-action:active, .text-action:active:not(:disabled) { transform: scale(0.98); }
  .add-action :global(svg), .suggestion button :global(svg), .test-action :global(svg), .text-action :global(svg) { width: 0.85rem; height: 0.85rem; }
  .add-action:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); cursor: not-allowed; }
  .gap-suggestions { margin-bottom: 0.8rem; padding: 0.75rem 0.85rem 0.2rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-elevated); }
  .suggestion-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.35rem 1rem; padding-bottom: 0.45rem; }
  .suggestion-heading strong { font-size: var(--text-sm); }
  .suggestion-heading span { color: var(--color-text-secondary); font-size: var(--text-xs); }
  .suggestion { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 1rem; align-items: center; padding: 0.55rem 0; border-top: 1px solid var(--color-border); }
  .suggestion > div > span { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); }
  .suggestion p { margin-top: 0.18rem; font-size: var(--text-sm); line-height: 1.45; }
  .assumption-list { display: grid; gap: 0.7rem; }
  .assumption { padding: 0.9rem 1rem; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-elevated); box-shadow: var(--shadow-sm); }
  /* Staleness reads from the "Older revision" label plus a muted (but AA)
   *  body color — never opacity, which would wash out the whole card. */
  .assumption.is-stale h5, .assumption.is-stale .assumption-detail dd { color: var(--color-text-secondary); }
  .assumption-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
  .assumption-origin { display: grid; gap: 0.2rem; min-width: 0; }
  .assumption-origin span, .assumption-origin strong { color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); line-height: 1.4; }
  .assumption-origin strong { color: var(--color-error-text); }
  .assumption-badges { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.35rem; }
  .assumption-badges span { padding: 0.22rem 0.4rem; border: 1px solid var(--color-border); border-radius: var(--radius-sm); color: var(--color-text-secondary); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; text-transform: uppercase; }
  .assumption-badges .impact--decisive { border-color: color-mix(in srgb, var(--color-error-text) 45%, var(--color-border)); color: var(--color-error-text); }
  .assumption h5 { margin-top: 0.55rem; max-width: 72ch; font-size: var(--text-base); line-height: 1.4; text-wrap: pretty; }
  .assumption-detail { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0.75rem 0 0; border-top: 1px solid var(--color-border); }
  .assumption-detail div { min-width: 0; padding: 0.6rem 0.75rem 0.15rem 0; }
  .assumption-detail dt { color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 600; }
  .assumption-detail dd { margin: 0.2rem 0 0; font-size: var(--text-11); line-height: 1.45; overflow-wrap: anywhere; }
  .assumption-actions { display: flex; align-items: center; gap: 1rem; margin-top: 0.7rem; padding-top: 0.55rem; border-top: 1px solid var(--color-border); }
  .assumption-actions span { display: inline-flex; align-items: center; gap: 0.35rem; color: var(--color-text-secondary); font-size: var(--text-xs); }
  .assumption-actions span :global(svg) { width: 0.8rem; height: 0.8rem; }
  .map-note { padding-top: 0.9rem; color: var(--color-text-secondary); font-size: var(--text-xs); }

  /* ── Overlay form ── */
  .editor { display: grid; gap: 1.3rem; padding: 0.1rem; }
  .field { display: grid; gap: 0.4rem; }
  .field-label { display: flex; align-items: baseline; gap: 0.45rem; font-size: var(--text-13); font-weight: 600; color: var(--color-text-primary); }
  .field-label .req { font-size: var(--text-11); font-weight: 500; color: var(--color-text-secondary); }
  .field-error { margin: 0; color: var(--color-error-text); font-size: var(--text-sm); line-height: 1.4; }
  .provenance-note { display: grid; gap: 0.22rem; padding: 0.75rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .provenance-note strong { font-size: var(--text-sm); }
  .provenance-note span { color: var(--color-text-secondary); font-size: var(--text-sm); }
  .provenance-note p { margin-top: 0.2rem; color: var(--color-text-secondary); font-size: var(--text-sm); }
  .analyst-draft-note { display: grid; gap: 0.65rem; padding: 0.8rem; border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .analyst-draft-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.25rem 1rem; }
  .analyst-draft-heading strong { font-size: var(--text-sm); }
  .analyst-draft-heading span, .analyst-draft-note > p { color: var(--color-text-secondary); font-size: var(--text-sm); line-height: 1.45; }
  .analyst-draft-note dl { display: grid; gap: 0.45rem; margin: 0; }
  .analyst-draft-note dl div { display: grid; grid-template-columns: minmax(8rem, 0.35fr) minmax(0, 1fr); gap: 0.5rem; }
  .analyst-draft-note dt { color: var(--color-text-secondary); font-size: var(--text-xs); font-weight: 600; }
  .analyst-draft-note dd { display: flex; flex-wrap: wrap; gap: 0.3rem; margin: 0; }
  .analyst-draft-note dd span { padding: 0.18rem 0.35rem; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg-elevated); color: var(--color-text-secondary); font-size: var(--text-xs); }
  .analyst-draft-note .owner-boundary { color: var(--color-text-primary); font-weight: 700; }
  .editor-error { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin: 0; padding: 0.7rem; border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background: var(--color-error-subtle); color: var(--color-error-text); font-size: var(--text-sm); }
  .reload-action { display: inline-flex; align-items: center; flex: 0 0 auto; min-height: 2.1rem; border: 0; background: transparent; color: inherit; font: inherit; font-weight: 700; cursor: pointer; text-decoration: underline; text-underline-offset: 0.2em; transition: opacity var(--duration-fast) var(--ease-default); }
  .reload-action:hover { opacity: 0.75; }
  .reload-action:active { transform: scale(0.98); }
  .cancel-btn { display: inline-flex; align-items: center; justify-content: center; min-height: 2.4rem; padding: 0.5rem 0.9rem; border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 600; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .cancel-btn:hover:not(:disabled) { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .cancel-btn:active:not(:disabled) { transform: scale(0.98); }
  .cancel-btn:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: wait; }
  .cancel-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  button:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  :global(.map-spin) { animation: assumption-spin 800ms linear infinite; }
  @keyframes assumption-spin { to { transform: rotate(360deg); } }

  @media (prefers-reduced-motion: reduce) {
    .map-error button:active,
    .add-action:active:not(:disabled),
    .suggestion button:active,
    .test-action:active,
    .text-action:active:not(:disabled),
    .reload-action:active,
    .cancel-btn:active:not(:disabled) {
      transform: none;
    }
  }

  @media (max-width: 720px) {
    .assumption-map { padding: 1rem; }
    .map-head { display: block; }
    .map-count { display: block; margin-top: 0.55rem; }
    .idea-head { align-items: flex-start; }
    .suggestion { grid-template-columns: 1fr; gap: 0.35rem; }
    .suggestion button { justify-content: flex-start; }
    .assumption-top { display: grid; }
    .assumption-badges { justify-content: flex-start; }
    .assumption-detail { grid-template-columns: 1fr; }
    .assumption-detail div { padding-right: 0; padding-bottom: 0.55rem; border-bottom: 1px solid var(--color-border); }
    .assumption-actions { flex-wrap: wrap; }
    .analyst-draft-note dl div { grid-template-columns: 1fr; }
  }
</style>
