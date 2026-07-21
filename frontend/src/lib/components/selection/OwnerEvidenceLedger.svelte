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
  import type { SelectionChallengeLens } from "$lib/types/selectionChallenge";
  import type { SelectionOwnerEvidencePrefill } from "$lib/types/selectionCopilot";
  import type { SelectionOwnerEvidence, SelectionOwnerEvidenceKind, SelectionOwnerEvidencePosition } from "$lib/types/selectionOwnerEvidence";

  interface Props {
    jobId?: string;
    ideaId: string;
    ideaTitle?: string;
    ideaRevision: number;
    lens: SelectionChallengeLens;
    onChanged?: () => void | Promise<void>;
    prefill?: SelectionOwnerEvidencePrefill | null;
  }

  let { jobId, ideaId, ideaTitle, ideaRevision, lens, onChanged, prefill = null }: Props = $props();
  let evidence = $state<SelectionOwnerEvidence[]>([]);
  let editable = $state(false);
  let loading = $state(false);
  let saving = $state(false);
  let error = $state("");
  let addError = $state("");
  let titleError = $state("");
  let contentError = $state("");
  let sourceUrlError = $state("");
  let retractError = $state("");
  let status = $state("");
  let loadedJob = "";
  let loaded = $state(false);
  let adding = $state(false);
  let draftContext = $state("");
  let position = $state<SelectionOwnerEvidencePosition | "">("");
  let kind = $state<SelectionOwnerEvidenceKind>("NOTE");
  let title = $state("");
  let content = $state("");
  let sourceUrl = $state("");
  let observedOn = $state("");
  let retractingId = $state("");
  let retractionReason = $state("");
  let retracting = $state(false);
  let appliedPrefillId = $state("");
  let prefillFeedback = $state<{ failed: boolean; message: string } | null>(null);

  const contextKey = $derived([ideaId, ideaRevision, lens].join(":"));
  const current = $derived(evidence.filter((item) => item.ideaId === ideaId && item.ideaRevision === ideaRevision && item.lens === lens));
  const active = $derived(current.filter((item) => !item.retractedAt));
  const retracted = $derived(current.filter((item) => Boolean(item.retractedAt)));
  const earlier = $derived(evidence.filter((item) => item.ideaId === ideaId && item.ideaRevision !== ideaRevision && item.lens === lens));
  const contradicts = $derived(active.filter((item) => item.position === "CONTRADICTS").length);
  const retractingItem = $derived(active.find((item) => item.id === retractingId) ?? null);

  const kindLabels: Record<SelectionOwnerEvidenceKind, string> = {
    NOTE: "Note",
    CUSTOMER_QUOTE: "Customer quote",
    ANALYTICS_OBSERVATION: "Analytics observation",
    LINK: "Link",
  };

  const POSITION_OPTIONS: Array<{ value: SelectionOwnerEvidencePosition; label: string }> = [
    { value: "SUPPORTS", label: "Supports" },
    { value: "CONTRADICTS", label: "Contradicts" },
    { value: "CONTEXT", label: "Context" },
  ];

  function positionLabel(value: SelectionOwnerEvidencePosition) {
    return value[0] + value.slice(1).toLowerCase();
  }

  function dateLabel(value: string | null) {
    return value
      ? new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(value))
      : "";
  }

  function resetDraft() {
    adding = false;
    draftContext = "";
    position = "";
    kind = "NOTE";
    title = "";
    content = "";
    sourceUrl = "";
    observedOn = "";
    addError = "";
    titleError = "";
    contentError = "";
    sourceUrlError = "";
  }

  async function announceStatus(message: string) {
    status = "";
    await tick();
    status = message;
  }

  function beginAdd() {
    retractingId = "";
    retractionReason = "";
    adding = true;
    draftContext = contextKey;
    addError = "";
    prefillFeedback = null;
  }

  function addDraftIsDirty() {
    return Boolean(
      position || kind !== "NOTE" || title.trim() || content.trim() || sourceUrl.trim() || observedOn,
    );
  }

  /** Confirmed close: FormOverlay owns the dirty two-press gate. */
  function closeAdd() {
    if (saving) return;
    resetDraft();
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
    if ((adding && addDraftIsDirty()) || retractingId) {
      prefillFeedback = {
        failed: true,
        message: "You have an unfinished evidence form. Save or close it before reviewing another analyst draft.",
      };
      return;
    }

    retractingId = "";
    retractionReason = "";
    adding = true;
    draftContext = contextKey;
    position = request.values.position ?? "";
    kind = request.values.kind ?? "NOTE";
    title = request.values.title ?? "";
    content = request.values.content ?? "";
    sourceUrl = request.values.sourceUrl ?? "";
    observedOn = observedDate(request.values.observedAt);
    addError = "";
    appliedPrefillId = request.requestId;
    prefillFeedback = { failed: false, message: "Analyst draft opened. Review the evidence before adding it to the ledger." };
  }

  async function addEvidence() {
    if (!jobId || saving) return;
    addError = "";
    titleError = "";
    contentError = "";
    sourceUrlError = "";
    if (!position) {
      addError = "Choose whether this evidence supports, contradicts, or adds context.";
      return;
    }
    if (title.trim().length < 3) titleError = "Add a title of at least 3 characters.";
    if (content.trim().length < 3) contentError = "Add evidence of at least 3 characters.";
    if (kind === "LINK" && !sourceUrl.trim()) sourceUrlError = "A source URL is required for link evidence.";
    if (titleError || contentError || sourceUrlError) {
      addError = "Fix the highlighted fields before saving.";
      return;
    }
    saving = true;
    try {
      const response = await createSelectionOwnerEvidence(jobId, {
        ideaId,
        ideaRevision,
        lens,
        kind,
        position,
        title: title.trim(),
        content: content.trim(),
        sourceUrl: sourceUrl.trim() || null,
        observedAt: observedOn ? new Date(observedOn + "T00:00:00.000Z").toISOString() : null,
      });
      upsert(response.evidence);
      await announceStatus(response.cached ? "Evidence already recorded" : "Evidence added");
      resetDraft();
      await onChanged?.();
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
      await announceStatus(response.cached ? "Evidence was already retracted" : "Evidence retracted");
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
</script>

<details class="ledger">
  <summary>
    <span><strong>Your evidence</strong> · {active.length} active {#if contradicts}· {contradicts} contradicts{/if}</span>
    {#if loading}<Loader2 class="spin owner-evidence-spin" aria-hidden="true" /><span class="sr-only">Loading your evidence</span>{/if}
  </summary>
  <div class="ledger-body">
    <div class="ledger-intro">
      <p>Recorded for your decision and checked as unverified owner input.</p>
      {#if editable && !adding}
        <button type="button" class="text-action" onclick={beginAdd}><Plus aria-hidden="true" /> Add evidence</button>
      {:else if !editable}<span class="locked">Decision locked · evidence is read-only</span>{/if}
    </div>

    {#if error}<div class="message error" role="alert">{error} <button type="button" onclick={() => void load()}>Retry</button></div>{/if}
    <div class="sr-status" aria-live="polite">{status}</div>

    {#if !loading && active.length === 0}<EmptyState inline title="No owner evidence recorded yet." />
    {:else}<ul class="records" role="list">
      {#each active as item (item.id)}
        <li><details class="record"><summary>
          <span class="position position--{item.position.toLowerCase()}">{positionLabel(item.position)}</span>
          <span><strong>{item.title}</strong><small>{kindLabels[item.kind]} · {dateLabel(item.observedAt ?? item.createdAt)}</small></span>
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
  </div>
</details>

<p
  class="prefill-feedback"
  class:is-empty={adding || !prefillFeedback || prefillFeedback.failed}
  role="status"
  hidden={adding || !prefillFeedback || prefillFeedback.failed}
>{(!adding && prefillFeedback && !prefillFeedback.failed) ? prefillFeedback.message : ""}</p>
<p
  class="prefill-feedback is-error"
  class:is-empty={adding || !prefillFeedback?.failed}
  role="alert"
  hidden={adding || !prefillFeedback?.failed}
>{(!adding && prefillFeedback?.failed) ? prefillFeedback.message : ""}</p>

<FormOverlay
  open={adding}
  size="form"
  title="Add owner evidence"
  eyebrow="Evidence ledger"
  description={`${ideaTitle?.trim() || "Selected candidate"} · revision ${ideaRevision} · ${lens} lens`}
  annotationAnchor={`selection:owner-evidence:${ideaId}:${ideaRevision}:${lens}`}
  onRequestClose={closeAdd}
  dirty={addDraftIsDirty()}
  closeWarning="You have unsaved evidence. Close again to discard it."
  footerMessage={addError}
>
  {#if prefillFeedback?.failed}
    <p class="prefill-feedback is-error" role="alert">{prefillFeedback.message}</p>
  {/if}
  {#if draftContext !== contextKey}
    <div class="message context-warning" role="alert">Candidate or lens changed while this draft was open.
      <button type="button" class="text-action" onclick={beginAdd}>Start here instead</button>
      <button type="button" class="text-action" onclick={resetDraft}>Discard draft</button>
    </div>
  {:else}
    <form id="owner-evidence-form" class="evidence-form" onsubmit={(event) => { event.preventDefault(); void addEvidence(); }}>
      <div class="evidence-guidance">
        <div>
          <strong>Record one concrete observation</strong>
          <p>Use an exact quote, measured result, or specific fact. Keep your interpretation in the title and the observed detail in the evidence field.</p>
        </div>
        <DecisionHelp title="How owner evidence is used" label="Why this matters" position="bottom">
          Evidence is saved to this exact candidate revision and lens as unverified owner input, and can inform later evidence checks.
        </DecisionHelp>
      </div>

      <div class="field">
        <span class="field-label" id="owner-evidence-position-label">Does this strengthen or weaken the case?</span>
        <p class="field-hint">Use Context when the observation matters but does not point clearly for or against the candidate.</p>
        <SegmentControl
          density="compact"
          label="Evidence position"
          options={POSITION_OPTIONS}
          value={position}
          onChange={(value) => {
            position = value as SelectionOwnerEvidencePosition;
            addError = "";
          }}
        />
      </div>

      <FormField
        id="owner-evidence-kind"
        kind="select"
        label="Evidence type"
        bind:value={() => kind, (value) => { kind = value as SelectionOwnerEvidenceKind; addError = ""; }}
      >
        {#each Object.entries(kindLabels) as [value, label]}<option value={value}>{label}</option>{/each}
      </FormField>

      <FormField
        id="owner-evidence-title"
        label="Finding title"
        required
        minlength={3}
        maxlength={300}
        bind:value={title}
        placeholder="e.g. Four interviewees would not pay for another dashboard"
        error={titleError}
        onkeydown={() => { addError = ""; titleError = ""; }}
      />

      <FormField
        id="owner-evidence-content"
        kind="textarea"
        label="What did you observe?"
        required
        minlength={3}
        maxlength={8000}
        rows={4}
        bind:value={content}
        placeholder="Record the exact quote, number, behavior, or source finding and enough context to interpret it later."
        error={contentError}
        onkeydown={() => { addError = ""; contentError = ""; }}
      />

      <div class="form-row">
        <FormField
          id="owner-evidence-source"
          type="url"
          label="Source URL"
          optional={kind !== "LINK"}
          required={kind === "LINK"}
          maxlength={1000}
          bind:value={sourceUrl}
          placeholder="https://"
          error={sourceUrlError}
          onkeydown={() => { addError = ""; sourceUrlError = ""; }}
        />
        <FormField
          id="owner-evidence-observed"
          type="date"
          label="Observed on"
          optional
          bind:value={observedOn}
          onkeydown={() => (addError = "")}
        />
      </div>
      <p class="provenance">Saved to {ideaTitle?.trim() || "the selected candidate"} · revision {ideaRevision} · {lens} lens</p>
    </form>
  {/if}
  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={saving} onclick={closeAdd}>Cancel</button>
  {/snippet}
  {#snippet footer()}
    <SubmitButton
      type="button"
      label="Add to ledger"
      loadingText="Adding…"
      loading={saving}
      disabled={draftContext !== contextKey}
      onclick={addEvidence}
      class="submit-btn"
    />
  {/snippet}
</FormOverlay>

<FormOverlay
  open={Boolean(retractingItem)}
  size="compact"
  title="Retract owner evidence"
  eyebrow="Evidence ledger"
  description={retractingItem ? `“${retractingItem.title}” remains in the immutable record with your reason.` : undefined}
  annotationAnchor={retractingItem ? `selection:owner-evidence-retract:${retractingItem.id}` : undefined}
  onRequestClose={closeRetract}
  dirty={Boolean(retractionReason.trim())}
  closeWarning="Your reason has not been saved. Close again to discard it."
  footerMessage={retractError}
>
  {#if retractingItem}
    <form id="retract-evidence-form" class="retract-form" onsubmit={(event) => { event.preventDefault(); void retract(retractingItem); }}>
      <DecisionHelp title="Correct the record" label="Immutable history">
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
        onkeydown={() => (retractError = "")}
      />
    </form>
  {/if}
  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" disabled={retracting} onclick={closeRetract}>Cancel</button>
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
  .ledger > summary { display:flex; align-items:center; justify-content:space-between; min-height:2.75rem; color:var(--color-text-secondary); font-size:var(--text-11); cursor:pointer; transition:color var(--duration-fast) var(--ease-default); }
  .ledger > summary:hover { color:var(--color-text-primary); }
  .ledger > summary:active { transform:scale(0.98); }
  .ledger > summary strong { color:var(--color-text-primary); font-size:var(--text-xs); letter-spacing:.06em; text-transform:uppercase; }
  .ledger > summary :global(svg), .text-action :global(svg), .record-actions :global(svg) { width:.85rem; height:.85rem; }
  .ledger-body { padding-bottom:.8rem; }
  .ledger-intro { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.65rem 0; }
  .ledger-intro p { margin:0; color:var(--color-text-secondary); font-size:var(--text-11); line-height:1.45; }
  button { font:inherit; }
  .text-action, .record-actions button, .record-actions a, .message button { display:inline-flex; align-items:center; gap:.3rem; min-height:1.5rem; padding:.2rem 0; border:0; background:transparent; color:var(--color-accent-dark); font-size:var(--text-11); font-weight:700; cursor:pointer; text-decoration:none; transition:color var(--duration-fast) var(--ease-default); }
  .text-action:hover, .record-actions button:hover, .record-actions a:hover, .message button:hover { color:var(--color-accent-hover); }
  .text-action:active, .record-actions button:active, .record-actions a:active, .message button:active { transform:scale(0.98); }
  .locked { color:var(--color-text-secondary); font-size:var(--text-xs); }
  .message { padding:.6rem 0; color:var(--color-text-secondary); font-size:var(--text-11); }
  .message.error { color:var(--color-error-text); }
  .prefill-feedback { margin:.5rem 0 0; color:var(--color-text-secondary); font-size:var(--text-11); line-height:1.45; }
  .prefill-feedback.is-error { color:var(--color-error-text); }
  .prefill-feedback.is-empty { margin:0; }
  .context-warning { display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; }
  .sr-status { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }

  /* ── Overlay form ── */
  .evidence-form { display:grid; gap:1rem; }
  .evidence-guidance { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; padding:.8rem .9rem; border:1px solid var(--color-border); border-radius:var(--radius-md); background:var(--color-bg-surface); }
  .evidence-guidance > div { display:grid; gap:.18rem; min-width:0; }
  .evidence-guidance strong { color:var(--color-text-primary); font-size:var(--text-13); font-weight:600; }
  .evidence-guidance p { margin:0; color:var(--color-text-secondary); font-size:var(--text-sm); font-weight:500; line-height:1.45; text-wrap:pretty; }
  .field { display:grid; gap:.4rem; }
  .field-label { display:flex; align-items:baseline; gap:.45rem; font-size:var(--text-13); font-weight:600; color:var(--color-text-primary); }
  .field-hint { margin:-.1rem 0 0; font-size:var(--text-sm); line-height:1.45; color:var(--color-text-muted); }
  .form-row { display:grid; grid-template-columns:1.5fr 1fr; gap:1rem; }
  .provenance { margin:0; color:var(--color-text-muted); font-size:var(--text-sm); line-height:1.45; }
  .retract-form { display:grid; gap:1rem; }

  /* ── Overlay footer ── */
  .cancel-btn { display:inline-flex; align-items:center; justify-content:center; min-height:2.4rem; padding:.5rem .9rem; border:1px solid var(--color-input-border); border-radius:var(--radius-md); background:transparent; color:var(--color-text-secondary); font-size:var(--text-13); font-weight:600; cursor:pointer; transition:border-color var(--duration-fast) var(--ease-default), color var(--duration-fast) var(--ease-default), background var(--duration-fast) var(--ease-default); }
  .cancel-btn:hover:not(:disabled) { border-color:var(--color-text-secondary); color:var(--color-text-primary); }
  .cancel-btn:active:not(:disabled) { transform:scale(0.98); }
  .cancel-btn:disabled { background:var(--color-bg-hover); color:var(--color-text-muted); cursor:wait; }
  .cancel-btn:focus-visible { outline:2px solid var(--color-accent); outline-offset:2px; }

  /* ── Records (display) ── */
  .records { margin:0; padding:0; list-style:none; border-top:1px solid var(--color-border); }
  .record { border-bottom:1px solid var(--color-border); }
  .record > summary { display:grid; grid-template-columns:6rem minmax(0,1fr); gap:.7rem; padding:.7rem 0; cursor:pointer; transition:color var(--duration-fast) var(--ease-default); }
  .record > summary:hover { color:var(--color-text-primary); }
  .record > summary:active { transform:scale(0.98); }
  .record > summary > span:last-child { display:grid; gap:.18rem; }
  .record strong { font-size:var(--text-11); } .record small { color:var(--color-text-secondary); font-size:var(--text-xs); }
  .position { font-size:var(--text-xs); font-weight:800; text-transform:uppercase; }
  .position--supports { color:var(--color-success-text); } .position--contradicts { color:var(--color-error-text); } .position--context { color:var(--color-text-secondary); }
  .record-body { padding:0 0 .75rem 6.7rem; }
  .record-body > p { margin:0; color:var(--color-text-secondary); font-size:var(--text-11); line-height:1.5; white-space:pre-wrap; }
  .record-actions { display:flex; gap:.7rem; margin-top:.45rem; }
  .archive { padding-top:.65rem; color:var(--color-text-secondary); font-size:var(--text-xs); }
  .archive > summary { cursor:pointer; transition:color var(--duration-fast) var(--ease-default); }
  .archive > summary:hover { color:var(--color-text-primary); }
  .archive > summary:active { transform:scale(0.98); }
  .archive p { margin:.4rem 0 0; }
  summary:focus-visible, button:focus-visible, a:focus-visible { outline:2px solid var(--color-accent); outline-offset:2px; }
  :global(.owner-evidence-spin) { animation:owner-evidence-spin 800ms linear infinite; } @keyframes owner-evidence-spin { to { transform:rotate(360deg); } }
  @media(max-width:760px){ .ledger-intro{align-items:flex-start;flex-direction:column}.evidence-guidance{align-items:flex-start;flex-direction:column}.form-row{grid-template-columns:1fr}.record>summary{grid-template-columns:1fr;gap:.3rem}.record-body{padding-left:0} }
  @media (prefers-reduced-motion: reduce) {
    .ledger > summary:active,
    .text-action:active, .record-actions button:active, .record-actions a:active, .message button:active,
    .cancel-btn:active:not(:disabled),
    .record > summary:active,
    .archive > summary:active { transform:none; }
  }
</style>
