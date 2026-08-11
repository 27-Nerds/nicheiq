<script lang="ts" module>
  import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
  import type { SelectionOwnerEvidenceKind, SelectionOwnerEvidencePosition } from "$lib/types/selectionOwnerEvidence";

  type EvidenceEffect = SelectionOwnerEvidencePosition | "UNSURE" | "";

  /** The add-evidence draft lives at module level so typed text survives the
   *  remounts caused by candidate/lens context swaps and parent reloads.
   *  Only one ledger is on screen at a time, so a single slot is enough. */
  const draft = $state({
    active: false,
    context: "",
    jobId: "",
    ideaId: "",
    ideaTitle: "",
    ideaRevision: 0,
    lens: "demand" as SelectionChallengeLens,
    position: "" as EvidenceEffect,
    kind: "" as SelectionOwnerEvidenceKind | "",
    title: "",
    content: "",
    sourceUrl: "",
    observedOn: "",
  });

  /** Save/retract announcements survive the invalidateAll remount, so the
   *  "Evidence loaded" announcement cannot clobber them (AssumptionMap's
   *  persistent-announcement pattern). */
  const savedAnnouncement = $state({ context: "", message: "" });

  /** True when an unsaved add-evidence draft has content. The risks page uses
   *  this for its candidate-switch dirty check. */
  export function ownerEvidenceDraftIsDirty(): boolean {
    return draft.active && Boolean(
      draft.position || draft.kind || draft.title.trim() || draft.content.trim()
      || draft.sourceUrl.trim() || draft.observedOn,
    );
  }

  export function discardOwnerEvidenceDraft(): void {
    draft.active = false;
    draft.context = "";
    draft.jobId = "";
    draft.ideaId = "";
    draft.ideaTitle = "";
    draft.ideaRevision = 0;
    draft.lens = "demand";
    draft.position = "";
    draft.kind = "";
    draft.title = "";
    draft.content = "";
    draft.sourceUrl = "";
    draft.observedOn = "";
  }
</script>

<script lang="ts">
  import { tick } from "svelte";
  import { ExternalLink, Loader2, Plus } from "lucide-svelte";
  import { createSelectionOwnerEvidence, getSelectionOwnerEvidence, retractSelectionOwnerEvidence } from "$lib/api";
  import DecisionHelp from "$lib/components/ui/DecisionHelp.svelte";
  import EmptyState from "$lib/components/ui/EmptyState.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type { SelectionOwnerEvidencePrefill } from "$lib/types/selectionCopilot";
  import type { SelectionOwnerEvidence } from "$lib/types/selectionOwnerEvidence";

  interface Props {
    jobId?: string;
    ideaId: string;
    ideaTitle?: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    onChanged?: () => void | Promise<void>;
    onReturnToDraft?: (target: {
      jobId: string;
      ideaId: string;
      ideaRevision: number;
      lens: SelectionChallengeLens;
    }) => void | Promise<void>;
    prefill?: SelectionOwnerEvidencePrefill | null;
    /** The parent surface may own the single add-evidence action. */
    showAddAction?: boolean;
  }

  let {
    jobId,
    ideaId,
    ideaTitle,
    ideaRevision,
    lens,
    onChanged,
    onReturnToDraft,
    prefill = null,
    showAddAction = true,
  }: Props = $props();
  let evidence = $state<SelectionOwnerEvidence[]>([]);
  let editable = $state(false);
  let loading = $state(false);
  let saving = $state(false);
  let pendingOpen = false;
  let error = $state("");
  let addError = $state("");
  let titleError = $state("");
  let contentError = $state("");
  let sourceUrlError = $state("");
  let retractError = $state("");
  let status = $state("");
  let loadedJob = "";
  let loaded = $state(false);
  let ledgerOpen = $state(draft.active);
  let positionError = $state("");
  let kindError = $state("");
  let discardPending = $state(false);
  let retractingId = $state("");
  let retractionReason = $state("");
  let retracting = $state(false);
  let appliedPrefillId = "";
  let focusedDraftContext = "";
  let prefillFeedback = $state<{ failed: boolean; message: string } | null>(null);
  let optionalDetailsOpen = $state(Boolean(draft.title || draft.observedOn || draft.sourceUrl));
  let ledgerSummary = $state<HTMLElement | null>(null);

  const contextKey = $derived([jobId ?? "", ideaId, ideaRevision, lens].join(":"));
  const current = $derived(evidence.filter((item) => item.ideaId === ideaId && item.ideaRevision === ideaRevision && item.lens === lens));
  const active = $derived(current.filter((item) => !item.retractedAt));
  const retracted = $derived(current.filter((item) => Boolean(item.retractedAt)));
  const earlier = $derived(evidence.filter((item) => item.ideaId === ideaId && item.ideaRevision !== ideaRevision && item.lens === lens));
  const contradicts = $derived(active.filter((item) => item.position === "CONTRADICTS").length);
  const retractingItem = $derived(active.find((item) => item.id === retractingId) ?? null);
  const showLedger = $derived(
    showAddAction
    || Boolean(error)
    || draft.active
    || active.length > 0
    || retracted.length > 0
    || earlier.length > 0,
  );

  const kindLabels: Record<SelectionOwnerEvidenceKind, string> = {
    NOTE: "First-hand observation",
    CUSTOMER_QUOTE: "Customer conversation or quote",
    ANALYTICS_OBSERVATION: "Analytics or measured result",
    LINK: "Web page or document",
  };

  const POSITION_OPTIONS: Array<{ value: Exclude<EvidenceEffect, "">; label: string }> = [
    { value: "SUPPORTS", label: "Supports the idea" },
    { value: "CONTRADICTS", label: "Raises a concern" },
    { value: "CONTEXT", label: "Context only" },
    { value: "UNSURE", label: "Not sure" },
  ];

  const lensLabels: Record<SelectionChallengeLens, string> = {
    demand: "customer demand",
    distribution: "buyer reach",
    competition: "differentiation",
    dependencies: "build feasibility",
  };

  const recheckLabels: Record<SelectionChallengeLens, string> = {
    demand: "Recheck demand",
    distribution: "Recheck buyer reach",
    competition: "Recheck differentiation",
    dependencies: "Recheck build feasibility",
  };

  function positionLabel(value: SelectionOwnerEvidencePosition) {
    return value === "SUPPORTS" ? "Strengthens" : value === "CONTRADICTS" ? "Raises concern" : "Adds context";
  }

  function dateLabel(value: string | null) {
    return value
      ? new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(value))
      : "";
  }

  function resetDraft() {
    discardOwnerEvidenceDraft();
    addError = "";
    positionError = "";
    kindError = "";
    titleError = "";
    contentError = "";
    sourceUrlError = "";
    discardPending = false;
    optionalDetailsOpen = false;
  }

  async function announceStatus(message: string) {
    status = "";
    await tick();
    status = message;
  }

  async function announceSaved(message: string) {
    savedAnnouncement.context = contextKey;
    savedAnnouncement.message = "";
    await tick();
    savedAnnouncement.message = message;
  }

  function beginAdd() {
    retractingId = "";
    retractionReason = "";
    draft.active = true;
    draft.context = contextKey;
    draft.jobId = jobId ?? "";
    draft.ideaId = ideaId;
    draft.ideaTitle = ideaTitle?.trim() || "Selected candidate";
    draft.ideaRevision = ideaRevision;
    draft.lens = lens;
    ledgerOpen = true;
    addError = "";
    discardPending = false;
    prefillFeedback = null;
    void focusAddForm();
  }

  function returnToDraft() {
    if (!onReturnToDraft || !draft.jobId || !draft.ideaId || draft.ideaRevision < 1) return;
    void onReturnToDraft({
      jobId: draft.jobId,
      ideaId: draft.ideaId,
      ideaRevision: draft.ideaRevision,
      lens: draft.lens,
    });
  }

  /** Opens the canonical evidence form from any parent-owned entry action. */
  export function openAddEvidence() {
    ledgerOpen = true;
    if (!loaded || loading) {
      pendingOpen = true;
      return;
    }
    if (!editable) return;
    if (draft.active) {
      if (draft.context === contextKey) void focusAddForm();
      return;
    }
    beginAdd();
  }

  function addDraftIsDirty() {
    return Boolean(
      draft.position || draft.kind || draft.title.trim() || draft.content.trim()
      || draft.sourceUrl.trim() || draft.observedOn,
    );
  }

  async function focusAddForm(id = "owner-evidence-content") {
    await tick();
    document.getElementById(id)?.focus();
  }

  async function requestCloseAdd() {
    if (saving) return;
    if (addDraftIsDirty()) {
      discardPending = true;
      await tick();
      document.getElementById("owner-evidence-keep-editing")?.focus();
      return;
    }
    resetDraft();
    await tick();
    ledgerSummary?.focus();
  }

  function beginRetract(item: SelectionOwnerEvidence) {
    resetDraft();
    retractingId = item.id;
    retractionReason = "";
    retractError = "";
  }

  /** Confirmed close: FormOverlay owns the dirty two-press gate. */
  function closeRetract() {
    if (retracting) return;
    retractingId = "";
    retractionReason = "";
    retractError = "";
  }

  function upsert(item: SelectionOwnerEvidence) {
    evidence = [item, ...evidence.filter((candidate) => candidate.id !== item.id)];
  }

  async function load() {
    if (!jobId) return;
    loading = true;
    loaded = false;
    error = "";
    await announceStatus("Loading your evidence…");
    try {
      const response = await getSelectionOwnerEvidence(jobId);
      evidence = response.evidence;
      editable = response.editable;
      await announceStatus("Evidence loaded");
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not load your evidence.";
      await announceStatus("");
    } finally {
      loading = false;
      loaded = true;
      if (pendingOpen) {
        pendingOpen = false;
        if (editable) beginAdd();
      }
    }
  }

  function observedDate(value: string | null | undefined): string {
    if (!value) return "";
    const parsed = new Date(value);
    return Number.isNaN(parsed.valueOf()) ? "" : parsed.toISOString().slice(0, 10);
  }

  function reviewCopilotPrefill(request: SelectionOwnerEvidencePrefill): void {
    if (request.requestId === appliedPrefillId) return;
    if (saving) {
      prefillFeedback = { failed: true, message: "Wait for the current evidence save to finish." };
      return;
    }
    if (!editable) {
      prefillFeedback = { failed: true, message: "This decision is locked, so owner evidence is read-only." };
      return;
    }
    if (
      request.ideaId !== ideaId
      || request.ideaRevision !== ideaRevision
      || request.lens !== lens
    ) {
      prefillFeedback = {
        failed: true,
        message: "This evidence draft references a different candidate revision or evidence lens.",
      };
      return;
    }
    if ((draft.active && addDraftIsDirty()) || retractingId) {
      prefillFeedback = {
        failed: true,
        message: "You have an unfinished evidence form. Save or close it before reviewing another analyst draft.",
      };
      return;
    }

    retractingId = "";
    retractionReason = "";
    draft.active = true;
    draft.context = contextKey;
    draft.jobId = jobId ?? "";
    draft.ideaId = ideaId;
    draft.ideaTitle = ideaTitle?.trim() || "Selected candidate";
    draft.ideaRevision = ideaRevision;
    draft.lens = lens;
    ledgerOpen = true;
    draft.position = request.values.position ?? "";
    draft.kind = request.values.kind ?? "";
    draft.title = request.values.title ?? "";
    draft.content = request.values.content ?? "";
    draft.sourceUrl = request.values.sourceUrl ?? "";
    draft.observedOn = observedDate(request.values.observedAt);
    addError = "";
    positionError = "";
    kindError = "";
    titleError = "";
    contentError = "";
    sourceUrlError = "";
    discardPending = false;
    optionalDetailsOpen = Boolean(draft.title || draft.observedOn || (draft.sourceUrl && draft.kind !== "LINK"));
    appliedPrefillId = request.requestId;
    prefillFeedback = { failed: false, message: "Analyst draft opened. Review it before saving the evidence." };
    void focusAddForm();
  }

  function generatedTitle(value: string): string {
    const compact = value.trim().replace(/\s+/g, " ");
    return compact.length <= 120 ? compact : `${compact.slice(0, 119).trimEnd()}…`;
  }

  function savedPosition(value: EvidenceEffect): SelectionOwnerEvidencePosition | null {
    if (!value) return null;
    return value === "UNSURE" ? "CONTEXT" : value;
  }

  function validateContent(value = draft.content): string {
    return value.trim().length < 3
      ? "Describe one observation, quote, behavior, or measured result."
      : "";
  }

  function validateTitle(value = draft.title): string {
    return value.trim() && value.trim().length < 3
      ? "Use at least 3 characters, or leave the title blank."
      : "";
  }

  function validateSourceUrl(value = draft.sourceUrl): string {
    const compact = value.trim();
    if (!compact) {
      return draft.kind === "LINK" ? "Add the web address for this source." : "";
    }
    try {
      const parsed = new URL(compact);
      if (!["http:", "https:"].includes(parsed.protocol)) {
        return "Use a web address that starts with http:// or https://.";
      }
      if (parsed.username || parsed.password) {
        return "Remove the username or password from this web address.";
      }
      return "";
    } catch {
      return "Enter a complete web address, such as https://example.com/source.";
    }
  }

  async function addEvidence() {
    if (!jobId || saving) return;
    addError = "";
    positionError = "";
    kindError = "";
    titleError = "";
    contentError = "";
    sourceUrlError = "";
    const persistedPosition = savedPosition(draft.position);
    if (!persistedPosition) positionError = "Choose how this affects the idea.";
    if (!draft.kind) kindError = "Choose where this evidence came from.";
    titleError = validateTitle();
    contentError = validateContent();
    sourceUrlError = validateSourceUrl();
    if (!persistedPosition || !draft.kind || titleError || contentError || sourceUrlError) {
      addError = "Check the highlighted answers before saving.";
      if (titleError || (sourceUrlError && draft.kind !== "LINK")) optionalDetailsOpen = true;
      await tick();
      const firstInvalidId = contentError
        ? "owner-evidence-content"
        : kindError
          ? "owner-evidence-kind"
          : sourceUrlError
            ? "owner-evidence-source"
            : positionError
              ? "owner-evidence-effect"
              : "owner-evidence-title";
      if (firstInvalidId === "owner-evidence-effect") {
        document.querySelector<HTMLButtonElement>("#owner-evidence-effect [role='radio']")?.focus();
      } else {
        document.getElementById(firstInvalidId)?.focus();
      }
      return;
    }
    const savedTitle = draft.title.trim() || generatedTitle(draft.content);
    saving = true;
    try {
      const response = await createSelectionOwnerEvidence(jobId, {
        ideaId,
        ideaRevision,
        lens,
        kind: draft.kind,
        position: persistedPosition,
        title: savedTitle,
        content: draft.content.trim(),
        sourceUrl: draft.sourceUrl.trim() || null,
        observedAt: draft.observedOn ? new Date(draft.observedOn + "T00:00:00.000Z").toISOString() : null,
      });
      upsert(response.evidence);
      await announceSaved(
        response.cached
          ? `This evidence was already saved. ${recheckLabels[lens]} to include it in the review.`
          : `Evidence saved. ${recheckLabels[lens]} to include it in the review.`,
      );
      resetDraft();
      await onChanged?.();
      await tick();
      ledgerSummary?.focus();
    } catch (cause) {
      addError = cause instanceof Error ? cause.message : "Could not add evidence.";
    } finally {
      saving = false;
    }
  }

  async function retract(item: SelectionOwnerEvidence) {
    if (!jobId || retracting || retractionReason.trim().length < 3) {
      if (retractionReason.trim().length < 3) retractError = "Add a short reason for the retraction.";
      return;
    }
    retracting = true;
    retractError = "";
    try {
      const response = await retractSelectionOwnerEvidence(jobId, item.id, retractionReason.trim());
      upsert(response.evidence);
      retractingId = "";
      retractionReason = "";
      await announceSaved(
        response.cached
          ? `This evidence was already retracted. ${recheckLabels[lens]} for a current review.`
          : `Evidence retracted. ${recheckLabels[lens]} for a current review.`,
      );
      await onChanged?.();
    } catch (cause) {
      retractError = cause instanceof Error ? cause.message : "Could not retract evidence.";
    } finally {
      retracting = false;
    }
  }

  $effect(() => {
    if (!jobId || loadedJob === jobId) return;
    loadedJob = jobId;
    void load();
  });

  $effect(() => {
    if (!prefill || !loaded || loading || prefill.requestId === appliedPrefillId) return;
    reviewCopilotPrefill(prefill);
  });

  $effect(() => {
    if (!draft.active || draft.context !== contextKey || focusedDraftContext === contextKey) return;
    focusedDraftContext = contextKey;
    ledgerOpen = true;
    void focusAddForm();
  });
</script>

{#if showLedger}
<details class="ledger" bind:open={ledgerOpen}>
  <summary bind:this={ledgerSummary}>
    <span><strong>Your evidence</strong> · {active.length} saved {#if contradicts}· {contradicts} {contradicts === 1 ? "raises" : "raise"} concern{/if}</span>
    {#if loading}<Loader2 class="spin owner-evidence-spin" aria-hidden="true" /><span class="sr-only">Loading your evidence</span>{/if}
  </summary>
  <div class="ledger-body">
    <div class="ledger-intro">
      <p>Your evidence stays separate from Discovery sources, remains marked as unverified, and is included the next time you check this risk area.</p>
      {#if editable && showAddAction && !draft.active}
        <button type="button" class="text-action" onclick={beginAdd}><Plus aria-hidden="true" /> Add your evidence</button>
      {:else if !editable}<span class="locked">Decision locked · evidence is read-only</span>{/if}
    </div>

    {#if error}<div class="message error" role="alert">{error} <button type="button" onclick={() => void load()}>Retry</button></div>{/if}
    <div class="sr-status" aria-live="polite">{status}</div>
    {#if savedAnnouncement.context === contextKey && savedAnnouncement.message}
      <p class="save-feedback" role="status">{savedAnnouncement.message}</p>
    {/if}

    {#if !loading && active.length === 0}<EmptyState inline title="No evidence added for this risk area." />
    {:else}<ul class="records" role="list">
      {#each active as item (item.id)}
        <li><details class="record"><summary>
          <span class="position position--{item.position.toLowerCase()}">{positionLabel(item.position)}</span>
          <span><strong>{item.title}</strong><small>{kindLabels[item.kind]} · {dateLabel(item.observedAt ?? item.createdAt)} · <span class="unverified">Unverified</span></small></span>
        </summary><div class="record-body">
          <p>{item.content}</p><div class="record-actions">
            {#if item.sourceUrl}<a href={item.sourceUrl} target="_blank" rel="noreferrer"><ExternalLink aria-hidden="true" /> Source<span class="sr-only"> (opens in new tab)</span></a>{/if}
            {#if editable}<button type="button" onclick={() => beginRetract(item)}>Retract</button>{/if}
          </div>
        </div></details></li>
      {/each}
    </ul>{/if}

    {#if retracted.length}<details class="archive"><summary>Retracted ({retracted.length})</summary>{#each retracted as item}<p><strong>{item.title}</strong> · {item.retractionReason}</p>{/each}</details>{/if}
    {#if earlier.length}<details class="archive"><summary>Earlier revisions ({earlier.length})</summary>{#each earlier as item}<p><strong>{item.title}</strong> · Rev {item.ideaRevision} · no longer current</p>{/each}</details>{/if}

    <p
      class="prefill-feedback"
      class:is-empty={draft.active || !prefillFeedback || prefillFeedback.failed}
      role="status"
      hidden={draft.active || !prefillFeedback || prefillFeedback.failed}
    >{(!draft.active && prefillFeedback && !prefillFeedback.failed) ? prefillFeedback.message : ""}</p>
    <p
      class="prefill-feedback is-error"
      class:is-empty={draft.active || !prefillFeedback?.failed}
      role="alert"
      hidden={draft.active || !prefillFeedback?.failed}
    >{(!draft.active && prefillFeedback?.failed) ? prefillFeedback.message : ""}</p>

    {#if draft.active}
<section
  class="evidence-editor"
  aria-labelledby="owner-evidence-form-title"
  data-annotation-anchor={`selection:owner-evidence:${ideaId}:${ideaRevision}:${lens}`}
>
  <header class="editor-header">
    <div>
      <span class="editor-eyebrow">Add evidence</span>
      <h4 id="owner-evidence-form-title">Record what you learned</h4>
      <p>{ideaTitle?.trim() || "Selected candidate"} · revision {ideaRevision} · {lensLabels[lens]}</p>
    </div>
    <DecisionHelp title="How this evidence is used" label="Why this matters" position="bottom">
      This is saved to the exact idea revision as unverified evidence. It is included when you next check this risk area, but it never changes a score by itself.
    </DecisionHelp>
  </header>

  {#if prefillFeedback?.failed}
    <p class="prefill-feedback is-error" role="alert">{prefillFeedback.message}</p>
  {/if}
  {#if draft.context !== contextKey}
    <div class="message context-warning" role="alert">
      <span>
        This draft belongs to <strong>{draft.ideaTitle}</strong> · revision {draft.ideaRevision} · {lensLabels[draft.lens]}.
        It cannot be moved to a different idea or risk area.
      </span>
      {#if onReturnToDraft}
        <button type="button" class="text-action" onclick={returnToDraft}>Return to draft</button>
      {/if}
      <button type="button" class="text-action danger-action" onclick={resetDraft}>Discard draft</button>
    </div>
  {:else}
    <form id="owner-evidence-form" class="evidence-form" novalidate onsubmit={(event) => { event.preventDefault(); void addEvidence(); }}>
      {#if addError}<p class="form-error-summary" role="alert">{addError}</p>{/if}

      <FormField
        id="owner-evidence-content"
        kind="textarea"
        label="What did you learn?"
        hint="Record an observation, exact quote, behavior, or measured result, not a hunch or conclusion. Save an unresolved belief as a question to resolve instead."
        required
        minlength={3}
        maxlength={8000}
        rows={5}
        bind:value={draft.content}
        placeholder="Record the observation and enough context to understand it later."
        error={contentError}
        oninput={() => {
          addError = "";
          if (!validateContent()) contentError = "";
          discardPending = false;
        }}
        onblur={() => (contentError = validateContent())}
      />

      <fieldset class="source-group">
        <legend>Where did it come from?</legend>
        <p class="field-hint">Choose the source so you can judge and find this evidence later.</p>

        <FormField
          id="owner-evidence-kind"
          kind="select"
          label="Source type"
          required
          error={kindError}
          bind:value={() => draft.kind, (value) => {
            draft.kind = value as SelectionOwnerEvidenceKind | "";
            addError = "";
            kindError = "";
            sourceUrlError = "";
            discardPending = false;
          }}
          onblur={() => {
            if (!draft.kind) kindError = "Choose where this evidence came from.";
          }}
        >
          <option value="" disabled>Select a source type</option>
          {#each Object.entries(kindLabels) as [value, label]}<option value={value}>{label}</option>{/each}
        </FormField>

        {#if draft.kind === "LINK"}
          <FormField
            id="owner-evidence-source"
            type="url"
            label="Source URL"
            hint="Link to the page or document."
            required
            maxlength={1000}
            bind:value={draft.sourceUrl}
            placeholder="https://"
            error={sourceUrlError}
            oninput={() => {
              addError = "";
              if (!validateSourceUrl()) sourceUrlError = "";
              discardPending = false;
            }}
            onblur={() => (sourceUrlError = validateSourceUrl())}
          />
        {/if}
      </fieldset>

      <div class="field" id="owner-evidence-effect">
        <span class="field-label" id="owner-evidence-position-label">What does this evidence suggest?</span>
        <p class="field-hint" id="owner-evidence-position-hint">Choose “Not sure” when the evidence matters but its direction is unclear. It will be saved as context.</p>
        <SegmentControl
          density="compact"
          label="How the evidence affects the idea"
          labelledBy="owner-evidence-position-label"
          describedBy={positionError ? "owner-evidence-position-hint owner-evidence-position-error" : "owner-evidence-position-hint"}
          invalid={Boolean(positionError)}
          options={POSITION_OPTIONS}
          value={draft.position}
          onChange={(value) => {
            draft.position = value as EvidenceEffect;
            addError = "";
            positionError = "";
            discardPending = false;
          }}
        />
        {#if positionError}<p class="field-error" id="owner-evidence-position-error" role="alert">{positionError}</p>{/if}
      </div>

      <details class="optional-details" bind:open={optionalDetailsOpen}>
        <summary>Optional details</summary>
        <div class="optional-fields">
          {#if draft.kind && draft.kind !== "LINK"}
            <FormField
              id="owner-evidence-source"
              type="url"
              label="Source link"
              hint="Link to notes, a recording, dashboard, or report if you have one."
              optional
              maxlength={1000}
              bind:value={draft.sourceUrl}
              placeholder="https://"
              error={sourceUrlError}
              oninput={() => {
                addError = "";
                if (!validateSourceUrl()) sourceUrlError = "";
                discardPending = false;
              }}
              onblur={() => (sourceUrlError = validateSourceUrl())}
            />
          {/if}
          <div class="form-row">
            <FormField
              id="owner-evidence-observed"
              type="date"
              label="Observed on"
              optional
              bind:value={draft.observedOn}
              oninput={() => { addError = ""; discardPending = false; }}
            />
            <FormField
              id="owner-evidence-title"
              label="Short title"
              hint="Leave blank and we’ll use the beginning of what you learned."
              optional
              minlength={3}
              maxlength={300}
              bind:value={draft.title}
              placeholder="Four interviewees would not pay for another dashboard"
              error={titleError}
              oninput={() => {
                addError = "";
                if (!validateTitle()) titleError = "";
                discardPending = false;
              }}
              onblur={() => (titleError = validateTitle())}
            />
          </div>
        </div>
      </details>

      {#if discardPending}
        <div class="discard-prompt" role="alert">
          <span>Discard this unsaved evidence?</span>
          <div>
            <button id="owner-evidence-keep-editing" type="button" class="text-action" onclick={() => { discardPending = false; void focusAddForm(); }}>Keep editing</button>
            <button type="button" class="text-action danger-action" onclick={resetDraft}>Discard draft</button>
          </div>
        </div>
      {/if}

      <div class="editor-actions">
        <button type="button" class="cancel-btn" disabled={saving} onclick={requestCloseAdd}>Cancel</button>
        <SubmitButton
          type="submit"
          label="Save evidence"
          loadingText="Saving…"
          loading={saving}
          class="submit-btn"
        />
      </div>
    </form>
  {/if}
</section>
    {/if}
  </div>
</details>
{/if}

<FormOverlay
  open={Boolean(retractingItem)}
  size="compact"
  title="Retract evidence"
  eyebrow="Evidence"
  description={retractingItem ? `“${retractingItem.title}” remains in the immutable record with your reason.` : undefined}
  annotationAnchor={retractingItem ? `selection:owner-evidence-retract:${retractingItem.id}` : undefined}
  onRequestClose={closeRetract}
  dirty={Boolean(retractionReason.trim())}
  closeWarning="Your reason has not been saved. Close again to discard it."
>
  {#if retractingItem}
    <form id="retract-evidence-form" class="retract-form" onsubmit={(event) => { event.preventDefault(); void retract(retractingItem); }}>
      <DecisionHelp title="Correct the evidence" label="Immutable history">
        Retract an entry when it no longer stands, then add a corrected one if you have better information. Future evidence checks skip retracted entries; the archive keeps the original, so your decision trail stays complete.
      </DecisionHelp>
      <FormField
        id="retract-reason"
        kind="textarea"
        label="Why are you retracting this?"
        required
        minlength={3}
        maxlength={500}
        rows={3}
        bind:value={retractionReason}
        error={retractError}
        oninput={() => {
          if (retractionReason.trim().length >= 3) retractError = "";
        }}
        onblur={() => {
          if (retractionReason.trim().length < 3) retractError = "Add a short reason for the retraction.";
        }}
      />
    </form>
  {/if}
  {#snippet footerCancel(requestClose)}
    <button type="button" class="cancel-btn" disabled={retracting} onclick={requestClose}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <SubmitButton
      type="button"
      label="Confirm retraction"
      loadingText="Retracting…"
      loading={retracting}
      disabled={!retractingItem}
      onclick={() => { if (retractingItem) void retract(retractingItem); }}
      class="submit-btn"
    />
  {/snippet}
</FormOverlay>

<style>
  .ledger { border-block: 1px solid var(--color-border); }
  .ledger > summary { display:flex; align-items:center; justify-content:space-between; min-height:var(--space-12); color:var(--color-text-secondary); font-size:var(--text-13); cursor:pointer; transition:color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .ledger > summary:hover { color:var(--color-text-primary); }
  .ledger > summary:active { transform:scale(0.98); }
  .ledger > summary strong { color:var(--color-text-primary); font-size:var(--text-13); letter-spacing:var(--tracking-normal); }
  .ledger > summary :global(svg), .text-action :global(svg), .record-actions :global(svg) { width:var(--text-base); height:var(--text-base); }
  .ledger-body { padding-bottom:var(--space-3); }
  .ledger-intro { display:flex; align-items:center; justify-content:space-between; gap:var(--space-4); padding:var(--space-3) 0; }
  .ledger-intro p { max-width:65ch; margin:0; color:var(--color-text-secondary); font-size:var(--text-13); line-height:var(--leading-normal); text-wrap:pretty; }
  button { font:inherit; }
  .text-action, .record-actions button, .record-actions a, .message button { display:inline-flex; align-items:center; gap:var(--space-1-5); min-height:var(--space-8); padding:var(--space-1) 0; border:0; background:transparent; color:var(--color-accent-dark); font-size:var(--text-13); font-weight:700; white-space:nowrap; cursor:pointer; text-decoration:none; transition:color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .text-action:hover, .record-actions button:hover, .record-actions a:hover, .message button:hover { color:var(--color-accent-hover); }
  .text-action:active, .record-actions button:active, .record-actions a:active, .message button:active { transform:scale(0.98); }
  .locked { color:var(--color-text-secondary); font-size:var(--text-xs); }
  .message { max-width:65ch; padding:var(--space-3) 0; color:var(--color-text-secondary); font-size:var(--text-13); line-height:var(--leading-normal); }
  .message.error { color:var(--color-error-text); }
  .save-feedback { max-width:65ch; margin:var(--space-2) 0; padding:var(--space-2) var(--space-3); border-radius:var(--radius-md); background:var(--color-success-subtle); color:var(--color-success-text); font-size:var(--text-13); font-weight:600; line-height:var(--leading-normal); }
  .prefill-feedback { max-width:65ch; margin:var(--space-2) 0 0; color:var(--color-text-secondary); font-size:var(--text-13); line-height:var(--leading-normal); }
  .prefill-feedback.is-error { color:var(--color-error-text); }
  .prefill-feedback.is-empty { margin:0; }
  .context-warning { display:flex; flex-wrap:wrap; align-items:center; gap:var(--space-2); padding:var(--space-3); border-radius:var(--radius-md); background:var(--color-warning-subtle); }
  .context-warning > span { flex:1 1 28rem; }
  .sr-status { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }

  /* ── Inline evidence form ── */
  .evidence-editor { display:grid; gap:var(--space-5); max-width:56rem; margin-top:var(--space-5); padding:var(--space-5) 0 0; border-top:1px solid var(--color-border-emphasis); }
  .editor-header { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-6); padding-bottom:var(--space-4); border-bottom:1px solid var(--color-border); }
  .editor-header > div { display:grid; gap:var(--space-1); min-width:0; }
  .editor-eyebrow { color:var(--color-text-muted); font-family:var(--font-mono); font-size:var(--text-11); font-weight:700; letter-spacing:var(--tracking-wider); text-transform:uppercase; }
  .editor-header h4 { max-width:34ch; margin:0; color:var(--color-text-primary); font-size:var(--text-xl); line-height:var(--leading-tight); letter-spacing:var(--tracking-tight); text-wrap:balance; }
  .editor-header p { max-width:65ch; margin:var(--space-1) 0 0; color:var(--color-text-secondary); font-size:var(--text-13); line-height:var(--leading-normal); text-wrap:pretty; }
  .evidence-form { display:grid; gap:var(--space-5); }
  .form-error-summary { margin:0; padding:var(--space-3); border:1px solid var(--color-border-error); border-radius:var(--radius-md); background:var(--color-error-subtle); color:var(--color-error-text); font-size:var(--text-sm); font-weight:600; line-height:var(--leading-normal); }
  .source-group { display:grid; gap:var(--space-3); min-width:0; margin:0; padding:0; border:0; }
  .source-group legend { margin:0; padding:0; color:var(--color-text-primary); font-size:var(--text-base); font-weight:700; }
  .source-group > .field-hint { margin:calc(var(--space-1) * -1) 0 0; }
  .field { display:grid; gap:var(--space-1-5); }
  .field-label { display:flex; align-items:baseline; gap:var(--space-2); font-size:var(--text-base); font-weight:700; color:var(--color-text-primary); }
  .field-hint { max-width:65ch; margin:0; font-size:var(--text-13); line-height:var(--leading-normal); color:var(--color-text-muted); text-wrap:pretty; }
  .field-error { margin:0; color:var(--color-error-text); font-size:var(--text-13); line-height:var(--leading-normal); }
  .form-row { display:grid; grid-template-columns:1.5fr 1fr; gap:var(--space-4); }
  .optional-details { border-top:1px solid var(--color-border); }
  .optional-details > summary { display:flex; align-items:center; min-height:var(--space-10); color:var(--color-text-secondary); font-size:var(--text-13); font-weight:700; cursor:pointer; }
  .optional-details > summary:hover { color:var(--color-text-primary); }
  .optional-details > summary:active { transform:scale(0.98); transform-origin:left; }
  .optional-fields { display:grid; gap:var(--space-4); padding-top:var(--space-3); }
  .discard-prompt { display:flex; align-items:center; justify-content:space-between; gap:var(--space-4); padding:var(--space-3); border:1px solid var(--color-error-text); border-radius:var(--radius-md); background:var(--color-error-subtle); color:var(--color-text-primary); font-size:var(--text-sm); font-weight:600; }
  .discard-prompt > div { display:flex; align-items:center; gap:var(--space-3); }
  .danger-action { color:var(--color-error-text); }
  .editor-actions { display:flex; align-items:center; justify-content:flex-end; gap:var(--space-3); padding-top:var(--space-1-5); }
  .editor-actions :global(button) { white-space:nowrap; }
  .retract-form { display:grid; gap:var(--space-4); }

  /* ── Overlay footer ── */
  .cancel-btn { display:inline-flex; align-items:center; justify-content:center; min-height:var(--space-10); padding:var(--space-2) var(--space-4); border:1px solid var(--color-input-border); border-radius:var(--radius-md); background:transparent; color:var(--color-text-secondary); font-size:var(--text-13); font-weight:700; white-space:nowrap; cursor:pointer; transition:transform var(--duration-fast) var(--ease-default), border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default); }
  .cancel-btn:hover:not(:disabled) { border-color:var(--color-text-secondary); color:var(--color-text-primary); }
  .cancel-btn:active:not(:disabled) { transform:scale(0.98); }
  .cancel-btn:disabled { background:var(--color-bg-hover); color:var(--color-text-muted); cursor:wait; }
  .cancel-btn:focus-visible { outline:2px solid var(--color-accent); outline-offset:2px; }

  /* ── Records (display) ── */
  .records { margin:0; padding:0; list-style:none; border-top:1px solid var(--color-border); }
  .record { border-bottom:1px solid var(--color-border); }
  .record > summary { display:grid; grid-template-columns:7rem minmax(0,1fr); gap:var(--space-3); padding:var(--space-3) 0; cursor:pointer; transition:color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default); }
  .record > summary:hover { transform:translateX(2px); color:var(--color-text-primary); }
  .record > summary:active { transform:scale(0.98); }
  .record > summary > span:last-child { display:grid; gap:var(--space-1); }
  .record strong { max-width:55ch; font-size:var(--text-13); line-height:var(--leading-snug); text-wrap:pretty; } .record small { color:var(--color-text-secondary); font-size:var(--text-sm); }
  .record .unverified { color:var(--color-text-muted); font-size:var(--text-xs); font-weight:700; letter-spacing:var(--tracking-wide); text-transform:uppercase; }
  .position { font-size:var(--text-sm); font-weight:800; text-transform:uppercase; }
  .position--supports { color:var(--color-success-text); } .position--contradicts { color:var(--color-error-text); } .position--context { color:var(--color-text-secondary); }
  .record-body { padding:0 0 var(--space-3) calc(var(--space-30) + var(--space-1)); }
  .record-body > p { max-width:65ch; margin:0; color:var(--color-text-secondary); font-size:var(--text-13); line-height:var(--leading-normal); white-space:pre-wrap; text-wrap:pretty; }
  .record-actions { display:flex; gap:var(--space-3); margin-top:var(--space-2); }
  .archive { padding-top:var(--space-3); color:var(--color-text-secondary); font-size:var(--text-sm); line-height:var(--leading-normal); }
  .archive > summary { cursor:pointer; transition:color var(--duration-fast) var(--ease-default); }
  .archive > summary:hover { color:var(--color-text-primary); }
  .archive > summary:active { transform:scale(0.98); }
  .archive p { margin:var(--space-2) 0 0; }
  summary:focus-visible, button:focus-visible, a:focus-visible { outline:2px solid var(--color-accent); outline-offset:2px; }
  :global(.owner-evidence-spin) { animation:owner-evidence-spin var(--duration-slowest) linear infinite; } @keyframes owner-evidence-spin { to { transform:rotate(360deg); } }
  @media(max-width:760px){ .ledger-intro{align-items:flex-start;flex-direction:column;gap:var(--space-1-5)}.editor-header{align-items:flex-start;flex-direction:column;gap:var(--space-3)}.form-row{grid-template-columns:1fr}.discard-prompt{align-items:flex-start;flex-direction:column}.editor-actions{align-items:stretch;flex-direction:column}.editor-actions :global(button){width:100%}.record>summary{grid-template-columns:1fr;gap:var(--space-1)}.record-body{padding-left:0} }
  @media (prefers-reduced-motion: reduce) {
    .ledger *,
    .ledger *::before,
    .ledger *::after,
    .evidence-editor *,
    .evidence-editor *::before,
    .evidence-editor *::after {
      transition:none !important;
      animation:none !important;
    }
    .ledger > summary:active,
    .text-action:hover, .record-actions button:hover, .record-actions a:hover, .message button:hover,
    .text-action:active, .record-actions button:active, .record-actions a:active, .message button:active,
    .cancel-btn:hover:not(:disabled),
    .cancel-btn:active:not(:disabled),
    .record > summary:hover,
    .record > summary:active,
    .archive > summary:active { transform:none; }
    .optional-details > summary:active { transform:none; }
  }
</style>
