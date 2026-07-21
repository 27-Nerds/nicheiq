<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { X } from "lucide-svelte";
  import {
    closeSelectionExperimentRun,
    concludeSelectionExperiment,
    createSelectionExperiment,
    createSelectionIdeaNarrowingProposal,
    getSelectionExperimentResults,
    getSelectionExperiments,
    getSelectionIdeaNarrowingProposal,
    launchSelectionExperiment,
    lockSelectionExperiment,
    updateSelectionExperiment,
    type IdeaSynthesisPatch,
    type SeedResultSummary,
  } from "$lib/api";
  import type { SolutionPreview } from "$lib/types/job";
  import type {
    ExperimentAssumptionType,
    ExperimentConclusionOutcome,
    ExperimentEvidenceSignal,
    ExperimentMethod,
    SelectionExperiment,
    SelectionExperimentDraft,
    SelectionExperimentDraftSeed,
    SelectionExperimentLaunch,
    SelectionExperimentPrefill,
    SelectionExperimentResults,
  } from "$lib/types/selectionExperiment";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";
  import ConfirmGate from "$lib/components/ui/ConfirmGate.svelte";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import WorkspaceOverlay from "$lib/components/ui/WorkspaceOverlay.svelte";
  import {
    DRAFT_TEST_BRIEF_LABEL,
    STRESS_TEST_EVIDENCE_LABEL,
    TOOL_NAMES,
  } from "$lib/selection/labels";
  import {
    SELECTION_CHALLENGE_LENSES,
    SELECTION_CHALLENGE_QUESTION_LABELS,
    selectionChallengeConsensusLabel,
  } from "$lib/utils/selectionRisk";
  import ReshapeProposalPanel from "./ReshapeProposalPanel.svelte";

  interface Props {
    open?: boolean;
    jobId: string;
    ideas: SolutionPreview[];
    prefill?: SelectionExperimentPrefill | null;
    seedCost?: number | null;
    narrowingDisabled?: boolean;
    onEvaluateNarrowing?: (patch: IdeaSynthesisPatch, sourceMessageId: string) => Promise<boolean>;
    onReviewNarrowing?: (
      patch: IdeaSynthesisPatch,
      child: SeedResultSummary,
      sourceMessageId: string,
    ) => { ok: boolean; message?: string };
    onUseNarrowing?: (
      patch: IdeaSynthesisPatch,
      child: SeedResultSummary,
      sourceMessageId: string,
    ) => { ok: boolean; message?: string };
    onChanged?: () => void;
    onClose?: () => void;
    /** Opens the evidence challenge so a test can anchor to a challenged
     *  assumption. Only passed when the challenge workspace is available. */
    onOpenChallenge?: () => void;
  }

  let {
    open = true,
    jobId,
    ideas,
    prefill = null,
    seedCost = null,
    narrowingDisabled = false,
    onEvaluateNarrowing,
    onReviewNarrowing,
    onUseNarrowing,
    onChanged = () => {},
    onClose = () => {},
    onOpenChallenge,
  }: Props = $props();

  const ASSUMPTION_TYPES: Array<{ value: ExperimentAssumptionType; label: string }> = [
    { value: "DESIRABILITY", label: "Desirability" },
    { value: "USABILITY", label: "Usability" },
    { value: "FEASIBILITY", label: "Feasibility" },
    { value: "VIABILITY", label: "Viability" },
    { value: "ETHICS", label: "Ethics / safety" },
  ];
  const METHODS: Array<{ value: ExperimentMethod; label: string }> = [
    { value: "CUSTOMER_INTERVIEWS", label: "Customer interviews" },
    { value: "SURVEY", label: "Survey" },
    { value: "CTA_SMOKE_TEST", label: "CTA smoke test" },
    { value: "BOOKED_CALL", label: "Booked-call test" },
    { value: "PREORDER", label: "Preorder / deposit" },
    { value: "CONCIERGE", label: "Concierge test" },
    { value: "PROTOTYPE", label: "Prototype test" },
    { value: "TECHNICAL_SPIKE", label: "Technical spike" },
    { value: "OTHER", label: "Other" },
  ];
  const SIGNALS: Array<{ value: ExperimentEvidenceSignal; label: string; meaning: string }> = [
    { value: "LANGUAGE", label: "Language / context", meaning: "Shows language and prior behavior, not demand." },
    { value: "STATED_PREFERENCE", label: "Stated preference", meaning: "Shows what people say, not what they will do." },
    { value: "CTA_INTEREST", label: "CTA interest", meaning: "Shows interest in the message or entry point." },
    { value: "SMALL_COMMITMENT", label: "Small commitment", meaning: "Shows a signup, reply, or booked call." },
    { value: "PAYMENT_INTENT", label: "Payment intent", meaning: "Shows stronger willingness and ability to pay." },
    { value: "USAGE", label: "Real usage", meaning: "Shows delivered value or repeat behavior." },
  ];
  const CONCLUSION_OUTCOMES: Array<{
    value: ExperimentConclusionOutcome;
    label: string;
    description: string;
  }> = [
    { value: "PASS", label: "Pass rule met", description: "The observations meet the written pass rule." },
    { value: "FAIL", label: "Fail rule met", description: "The observations meet the written fail rule." },
    { value: "AMBIGUOUS", label: "Neither rule met", description: "The result sits between the written rules or remains inconclusive." },
    { value: "INVALID", label: "Test could not answer the question", description: "Targeting, instrumentation, or execution made the result unusable." },
  ];

  const EMPTY_DRAFT: SelectionExperimentDraft = {
    ideaId: "",
    ideaRevision: 1,
    originChallengeId: null,
    originQuestionId: null,
    assumptionType: "DESIRABILITY",
    assumption: "",
    whyCritical: "",
    currentEvidence: "",
    method: "CTA_SMOKE_TEST",
    evidenceSignal: "CTA_INTEREST",
    stimulus: "",
    audience: "",
    channel: "",
    primaryMetric: "",
    passThreshold: "",
    failThreshold: "",
    measurementWindow: "",
    sampleTarget: null,
    costEstimate: "",
    passAction: "",
    failAction: "",
    flatAction: "",
    invalidAction: "",
  };

  let experiments = $state<SelectionExperiment[]>([]);
  let draft = $state<SelectionExperimentDraft>({ ...EMPTY_DRAFT });
  let editingId = $state<string | null>(null);
  let editing = $state(false);
  let loading = $state(true);
  let saving = $state(false);
  let lockingId = $state<string | null>(null);
  let error = $state("");
  let loadError = $state("");
  let launchId = $state<string | null>(null);
  let launchDraft = $state<SelectionExperimentLaunch>({
    headline: "",
    promise: "",
    ctaLabel: "IM_INTERESTED",
  });
  let launchingId = $state<string | null>(null);
  let closingId = $state<string | null>(null);
  let resultsLoadingId = $state<string | null>(null);
  let copiedId = $state<string | null>(null);
  let copiedBriefId = $state<string | null>(null);
  let resultsById = $state<Record<string, SelectionExperimentResults>>({});
  let appliedPrefillId = $state<string | null>(null);
  let conclusionId = $state<string | null>(null);
  let conclusionOutcome = $state<ExperimentConclusionOutcome | null>(null);
  let conclusionRationale = $state("");
  let observationSummary = $state("");
  let observedAt = $state("");
  let observedSampleSize = $state<number | null>(null);
  let observedMetric = $state("");
  let sourceReferences = $state("");
  let conclusionLimitations = $state("");
  let concludingId = $state<string | null>(null);
  let conclusionErrors = $state<Record<string, string>>({});
  let editorBaseline = $state("");
  let launchBaseline = $state("");
  let resultsAnnouncement = $state("");
  // Candidate held while the switch-away-from-a-dirty-draft confirmation is
  // showing. Cleared by confirming, cancelling, editing the draft further,
  // or saving (see the $effect below and save()).
  let pendingIdea = $state<SolutionPreview | null>(null);
  let candidateConfirmEl = $state<HTMLButtonElement>();
  // The Candidate <select> is bound to its own local state rather than
  // draft.ideaId directly: a plain DOM revert (select.value = ...) gets
  // clobbered on the next Svelte re-render because FormField owns the
  // control's value via its own $bindable local state. Binding this instead
  // keeps the control and the guard's "revert" in the same reactive system.
  let selectedCandidateId = $state(untrack(() => draft.ideaId));
  $effect(() => {
    selectedCandidateId = draft.ideaId;
  });

  const selectedSignal = $derived(SIGNALS.find((signal) => signal.value === draft.evidenceSignal));
  const editorDirty = $derived(JSON.stringify(draft) !== editorBaseline);
  const launchDirty = $derived(JSON.stringify(launchDraft) !== launchBaseline);
  const requiredText = $derived([
    draft.assumption,
    draft.whyCritical,
    draft.stimulus,
    draft.audience,
    draft.channel,
    draft.primaryMetric,
    draft.passThreshold,
    draft.failThreshold,
    draft.measurementWindow,
    draft.passAction,
    draft.failAction,
    draft.flatAction,
    draft.invalidAction,
  ]);
  const canSave = $derived(Boolean(draft.ideaId) && requiredText.every((value) => value.trim().length >= 3));
  const canPublish = $derived(
    launchDraft.headline.trim().length >= 3 && launchDraft.promise.trim().length >= 3,
  );
  const launchExperiment = $derived(experiments.find((item) => item.id === launchId) ?? null);
  const conclusionExperiment = $derived(experiments.find((item) => item.id === conclusionId) ?? null);

  // Inline validation for the 13-field editor: a field's error shows once it
  // has been touched (blurred) or once a save was attempted while it was
  // still invalid. This replaces "the Save button is mysteriously disabled"
  // with a specific, per-field reason.
  type RequiredDraftField =
    | "assumption" | "whyCritical" | "stimulus" | "audience" | "channel"
    | "primaryMetric" | "passThreshold" | "failThreshold" | "measurementWindow"
    | "passAction" | "failAction" | "flatAction" | "invalidAction";
  let touchedDraftFields = $state<Set<RequiredDraftField>>(new Set());
  let editorSubmitAttempted = $state(false);

  function touchDraftField(field: RequiredDraftField) {
    touchedDraftFields.add(field);
    touchedDraftFields = new Set(touchedDraftFields);
  }

  function requiredTextError(value: string): string {
    if (value.trim().length === 0) return "Required.";
    return value.trim().length < 3 ? "Enter at least 3 characters." : "";
  }

  function draftFieldError(field: RequiredDraftField): string {
    if (!editorSubmitAttempted && !touchedDraftFields.has(field)) return "";
    return requiredTextError(draft[field]);
  }

  function resetEditorValidation() {
    touchedDraftFields = new Set();
    editorSubmitAttempted = false;
  }

  /** Submit-attempt entry point: reveals every missing required field instead
   *  of relying on a silently disabled button. */
  function attemptSave() {
    if (!canSave) {
      editorSubmitAttempted = true;
      return;
    }
    void save();
  }

  // Mirrors the 13-field editor's touch/attempt validation for the two-field
  // public launch form: the field's error shows once touched or once a
  // publish was attempted while it was still invalid.
  type RequiredLaunchField = "headline" | "promise";
  let touchedLaunchFields = $state<Set<RequiredLaunchField>>(new Set());
  let launchSubmitAttempted = $state(false);

  function touchLaunchField(field: RequiredLaunchField) {
    touchedLaunchFields.add(field);
    touchedLaunchFields = new Set(touchedLaunchFields);
  }

  function launchFieldError(field: RequiredLaunchField): string {
    if (!launchSubmitAttempted && !touchedLaunchFields.has(field)) return "";
    return requiredTextError(field === "headline" ? launchDraft.headline : launchDraft.promise);
  }

  function resetLaunchValidation() {
    touchedLaunchFields = new Set();
    launchSubmitAttempted = false;
  }

  /** Submit-attempt entry point: reveals per-field errors instead of a
   *  silently disabled Publish button (same reveal-on-attempt pattern as
   *  attemptSave). */
  function attemptPublish() {
    if (!launchExperiment) return;
    if (!canPublish) {
      launchSubmitAttempted = true;
      return;
    }
    void publishRun(launchExperiment);
  }

  onMount(() => {
    void load();
  });

  $effect(() => {
    if (!prefill || prefill.requestId === appliedPrefillId) return;
    reviewCopilotDraft(prefill.requestId, prefill.draft);
  });

  async function load() {
    loading = true;
    loadError = "";
    try {
      experiments = await getSelectionExperiments(jobId);
    } catch (cause) {
      loadError = cause instanceof Error ? cause.message : "Could not load experiment briefs.";
    } finally {
      loading = false;
    }
  }

  function draftForIdea(idea: SolutionPreview): SelectionExperimentDraft {
    const audience = idea.source_segment?.trim() || idea.target_personas?.find(Boolean)?.trim() || "";
    const evidence = idea.source_pain?.trim() || idea.pain_points_addressed?.find(Boolean)?.trim() || "";
    return {
      ...EMPTY_DRAFT,
      ideaId: idea.idea_id ?? idea.solution_name,
      ideaRevision: idea.idea_revision ?? 1,
      assumption: idea.critic_concern?.trim() || "",
      whyCritical: idea.value_proposition?.trim() || "",
      currentEvidence: evidence,
      audience,
      stimulus: `A focused test of ${solutionDisplayTitle(idea)} with one observable next step.`,
    };
  }

  function draftForExperiment(experiment: SelectionExperiment): SelectionExperimentDraft {
    const {
      id: _id,
      jobId: _jobId,
      ideaSnapshot: _snapshot,
      status: _status,
      lockedAt: _lockedAt,
      createdAt: _createdAt,
      updatedAt: _updatedAt,
      originSnapshot: _originSnapshot,
      run: _run,
      conclusion: _conclusion,
      ...values
    } = experiment;
    return { ...values };
  }

  /** Opens a review-only experiment draft. Identity is forced from the current
   *  candidate; supplied values merge into the existing/new baseline and never
   *  replace a dirty editor. Save remains the sole persistence path. */
  export function reviewCopilotDraft(
    requestId: string,
    values: SelectionExperimentDraftSeed,
    record?: { id: string; status?: string },
  ): { ok: boolean; message: string } {
    if (requestId === appliedPrefillId) {
      return { ok: true, message: "This test draft is already open for review." };
    }
    if (saving) return { ok: false, message: "Wait for the current test save to finish." };
    if (editing && JSON.stringify(draft) !== editorBaseline) {
      return {
        ok: false,
        message: "Your test brief has unsaved changes. Save or close it before reviewing another draft.",
      };
    }

    const candidate = ideas.find((idea) =>
      idea.idea_id === values.ideaId
      && Number(idea.idea_revision ?? 1) === values.ideaRevision
    );
    if (!candidate) {
      error = "This test draft references an older candidate revision that is no longer current.";
      return { ok: false, message: error };
    }

    const existing = record ? experiments.find((item) => item.id === record.id) : undefined;
    if (record && (!existing || existing.status !== "DRAFT" || (record.status && record.status !== existing.status))) {
      error = "This saved test is no longer an editable draft. Refresh the analyst suggestion.";
      return { ok: false, message: error };
    }

    const baseline = existing ? draftForExperiment(existing) : draftForIdea(candidate);
    draft = {
      ...baseline,
      ...values,
      ideaId: values.ideaId,
      ideaRevision: values.ideaRevision,
    };
    editingId = existing?.id ?? null;
    error = "";
    editing = true;
    // Baseline the merged prefilled draft, not the pre-merge base: a copilot
    // prefill the owner has not touched must open clean (no discard warning).
    editorBaseline = JSON.stringify(draft);
    launchId = null;
    conclusionId = null;
    appliedPrefillId = requestId;
    resetEditorValidation();
    return { ok: true, message: "Test draft opened. Review every field before saving." };
  }

  function beginNew() {
    const firstIdea = ideas[0];
    if (!firstIdea) return;
    draft = draftForIdea(firstIdea);
    editingId = null;
    error = "";
    editing = true;
    editorBaseline = JSON.stringify(draft);
    launchId = null;
    conclusionId = null;
    resetEditorValidation();
  }

  function edit(experiment: SelectionExperiment) {
    draft = draftForExperiment(experiment);
    editingId = experiment.id;
    error = "";
    editing = true;
    editorBaseline = JSON.stringify(draft);
    launchId = null;
    conclusionId = null;
    resetEditorValidation();
  }

  function chooseIdea(event: Event) {
    const select = event.currentTarget as HTMLSelectElement;
    const ideaId = select.value;
    const idea = ideas.find((candidate) => (candidate.idea_id ?? candidate.solution_name) === ideaId);
    if (!idea) return;
    if (editorDirty) {
      // Revert the control immediately and hold the switch as pending until
      // the inline confirmation below the field is answered.
      selectedCandidateId = draft.ideaId;
      pendingIdea = idea;
      return;
    }
    draft = draftForIdea(idea);
    resetEditorValidation();
  }

  function confirmCandidateSwitch() {
    if (!pendingIdea) return;
    draft = draftForIdea(pendingIdea);
    resetEditorValidation();
    pendingIdea = null;
  }

  function cancelCandidateSwitch() {
    pendingIdea = null;
  }

  // Any further draft edit (a keystroke, a field blur-triggered mutation)
  // supersedes a pending candidate switch: the owner has chosen to keep
  // working on the current draft instead of answering the prompt.
  // `lastDraftJSON` is a plain (non-reactive) variable so this effect only
  // depends on `draft`, not on `pendingIdea` itself — reading `pendingIdea`
  // here would make setting it in chooseIdea() re-trigger this same effect
  // and immediately clear the value it just set.
  let lastDraftJSON = untrack(() => JSON.stringify(draft));
  $effect(() => {
    const json = JSON.stringify(draft);
    if (json !== lastDraftJSON) {
      lastDraftJSON = json;
      pendingIdea = null;
    }
  });

  $effect(() => {
    if (pendingIdea) candidateConfirmEl?.focus();
  });

  async function save() {
    if (!canSave || saving) return;
    pendingIdea = null;
    saving = true;
    error = "";
    try {
      const experiment = editingId
        ? await updateSelectionExperiment(jobId, editingId, draft)
        : await createSelectionExperiment(jobId, draft);
      experiments = [experiment, ...experiments.filter((item) => item.id !== experiment.id)];
      editing = false;
      editingId = null;
      onChanged();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not save the experiment brief.";
    } finally {
      saving = false;
    }
  }

  async function lock(experimentId: string) {
    lockingId = experimentId;
    error = "";
    try {
      const locked = await lockSelectionExperiment(jobId, experimentId);
      experiments = experiments.map((item) => item.id === locked.id ? locked : item);
      onChanged();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not lock the experiment brief.";
    } finally {
      lockingId = null;
    }
  }

  function canHost(experiment: SelectionExperiment): boolean {
    return experiment.status === "LOCKED"
      && experiment.method === "CTA_SMOKE_TEST"
      && experiment.evidenceSignal === "CTA_INTEREST";
  }

  function beginLaunch(experiment: SelectionExperiment) {
    const snapshot = experiment.ideaSnapshot;
    launchDraft = {
      headline: String(snapshot.headline || snapshot.solution_name || experiment.ideaId),
      promise: String(snapshot.value_proposition || experiment.stimulus),
      ctaLabel: "IM_INTERESTED",
    };
    launchId = experiment.id;
    editing = false;
    conclusionId = null;
    error = "";
    launchBaseline = JSON.stringify(launchDraft);
    resetLaunchValidation();
  }

  async function publishRun(experiment: SelectionExperiment) {
    launchingId = experiment.id;
    error = "";
    try {
      const run = await launchSelectionExperiment(jobId, experiment.id, launchDraft);
      experiments = experiments.map((item) => item.id === experiment.id ? { ...item, run } : item);
      launchId = null;
      await refreshResults(experiment.id);
      onChanged();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "The test wasn’t published. Nothing is live.";
    } finally {
      launchingId = null;
    }
  }

  async function refreshResults(experimentId: string): Promise<boolean> {
    resultsLoadingId = experimentId;
    error = "";
    try {
      const result = await getSelectionExperimentResults(jobId, experimentId);
      resultsById[experimentId] = result;
      resultsAnnouncement = `Results loaded: ${result.exposures} exposures, ${result.ctaClicks} CTA actions.`;
      return true;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Results are temporarily unavailable.";
      resultsAnnouncement = "Results could not be loaded.";
      return false;
    } finally {
      resultsLoadingId = null;
    }
  }

  function resetConclusionDraft() {
    conclusionOutcome = null;
    conclusionRationale = "";
    observationSummary = "";
    observedAt = new Date().toISOString().slice(0, 10);
    observedSampleSize = null;
    observedMetric = "";
    sourceReferences = "";
    conclusionLimitations = "";
  }

  async function beginConclusion(experiment: SelectionExperiment) {
    conclusionErrors[experiment.id] = "";
    if (experiment.run?.status === "ACTIVE") {
      conclusionErrors[experiment.id] = "Close collection before recording an outcome.";
      return;
    }
    if (experiment.run && !resultsById[experiment.id]) {
      const loaded = await refreshResults(experiment.id);
      if (!loaded) {
        conclusionErrors[experiment.id] = "Observations are unavailable. Retry before recording an outcome.";
        return;
      }
    }
    resetConclusionDraft();
    conclusionId = experiment.id;
    editing = false;
    launchId = null;
  }

  function nextActionFor(experiment: SelectionExperiment): string {
    switch (conclusionOutcome) {
      case "PASS": return experiment.passAction;
      case "FAIL": return experiment.failAction;
      case "AMBIGUOUS": return experiment.flatAction;
      case "INVALID": return experiment.invalidAction;
      default: return "";
    }
  }

  function canSaveConclusion(experiment: SelectionExperiment): boolean {
    if (!conclusionOutcome || conclusionRationale.trim().length < 3) return false;
    if (!experiment.run && (observationSummary.trim().length < 3 || !observedAt)) return false;
    return true;
  }

  function outcomeUnavailable(
    experiment: SelectionExperiment,
    outcome: ExperimentConclusionOutcome,
  ): boolean {
    return Boolean(
      experiment.run
      && resultsById[experiment.id]?.dataQualityWarning
      && (outcome === "PASS" || outcome === "FAIL"),
    );
  }

  async function saveConclusion(experiment: SelectionExperiment) {
    if (!canSaveConclusion(experiment) || concludingId) return;
    concludingId = experiment.id;
    conclusionErrors[experiment.id] = "";
    try {
      const limitations = conclusionLimitations
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
      const conclusion = await concludeSelectionExperiment(
        jobId,
        experiment.id,
        experiment.run
          ? {
              evidenceSource: "HOSTED_RUN",
              outcome: conclusionOutcome!,
              ownerRationale: conclusionRationale,
              limitations,
            }
          : {
              evidenceSource: "MANUAL",
              outcome: conclusionOutcome!,
              ownerRationale: conclusionRationale,
              observationSummary,
              observedAt,
              sampleSize: observedSampleSize,
              observedMetric,
              sourceReferences: sourceReferences
                .split("\n")
                .map((item) => item.trim())
                .filter(Boolean),
              limitations,
            },
      );
      experiments = experiments.map((item) =>
        item.id === experiment.id ? { ...item, conclusion } : item
      );
      conclusionId = null;
      onChanged();
    } catch (cause) {
      conclusionErrors[experiment.id] = cause instanceof Error
        ? cause.message
        : "The conclusion could not be saved. Your entries are still here.";
    } finally {
      concludingId = null;
    }
  }

  async function closeRun(experiment: SelectionExperiment) {
    closingId = experiment.id;
    error = "";
    try {
      const run = await closeSelectionExperimentRun(jobId, experiment.id);
      experiments = experiments.map((item) => item.id === experiment.id ? { ...item, run } : item);
      await refreshResults(experiment.id);
      onChanged();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "The test could not be closed.";
    } finally {
      closingId = null;
    }
  }

  async function copyTestLink(experiment: SelectionExperiment) {
    if (!experiment.run) return;
    try {
      const url = new URL(`/validate/${experiment.run.publicToken}`, window.location.origin).href;
      await navigator.clipboard.writeText(url);
      copiedId = experiment.id;
      window.setTimeout(() => {
        if (copiedId === experiment.id) copiedId = null;
      }, 2_000);
    } catch {
      error = "Could not copy the test link.";
    }
  }

  async function copyBrief(experiment: SelectionExperiment) {
    try {
      const response = await fetch(
        `/api/jobs/${jobId}/selection-experiments/${experiment.id}/export/md`,
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "Could not load the locked test brief.");
      }
      await navigator.clipboard.writeText(await response.text());
      copiedBriefId = experiment.id;
      window.setTimeout(() => {
        if (copiedBriefId === experiment.id) copiedBriefId = null;
      }, 2_000);
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not copy the test brief.";
    }
  }

  function runLabel(experiment: SelectionExperiment): string {
    if (experiment.conclusion) return "Concluded";
    if (experiment.run?.status === "ACTIVE") return "Still collecting";
    if (experiment.run?.status === "CLOSED") return "Run closed";
    return experiment.status === "DRAFT" ? "Draft · not collecting" : "Test brief locked";
  }

  function conclusionLabel(outcome: ExperimentConclusionOutcome): string {
    return CONCLUSION_OUTCOMES.find((item) => item.value === outcome)?.label ?? outcome;
  }

  function formatRate(value: number | null): string {
    return value === null ? "N/A" : `${(value * 100).toFixed(1)}%`;
  }

  function experimentTitle(experiment: SelectionExperiment): string {
    const snapshot = experiment.ideaSnapshot;
    return String(snapshot.headline || snapshot.solution_name || experiment.ideaId);
  }

  function labelFor<T extends string>(items: Array<{ value: T; label: string }>, value: T): string {
    return items.find((item) => item.value === value)?.label ?? value;
  }

  function originQuestion(experiment: SelectionExperiment): string {
    const questionId = experiment.originSnapshot?.questionId ?? experiment.originQuestionId;
    return questionId ? SELECTION_CHALLENGE_QUESTION_LABELS[questionId] ?? questionId : "Manual test brief";
  }

  function originLens(experiment: SelectionExperiment): string {
    const lens = experiment.originSnapshot?.lens;
    return lens ? SELECTION_CHALLENGE_LENSES.find((item) => item.value === lens)?.label ?? lens : "Owner drafted";
  }

  function conclusionIsDirty() {
    return Boolean(
      conclusionOutcome
      || conclusionRationale.trim()
      || observationSummary.trim()
      || observedMetric.trim()
      || sourceReferences.trim()
      || conclusionLimitations.trim()
      || observedSampleSize,
    );
  }

  /** Confirmed close: FormOverlay owns the dirty two-press gate. */
  function closeEditor() {
    if (saving) return;
    editing = false;
    editingId = null;
    error = "";
    resetEditorValidation();
  }

  function closeLaunch() {
    if (launchingId) return;
    launchId = null;
    error = "";
    resetLaunchValidation();
  }

  function closeConclusion() {
    if (concludingId) return;
    const wasOpen = conclusionExperiment;
    conclusionId = null;
    if (wasOpen) conclusionErrors[wasOpen.id] = "";
  }
</script>

<WorkspaceOverlay {open} size="wide" label="Test decision assumptions" {onClose}>
<section id="selection-experiments" class="workspace" aria-labelledby="experiments-title" data-annotation-anchor="selection:experiments" tabindex="-1">
  <header class="workspace-head">
    <div>
      <p class="kicker">Next-best test</p>
      <h3 id="experiments-title">Test what could change the decision</h3>
      <p>Define one risky assumption, a behavioral signal, and the outcome rules before collecting results.</p>
    </div>
    <div class="workspace-actions">
      {#if !editing}
        <button type="button" class="new-action" onclick={beginNew} disabled={!ideas.length}>{DRAFT_TEST_BRIEF_LABEL}</button>
      {/if}
      <button type="button" class="close-action" aria-label="Close test workspace" onclick={onClose}>
        <X aria-hidden="true" />
      </button>
    </div>
  </header>

  <p class="sr-only" role="status">{resultsAnnouncement}</p>

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if loadError}
    <div class="load-error" role="alert">
      <div>
        <strong>Tests are temporarily unavailable.</strong>
        <span>Your shortlist and Deep Research are unaffected.</span>
      </div>
      <button type="button" onclick={() => void load()}>Retry</button>
    </div>
  {/if}

  {#if loading}
    <p class="empty" role="status">Loading experiment briefs…</p>
  {:else if !loadError && !editing && experiments.length === 0}
    <EmptyState
      title="No test briefs yet"
      description="The strongest tests anchor to an assumption a challenge already exposed. Stress-test the evidence first, then draft the brief from the gap it finds."
    >
      {#if onOpenChallenge}
        <button type="button" class="empty-primary" onclick={onOpenChallenge}>{STRESS_TEST_EVIDENCE_LABEL}</button>
      {/if}
      <button type="button" class="empty-secondary" onclick={beginNew} disabled={!ideas.length}>{DRAFT_TEST_BRIEF_LABEL}</button>
    </EmptyState>
  {/if}

  {#if !editing && experiments.length > 0}
    <div class="experiment-list">
      {#each experiments as experiment (experiment.id)}
        <article
          class="experiment-row"
          aria-busy={launchingId === experiment.id || closingId === experiment.id || concludingId === experiment.id}
        >
          <div class="experiment-main">
            <div class="row-meta">
              <span
                class:locked={experiment.status !== "DRAFT"}
                class:active={experiment.run?.status === "ACTIVE"}
              >{runLabel(experiment)}</span>
              <span>{labelFor(ASSUMPTION_TYPES, experiment.assumptionType)}</span>
              <span>Revision {experiment.ideaRevision}</span>
              {#if experiment.originChallengeId}<span>From evidence check</span>{/if}
            </div>
            <h4>{experimentTitle(experiment)}</h4>
            <p>{experiment.assumption}</p>
          </div>
          <dl class="experiment-rule">
            <div><dt>Signal</dt><dd>{labelFor(SIGNALS, experiment.evidenceSignal)}</dd></div>
            <div><dt>Pass</dt><dd>{experiment.passThreshold}</dd></div>
            <div><dt>Stop</dt><dd>{experiment.measurementWindow}</dd></div>
          </dl>
          <div class="row-actions">
            {#if experiment.conclusion}
              <span class="locked-note">Read-only owner record</span>
            {:else if experiment.status === "DRAFT"}
              <button type="button" class="text-action" onclick={() => edit(experiment)}>Edit</button>
              <ConfirmGate
                variant="free"
                label="Lock brief"
                confirmLabel="Lock brief"
                consequence="BECOMES IMMUTABLE"
                busy={lockingId === experiment.id}
                onConfirm={() => void lock(experiment.id)}
              />
            {:else if !experiment.run}
              {#if canHost(experiment)}
                <button type="button" onclick={() => beginLaunch(experiment)}>Set up public test</button>
              {/if}
              <button type="button" onclick={() => void beginConclusion(experiment)}>Record external result</button>
            {:else}
              {#if experiment.run.status === "ACTIVE"}
                <a class="text-action action-link" href={`/validate/${experiment.run.publicToken}`} target="_blank" rel="noreferrer">Open test<span class="sr-only"> (opens in new tab)</span></a>
                <button type="button" class="text-action" onclick={() => void copyTestLink(experiment)}>
                  {copiedId === experiment.id ? "Copied" : "Copy link"}
                </button>
              {/if}
              <button
                type="button"
                class="text-action"
                disabled={resultsLoadingId === experiment.id}
                onclick={() => void refreshResults(experiment.id)}
              >{resultsLoadingId === experiment.id ? "Refreshing…" : "View results"}</button>
              {#if experiment.run.status === "ACTIVE"}
                <ConfirmGate
                  variant="free"
                  label="Close run"
                  confirmLabel="Close run"
                  consequence="COLLECTION ENDS"
                  busy={closingId === experiment.id}
                  onConfirm={() => void closeRun(experiment)}
                />
              {:else}
                <button type="button" onclick={() => void beginConclusion(experiment)}>Review and record outcome</button>
              {/if}
            {/if}
          </div>
          {#if conclusionErrors[experiment.id]}
            <p class="row-error" role="alert">{conclusionErrors[experiment.id]}</p>
          {/if}

          {#if experiment.status === "LOCKED"}
            <details class="brief-export">
              <summary>View portable test brief</summary>
              <div class="brief-export-body">
                <p><strong>{originQuestion(experiment)}</strong><span>{originLens(experiment)} · candidate revision {experiment.ideaRevision}</span></p>
                {#if experiment.originSnapshot}
                  <p class="origin-status">Evidence review recorded {selectionChallengeConsensusLabel(experiment.originSnapshot.consensus)} with {experiment.originSnapshot.citedSources.length} cited source{experiment.originSnapshot.citedSources.length === 1 ? "" : "s"}.</p>
                {/if}
                <div class="brief-export-actions">
                  <button type="button" class="text-action" onclick={() => void copyBrief(experiment)}>
                    {copiedBriefId === experiment.id ? "Markdown copied" : "Copy Markdown"}
                  </button>
                  <a href={`/api/jobs/${jobId}/selection-experiments/${experiment.id}/export/md`}>Download .md</a>
                  <a href={`/api/jobs/${jobId}/selection-experiments/${experiment.id}/export/json`}>Download JSON</a>
                </div>
              </div>
            </details>
          {/if}

          {#if resultsById[experiment.id]}
            {@const result = resultsById[experiment.id]}
            <section class="results-sheet" aria-label="Test observations">
              <dl class="result-ledger">
                <div><dt>Exposures</dt><dd>{result.exposures}</dd></div>
                <div><dt>CTA actions</dt><dd>{result.ctaClicks}</dd></div>
                <div><dt>Observed rate</dt><dd>{result.ctaClicks} / {result.exposures} · {formatRate(result.ctaRate)}</dd></div>
                <div><dt>Stopping progress</dt><dd>{result.sampleTarget ? `${result.exposures} of ${result.sampleTarget}` : "No numeric target"}</dd></div>
              </dl>
              <p class="result-status">
                {#if result.runStatus === "ACTIVE"}
                  {result.sampleTarget && result.exposures < result.sampleTarget
                    ? `Still collecting: ${result.exposures} of ${result.sampleTarget} exposures. Wait for the stopping rule before concluding.`
                    : "Still collecting. Close the run only at the precommitted stopping rule."}
                {:else}
                  Run closed. Compare the observed numerator and denominator with the written rule before changing the shortlist.
                {/if}
              </p>
              <p class="signal-note"><strong>Scope:</strong> A CTA click shows interest in this exact promise, placement, audience, channel, and time. It does not prove willingness to pay, satisfaction, retention, or market size.</p>
              {#if result.dataQualityWarning}<p class="error" role="alert">{result.dataQualityWarning}</p>{/if}
            </section>
          {/if}

          {#if experiment.conclusion}
            <section class="conclusion-summary" aria-label="Your conclusion">
              <div class="conclusion-heading">
                <div>
                  <p class="kicker">Your conclusion</p>
                  <h5>{conclusionLabel(experiment.conclusion.outcome)}</h5>
                </div>
                <span>Idea revision {experiment.conclusion.ideaRevision} · {new Date(experiment.conclusion.createdAt).toLocaleDateString()}</span>
              </div>
              <dl>
                <div>
                  <dt>Precommitted next action</dt>
                  <dd>{experiment.conclusion.nextActionSnapshot}</dd>
                </div>
                <div>
                  <dt>Why the evidence fits</dt>
                  <dd>{experiment.conclusion.ownerRationale}</dd>
                </div>
              </dl>
              <p class="conclusion-scope">This records the owner’s interpretation of one test. It does not validate the idea or change its research score.</p>
              {#if onEvaluateNarrowing && (experiment.conclusion.outcome === "FAIL" || experiment.conclusion.outcome === "AMBIGUOUS")}
                <ReshapeProposalPanel
                  source={{ kind: "experiment", experiment }}
                  {seedCost}
                  disabled={narrowingDisabled}
                  createProposal={() => createSelectionIdeaNarrowingProposal(jobId, experiment.id)}
                  fetchProposal={() => getSelectionIdeaNarrowingProposal(jobId, experiment.id)}
                  onEvaluate={onEvaluateNarrowing}
                  onReview={onReviewNarrowing}
                  onUse={onUseNarrowing}
                />
              {/if}
            </section>
          {/if}
        </article>
      {/each}
    </div>
  {/if}

</section>
</WorkspaceOverlay>

<FormOverlay
  open={editing}
  size="wizard"
  eyebrow="Next-best test"
  title={editingId ? "Edit test plan" : TOOL_NAMES.test}
  description="Define the question, signal, and outcome rules before results can influence your decision."
  annotationAnchor={editingId ? `selection:experiment:${editingId}:edit` : "selection:experiment:draft:edit"}
  onRequestClose={closeEditor}
  dirty={editorDirty}
  closeWarning="You have unsaved changes. Close again to discard them."
  footerMessage="Saving keeps this editable. Nothing is published or collecting responses yet."
>
  <form id="experiment-editor-form" class="experiment-form" onsubmit={(event) => { event.preventDefault(); attemptSave(); }}>
    <DecisionHelp title="Decide the rules before the data" label="Precommitment">
      Set the audience, metric, thresholds, stopping rule, and next actions while no result can sway them. Lock the brief once every field is final. It becomes the fixed contract your evidence is judged against, and the gate every run, export, and conclusion passes through.
    </DecisionHelp>
    {#if draft.originChallengeId && draft.originQuestionId}
      <aside class="origin-strip">
        <span>Evidence gap</span>
        <strong>{SELECTION_CHALLENGE_QUESTION_LABELS[draft.originQuestionId] ?? draft.originQuestionId}</strong>
        <small>Drafted from a current evidence check for candidate revision {draft.ideaRevision}. This origin cannot be changed.</small>
      </aside>
    {/if}
    <fieldset>
      <legend>1. Decision risk</legend>
      <div class="field-grid two">
        <FormField
          id="experiment-candidate"
          kind="select"
          label="Candidate"
          bind:value={selectedCandidateId}
          onchange={chooseIdea}
          disabled={Boolean(editingId)}
        >
          {#each ideas as idea (idea.idea_id ?? idea.solution_name)}<option value={idea.idea_id ?? idea.solution_name}>{solutionDisplayTitle(idea)} · rev {idea.idea_revision ?? 1}</option>{/each}
        </FormField>
        <FormField id="experiment-assumption-type" kind="select" label="Assumption type" bind:value={draft.assumptionType}>
          {#each ASSUMPTION_TYPES as option}<option value={option.value}>{option.label}</option>{/each}
        </FormField>
      </div>
      {#if pendingIdea}
        <div class="candidate-confirm" role="alert">
          <p>Switching to {solutionDisplayTitle(pendingIdea)} replaces every field below with its starting values. Your current entries will be lost.</p>
          <div class="candidate-confirm-actions">
            <button type="button" class="candidate-confirm-cancel" onclick={cancelCandidateSwitch}>Keep editing</button>
            <button
              type="button"
              class="candidate-confirm-confirm"
              bind:this={candidateConfirmEl}
              onclick={confirmCandidateSwitch}
            >Discard draft and switch</button>
          </div>
        </div>
      {/if}
      <FormField
        id="experiment-assumption"
        kind="textarea"
        label="One atomic assumption that must be true"
        required
        bind:value={draft.assumption}
        rows={2}
        maxlength={1000}
        placeholder="Qualified buyers will…"
        error={draftFieldError("assumption")}
        onblur={() => touchDraftField("assumption")}
      />
      <div class="field-grid two">
        <FormField
          id="experiment-why-critical"
          kind="textarea"
          label="Why failure changes the decision"
          required
          bind:value={draft.whyCritical}
          rows={3}
          maxlength={1500}
          error={draftFieldError("whyCritical")}
          onblur={() => touchDraftField("whyCritical")}
        />
        <FormField
          id="experiment-current-evidence"
          kind="textarea"
          label="What the research currently supports"
          optional
          bind:value={draft.currentEvidence}
          rows={3}
          maxlength={2000}
        />
      </div>
    </fieldset>
    <fieldset>
      <legend>2. Test and evidence signal</legend>
      <div class="field-grid three">
        <FormField id="experiment-method" kind="select" label="Method" bind:value={draft.method}>
          {#each METHODS as option}<option value={option.value}>{option.label}</option>{/each}
        </FormField>
        <FormField id="experiment-evidence-signal" kind="select" label="What this result can show" bind:value={draft.evidenceSignal}>
          {#each SIGNALS as option}<option value={option.value}>{option.label}</option>{/each}
        </FormField>
        <FormField
          id="experiment-cost-estimate"
          label="Estimated cost"
          optional
          bind:value={draft.costEstimate}
          maxlength={255}
          placeholder="Under $300"
        />
      </div>
      <p class="signal-note"><strong>Scope:</strong> {selectedSignal?.meaning}</p>
      <FormField
        id="experiment-stimulus"
        kind="textarea"
        label="Exact stimulus, offer, prototype, or task"
        required
        bind:value={draft.stimulus}
        rows={2}
        maxlength={1500}
        error={draftFieldError("stimulus")}
        onblur={() => touchDraftField("stimulus")}
      />
      <div class="field-grid two">
        <FormField
          id="experiment-audience"
          kind="textarea"
          label="Qualified audience"
          required
          bind:value={draft.audience}
          rows={2}
          maxlength={1000}
          error={draftFieldError("audience")}
          onblur={() => touchDraftField("audience")}
        />
        <FormField
          id="experiment-channel"
          kind="textarea"
          label="Recruitment or traffic channel"
          required
          bind:value={draft.channel}
          rows={2}
          maxlength={500}
          error={draftFieldError("channel")}
          onblur={() => touchDraftField("channel")}
        />
      </div>
    </fieldset>
    <fieldset>
      <legend>3. Precommitment</legend>
      <FormField
        id="experiment-primary-metric"
        label="Primary behavioral metric, including numerator and denominator"
        required
        bind:value={draft.primaryMetric}
        maxlength={500}
        error={draftFieldError("primaryMetric")}
        onblur={() => touchDraftField("primaryMetric")}
      />
      <div class="field-grid two">
        <FormField
          id="experiment-pass-threshold"
          label="Pass at"
          required
          bind:value={draft.passThreshold}
          maxlength={500}
          placeholder="At least…"
          error={draftFieldError("passThreshold")}
          onblur={() => touchDraftField("passThreshold")}
        />
        <FormField
          id="experiment-fail-threshold"
          label="Fail below"
          required
          bind:value={draft.failThreshold}
          maxlength={500}
          placeholder="Below…"
          error={draftFieldError("failThreshold")}
          onblur={() => touchDraftField("failThreshold")}
        />
      </div>
      <div class="field-grid two">
        <FormField
          id="experiment-measurement-window"
          label="Measurement window and stopping rule"
          required
          bind:value={draft.measurementWindow}
          maxlength={500}
          error={draftFieldError("measurementWindow")}
          onblur={() => touchDraftField("measurementWindow")}
        />
        <label><span>Target sample or exposures <small>optional</small></span><input type="number" min="1" max="1000000" bind:value={draft.sampleTarget} /></label>
      </div>
    </fieldset>
    <fieldset>
      <legend>4. Decide before results</legend>
      <div class="field-grid two">
        <FormField
          id="experiment-pass-action"
          kind="textarea"
          label="If it passes"
          required
          bind:value={draft.passAction}
          rows={2}
          maxlength={1000}
          error={draftFieldError("passAction")}
          onblur={() => touchDraftField("passAction")}
        />
        <FormField
          id="experiment-fail-action"
          kind="textarea"
          label="If it fails"
          required
          bind:value={draft.failAction}
          rows={2}
          maxlength={1000}
          error={draftFieldError("failAction")}
          onblur={() => touchDraftField("failAction")}
        />
        <FormField
          id="experiment-flat-action"
          kind="textarea"
          label="If it is flat"
          required
          bind:value={draft.flatAction}
          rows={2}
          maxlength={1000}
          error={draftFieldError("flatAction")}
          onblur={() => touchDraftField("flatAction")}
        />
        <FormField
          id="experiment-invalid-action"
          kind="textarea"
          label="If it is invalid"
          required
          bind:value={draft.invalidAction}
          rows={2}
          maxlength={1000}
          error={draftFieldError("invalidAction")}
          onblur={() => touchDraftField("invalidAction")}
        />
      </div>
    </fieldset>
  </form>
  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={saving} onclick={closeEditor}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <div class="footer-submit">
      {#if error}<p class="form-error" role="alert">{error}</p>{/if}
      <SubmitButton
        type="button"
        label={editingId ? "Save changes" : "Save draft"}
        loadingText="Saving…"
        loading={saving}
        onclick={attemptSave}
        class="submit-btn"
      />
    </div>
  {/snippet}
</FormOverlay>

  <FormOverlay
    open={Boolean(launchExperiment)}
    size="form"
  title="Set up public test"
  eyebrow="Public artifact"
  description="Review exactly what participants will see before publishing an immutable run."
  annotationAnchor={launchExperiment ? `selection:experiment:${launchExperiment.id}:launch` : undefined}
  onRequestClose={closeLaunch}
  dirty={launchDirty}
  closeWarning="You have unsaved changes. Close again to discard them."
  footerMessage="Publishing freezes this public artifact. A changed offer requires a new brief."
>
  {#if launchExperiment}
    <form id="experiment-launch-form" class="launch-sheet" onsubmit={(event) => { event.preventDefault(); attemptPublish(); }}>
      <DecisionHelp title="Your copy is the whole test" label="Public scope">
        Write the headline and promise as a live offer. Participants judge this page at face value, so the click rate measures exactly the words you publish here. Responses stay anonymous: no account, email, or payment is ever collected, which keeps the interest signal honest.
      </DecisionHelp>
      <p class="overlay-explanation">Participants see only this offer and action, not your hypothesis, scores, thresholds, or founder constraints.</p>
      <label>
        <span>Headline <small>required</small></span>
        <input
          bind:value={launchDraft.headline}
          maxlength="140"
          aria-required="true"
          aria-invalid={launchFieldError("headline") ? "true" : undefined}
          onblur={() => touchLaunchField("headline")}
        />
        {#if launchFieldError("headline")}<p class="form-error" role="alert">{launchFieldError("headline")}</p>{/if}
      </label>
      <label>
        <span>Support sentence <small>required</small></span>
        <textarea
          bind:value={launchDraft.promise}
          rows="3"
          maxlength="1000"
          aria-required="true"
          aria-invalid={launchFieldError("promise") ? "true" : undefined}
          onblur={() => touchLaunchField("promise")}
        ></textarea>
        {#if launchFieldError("promise")}<p class="form-error" role="alert">{launchFieldError("promise")}</p>{/if}
      </label>
      <label><span>Interest action</span><select bind:value={launchDraft.ctaLabel}><option value="IM_INTERESTED">I’m interested</option><option value="SHOW_ME_THE_CONCEPT">Show me the concept</option><option value="ID_TRY_THIS">I’d try this</option></select></label>
      <p class="signal-note"><strong>After the click:</strong> NicheIQ immediately explains that this is a concept test.</p>
    </form>
  {/if}
  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={Boolean(launchingId)} onclick={closeLaunch}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <div class="footer-submit">
      {#if error}<p class="form-error" role="alert">{error}</p>{/if}
      <SubmitButton
        type="button"
        label="Publish test"
        loadingText="Publishing test…"
        loading={Boolean(launchingId)}
        disabled={!launchExperiment}
        onclick={attemptPublish}
        class="submit-btn"
      />
    </div>
  {/snippet}
</FormOverlay>

<FormOverlay
  open={Boolean(conclusionExperiment)}
  size="wizard"
  title="Record test conclusion"
  eyebrow="Test conclusion"
  description="Compare the observations with the rules you locked before choosing an outcome."
  annotationAnchor={conclusionExperiment ? `selection:experiment:${conclusionExperiment.id}:conclusion` : undefined}
  onRequestClose={closeConclusion}
  dirty={conclusionIsDirty()}
  closeWarning="You have unsaved changes. Close again to discard them."
  footerMessage="This conclusion becomes read-only and stays attached to this exact idea revision."
>
  {#if conclusionExperiment}
    <form id="experiment-conclusion-form" class="conclusion-sheet" onsubmit={(event) => { event.preventDefault(); void saveConclusion(conclusionExperiment); }}>
      <DecisionHelp title="Trigger the plan you already wrote" label="Conclusion scope">
        Record the outcome, and the next action you committed before the test comes with it. Hindsight can’t swap in a friendlier plan. NicheIQ seals the evidence and your rationale into one permanent receipt. The idea’s research score stays untouched: this record is your judgment layer.
      </DecisionHelp>
      {#if !conclusionExperiment.run}
        <fieldset class="manual-evidence">
          <legend>1. Observed evidence</legend>
          <label><span>Observed result <small>required</small></span><textarea bind:value={observationSummary} rows="3" maxlength="3000" placeholder="Describe the concrete behavior, numerator and denominator, or technical finding." aria-required="true" aria-invalid={observationSummary.trim().length < 3 ? "true" : undefined}></textarea></label>
          <div class="field-grid three">
            <label><span>Observed on <small>required</small></span><input type="date" bind:value={observedAt} aria-required="true" aria-invalid={observedAt ? undefined : "true"} /></label>
            <label><span>Sample size <small>optional</small></span><input type="number" min="1" max="1000000" bind:value={observedSampleSize} /></label>
            <label><span>Observed metric <small>optional</small></span><input bind:value={observedMetric} maxlength="500" placeholder="3 of 12 booked a call" /></label>
          </div>
          <label><span>Evidence links or references <small>optional, one per line</small></span><textarea bind:value={sourceReferences} rows="2" maxlength="5000" placeholder="Interview notes / July cohort"></textarea></label>
        </fieldset>
      {/if}
      <fieldset class="outcome-fieldset">
        <legend>{conclusionExperiment.run ? "1" : "2"}. Which written rule fits?</legend>
        <div class="outcome-picker">
          <SegmentControl
            density="card"
            label="Which written rule fits?"
            options={CONCLUSION_OUTCOMES.map((option) => ({
              ...option,
              disabled: outcomeUnavailable(conclusionExperiment, option.value),
            }))}
            value={conclusionOutcome ?? ""}
            onChange={(value) => (conclusionOutcome = value as ExperimentConclusionOutcome)}
          />
        </div>
      </fieldset>
      <fieldset>
        <legend>{conclusionExperiment.run ? "2" : "3"}. Owner rationale</legend>
        <label><span>Why this outcome fits the written rule <small>required</small></span><textarea bind:value={conclusionRationale} rows="3" maxlength="2000" aria-required="true" aria-invalid={conclusionRationale.trim().length < 3 ? "true" : undefined}></textarea></label>
        <label><span>Limitations <small>optional, one per line</small></span><textarea bind:value={conclusionLimitations} rows="2" maxlength="5000" placeholder="Only one acquisition channel was tested."></textarea></label>
      </fieldset>
      <aside class="next-action" aria-live="polite">
        <span>Precommitted next action</span>
        <strong>{conclusionOutcome ? nextActionFor(conclusionExperiment) : "Choose which written rule fits above to preview the action."}</strong>
      </aside>
    </form>
  {/if}
  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={Boolean(concludingId)} onclick={closeConclusion}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <div class="footer-submit">
      {#if conclusionExperiment && conclusionErrors[conclusionExperiment.id]}<p class="form-error" role="alert">{conclusionErrors[conclusionExperiment.id]}</p>{/if}
      <SubmitButton
        type="button"
        label="Save conclusion"
        loadingText="Saving conclusion…"
        loading={Boolean(concludingId)}
        disabled={!conclusionExperiment || !canSaveConclusion(conclusionExperiment)}
        onclick={() => { if (conclusionExperiment) void saveConclusion(conclusionExperiment); }}
        class="submit-btn"
      />
    </div>
  {/snippet}
</FormOverlay>

<style>
  .workspace { height: 100%; margin: 0; padding: 0 1.4rem 1.4rem; overflow: auto; background: var(--color-bg-elevated); }
  .workspace:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
  .workspace-head { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 1.5rem; padding: 1.15rem 0.15rem 1rem; border-bottom: 1px solid var(--color-border); background: var(--color-bg-elevated); }
  .workspace-head > div { max-width: 52rem; }
  .kicker { margin: 0 0 0.18rem; font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-secondary); }
  h3, h4, p { margin: 0; }
  h3 { font-size: 1rem; color: var(--color-text-primary); }
  .workspace-head div > p:last-child { margin-top: 0.3rem; font-size: 0.8rem; line-height: 1.45; color: var(--color-text-secondary); }
  button { min-height: 2.35rem; border: 1px solid var(--color-border); border-radius: 0.65rem; background: var(--color-bg-elevated); color: var(--color-text-primary); font-size: 0.76rem; font-weight: 700; cursor: pointer; transition: border-color 140ms ease, background 140ms ease, transform 140ms ease; }
  button:hover:not(:disabled) { border-color: var(--color-text-muted); }
  button:active:not(:disabled) { transform: translateY(1px); }
  @media (prefers-reduced-motion: reduce) {
    button:active:not(:disabled) { transform: none; }
  }
  button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  button:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: not-allowed; }
  .new-action { padding: 0 0.9rem; background: var(--color-text-primary); color: var(--color-bg-primary); border-color: var(--color-text-primary); white-space: nowrap; }
  .workspace-actions { display: flex; align-items: center; gap: 0.5rem; }
  .close-action { display: grid; flex: 0 0 2.35rem; width: 2.35rem; padding: 0; place-items: center; }
  .close-action :global(svg) { width: 1rem; height: 1rem; }
  .empty, .error { padding: 0.9rem 0.15rem 1rem; font-size: 0.78rem; color: var(--color-text-muted); }
  .empty-primary,
  .empty-secondary {
    min-height: 2.35rem;
    padding: 0.45rem 0.85rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.55rem;
    font: inherit;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
  }
  .empty-primary {
    border-color: var(--color-text-primary);
    background: var(--color-text-primary);
    color: var(--color-bg-primary);
  }
  .empty-secondary {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }
  .empty-secondary:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: not-allowed; }
  .empty-primary:focus-visible,
  .empty-secondary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .error { color: var(--color-error-text); }
  .load-error { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.8rem .9rem; border:1px solid var(--color-border); border-radius:.65rem; background:var(--color-bg-subtle); }
  .load-error > div { display:grid; gap:.15rem; }
  .load-error strong { color:var(--color-text-primary); font-size:.76rem; }
  .load-error span { color:var(--color-text-secondary); font-size:.7rem; }
  .load-error button { min-height:2rem; padding:.35rem .7rem; border:1px solid var(--color-border-emphasis); border-radius:.45rem; background:var(--color-bg-elevated); color:var(--color-text-primary); font-weight:700; cursor:pointer; }
  .experiment-list { border-top: 1px solid var(--color-border); }
  .experiment-row { display: grid; grid-template-columns: minmax(16rem, 1.5fr) minmax(18rem, 1fr) auto; gap: 1.25rem; align-items: center; padding: 1rem 0.15rem; border-bottom: 1px solid var(--color-border); }
  .experiment-row:last-child { border-bottom: 0; }
  .row-meta { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-bottom: 0.32rem; font-family: var(--font-mono); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-secondary); }
  .row-meta span:first-child { color: var(--color-warning-dark); }
  .row-meta span.locked { color: var(--color-success-dark); }
  .row-meta span.active { color: var(--color-accent-dark); }
  h4 { font-size: 0.88rem; color: var(--color-text-primary); }
  .experiment-main > p { margin-top: 0.28rem; font-size: 0.76rem; line-height: 1.45; color: var(--color-text-secondary); }
  .experiment-rule { display: grid; gap: 0.25rem; margin: 0; }
  .experiment-rule div { display: grid; grid-template-columns: 3rem minmax(0, 1fr); gap: 0.5rem; }
  .experiment-rule dt { font-size: var(--text-xs); font-weight: 700; text-transform: uppercase; color: var(--color-text-secondary); }
  .experiment-rule dd { margin: 0; font-size: 0.72rem; color: var(--color-text-secondary); }
  .row-actions { display: flex; gap: 0.45rem; align-items: center; }
  .row-actions button { padding: 0 0.72rem; }
  .row-error { grid-column: 1 / -1; margin: 0; padding: 0.65rem 0.75rem; border-left: 2px solid var(--color-error-text); color: var(--color-error-text); font-size: 0.74rem; }
  .text-action { border-color: transparent; background: transparent; }
  .action-link { display: inline-flex; min-height: 2.35rem; align-items: center; padding: 0 0.45rem; border-radius: 0.55rem; color: var(--color-text-primary); font-size: 0.76rem; font-weight: 700; text-decoration: none; }
  .locked-note { font-family: var(--font-mono); font-size: var(--text-11); color: var(--color-success-dark); }
  .brief-export { grid-column: 1 / -1; border-top: 1px solid var(--color-border); }
  .brief-export summary { width: fit-content; padding-top: 0.75rem; color: var(--color-text-secondary); font-size: 0.72rem; font-weight: 700; cursor: pointer; }
  .brief-export-body { display: grid; grid-template-columns: minmax(16rem, 1fr) minmax(18rem, 1.2fr) auto; gap: 1rem; align-items: center; padding: 0.75rem 0 0.15rem; }
  .brief-export-body > p { display: grid; gap: 0.2rem; font-size: 0.72rem; color: var(--color-text-secondary); }
  .brief-export-body > p strong { color: var(--color-text-primary); }
  .brief-export-body > p span, .brief-export-body .origin-status { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-secondary); }
  .brief-export-actions { display: flex; flex-wrap: wrap; gap: 0.35rem; justify-content: flex-end; align-items: center; }
  .brief-export-actions button { padding: 0 0.55rem; }
  .brief-export-actions a { display: inline-flex; min-height: 2.35rem; align-items: center; padding: 0 0.5rem; color: var(--color-text-secondary); font-size: 0.7rem; font-weight: 700; text-decoration: none; }
  .results-sheet, .conclusion-summary { grid-column: 1 / -1; width: 100%; padding: 1.1rem 0.15rem 0.2rem; border-top: 1px solid var(--color-border); }
  .launch-sheet, .conclusion-sheet { width: 100%; }
  .launch-sheet > label { max-width: 52rem; }
  .result-ledger { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; border-block: 1px solid var(--color-border); }
  .result-ledger div { min-width: 0; padding: 0.85rem 1rem; border-right: 1px solid var(--color-border); }
  .result-ledger div:first-child { padding-left: 0; }
  .result-ledger div:last-child { border-right: 0; }
  .result-ledger dt { font-size: var(--text-xs); font-weight: 700; color: var(--color-text-secondary); }
  .result-ledger dd { margin: 0.28rem 0 0; font-family: var(--font-mono); font-size: 0.82rem; color: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .result-status { margin-top: 0.85rem; font-size: 0.75rem; line-height: 1.5; color: var(--color-text-secondary); }
  .conclusion-heading { display: grid; grid-template-columns: minmax(16rem, 0.8fr) minmax(18rem, 1.2fr); gap: 1.5rem; align-items: start; }
  .conclusion-heading h5 { margin: 0; font-size: 0.9rem; color: var(--color-text-primary); }
  .conclusion-heading > span { font-size: 0.72rem; line-height: 1.5; color: var(--color-text-secondary); }
  .conclusion-heading > span { justify-self: end; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-secondary); }
  .conclusion-sheet fieldset { padding-inline: 0; }
  .outcome-picker { margin-top: 0.8rem; }
  .outcome-picker :global(.segment-cards) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  label > span small { font-weight: 500; color: var(--color-text-secondary); }
  .next-action { display: grid; gap: 0.3rem; margin-top: 1rem; padding: 0.85rem 1rem; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .next-action span { font-family: var(--font-mono); font-size: var(--text-11); font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: var(--color-text-secondary); }
  .next-action strong { font-size: var(--text-13); line-height: 1.45; color: var(--color-text-primary); }
  .conclusion-summary dl { display: grid; grid-template-columns: minmax(16rem, 0.8fr) minmax(18rem, 1.2fr); gap: 1.5rem; margin: 1rem 0 0; padding-block: 0.9rem; border-block: 1px solid var(--color-border); }
  .conclusion-summary dt { font-size: var(--text-xs); font-weight: 700; color: var(--color-text-secondary); }
  .conclusion-summary dd { margin: 0.3rem 0 0; font-size: 0.76rem; line-height: 1.5; color: var(--color-text-primary); }
  .conclusion-scope { margin-top: 0.75rem; font-size: 0.7rem; line-height: 1.45; color: var(--color-text-secondary); }
  .experiment-form { padding-bottom: 0.25rem; }
  .origin-strip { display: grid; grid-template-columns: 7rem minmax(12rem, 0.8fr) minmax(18rem, 1.2fr); gap: 0.8rem; align-items: baseline; padding: 0.85rem 0.15rem; border-bottom: 1px solid var(--color-border); }
  .origin-strip span { font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; color: var(--color-accent-dark); }
  .origin-strip strong { font-size: 0.76rem; color: var(--color-text-primary); }
  .origin-strip small { font-size: 0.7rem; line-height: 1.45; color: var(--color-text-secondary); }
  .candidate-confirm { display: grid; gap: 0.6rem; margin-top: 0.85rem; padding: 0.75rem 0.85rem; border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .candidate-confirm p { margin: 0; font-size: var(--text-13); line-height: 1.5; color: var(--color-text-primary); }
  .candidate-confirm-actions { display: flex; gap: 0.5rem; }
  .candidate-confirm-cancel, .candidate-confirm-confirm { display: inline-flex; align-items: center; justify-content: center; min-height: 2.1rem; padding: 0.35rem 0.8rem; border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: 700; cursor: pointer; }
  .candidate-confirm-cancel { border: 1px solid var(--color-input-border); background: transparent; color: var(--color-text-secondary); transition: border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .candidate-confirm-cancel:hover { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .candidate-confirm-confirm { border: 0; background: var(--color-accent-hover); color: var(--color-text-on-accent); transition: background var(--duration-fast) var(--ease-default); }
  .candidate-confirm-confirm:hover { background: var(--color-accent-dark); }
  .candidate-confirm-cancel:focus-visible, .candidate-confirm-confirm:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  fieldset { min-width: 0; margin: 0; padding: 1rem 0.15rem; border: 0; border-bottom: 1px solid var(--color-border); }
  legend { padding: 0; font-size: 0.78rem; font-weight: 800; color: var(--color-text-primary); }
  label { display: grid; gap: 0.38rem; margin-top: 0.8rem; }
  label > span { font-size: var(--text-11); font-weight: 700; color: var(--color-text-secondary); }
  input, textarea, select { width: 100%; border: 1px solid var(--color-input-border); border-radius: 0.55rem; background: var(--color-bg-primary); color: var(--color-text-primary); font: inherit; font-size: 0.78rem; line-height: 1.4; }
  input, select { min-height: 2.45rem; padding: 0 0.68rem; }
  textarea { resize: vertical; padding: 0.62rem 0.68rem; }
  .field-grid { display: grid; gap: 0.85rem; }
  .field-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .field-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .signal-note { margin-top: 0.7rem; padding-left: 0.7rem; border-left: 2px solid var(--color-border); font-size: 0.72rem; color: var(--color-text-secondary); }
  .signal-note strong { color: var(--color-text-secondary); }
  .overlay-explanation { margin: 0.35rem 0 0.85rem; color: var(--color-text-secondary); font-size: 0.76rem; line-height: 1.5; }
  .footer-submit { display: flex; align-items: center; gap: 0.75rem; }
  .form-error { margin: 0; color: var(--color-error-text); font-size: var(--text-sm); line-height: 1.4; }
  .cancel-btn { display: inline-flex; align-items: center; justify-content: center; min-height: 2.4rem; padding: 0.5rem 0.9rem; border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 600; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .cancel-btn:hover:not(:disabled) { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .cancel-btn:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: wait; }
  .cancel-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

  @media (max-width: 900px) {
    .experiment-row { grid-template-columns: minmax(0, 1fr) auto; }
    .experiment-rule { grid-column: 1 / -1; grid-row: 2; }
    .results-sheet, .conclusion-summary { grid-row: auto; }
    .result-ledger { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .result-ledger div:nth-child(2) { border-right: 0; }
    .result-ledger div:nth-child(-n+2) { border-bottom: 1px solid var(--color-border); }
    .field-grid.three { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .brief-export-body { grid-template-columns: minmax(0, 1fr) auto; }
    .brief-export-body .origin-status { grid-column: 1 / -1; }
  }
  @media (max-width: 600px) {
    .workspace { padding-inline: 0.9rem; }
    .workspace-head { align-items: flex-start; gap: 0.75rem; }
    .workspace-actions { flex-direction: column-reverse; align-items: flex-end; }
    .workspace-head .new-action { width: auto; }
    .experiment-row { grid-template-columns: 1fr; }
    .experiment-rule, .row-actions { grid-column: auto; grid-row: auto; }
    .row-actions { flex-wrap: wrap; }
    .row-actions button, .row-actions a { min-height: 2.75rem; }
    .brief-export-body, .origin-strip { grid-template-columns: 1fr; }
    .brief-export-body .origin-status { grid-column: auto; }
    .brief-export-actions { justify-content: flex-start; }
    .brief-export-actions button, .brief-export-actions a { min-height: 2.75rem; }
    .conclusion-heading, .conclusion-summary dl { grid-template-columns: 1fr; }
    .conclusion-heading > span { justify-self: start; }
    .outcome-picker :global(.segment-cards) { grid-template-columns: 1fr; }
    .result-ledger { grid-template-columns: 1fr; }
    .result-ledger div { padding-left: 0; border-right: 0; border-bottom: 1px solid var(--color-border); }
    .result-ledger div:last-child { border-bottom: 0; }
    .field-grid.two, .field-grid.three { grid-template-columns: 1fr; }
  }
</style>
