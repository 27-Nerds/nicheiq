<script lang="ts">
  import { getSolutions, saveSelectionDecisionProfile } from "$lib/api";
  import {
    FOUNDER_CONTEXT_OVERLAY_TITLE,
    FOUNDER_CONTEXT_SAVED,
    SAVE_FOUNDER_CONTEXT_LABEL,
    founderContextLabel,
  } from "$lib/selection/labels";
  import ChipGroup from "$lib/components/ui/ChipGroup.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import SegmentControl from "$lib/components/ui/SegmentControl.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type { AudienceDriftNotice } from "$lib/types/report";
  import type {
    BuildModel,
    DecisionProfilePreset,
    DistributionAdvantage,
    RevenueHorizon,
    SelectionDecisionProfile,
    TeamShape,
    ValidationBudget,
    WeeklyTime,
  } from "$lib/types/job";

  interface Props {
    jobId: string;
    profile: SelectionDecisionProfile | null;
    onSaved: (profile: SelectionDecisionProfile) => void;
    /** "card" = the full persistent section (kept for the no-profile case the
     *  guidance spine is pointing at). "summary" = Phase-1b display-only row
     *  ("Founder context: saved") with its own quiet edit button. The editor
     *  overlay is available in every variant (openEditor / reviewCopilotDraft). */
    variant?: "card" | "summary";
    /** Mounts only the editor overlay. The selection workspace states the saved
     *  constraints in its own header, so a second summary row there would be a
     *  duplicate of the same fact. */
    hideSummary?: boolean;
    /** Blocks saving while the host workspace is not interactive (e.g. the job
     *  is REGENERATING). The editor stays open so a dirty draft is preserved. */
    disabled?: boolean;
    /** Recommendation-scoped drift from the three-way audience comparison. */
    audienceDrift?: AudienceDriftNotice | null;
  }

  let {
    jobId,
    profile,
    onSaved,
    variant = "card",
    hideSummary = false,
    disabled = false,
    audienceDrift = undefined,
  }: Props = $props();

  let verifiedAudienceDrift = $state<AudienceDriftNotice | null>(null);
  /** True when this run's report was produced before the buyer comparison existed at all. */
  let audienceCheckUnavailable = $state(false);
  const renderedAudienceDrift = $derived(
    audienceDrift === undefined ? verifiedAudienceDrift : audienceDrift,
  );

  $effect(() => {
    if (audienceDrift !== undefined) return;
    let cancelled = false;
    void getSolutions(jobId)
      .then((response) => {
        if (cancelled) return;
        const mapping = response.artifactVerification === "verified"
          ? response.previewReport?.audience_mapping
          : null;
        verifiedAudienceDrift = mapping?.audience_drift_notice ?? null;
        // The asset's content hash proves the bytes are the ones the worker registered. It
        // proves nothing about WHEN they were written, so a report materialized before the
        // buyer comparison shipped verifies cleanly and then has no comparison to report.
        // Absence of the field is the only evidence of that, and it must not read as "no
        // buyer change was found" — that is a claim this run never made.
        audienceCheckUnavailable = !!mapping && !("audience_drift_notice" in mapping);
      })
      .catch(() => {
        if (!cancelled) {
          verifiedAudienceDrift = null;
          audienceCheckUnavailable = false;
        }
      });
    return () => { cancelled = true; };
  });

  const DEFAULT_PROFILE: SelectionDecisionProfile = {
    preset: "balanced",
    weeklyTime: "10_20",
    budget: "1k_5k",
    team: "solo",
    buildModel: "self",
    revenueHorizon: "6_months",
    distributionAdvantages: [],
    strengths: "",
    hardConstraints: "",
  };

  const PRESET_OPTIONS: Array<{ value: DecisionProfilePreset; label: string; description: string }> = [
    { value: "balanced", label: "Balanced", description: "No single constraint dominates." },
    { value: "fast_revenue", label: "Fast revenue", description: "Prefer a short path to a paid test." },
    { value: "solo_bootstrap", label: "Solo bootstrap", description: "Keep cost and operations light." },
    { value: "audience_first", label: "Audience first", description: "Build around channels you already own." },
  ];

  // Full labels drive the display-only summary list; the compact segment
  // controls carry short labels so the choices read as a control, not prose.
  const TIME_OPTIONS: Array<{ value: WeeklyTime; label: string }> = [
    { value: "under_10", label: "Under 10 hrs / week" },
    { value: "10_20", label: "10-20 hrs / week" },
    { value: "20_40", label: "20-40 hrs / week" },
    { value: "full_time", label: "Full time" },
  ];
  const BUDGET_OPTIONS: Array<{ value: ValidationBudget; label: string }> = [
    { value: "under_1k", label: "Under $1k" },
    { value: "1k_5k", label: "$1k-$5k" },
    { value: "5k_20k", label: "$5k-$20k" },
    { value: "20k_plus", label: "$20k+" },
  ];
  const TEAM_OPTIONS: Array<{ value: TeamShape; label: string }> = [
    { value: "solo", label: "Solo" },
    { value: "small_team", label: "Small in-house team" },
    { value: "funded_team", label: "Funded in-house team" },
  ];
  const BUILD_MODEL_OPTIONS: Array<{ value: BuildModel; label: string }> = [
    { value: "self", label: "I will build the software" },
    { value: "contractor", label: "Hire a contractor or agency to build it" },
  ];
  const HORIZON_OPTIONS: Array<{ value: RevenueHorizon; label: string }> = [
    { value: "30_days", label: "Revenue within 30 days" },
    { value: "90_days", label: "Revenue within 90 days" },
    { value: "6_months", label: "Revenue within 6 months" },
    { value: "patient", label: "Patient / long horizon" },
  ];

  const TIME_SEG: Array<{ value: WeeklyTime; label: string }> = [
    { value: "under_10", label: "Under 10" },
    { value: "10_20", label: "10 to 20" },
    { value: "20_40", label: "20 to 40" },
    { value: "full_time", label: "Full time" },
  ];
  const BUDGET_SEG: Array<{ value: ValidationBudget; label: string }> = [
    { value: "under_1k", label: "Under $1k" },
    { value: "1k_5k", label: "$1k to $5k" },
    { value: "5k_20k", label: "$5k to $20k" },
    { value: "20k_plus", label: "$20k+" },
  ];
  const HORIZON_SEG: Array<{ value: RevenueHorizon; label: string }> = [
    { value: "30_days", label: "30 days" },
    { value: "90_days", label: "90 days" },
    { value: "6_months", label: "6 months" },
    { value: "patient", label: "Patient" },
  ];

  const CHANNEL_OPTIONS: Array<{ value: DistributionAdvantage; label: string }> = [
    { value: "seo", label: "SEO" },
    { value: "community", label: "Communities" },
    { value: "existing_audience", label: "Existing audience" },
    { value: "outbound", label: "Outbound" },
    { value: "paid", label: "Paid acquisition" },
    { value: "partnerships", label: "Partnerships" },
  ];

  let editing = $state(false);
  let saving = $state(false);
  let error = $state("");
  let showMoreContext = $state(false);
  let draft = $state<SelectionDecisionProfile>({ ...DEFAULT_PROFILE });
  let lastCopilotRequestId: string | null = null;
  /** Persists past the overlay closing so the save confirmation still reaches
   *  screen readers (the overlay itself unmounts on success). */
  let savedAnnouncement = $state("");

  const optionLabel = <T extends string>(
    options: Array<{ value: T; label: string }>,
    value: T | undefined,
    missing = "Not specified",
  ) => value ? (options.find((option) => option.value === value)?.label ?? value) : missing;

  function cloneProfile(value: SelectionDecisionProfile): SelectionDecisionProfile {
    return { ...value, distributionAdvantages: [...value.distributionAdvantages] };
  }

  function beginEditing() {
    if (editing || saving) return;
    draft = cloneProfile(profile ?? DEFAULT_PROFILE);
    showMoreContext = Boolean(
      profile?.distributionAdvantages.length
      || profile?.strengths.trim()
      || profile?.hardConstraints.trim(),
    );
    error = "";
    editing = true;
  }

  export function openEditor(): void {
    if (!saving) beginEditing();
  }

  /** Opens an owner-reviewed draft without persisting it. Repeated delivery is
   *  idempotent, and an already-dirty editor always wins over a new suggestion. */
  export function reviewCopilotDraft(
    requestId: string,
    values: Partial<SelectionDecisionProfile>,
  ): { ok: boolean; message: string } {
    if (requestId === lastCopilotRequestId) {
      return { ok: true, message: "This draft is already open for review." };
    }
    if (saving) return { ok: false, message: "Wait for the current save to finish." };
    if (editing && hasUnsavedChanges()) {
      return {
        ok: false,
        message: "Your founder-context form has unsaved changes. Save or close it before reviewing another draft.",
      };
    }

    const base = cloneProfile(profile ?? DEFAULT_PROFILE);
    draft = {
      ...base,
      ...values,
      distributionAdvantages: values.distributionAdvantages
        ? [...values.distributionAdvantages]
        : [...base.distributionAdvantages],
    };
    showMoreContext = Boolean(
      values.revenueHorizon
      || values.distributionAdvantages?.length
      || values.strengths?.trim()
      || values.hardConstraints?.trim(),
    );
    error = "";
    editing = true;
    lastCopilotRequestId = requestId;
    return { ok: true, message: "Build limits opened. Review every value before saving." };
  }

  function hasUnsavedChanges() {
    const base = profile ?? DEFAULT_PROFILE;
    if (
      draft.preset !== base.preset ||
      draft.weeklyTime !== base.weeklyTime ||
      draft.budget !== base.budget ||
      draft.team !== base.team ||
      draft.buildModel !== base.buildModel ||
      draft.revenueHorizon !== base.revenueHorizon ||
      draft.strengths !== base.strengths ||
      draft.hardConstraints !== base.hardConstraints
    ) {
      return true;
    }
    if (draft.distributionAdvantages.length !== base.distributionAdvantages.length) return true;
    return !draft.distributionAdvantages.every((value) => base.distributionAdvantages.includes(value));
  }

  /** Confirmed close: FormOverlay owns the dirty two-press gate. */
  export function closeEditor() {
    if (saving) return;
    editing = false;
    error = "";
  }

  function applyPreset(preset: DecisionProfilePreset) {
    const preserved = { strengths: draft.strengths, hardConstraints: draft.hardConstraints };
    const profiles: Record<DecisionProfilePreset, SelectionDecisionProfile> = {
      balanced: { ...DEFAULT_PROFILE },
      fast_revenue: {
        ...DEFAULT_PROFILE,
        preset,
        weeklyTime: "20_40",
        revenueHorizon: "30_days",
        team: "small_team",
        distributionAdvantages: ["outbound", "existing_audience"],
      },
      solo_bootstrap: {
        ...DEFAULT_PROFILE,
        preset,
        budget: "under_1k",
        revenueHorizon: "90_days",
        distributionAdvantages: ["seo", "community"],
      },
      audience_first: {
        ...DEFAULT_PROFILE,
        preset,
        revenueHorizon: "90_days",
        distributionAdvantages: ["existing_audience", "community"],
      },
    };
    draft = { ...profiles[preset], ...preserved };
  }

  async function save() {
    if (saving || disabled) return;
    saving = true;
    error = "";
    try {
      const response = await saveSelectionDecisionProfile(jobId, draft);
      onSaved(cloneProfile(response.selectionDecisionProfile));
      editing = false;
      savedAnnouncement = "Build limits saved";
    } catch (cause) {
      error = cause instanceof Error ? cause.message : "Could not save your build limits.";
    } finally {
      saving = false;
    }
  }
</script>

{#if renderedAudienceDrift}
  <aside class="decision-audience-drift" role="note" aria-label="Audience mismatch before recommendation">
    <strong>Before you act on this recommendation</strong>
    <p>{renderedAudienceDrift.message}</p>
  </aside>
{:else if audienceCheckUnavailable}
  <aside class="decision-audience-unchecked" role="note" aria-label="Audience check unavailable">
    <p>
      This run finished before the buyer comparison existed, so nothing here has checked the
      recommendation against the audience you asked for. Compare them yourself before you build.
    </p>
  </aside>
{/if}

{#if hideSummary}
  <!-- Editor-only mount: the host surface states the constraints itself. -->
{:else if variant === "summary"}
  {#if profile}
    <section class="brief-row" aria-label="Build limits summary" data-annotation-anchor="selection:decision-brief">
      <div class="brief-row-main">
        <p class="brief-row-copy">{FOUNDER_CONTEXT_SAVED}</p>
        <p class="brief-row-values" aria-label="Saved build limits">
          <span>{optionLabel(TIME_OPTIONS, profile.weeklyTime)}</span>
          <span>{optionLabel(BUDGET_OPTIONS, profile.budget)}</span>
          <span>{optionLabel(TEAM_OPTIONS, profile.team)}</span>
          <span>{optionLabel(BUILD_MODEL_OPTIONS, profile.buildModel, "Build model not specified")}</span>
          <span>{optionLabel(HORIZON_OPTIONS, profile.revenueHorizon)}</span>
          {#if profile.distributionAdvantages.length > 0}
            <span>{profile.distributionAdvantages.map((value) => optionLabel(CHANNEL_OPTIONS, value)).join(", ")}</span>
          {/if}
        </p>
      </div>
      {#if !editing}
        <button type="button" class="edit-action" onclick={beginEditing}>
          {founderContextLabel(Boolean(profile))}
        </button>
      {/if}
    </section>
  {/if}
{:else}
<section class="brief" aria-labelledby="decision-brief-title" data-annotation-anchor="selection:decision-brief">
  <header class="brief-head">
    <div class="brief-copy">
      <p class="kicker">Founder fit</p>
      <h3 id="decision-brief-title">Your build limits</h3>
      <p>Research ranks the market. These constraints describe what is practical for you.</p>
    </div>

    {#if profile}
      <dl class="profile-summary" aria-label="Saved build limits">
        <div><dt>Time</dt><dd>{optionLabel(TIME_OPTIONS, profile.weeklyTime)}</dd></div>
        <div><dt>Budget</dt><dd>{optionLabel(BUDGET_OPTIONS, profile.budget)}</dd></div>
        <div><dt>Team</dt><dd>{optionLabel(TEAM_OPTIONS, profile.team)}</dd></div>
        <div><dt>Build model</dt><dd>{optionLabel(BUILD_MODEL_OPTIONS, profile.buildModel, "Not specified (legacy profile)")}</dd></div>
        <div><dt>Horizon</dt><dd>{optionLabel(HORIZON_OPTIONS, profile.revenueHorizon)}</dd></div>
      </dl>
    {:else}
      <p class="empty-copy">Add your limits before comparing ideas. They will not change the research score.</p>
    {/if}

    {#if !editing}
      <button type="button" class="edit-action" onclick={beginEditing}>
        {founderContextLabel(Boolean(profile))}
      </button>
    {/if}
  </header>

</section>
{/if}

<p class="sr-only" role="status" aria-live="polite">{savedAnnouncement}</p>

<FormOverlay
  open={editing}
  size="form"
  eyebrow="Fit for you"
  title={FOUNDER_CONTEXT_OVERLAY_TITLE}
  description="Set what you can realistically spend and build. These limits never change the Discovery score."
  annotationAnchor="selection:decision-profile-editor"
  onRequestClose={closeEditor}
  dirty={hasUnsavedChanges()}
  closeWarning="You have unsaved changes. Close again to discard them."
  footerMessage="Private to you. Saved context is checked against every candidate."
>
    <form id="decision-profile-form" class="brief-form" onsubmit={(event) => { event.preventDefault(); void save(); }}>
      <div class="field preset-seg form-section form-section--lead">
        <span class="field-label" id="brief-preset-label">Starting point</span>
        <p class="field-hint">A preset fills every field below. Adjust anything after.</p>
        <SegmentControl
          density="card"
          label="Starting point"
          labelledBy="brief-preset-label"
          options={PRESET_OPTIONS}
          value={draft.preset}
          onChange={(value) => applyPreset(value as DecisionProfilePreset)}
        />
      </div>

      <fieldset class="fgroup">
        <legend class="fgroup-title">Capacity and runway</legend>

        <div class="capacity-grid">
          <div class="field">
            <span class="field-label" id="brief-time-label">Available time <span class="opt">Hours per week</span></span>
            <SegmentControl
              density="compact"
              label="Available time"
              labelledBy="brief-time-label"
              options={TIME_SEG}
              value={draft.weeklyTime}
              onChange={(value) => (draft.weeklyTime = value as WeeklyTime)}
            />
          </div>

          <div class="field">
            <span class="field-label" id="brief-budget-label">Testing budget</span>
            <SegmentControl
              density="compact"
              label="Testing budget"
              labelledBy="brief-budget-label"
              options={BUDGET_SEG}
              value={draft.budget}
              onChange={(value) => (draft.budget = value as ValidationBudget)}
            />
          </div>

          <div class="field capacity-grid__team">
            <span class="field-label" id="brief-team-label">Team size</span>
            <SegmentControl
              density="compact"
              label="Team size"
              labelledBy="brief-team-label"
              options={TEAM_OPTIONS}
              value={draft.team}
              onChange={(value) => (draft.team = value as TeamShape)}
            />
          </div>

          <div class="field capacity-grid__build-model">
            <span class="field-label" id="brief-build-model-label">Who builds the software?</span>
            <p class="field-hint">This is separate from team size. It changes how founder fit evaluates delivery.</p>
            <SegmentControl
              density="compact"
              label="Who builds the software?"
              labelledBy="brief-build-model-label"
              options={BUILD_MODEL_OPTIONS}
              value={draft.buildModel ?? ""}
              onChange={(value) => (draft.buildModel = value as BuildModel)}
            />
          </div>
        </div>

      </fieldset>

      <button
        type="button"
        class="advanced-toggle"
        aria-expanded={showMoreContext}
        aria-controls="build-context-fields"
        onclick={() => (showMoreContext = !showMoreContext)}
      >
        <span>{showMoreContext ? "Hide launch context" : "Add launch context"}</span>
        <small>Revenue timing, channels, advantages, and non-negotiables</small>
      </button>

      {#if showMoreContext}
      <fieldset class="fgroup fgroup--secondary" id="build-context-fields">
        <legend class="fgroup-title">Launch context</legend>

        <div class="field">
          <span class="field-label" id="brief-horizon-label">Revenue horizon <span class="opt">Time to first revenue</span></span>
          <SegmentControl
            density="compact"
            label="Revenue horizon"
            labelledBy="brief-horizon-label"
            options={HORIZON_SEG}
            value={draft.revenueHorizon}
            onChange={(value) => (draft.revenueHorizon = value as RevenueHorizon)}
          />
        </div>

        <div class="field">
          <span class="field-label">Channels you can already reach</span>
          <ChipGroup
            label="Channels you can already reach, choose up to four"
            options={CHANNEL_OPTIONS}
            values={draft.distributionAdvantages}
            max={4}
            onChange={(values) => (draft.distributionAdvantages = values as DistributionAdvantage[])}
          />
        </div>

        <div class="notes-grid">
          <FormField
            id="brief-strengths"
            kind="textarea"
            label="Advantages you already have"
            optional
            bind:value={draft.strengths}
            maxlength={500}
            rows={3}
            placeholder="Domain access, technical skills, a trusted audience"
          />
          <FormField
            id="brief-constraints"
            kind="textarea"
            label="Hard constraints"
            optional
            hint="Dealbreakers only. One conflict marks a candidate blocked."
            bind:value={draft.hardConstraints}
            maxlength={1000}
            rows={3}
            placeholder="No regulated data, no 24/7 operations, must be remote"
          />
        </div>
      </fieldset>
      {/if}
    </form>

    {#snippet footerCancel(requestClose)}
      <button type="button" class="cancel-btn" disabled={saving} onclick={requestClose}>Cancel</button>
    {/snippet}
    {#snippet footer()}
      <div class="footer-submit">
        {#if error}<p class="form-error" role="alert">{error}</p>{/if}
        <SubmitButton
          type="button"
          label={SAVE_FOUNDER_CONTEXT_LABEL}
          loadingText="Saving…"
          loading={saving}
          {disabled}
          onclick={save}
          class="submit-btn"
        />
      </div>
    {/snippet}
</FormOverlay>

<style>
  .decision-audience-drift {
    display: grid;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid color-mix(in srgb, var(--color-warning) 48%, var(--color-border));
    border-left: 3px solid var(--color-warning);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-warning) 8%, var(--color-bg-surface));
  }
  .decision-audience-drift strong {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 800;
  }
  .decision-audience-drift p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
    text-wrap: pretty;
  }
  /* A missing check is a gap in what we know, not a warning about the buyer — neutral chrome
     so it cannot be mistaken for the notice above it. */
  .decision-audience-unchecked {
    margin-bottom: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-subtle);
  }
  .decision-audience-unchecked p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.5;
    text-wrap: pretty;
  }

  /* Phase-1b display-only summary row (DESIGN_SYSTEM §5.6). */
  .brief-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
  }
  .brief-row-copy {
    margin: 0;
    color: var(--color-text-primary);
    font-size: var(--text-13);
    font-weight: 600;
  }
  .brief-row-main {
    display: grid;
    min-width: 0;
    gap: var(--space-1);
  }
  .brief-row-values {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-3);
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.4;
  }
  .brief-row-values span {
    position: relative;
  }
  .brief-row-values span:not(:last-child)::after {
    position: absolute;
    left: calc(100% + var(--space-1));
    color: var(--color-text-muted);
    content: "\00b7";
  }
  .brief {
    margin: var(--space-5) 0 var(--space-6);
    border-block: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-elevated) 72%, transparent);
  }
  .brief-head {
    display: grid;
    grid-template-columns: minmax(15rem, 1.15fr) minmax(24rem, 1.8fr) auto;
    align-items: center;
    gap: var(--space-5);
    padding: var(--space-4) 0;
  }
  .brief-copy { max-width: 30rem; }
  .kicker {
    margin: 0 0 var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
  }
  h3 { margin: 0; font-size: var(--text-md); line-height: 1.25; letter-spacing: -0.01em; }
  .brief-copy > p:last-child, .empty-copy {
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.45;
    text-wrap: pretty;
  }
  .empty-copy { max-width: 34rem; }
  .profile-summary {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    margin: 0;
  }
  .profile-summary div { min-width: 0; padding: 0 var(--space-3); border-left: 1px solid var(--color-border); }
  .profile-summary dt {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-text-secondary);
  }
  .profile-summary dd {
    overflow: hidden;
    margin: var(--space-1) 0 0;
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 600;
    line-height: 1.3;
    text-overflow: ellipsis;
  }
  button { font: inherit; }
  .edit-action {
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default);
  }
  .edit-action:hover {
    border-color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }
  .edit-action:active { transform: scale(0.98); }
  .edit-action:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ── Overlay form ── */
  .brief-form {
    display: grid;
    gap: var(--space-5);
    padding-bottom: var(--space-1);
  }
  .field { display: grid; gap: var(--space-2); }
  .field-label {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    font-size: var(--text-13);
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .field-label .opt {
    font-size: var(--text-11);
    font-weight: 500;
    color: var(--color-text-secondary);
  }
  .field-hint {
    margin: 0;
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    color: var(--color-text-muted);
  }
  .form-section {
    border: 0;
    border-radius: 0;
    background: transparent;
  }
  .form-section--lead {
    padding: 0 0 var(--space-5);
    border-bottom: 1px solid var(--color-border);
  }
  .preset-seg :global(.segment-cards) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .fgroup {
    min-width: 0;
    display: grid;
    gap: var(--space-4);
    margin: 0;
    padding: 0 0 var(--space-5);
    border: 0;
    border-bottom: 1px solid var(--color-border);
    border-radius: 0;
    background: transparent;
  }
  .fgroup-title {
    padding: 0;
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .fgroup--secondary {
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-surface);
  }
  .capacity-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-4);
  }
  .capacity-grid__team,
  .capacity-grid__build-model {
    grid-column: 1 / -1;
  }
  .capacity-grid :global(.segment-track) {
    width: 100%;
  }
  .capacity-grid :global(.segment) {
    flex: 1 1 auto;
  }
  .advanced-toggle {
    display: grid;
    gap: var(--space-1);
    min-height: var(--space-10);
    padding: var(--space-2) 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: var(--color-text-secondary);
    text-align: left;
    cursor: pointer;
    transition: color var(--duration-fast) var(--ease-default), transform var(--duration-fast) var(--ease-default);
  }
  .advanced-toggle > span {
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .advanced-toggle > small {
    color: var(--color-text-muted);
    font-size: var(--text-xs);
    line-height: var(--leading-normal);
  }
  .advanced-toggle:hover {
    color: var(--color-text-primary);
  }
  .advanced-toggle:active { transform: scale(0.99); }
  .advanced-toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .notes-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-4);
  }
  .footer-submit {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .form-error {
    margin: 0;
    color: var(--color-error-text);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }
  .cancel-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: var(--space-10);
    padding: var(--space-2) var(--space-4);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }
  .cancel-btn:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }
  .cancel-btn:active:not(:disabled) { transform: scale(0.98); }
  .cancel-btn:disabled {
    cursor: wait;
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
  }
  .cancel-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  @media (max-width: 900px) {
    .brief-head { grid-template-columns: 1fr auto; }
    .profile-summary, .empty-copy { grid-column: 1 / -1; grid-row: 2; }
    .profile-summary { border-top: 1px solid var(--color-border); padding-top: var(--space-3); }
    .profile-summary div:first-child { border-left: 0; padding-left: 0; }
  }
  @media (max-width: 640px) {
    .preset-seg :global(.segment-cards) { grid-template-columns: 1fr; }
    .capacity-grid { grid-template-columns: 1fr; }
    .capacity-grid__team,
    .capacity-grid__build-model { grid-column: auto; }
    .notes-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 560px) {
    .brief-head { display: flex; flex-direction: column; align-items: stretch; gap: var(--space-3); }
    .profile-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: var(--space-3); }
    .profile-summary div:nth-child(3) { border-left: 0; padding-left: 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    .edit-action:active { transform: none; }
    .cancel-btn:active:not(:disabled) { transform: none; }
    .advanced-toggle { transition: none; }
    .advanced-toggle:active { transform: none; }
  }
</style>
