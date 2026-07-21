<script lang="ts">
  import { page } from "$app/state";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import type { SolutionPreview } from "$lib/types/job";
  import { solutionDisplayTitle } from "$lib/utils/solution-utils";

  interface Props {
    open: boolean;
    solutionNames: string[];
    solutions?: SolutionPreview[];
    loading?: boolean;
    error?: string;
    creditCost?: number;
    onConfirm: (rationale: string) => void;
    onCancel: () => void;
  }

  let {
    open = $bindable(false),
    solutionNames,
    solutions = [],
    loading = false,
    error: errorMessage = "",
    creditCost = 0,
    onConfirm,
    onCancel,
  }: Props = $props();

  // Display name map from solutions prop
  const displayMap = $derived(new Map(solutions?.map(s => [s.solution_name, solutionDisplayTitle(s)]) ?? []));
  let rationale = $state("");

  const isSingle = $derived(solutionNames.length === 1);
  const creditBalance = $derived((page.data?.creditBalance as number | undefined) ?? null);

  // The commit receipt: what Deep Research delivers for the credits.
  const deliverables = [
    "Market sizing",
    "Competitor landscape",
    "SEO opportunity",
    "Pricing analysis",
    "Technical blueprint",
  ];

  function handleConfirm() {
    onConfirm(rationale.trim());
  }

  function handleClose() {
    if (!loading) {
      onCancel();
    }
  }

  $effect(() => {
    if (!open) {
      rationale = "";
    }
  });
</script>

<FormOverlay
  {open}
  eyebrow="Deep Research"
  title="Validate your shortlist"
  onRequestClose={handleClose}
>
  {#if isSingle}
    <div class="confirm-selection">
      <span class="record-line">1 idea selected</span>
      <strong>{displayMap.get(solutionNames[0]) || solutionNames[0]}</strong>
    </div>
  {:else}
    <div class="confirm-selection">
      <span class="record-line">{solutionNames.length} ideas selected</span>
      <p>The strongest result becomes the primary recommendation. The rest stay available as alternatives.</p>
    </div>
    <ul class="confirm-list">
      {#each solutionNames as name}
        <li>
          <span class="confirm-dot" aria-hidden="true"></span>
          <span>
            {displayMap.get(name) || name}
            {#if displayMap.get(name) && displayMap.get(name) !== name}
              <span class="confirm-original-name">{name}</span>
            {/if}
          </span>
        </li>
      {/each}
    </ul>
  {/if}

  <FormField
    id="selection-rationale"
    kind="textarea"
    label="Why are you choosing this shortlist?"
    optional
    bind:value={rationale}
    maxlength={2000}
    rows={3}
    disabled={loading}
    placeholder="What looks strongest, and what should Deep Research challenge?"
    hint="Saved with your decision and passed into Deep Research."
  />

  <div class="confirm-receipt">
    <ul class="receipt-list">
      {#each deliverables as d}
        <li>{d}</li>
      {/each}
    </ul>
    <hr class="receipt-rule" />
    <p class="receipt-total record-line">
      <span>Total</span>
      <span>
        {creditCost} credits{#if creditBalance !== null}&nbsp;· balance {creditBalance}{/if}
      </span>
    </p>
  </div>

  {#if errorMessage}
    <p class="confirm-error" role="alert">{errorMessage}</p>
  {/if}

  {#snippet footerCancel()}
    <button type="button" class="cancel-btn" onclick={handleClose} disabled={loading}>
      Cancel
    </button>
  {/snippet}
  {#snippet footer()}
    <SubmitButton
      type="button"
      onclick={handleConfirm}
      {loading}
      loadingText="Starting…"
      label="Start Deep Research"
      class=""
    />
  {/snippet}
</FormOverlay>

<style>
  .confirm-selection {
    display: grid;
    gap: 0.3rem;
    padding: 0.8rem 0.9rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .confirm-selection strong,
  .confirm-selection p {
    margin: 0;
    color: var(--color-text-primary);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .confirm-list {
    display: grid;
    gap: 0.45rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .confirm-list li {
    display: grid;
    grid-template-columns: 0.44rem minmax(0, 1fr);
    gap: 0.5rem;
    align-items: start;
    color: var(--color-text-primary);
    font-size: var(--text-13);
    font-weight: 600;
    line-height: 1.35;
  }

  .confirm-dot {
    width: 0.42rem;
    height: 0.42rem;
    margin-top: 0.34rem;
    border-radius: 50%;
    background: var(--color-accent);
  }

  .confirm-original-name {
    display: block;
    margin-top: 0.15rem;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-text-muted);
  }

  .confirm-receipt {
    display: grid;
    gap: 0.55rem;
    padding: 0.85rem 0.9rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .receipt-list {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .receipt-list li {
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .receipt-rule {
    margin: 0.15rem 0;
    border: 0;
    border-top: 1px solid var(--color-border);
  }

  .receipt-total {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin: 0;
    color: var(--color-text-primary);
  }

  .confirm-error {
    margin: 0;
    color: var(--color-error-text);
    font-size: var(--text-13);
    line-height: 1.45;
  }
</style>
