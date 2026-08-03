<script lang="ts">
  import { onMount, tick, untrack } from "svelte";
  import { Check } from "lucide-svelte";
  import {
    closeSelectionExperimentRun,
    concludeSelectionExperiment,
    createSelectionExperiment,
    createSelectionIdeaNarrowingProposal,
    deleteSelectionExperiment,
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
    surface?: "page" | "form";
    jobId: string;
    ideas: SolutionPreview[];
    prefill?: SelectionExperimentPrefill | null;
    newDraftSeed?: SelectionExperimentDraftSeed | null;
    hasTrackedAssumption?: boolean;
    seedCost?: number | null;
    narrowingDisabled?: boolean;
    /** Blocks every mutating submit while the host workspace is not
     *  interactive (e.g. the job is REGENERATING). Open editors stay mounted
     *  so a dirty draft is preserved. */
    disabled?: boolean;
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
    surface = "page",
    jobId,
    ideas,
    prefill = null,
    newDraftSeed = null,
    hasTrackedAssumption = true,
    seedCost = null,
    narrowingDisabled = false,
    disabled = false,
    onEvaluateNarrowing,
    onReviewNarrowing,
    onUseNarrowing,
    onChanged = () => {},
    onClose = () => {},
    onOpenChallenge,
  }: Props = $props();

  const isForm = $derived(surface === "form");

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
  let startingConcern = $state("");
  let activeSuggestion = $state<SelectionExperimentPrefill["source"] | null>(null);
  let editingId = $state<string | null>(null);
  let editing = $state(false);
  let loading = $state(true);
  let saving = $state(false);
  let lockingId = $state<string | null>(null);
  let deletingId = $state<string | null>(null);
  let listHeadingEl = $state<HTMLHeadingElement>();
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
  let appliedPrefillId: string | null = null;
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
  let loadedOnce = false;
  let loadPromise: Promise<void> | null = null;
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
  let editorStep = $state<1 | 2 | 3>(1);
  let editorStageEl = $state<HTMLFieldSetElement>();

  const EDITOR_STEP_FIELDS: Record<1 | 2 | 3, RequiredDraftField[]> = {
    1: ["assumption", "whyCritical"],
    2: [
      "stimulus",
      "audience",
      "channel",
      "primaryMetric",
      "passThreshold",
      "failThreshold",
      "measurementWindow",
    ],
    3: ["passAction", "failAction", "flatAction", "invalidAction"],
  };

  /** Per-field actionable copy plus the rendered control's DOM id, so a
   *  failed submit can both explain and focus the first missing answer. */
  const DRAFT_FIELD_COPY: Record<RequiredDraftField, { id: string; message: string }> = {
    assumption: { id: "experiment-assumption", message: "Name the assumption you are testing." },
    whyCritical: { id: "experiment-why-critical", message: "Explain why failure would change the decision." },
    stimulus: { id: "experiment-stimulus", message: "Describe the exact stimulus, offer, prototype, or task in at least 3 characters." },
    audience: { id: "experiment-audience", message: "Describe the qualified audience in at least 3 characters." },
    channel: { id: "experiment-channel", message: "Name the recruitment or traffic channel." },
    primaryMetric: { id: "experiment-primary-metric", message: "Define the primary metric, including numerator and denominator." },
    passThreshold: { id: "experiment-pass-threshold", message: "Write the pass rule this test must meet." },
    failThreshold: { id: "experiment-fail-threshold", message: "Write the fail rule that would stop this test." },
    measurementWindow: { id: "experiment-measurement-window", message: "Set the measurement window and stopping rule." },
    passAction: { id: "experiment-pass-action", message: "Commit the next action if the test passes." },
    failAction: { id: "experiment-fail-action", message: "Commit the next action if the test fails." },
    flatAction: { id: "experiment-flat-action", message: "Commit the next action if the result is flat." },
    invalidAction: { id: "experiment-invalid-action", message: "Commit the next action if the test is invalid." },
  };

  const editorFooterMessage = $derived(
    editorStep === 3
      ? "Step 3 of 3 · Saving keeps this editable. Nothing is published or collecting responses yet."
      : `Step ${editorStep} of 3 · Changes stay in this draft.`,
  );

  function touchDraftField(field: RequiredDraftField) {
    touchedDraftFields.add(field);
    touchedDraftFields = new Set(touchedDraftFields);
  }

  function requiredDraftError(field: RequiredDraftField): string {
    return draft[field].trim().length < 3 ? DRAFT_FIELD_COPY[field].message : "";
  }

  function draftFieldError(field: RequiredDraftField): string {
    if (!editorSubmitAttempted && !touchedDraftFields.has(field)) return "";
    return requiredDraftError(field);
  }

  function resetEditorValidation() {
    touchedDraftFields = new Set();
    editorSubmitAttempted = false;
    editorStep = 1;
  }

  async function focusDraftField(field: RequiredDraftField) {
    await tick();
    document.getElementById(DRAFT_FIELD_COPY[field].id)?.focus();
  }

  async function continueEditor() {
    const fields = EDITOR_STEP_FIELDS[editorStep];
    for (const field of fields) touchedDraftFields.add(field);
    touchedDraftFields = new Set(touchedDraftFields);
    const firstInvalid = fields.find((field) => requiredDraftError(field));
    if (firstInvalid) {
      await focusDraftField(firstInvalid);
      return;
    }
    if (editorStep < 3) {
      editorStep = (editorStep + 1) as 2 | 3;
      await tick();
      editorStageEl?.focus();
    }
  }

  async function previousEditorStep() {
    if (editorStep > 1) {
      editorStep = (editorStep - 1) as 1 | 2;
      await tick();
      editorStageEl?.focus();
    }
  }

  /** Submit-attempt entry point: reveals every missing required field instead
   *  of relying on a silently disabled button, then focuses the first one. */
  async function attemptSave() {
    if (!canSave) {
      editorSubmitAttempted = true;
      const firstInvalidStep = ([1, 2, 3] as const).find((step) => (
        EDITOR_STEP_FIELDS[step].some((field) => requiredDraftError(field))
      ));
      if (firstInvalidStep) {
        editorStep = firstInvalidStep;
        const firstInvalid = EDITOR_STEP_FIELDS[firstInvalidStep]
          .find((field) => requiredDraftError(field));
        if (firstInvalid) await focusDraftField(firstInvalid);
      }
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

  const LAUNCH_FIELD_COPY: Record<RequiredLaunchField, { id: string; message: string }> = {
    headline: { id: "experiment-launch-headline", message: "Write the public headline in at least 3 characters." },
    promise: { id: "experiment-launch-promise", message: "Write the support sentence participants will read, in at least 3 characters." },
  };

  function requiredLaunchError(field: RequiredLaunchField): string {
    const value = field === "headline" ? launchDraft.headline : launchDraft.promise;
    return value.trim().length < 3 ? LAUNCH_FIELD_COPY[field].message : "";
  }

  function launchFieldError(field: RequiredLaunchField): string {
    if (!launchSubmitAttempted && !touchedLaunchFields.has(field)) return "";
    return requiredLaunchError(field);
  }

  function resetLaunchValidation() {
    touchedLaunchFields = new Set();
    launchSubmitAttempted = false;
  }

  /** Submit-attempt entry point: reveals per-field errors instead of a
   *  silently disabled Publish button (same reveal-on-attempt pattern as
   *  attemptSave), then focuses the first missing field. */
  async function attemptPublish() {
    if (!launchExperiment) return;
    if (!canPublish) {
      launchSubmitAttempted = true;
      const firstInvalid = (["headline", "promise"] as const).find((field) => requiredLaunchError(field));
      if (firstInvalid) {
        await tick();
        document.getElementById(LAUNCH_FIELD_COPY[firstInvalid].id)?.focus();
      }
      return;
    }
    void publishRun(launchExperiment);
  }

  type RequiredConclusionField = "observationSummary" | "observedAt" | "outcome" | "rationale";
  let touchedConclusionFields = $state<Set<RequiredConclusionField>>(new Set());
  let conclusionSubmitAttempted = $state(false);

  function touchConclusionField(field: RequiredConclusionField) {
    touchedConclusionFields.add(field);
    touchedConclusionFields = new Set(touchedConclusionFields);
  }

  function requiredConclusionError(field: RequiredConclusionField): string {
    if (field === "observedAt") return observedAt ? "" : "Choose the date when you observed this result.";
    if (field === "outcome") return conclusionOutcome ? "" : "Choose which written rule fits the result.";
    if (field === "observationSummary") {
      return observationSummary.trim().length < 3
        ? "Describe the observed result in at least 3 characters."
        : "";
    }
    return conclusionRationale.trim().length < 3
      ? "Explain why this outcome fits the written rule, in at least 3 characters."
      : "";
  }

  function conclusionFieldError(field: RequiredConclusionField): string {
    if (!conclusionSubmitAttempted && !touchedConclusionFields.has(field)) return "";
    return requiredConclusionError(field);
  }

  function resetConclusionValidation() {
    touchedConclusionFields = new Set();
    conclusionSubmitAttempted = false;
  }

  async function attemptSaveConclusion(experiment: SelectionExperiment) {
    if (!canSaveConclusion(experiment)) {
      conclusionSubmitAttempted = true;
      // Focus the first invalid control in visual order: manual evidence
      // fields (when there is no hosted run), then outcome, then rationale.
      await tick();
      if (!experiment.run && requiredConclusionError("observationSummary")) {
        document.getElementById("experiment-observation-summary")?.focus();
      } else if (!experiment.run && requiredConclusionError("observedAt")) {
        document.getElementById("experiment-observed-at")?.focus();
      } else if (requiredConclusionError("outcome")) {
        document.querySelector<HTMLElement>('#experiment-conclusion-form [role="radio"]')?.focus();
      } else if (requiredConclusionError("rationale")) {
        document.getElementById("experiment-conclusion-rationale")?.focus();
      }
      return;
    }
    void saveConclusion(experiment);
  }

  onMount(() => {
    if (!isForm || open) void load();
    else loading = false;
  });

  $effect(() => {
    // The direct form waits for saved drafts before applying a prefill so it
    // can resume the exact editable test instead of creating a duplicate.
    if (isForm || !prefill || prefill.requestId === appliedPrefillId) return;
    reviewCopilotDraft(prefill.requestId, prefill.draft);
  });

  async function load(): Promise<void> {
    if (loadPromise) return loadPromise;
    loadPromise = (async () => {
      loading = true;
      loadError = "";
      try {
        experiments = await getSelectionExperiments(jobId);
      } catch (cause) {
        loadError = cause instanceof Error ? cause.message : "Could not load experiment briefs.";
      } finally {
        loadedOnce = true;
        loading = false;
      }
    })();
    try {
      await loadPromise;
    } finally {
      loadPromise = null;
    }
  }

  function draftForIdea(idea: SolutionPreview): SelectionExperimentDraft {
    const audience = idea.source_segment?.trim() || idea.target_personas?.find(Boolean)?.trim() || "";
    const evidence = idea.source_pain?.trim() || idea.pain_points_addressed?.find(Boolean)?.trim() || "";
    return {
      ...EMPTY_DRAFT,
      ideaId: idea.idea_id ?? idea.solution_name,
      ideaRevision: idea.idea_revision ?? 1,
      currentEvidence: evidence,
      audience,
    };
  }

  function draftForExperiment(experiment: SelectionExperiment): SelectionExperimentDraft {
    const {
      id: _id,
      jobId: _jobId,
      version: _version,
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
    startingConcern = existing ? "" : candidate.critic_concern?.trim() || "";
    // Resuming a persisted record: the SAVED fields win over the seed values,
    // otherwise a stale copilot seed silently overwrites the owner's saved
    // brief and one Save persists the rewrite. Only a brand-new draft lets
    // the seed win over the idea-derived starting values.
    draft = existing
      ? {
          ...values,
          ...baseline,
          ideaId: values.ideaId,
          ideaRevision: values.ideaRevision,
        }
      : {
          ...baseline,
          ...values,
          ideaId: values.ideaId,
          ideaRevision: values.ideaRevision,
        };
    editingId = existing?.id ?? null;
    error = "";
    editing = true;
    // Baseline the opened draft: on resume that is the persisted record's own
    // values (seed differences never stage silently), and an untouched
    // prefill still opens clean (no discard warning).
    editorBaseline = JSON.stringify(draft);
    launchId = null;
    conclusionId = null;
    appliedPrefillId = requestId;
    activeSuggestion = existing ? null : prefill?.source ?? "analyst";
    resetEditorValidation();
    return { ok: true, message: "Test draft opened. Review every field before saving." };
  }

  function beginNew() {
    const seedIdea = newDraftSeed
      ? ideas.find((idea) => (
          idea.idea_id === newDraftSeed.ideaId
          && (idea.idea_revision ?? 1) === newDraftSeed.ideaRevision
        ))
      : undefined;
    const firstIdea = seedIdea ?? ideas[0];
    if (!firstIdea) return;
    const baseline = draftForIdea(firstIdea);
    startingConcern = firstIdea.critic_concern?.trim() || "";
    activeSuggestion = newDraftSeed ? "manual" : null;
    draft = newDraftSeed
      ? {
          ...baseline,
          ...newDraftSeed,
          ideaId: firstIdea.idea_id ?? firstIdea.solution_name,
          ideaRevision: firstIdea.idea_revision ?? 1,
        }
      : baseline;
    editingId = null;
    error = "";
    editing = true;
    editorBaseline = JSON.stringify(draft);
    launchId = null;
    conclusionId = null;
    resetEditorValidation();
  }

  function matchingEditableExperiment(
    values: SelectionExperimentDraftSeed,
  ): SelectionExperiment | undefined {
    const exactDrafts = experiments.filter((experiment) => (
      experiment.status === "DRAFT"
      && experiment.ideaId === values.ideaId
      && experiment.ideaRevision === values.ideaRevision
    ));
    if (values.assumptionId) {
      return exactDrafts.find((experiment) => experiment.assumptionId === values.assumptionId);
    }
    if (values.originChallengeId && values.originQuestionId) {
      return exactDrafts.find((experiment) => (
        experiment.originChallengeId === values.originChallengeId
        && experiment.originQuestionId === values.originQuestionId
      ));
    }
    const assumption = values.assumption?.trim();
    if (!assumption) return undefined;
    return exactDrafts.find((experiment) => (
      experiment.assumption.trim() === assumption
      && (!values.assumptionType || experiment.assumptionType === values.assumptionType)
    ));
  }

  async function openDirectForm(): Promise<void> {
    if (!loadedOnce || loadError) await load();
    if (!open) return;
    if (loadError) {
      beginNew();
      error = "Saved test plans could not be checked. Close this form and try again before creating another plan.";
      return;
    }
    if (prefill) {
      const existing = matchingEditableExperiment(prefill.draft);
      reviewCopilotDraft(
        prefill.requestId,
        prefill.draft,
        existing ? { id: existing.id, status: existing.status } : undefined,
      );
      if (!existing) activeSuggestion = prefill.source ?? activeSuggestion;
    } else {
      beginNew();
    }
  }

  // Form-only hosts own the surrounding context, so one open cycle maps to
  // one editor cycle. This dedupe guard is deliberately a plain `let`; reads
  // and writes inside the effect must not create another reactive dependency.
  let formOpenConsumed = false;
  $effect(() => {
    if (!isForm || !open) {
      formOpenConsumed = false;
      return;
    }
    if (formOpenConsumed || ideas.length === 0) return;
    formOpenConsumed = true;
    void openDirectForm();
  });

  function edit(experiment: SelectionExperiment) {
    draft = draftForExperiment(experiment);
    startingConcern = "";
    activeSuggestion = null;
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
    startingConcern = idea.critic_concern?.trim() || "";
    activeSuggestion = null;
    resetEditorValidation();
  }

  function confirmCandidateSwitch() {
    if (!pendingIdea) return;
    draft = draftForIdea(pendingIdea);
    startingConcern = pendingIdea.critic_concern?.trim() || "";
    activeSuggestion = null;
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
    if (!canSave || saving || disabled) return;
    pendingIdea = null;
    saving = true;
    error = "";
    try {
      const existing = editingId
        ? experiments.find((item) => item.id === editingId)
        : null;
      if (editingId && !existing) {
        throw new Error("This experiment draft is no longer available. Refresh and try again.");
      }
      const experiment = editingId && existing
        ? await updateSelectionExperiment(jobId, editingId, existing.version, draft)
        : await createSelectionExperiment(jobId, draft);
      experiments = [experiment, ...experiments.filter((item) => item.id !== experiment.id)];
      editing = false;
      editingId = null;
      onChanged();
      if (isForm) onClose();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not save the experiment brief.";
    } finally {
      saving = false;
    }
  }

  async function lock(experiment: SelectionExperiment) {
    if (disabled) return;
    lockingId = experiment.id;
    error = "";
    try {
      const locked = await lockSelectionExperiment(jobId, experiment.id, experiment.version);
      experiments = experiments.map((item) => item.id === locked.id ? locked : item);
      onChanged();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not lock the experiment brief.";
    } finally {
      lockingId = null;
    }
  }

  /** Hard-deletes a DRAFT plan (locked briefs stay immutable server-side).
   *  Focus lands on the workspace heading because the row it sat in is gone. */
  async function removeDraft(experiment: SelectionExperiment) {
    if (disabled) return;
    deletingId = experiment.id;
    error = "";
    try {
      await deleteSelectionExperiment(jobId, experiment.id, experiment.version);
      experiments = experiments.filter((item) => item.id !== experiment.id);
      onChanged();
      await tick();
      listHeadingEl?.focus();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not delete the draft test plan.";
    } finally {
      deletingId = null;
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
    if (disabled) return;
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
    resetConclusionValidation();
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
    if (!canSaveConclusion(experiment) || concludingId || disabled) return;
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
    if (disabled) return;
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
    if (isForm) onClose();
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
    resetConclusionValidation();
  }
</script>

{#snippet workspaceContent()}
<section
  id="selection-experiments"
  class="workspace workspace--page"
  aria-labelledby="experiments-title"
  data-annotation-anchor="selection:experiments"
>
  <header class="workspace-head">
    <div>
      <p class="kicker">Next-best test</p>
      <h2 id="experiments-title" tabindex="-1" bind:this={listHeadingEl}>Test what could change the decision</h2>
      <p>Define one risky assumption, a behavioral signal, and the outcome rules before collecting results.</p>
    </div>
    <div class="workspace-actions">
      {#if !editing && !loading && experiments.length > 0}
        <button type="button" class="new-action" onclick={beginNew} disabled={disabled || !ideas.length}>{DRAFT_TEST_BRIEF_LABEL}</button>
      {/if}
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
      title={hasTrackedAssumption ? "Plan a test for the open assumption" : "Start with one open assumption"}
      description={hasTrackedAssumption
        ? "Define the signal and outcome rules before collecting results. This optional test never changes the research score."
        : "Check the saved evidence first. If an unanswered question could change your choice, turn it into a small test."}
    >
      {#if hasTrackedAssumption || !onOpenChallenge}
        <button type="button" class="empty-primary" onclick={beginNew} disabled={disabled || !ideas.length}>{DRAFT_TEST_BRIEF_LABEL}</button>
      {:else}
        <button type="button" class="empty-primary" onclick={onOpenChallenge}>{STRESS_TEST_EVIDENCE_LABEL}</button>
      {/if}
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
            <h3>{experimentTitle(experiment)}</h3>
            <p>{experiment.assumption}</p>
          </div>
          <dl class="experiment-rule">
            <div><dt>Signal</dt><dd>{labelFor(SIGNALS, experiment.evidenceSignal)}</dd></div>
            <div><dt>Pass</dt><dd>{experiment.passThreshold}</dd></div>
            <div><dt>Fail</dt><dd>{experiment.failThreshold}</dd></div>
            <div><dt>Stop / window</dt><dd>{experiment.measurementWindow}</dd></div>
          </dl>
          <div class="row-actions">
            {#if experiment.conclusion}
              <span class="locked-note">Read-only owner record</span>
            {:else if experiment.status === "DRAFT"}
              <button type="button" class="text-action" disabled={disabled} onclick={() => edit(experiment)}>Edit</button>
              <ConfirmGate
                variant="free"
                label="Delete draft"
                confirmLabel="Delete draft"
                consequence="DRAFT IS REMOVED · NOTHING WAS COLLECTING"
                busy={deletingId === experiment.id}
                disabled={disabled || lockingId === experiment.id}
                onConfirm={() => void removeDraft(experiment)}
              />
              <ConfirmGate
                variant="free"
                label="Lock brief"
                confirmLabel="Lock brief"
                consequence="BECOMES IMMUTABLE"
                busy={lockingId === experiment.id}
                disabled={disabled || deletingId === experiment.id}
                onConfirm={() => void lock(experiment)}
              />
            {:else if !experiment.run}
              {#if canHost(experiment)}
                <button type="button" disabled={disabled} onclick={() => beginLaunch(experiment)}>Set up public test</button>
              {/if}
              <button type="button" disabled={disabled} onclick={() => void beginConclusion(experiment)}>Record external result</button>
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
                  disabled={disabled}
                  onConfirm={() => void closeRun(experiment)}
                />
              {:else}
                <button type="button" disabled={disabled} onclick={() => void beginConclusion(experiment)}>Review and record outcome</button>
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
                  <h4>{conclusionLabel(experiment.conclusion.outcome)}</h4>
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
                  disabled={disabled || narrowingDisabled}
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
{/snippet}

{#if surface === "page" && open}
  {@render workspaceContent()}
{/if}

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
  footerMessage={editorFooterMessage}
>
  <form
    id="experiment-editor-form"
    class="experiment-form"
    onsubmit={(event) => {
      event.preventDefault();
      if (editorStep < 3) continueEditor();
      else attemptSave();
    }}
  >
    <nav class="editor-progress" aria-label="Test plan progress">
      <ol>
        {#each [
          { step: 1, label: "Decision risk" },
          { step: 2, label: "Test design" },
          { step: 3, label: "Next actions" },
        ] as item}
          <li class:current={editorStep === item.step} class:complete={editorStep > item.step}>
            <span aria-hidden="true">
              {#if editorStep > item.step}<Check />{:else}{item.step}{/if}
            </span>
            <strong aria-current={editorStep === item.step ? "step" : undefined}>
              {item.label}
              {#if editorStep > item.step}<span class="sr-only"> completed</span>{/if}
            </strong>
          </li>
        {/each}
      </ol>
    </nav>
    <div class="form-context">
      <DecisionHelp title="Why decide this first?" label="Precommitment">
        Write the signal and next actions before results can bias the decision.
      </DecisionHelp>
      {#if draft.originChallengeId && draft.originQuestionId}
        <aside class="origin-strip">
          <span>From evidence</span>
          <strong>{SELECTION_CHALLENGE_QUESTION_LABELS[draft.originQuestionId] ?? draft.originQuestionId}</strong>
          <small>Candidate revision {draft.ideaRevision}</small>
        </aside>
      {/if}
      {#if activeSuggestion && activeSuggestion !== "manual"}
        <aside class="origin-strip suggestion-strip" role="note">
          <span>Suggested starting point</span>
          <strong>Review every populated field before saving</strong>
          <small>Nothing here is saved evidence or an owner decision yet.</small>
        </aside>
      {/if}
    </div>
    {#if editorStep === 1}
    <fieldset bind:this={editorStageEl} tabindex="-1">
      <legend>Name the decision risk</legend>
      <p class="stage-guide">Name the belief that would stop or redirect this idea.</p>
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
      {#if startingConcern}
        <aside class="evidence-context" aria-label="Starting concern">
          <span>Starting concern</span>
          <p>{startingConcern}</p>
          <small>Candidate context only. Rewrite it as one testable assumption below.</small>
        </aside>
      {/if}
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
      {#if editingId}
        <FormField
          id="experiment-current-evidence"
          kind="textarea"
          label="Current evidence note"
          optional
          hint="This is context for the plan, not a test result."
          bind:value={draft.currentEvidence}
          rows={3}
          maxlength={2000}
        />
      {:else if draft.currentEvidence.trim()}
        <aside class="evidence-context" aria-label="Current research context">
          <span>Current research context</span>
          <p>{draft.currentEvidence}</p>
          <small>Carried into this draft as context. It does not count as a test result.</small>
        </aside>
      {/if}
    </fieldset>
    {:else if editorStep === 2}
    <fieldset bind:this={editorStageEl} tabindex="-1">
      <legend>Design the smallest credible test</legend>
      <p class="stage-guide">Define the smallest credible signal and decide what counts before you run it.</p>
      <section class="form-cluster" aria-labelledby="experiment-design-heading">
      <h3 class="form-subhead" id="experiment-design-heading">What you will show and measure</h3>
      <div class="field-grid three">
        <FormField id="experiment-method" kind="select" label="Method" bind:value={draft.method}>
          {#each METHODS as option}<option value={option.value}>{option.label}</option>{/each}
        </FormField>
        <FormField id="experiment-evidence-signal" kind="select" label="What this result can show" bind:value={draft.evidenceSignal}>
          {#each SIGNALS as option}<option value={option.value}>{option.label}</option>{/each}
        </FormField>
        <FormField
          id="experiment-cost-estimate"
          class="supporting-cost"
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
      </section>
      <section class="form-cluster" aria-labelledby="experiment-result-heading">
      <h3 class="form-subhead" id="experiment-result-heading">What counts as a result</h3>
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
        <label class="sample-target"><span>Target sample or exposures <small>Optional</small></span><input type="number" min="1" max="1000000" bind:value={draft.sampleTarget} /></label>
      </div>
      </section>
    </fieldset>
    {:else}
    <fieldset bind:this={editorStageEl} tabindex="-1">
      <legend>Decide before results</legend>
      <p class="stage-guide">Commit the next action for every credible outcome.</p>
      <div class="field-grid two action-grid">
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
          class="contingency-action"
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
          class="contingency-action"
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
    {/if}
  </form>
  {#snippet footerCancel(requestClose)}
    {#if editorStep === 1}
      <button type="button" class="cancel-btn" disabled={saving} onclick={requestClose}>Cancel</button>
    {:else}
      <button type="button" class="cancel-btn" disabled={saving} onclick={previousEditorStep}>Back</button>
    {/if}
  {/snippet}
  {#snippet footer()}
    <div class="footer-submit">
      {#if error}<p class="form-error" role="alert">{error}</p>{/if}
      {#if editorStep < 3}
        <SubmitButton
          type="button"
          label="Continue"
          loadingText="Continue"
          loading={false}
          disabled={Boolean(loadError)}
          onclick={continueEditor}
          class="submit-btn"
        />
      {:else}
        <SubmitButton
          type="button"
          label={editingId ? "Save changes" : "Save draft"}
          loadingText="Saving…"
          loading={saving}
          disabled={Boolean(loadError) || disabled}
          onclick={attemptSave}
          class="submit-btn"
        />
      {/if}
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
      <FormField
        id="experiment-launch-headline"
        label="Headline"
        required
        bind:value={launchDraft.headline}
        minlength={3}
        maxlength={140}
        error={launchFieldError("headline")}
        onblur={() => touchLaunchField("headline")}
      />
      <FormField
        id="experiment-launch-promise"
        kind="textarea"
        label="Support sentence"
        required
        bind:value={launchDraft.promise}
        minlength={3}
        maxlength={1000}
        rows={3}
        error={launchFieldError("promise")}
        onblur={() => touchLaunchField("promise")}
      />
      <FormField id="experiment-launch-cta" kind="select" label="Interest action" bind:value={launchDraft.ctaLabel}>
        <option value="IM_INTERESTED">I’m interested</option>
        <option value="SHOW_ME_THE_CONCEPT">Show me the concept</option>
        <option value="ID_TRY_THIS">I’d try this</option>
      </FormField>
      <p class="signal-note"><strong>After the click:</strong> NicheIQ immediately explains that this is a concept test.</p>
    </form>
  {/if}
  {#snippet footerCancel(requestClose)}
    <button type="button" class="cancel-btn" disabled={Boolean(launchingId)} onclick={requestClose}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <div class="footer-submit">
      {#if error}<p class="form-error" role="alert">{error}</p>{/if}
      <SubmitButton
        type="button"
        label="Publish test"
        loadingText="Publishing test…"
        loading={Boolean(launchingId)}
        disabled={!launchExperiment || disabled}
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
    <form id="experiment-conclusion-form" class="conclusion-sheet" onsubmit={(event) => { event.preventDefault(); attemptSaveConclusion(conclusionExperiment); }}>
      <DecisionHelp title="Trigger the plan you already wrote" label="Conclusion scope">
        Record the outcome, and the next action you committed before the test comes with it. Hindsight can’t swap in a friendlier plan. NicheIQ seals the evidence and your rationale into one permanent receipt. The idea’s research score stays untouched: this record is your judgment layer.
      </DecisionHelp>
      {#if !conclusionExperiment.run}
        <fieldset class="manual-evidence">
          <legend>1. Observed evidence</legend>
          <FormField
            id="experiment-observation-summary"
            kind="textarea"
            label="Observed result"
            required
            bind:value={observationSummary}
            minlength={3}
            maxlength={3000}
            rows={3}
            placeholder="Describe the concrete behavior, numerator and denominator, or technical finding."
            error={conclusionFieldError("observationSummary")}
            onblur={() => touchConclusionField("observationSummary")}
          />
          <div class="field-grid three">
            <FormField
              id="experiment-observed-at"
              type="date"
              label="Observed on"
              required
              bind:value={observedAt}
              error={conclusionFieldError("observedAt")}
              onblur={() => touchConclusionField("observedAt")}
            />
            <label for="experiment-observed-sample-size"><span>Sample size <small>optional</small></span><input id="experiment-observed-sample-size" type="number" min="1" max="1000000" bind:value={observedSampleSize} /></label>
            <FormField id="experiment-observed-metric" label="Observed metric" optional bind:value={observedMetric} maxlength={500} placeholder="3 of 12 booked a call" />
          </div>
          <FormField id="experiment-source-references" kind="textarea" label="Evidence links or references" optional hint="One per line." bind:value={sourceReferences} rows={2} maxlength={5000} placeholder="Interview notes / July cohort" />
        </fieldset>
      {/if}
      <fieldset
        class="outcome-fieldset"
        aria-describedby={conclusionFieldError("outcome") ? "experiment-outcome-error" : undefined}
      >
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
            onChange={(value) => {
              conclusionOutcome = value as ExperimentConclusionOutcome;
              touchConclusionField("outcome");
            }}
          />
          {#if conclusionFieldError("outcome")}<p id="experiment-outcome-error" class="form-error" role="alert">{conclusionFieldError("outcome")}</p>{/if}
        </div>
      </fieldset>
      <fieldset>
        <legend>{conclusionExperiment.run ? "2" : "3"}. Owner rationale</legend>
        <FormField
          id="experiment-conclusion-rationale"
          kind="textarea"
          label="Why this outcome fits the written rule"
          required
          bind:value={conclusionRationale}
          minlength={3}
          maxlength={2000}
          rows={3}
          error={conclusionFieldError("rationale")}
          onblur={() => touchConclusionField("rationale")}
        />
        <FormField id="experiment-conclusion-limitations" kind="textarea" label="Limitations" optional hint="One per line." bind:value={conclusionLimitations} rows={2} maxlength={5000} placeholder="Only one acquisition channel was tested." />
      </fieldset>
      <aside class="next-action" aria-live="polite">
        <span>Precommitted next action</span>
        <strong>{conclusionOutcome ? nextActionFor(conclusionExperiment) : "Choose which written rule fits above to preview the action."}</strong>
      </aside>
    </form>
  {/if}
  {#snippet footerCancel(requestClose)}
    <button type="button" class="cancel-btn" disabled={Boolean(concludingId)} onclick={requestClose}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <div class="footer-submit">
      {#if conclusionExperiment && conclusionErrors[conclusionExperiment.id]}<p class="form-error" role="alert">{conclusionErrors[conclusionExperiment.id]}</p>{/if}
      <SubmitButton
        type="button"
        label="Save conclusion"
        loadingText="Saving conclusion…"
        loading={Boolean(concludingId)}
        disabled={!conclusionExperiment || disabled}
        onclick={() => { if (conclusionExperiment) attemptSaveConclusion(conclusionExperiment); }}
        class="submit-btn"
      />
    </div>
  {/snippet}
</FormOverlay>

<style>
  .workspace { height: 100%; margin: 0; padding: 0 var(--space-6) var(--space-6); overflow: auto; background: var(--color-bg-elevated); }
  .workspace--page { height: auto; min-height: 0; padding: 0; overflow: visible; background: transparent; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
  .workspace-head { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: var(--space-6); padding: var(--space-5) 0 var(--space-4); border-bottom: 1px solid var(--color-border); background: var(--color-bg-elevated); }
  .workspace--page .workspace-head { position: static; padding: 0 0 var(--space-5); background: transparent; }
  .workspace-head > div { max-width: 52rem; }
  .kicker { margin: 0 0 var(--space-1); font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 800; letter-spacing: var(--tracking-wider); text-transform: uppercase; color: var(--color-text-secondary); }
  h2, h3, h4, p { margin: 0; }
  h2 { font-family: var(--font-display); font-size: var(--text-3xl); line-height: var(--leading-tight); color: var(--color-text-primary); }
  h3 { font-size: var(--text-md); color: var(--color-text-primary); }
  .workspace-head div > p:last-child { margin-top: var(--space-1); font-size: var(--text-13); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  button { min-height: var(--space-10); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-elevated); color: var(--color-text-primary); font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  button:hover:not(:disabled) { border-color: var(--color-text-muted); }
  button:active:not(:disabled) { transform: scale(0.98); }
  @media (prefers-reduced-motion: reduce) {
    button:active:not(:disabled) { transform: none; }
  }
  button:focus-visible, a:focus-visible, input:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  /* Programmatic landing spot after a row is deleted from under the focus. */
  #experiments-title:focus { outline: 2px solid var(--color-accent); outline-offset: 3px; border-radius: var(--radius-sm); }
  button:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: not-allowed; }
  .new-action { padding: 0 var(--space-4); background: var(--color-accent-hover); color: var(--color-text-on-accent); border-color: var(--color-accent-hover); white-space: nowrap; }
  .new-action:hover:not(:disabled) { background: var(--color-accent-dark); border-color: var(--color-accent-dark); }
  .workspace-actions { display: flex; align-items: center; gap: var(--space-2); }
  .empty, .error { padding: var(--space-4) 0; font-size: var(--text-sm); color: var(--color-text-muted); }
  .empty-primary {
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    font: inherit;
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
  }
  .empty-primary { border-color: var(--color-accent-hover); background: var(--color-accent-hover); color: var(--color-text-on-accent); }
  .empty-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .error { color: var(--color-error-text); }
  .load-error { display:flex; align-items:center; justify-content:space-between; gap:var(--space-4); padding:var(--space-3) var(--space-4); border:1px solid var(--color-border); border-radius: var(--radius-lg); background:var(--color-bg-subtle); }
  .load-error > div { display:grid; gap:var(--space-1); }
  .load-error strong { color:var(--color-text-primary); font-size: var(--text-sm); }
  .load-error span { color:var(--color-text-secondary); font-size: var(--text-11); }
  .load-error button { min-height:var(--space-8); padding:var(--space-1) var(--space-3); border:1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background:var(--color-bg-elevated); color:var(--color-text-primary); font-weight:700; cursor:pointer; }
  .experiment-list { border-top: 1px solid var(--color-border); }
  .experiment-row { display: grid; grid-template-columns: minmax(16rem, 1.5fr) minmax(18rem, 1fr) auto; gap: var(--space-5); align-items: center; padding: var(--space-4) 0; border-bottom: 1px solid var(--color-border); }
  .experiment-row:last-child { border-bottom: 0; }
  .row-meta { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-1); font-family: var(--font-mono); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--color-text-secondary); }
  /* Draft status stays a muted record line: warning orange beside the brand
     accent misread as an alert. Locked/active states recolor below. */
  .row-meta span:first-child { color: var(--color-text-muted); }
  .row-meta span.locked { color: var(--color-success-text); }
  .row-meta span.active { color: var(--color-info-dark); }
  .experiment-main h3 { font-size: var(--text-base); color: var(--color-text-primary); }
  .experiment-main > p { margin-top: var(--space-1); font-size: var(--text-sm); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  .experiment-rule { display: grid; gap: var(--space-1); margin: 0; }
  .experiment-rule div { display: grid; grid-template-columns: var(--space-12) minmax(0, 1fr); gap: var(--space-2); }
  .experiment-rule dt { font-size: var(--text-xs); font-weight: 700; text-transform: uppercase; color: var(--color-text-secondary); }
  .experiment-rule dd { margin: 0; font-size: var(--text-sm); color: var(--color-text-secondary); }
  .row-actions { display: flex; gap: var(--space-2); align-items: center; }
  .row-actions button { padding: 0 var(--space-3); }
  .row-error { grid-column: 1 / -1; margin: 0; padding: var(--space-3); border: 1px solid var(--color-border-error); border-radius: var(--radius-md); background: var(--color-error-subtle); color: var(--color-error-text); font-size: var(--text-sm); }
  .text-action { border-color: transparent; background: transparent; }
  .action-link { display: inline-flex; min-height: var(--space-10); align-items: center; padding: 0 var(--space-2); border-radius: var(--radius-md); color: var(--color-text-primary); font-size: var(--text-sm); font-weight: 700; text-decoration: none; }
  .locked-note { font-family: var(--font-mono); font-size: var(--text-11); color: var(--color-success-text); }
  .brief-export { grid-column: 1 / -1; border-top: 1px solid var(--color-border); }
  .brief-export summary { width: fit-content; padding-top: var(--space-3); color: var(--color-text-secondary); font-size: var(--text-sm); font-weight: 700; cursor: pointer; }
  .brief-export-body { display: grid; grid-template-columns: minmax(16rem, 1fr) minmax(18rem, 1.2fr) auto; gap: var(--space-4); align-items: center; padding: var(--space-3) 0 0; }
  .brief-export-body > p { display: grid; gap: var(--space-1); font-size: var(--text-sm); color: var(--color-text-secondary); }
  .brief-export-body > p strong { color: var(--color-text-primary); }
  .brief-export-body > p span, .brief-export-body .origin-status { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-secondary); }
  .brief-export-actions { display: flex; flex-wrap: wrap; gap: var(--space-1); justify-content: flex-end; align-items: center; }
  .brief-export-actions button { padding: 0 var(--space-2); }
  .brief-export-actions a { display: inline-flex; min-height: var(--space-10); align-items: center; padding: 0 var(--space-2); color: var(--color-text-secondary); font-size: var(--text-11); font-weight: 700; text-decoration: none; }
  .results-sheet, .conclusion-summary { grid-column: 1 / -1; width: 100%; padding: var(--space-5) 0 0; border-top: 1px solid var(--color-border); }
  .launch-sheet, .conclusion-sheet { width: 100%; }
  .result-ledger { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; border-block: 1px solid var(--color-border); }
  .result-ledger div { min-width: 0; padding: var(--space-3) var(--space-4); border-right: 1px solid var(--color-border); }
  .result-ledger div:first-child { padding-left: 0; }
  .result-ledger div:last-child { border-right: 0; }
  .result-ledger dt { font-size: var(--text-xs); font-weight: 700; color: var(--color-text-secondary); }
  .result-ledger dd { margin: var(--space-1) 0 0; font-family: var(--font-mono); font-size: var(--text-13); color: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .result-status { margin-top: var(--space-4); font-size: var(--text-sm); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  .conclusion-heading { display: grid; grid-template-columns: minmax(16rem, 0.8fr) minmax(18rem, 1.2fr); gap: var(--space-6); align-items: start; }
  .conclusion-heading h4 { margin: 0; font-size: var(--text-base); color: var(--color-text-primary); }
  .conclusion-heading > span { font-size: var(--text-sm); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  .conclusion-heading > span { justify-self: end; font-family: var(--font-mono); font-size: var(--text-xs); color: var(--color-text-secondary); }
  .conclusion-sheet fieldset { padding-inline: 0; }
  .outcome-picker { margin-top: var(--space-3); }
  .outcome-picker :global(.segment-cards) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  label > span small { font-weight: 500; color: var(--color-text-secondary); }
  .next-action { display: grid; gap: var(--space-1); margin-top: var(--space-4); padding: var(--space-3) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .next-action span { font-family: var(--font-mono); font-size: var(--text-11); font-weight: 700; letter-spacing: var(--tracking-wider); text-transform: uppercase; color: var(--color-text-secondary); }
  .next-action strong { font-size: var(--text-13); line-height: var(--leading-normal); color: var(--color-text-primary); }
  .conclusion-summary dl { display: grid; grid-template-columns: minmax(16rem, 0.8fr) minmax(18rem, 1.2fr); gap: var(--space-6); margin: var(--space-4) 0 0; padding-block: var(--space-4); border-block: 1px solid var(--color-border); }
  .conclusion-summary dt { font-size: var(--text-xs); font-weight: 700; color: var(--color-text-secondary); }
  .conclusion-summary dd { margin: var(--space-1) 0 0; font-size: var(--text-sm); line-height: var(--leading-normal); color: var(--color-text-primary); }
  .conclusion-scope { margin-top: var(--space-3); font-size: var(--text-11); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  .experiment-form {
    display: grid;
    gap: var(--space-5);
    padding-bottom: var(--space-1);
  }
  .form-context {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    min-width: 0;
  }
  .editor-progress {
    margin: 0;
    padding: 0;
    border: 0;
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
    background: transparent;
  }
  .editor-progress ol { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; margin: 0 0 -1px; padding: 0; list-style: none; }
  .editor-progress li {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3) var(--space-3);
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: var(--color-text-muted);
  }
  .editor-progress li > span { display: grid; flex: 0 0 var(--space-6); width: var(--space-6); height: var(--space-6); place-items: center; border: 1px solid var(--color-border); border-radius: var(--radius-full); background: var(--color-bg-surface); font: 700 var(--text-xs)/var(--leading-none) var(--font-mono); }
  .editor-progress li > span :global(svg) { width: var(--space-3); height: var(--space-3); stroke-width: 3; }
  .editor-progress li > strong { overflow: hidden; font-size: var(--text-xs); font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
  .editor-progress li.current {
    border-bottom-color: var(--color-accent);
    background: transparent;
    box-shadow: none;
    color: var(--color-text-primary);
  }
  .editor-progress li.current > span { border-color: var(--color-border-accent); color: var(--color-accent-dark); background: var(--color-accent-subtle); }
  .editor-progress li.complete { color: var(--color-text-secondary); }
  .editor-progress li.complete > span { border-color: var(--color-success); color: var(--color-success-text); background: var(--color-success-subtle); }
  .origin-strip { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: baseline; min-width: 0; padding: 0; border: 0; background: transparent; text-align: right; }
  .origin-strip span { font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700; letter-spacing: var(--tracking-wide); text-transform: uppercase; color: var(--color-text-muted); }
  .origin-strip strong { font-size: var(--text-sm); color: var(--color-text-primary); }
  .origin-strip small { font-size: var(--text-11); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  .evidence-context { display: grid; gap: var(--space-2); margin-top: var(--space-4); padding: var(--space-3) 0; border-block: 1px solid var(--color-border); border-radius: 0; background: transparent; }
  .evidence-context span { color: var(--color-text-secondary); font: 700 var(--text-11)/var(--leading-snug) var(--font-mono); letter-spacing: var(--tracking-wider); text-transform: uppercase; }
  .evidence-context p { color: var(--color-text-primary); font-size: var(--text-13); line-height: var(--leading-normal); white-space: pre-wrap; }
  .evidence-context small { color: var(--color-text-secondary); font-size: var(--text-xs); line-height: var(--leading-normal); }
  .candidate-confirm { display: grid; gap: var(--space-2); margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); background: var(--color-bg-surface); }
  .candidate-confirm p { margin: 0; font-size: var(--text-13); line-height: var(--leading-normal); color: var(--color-text-primary); }
  .candidate-confirm-actions { display: flex; gap: var(--space-2); }
  .candidate-confirm-cancel, .candidate-confirm-confirm { display: inline-flex; align-items: center; justify-content: center; min-height: var(--space-10); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: 700; cursor: pointer; }
  .candidate-confirm-cancel { border: 1px solid var(--color-input-border); background: transparent; color: var(--color-text-secondary); transition: border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .candidate-confirm-cancel:hover { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .candidate-confirm-confirm { border: 0; background: var(--color-accent-hover); color: var(--color-text-on-accent); transition: background var(--duration-fast) var(--ease-default); }
  .candidate-confirm-confirm:hover { background: var(--color-accent-dark); }
  .candidate-confirm-cancel:focus-visible, .candidate-confirm-confirm:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  fieldset {
    min-width: 0;
    display: grid;
    gap: var(--space-4);
    margin: 0;
    padding: 0;
    border: 0;
    outline: none;
  }
  fieldset:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: var(--space-1);
  }
  legend { padding: 0; font-size: var(--text-md); font-weight: 700; color: var(--color-text-primary); }
  .stage-guide {
    margin-top: calc(var(--space-3) * -1);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
  }
  .form-cluster {
    display: grid;
    gap: var(--space-4);
    padding: 0 0 var(--space-5);
    border: 0;
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
    background: transparent;
  }
  .form-cluster:last-child { padding-bottom: 0; border-bottom: 0; }
  .action-grid { padding: 0; border: 0; background: transparent; }
  .form-subhead { margin: 0; color: var(--color-text-primary); font-size: var(--text-base); font-weight: 700; }
  label { display: grid; gap: var(--space-2); margin: 0; }
  label > span { font-size: var(--text-13); font-weight: 600; color: var(--color-text-primary); }
  label > span small { font-size: var(--text-11); font-weight: 500; color: var(--color-text-muted); }
  input { width: 100%; min-height: var(--space-10); padding: 0 var(--space-3); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: var(--color-bg-elevated); color: var(--color-text-primary); font: inherit; font-size: var(--text-13); line-height: var(--leading-normal); }
  .field-grid { display: grid; gap: var(--space-4); }
  .field-grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .field-grid.three { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .field-grid.three :global(.supporting-cost) { grid-column: 1 / -1; max-width: 24rem; }
  .action-grid :global(.contingency-action) { margin-top: var(--space-2); padding-top: var(--space-4); border-top: 1px solid var(--color-border); }
  .signal-note { margin: calc(var(--space-2) * -1) 0 0; font-size: var(--text-xs); line-height: var(--leading-normal); color: var(--color-text-secondary); }
  .signal-note strong { color: var(--color-text-secondary); }
  .overlay-explanation { margin: var(--space-1) 0 var(--space-4); color: var(--color-text-secondary); font-size: var(--text-sm); line-height: var(--leading-normal); }
  .footer-submit { display: flex; align-items: center; gap: var(--space-3); }
  .form-error { margin: 0; color: var(--color-error-text); font-size: var(--text-sm); line-height: var(--leading-normal); }
  .cancel-btn { display: inline-flex; align-items: center; justify-content: center; min-height: var(--space-10); padding: var(--space-2) var(--space-4); border: 1px solid var(--color-input-border); border-radius: var(--radius-md); background: transparent; color: var(--color-text-secondary); font-size: var(--text-13); font-weight: 600; cursor: pointer; transition: border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default); }
  .cancel-btn:hover:not(:disabled) { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
  .cancel-btn:active:not(:disabled) { transform: scale(0.98); }
  .cancel-btn:disabled { background: var(--color-bg-hover); color: var(--color-text-muted); border-color: var(--color-border); cursor: wait; }
  .cancel-btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

  @media (max-width: 900px) {
    .experiment-row { grid-template-columns: minmax(0, 1fr) auto; }
    .experiment-rule { grid-column: 1 / -1; grid-row: 2; }
    .results-sheet, .conclusion-summary { grid-row: auto; }
    .result-ledger { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .result-ledger div:nth-child(2) { border-right: 0; }
    .result-ledger div:nth-child(-n+2) { border-bottom: 1px solid var(--color-border); }
    .brief-export-body { grid-template-columns: minmax(0, 1fr) auto; }
    .brief-export-body .origin-status { grid-column: 1 / -1; }
  }
  @media (max-width: 600px) {
    .workspace { padding-inline: var(--space-4); }
    .workspace-head { align-items: flex-start; gap: var(--space-3); }
    .workspace-actions { flex-direction: column-reverse; align-items: flex-end; }
    .workspace-head .new-action { width: auto; }
    .experiment-row { grid-template-columns: 1fr; }
    .experiment-rule, .row-actions { grid-column: auto; grid-row: auto; }
    .row-actions { flex-wrap: wrap; }
    .row-actions button, .row-actions a { min-height: var(--space-12); }
    .form-context { align-items: flex-start; flex-direction: column; }
    .origin-strip { text-align: left; }
    .editor-progress li { align-items: center; flex-direction: row; padding-inline: var(--space-2); }
    .editor-progress li > strong { white-space: normal; }
    .brief-export-body .origin-status { grid-column: auto; }
    .brief-export-actions { justify-content: flex-start; }
    .brief-export-actions button, .brief-export-actions a { min-height: var(--space-12); }
    .conclusion-heading, .conclusion-summary dl { grid-template-columns: 1fr; }
    .conclusion-heading > span { justify-self: start; }
    .outcome-picker :global(.segment-cards) { grid-template-columns: 1fr; }
    .result-ledger { grid-template-columns: 1fr; }
    .result-ledger div { padding-left: 0; border-right: 0; border-bottom: 1px solid var(--color-border); }
    .result-ledger div:last-child { border-bottom: 0; }
    .field-grid.two, .field-grid.three { grid-template-columns: 1fr; }
    .field-grid.three :global(.supporting-cost) { grid-column: auto; max-width: none; }
    .action-grid :global(.contingency-action) { margin-top: 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    .cancel-btn:active:not(:disabled) { transform: none; }
  }
</style>
