<script lang="ts">
  import { portal } from "$lib/actions/portal";
  import { X, Loader2, AlertCircle, Coins } from "lucide-svelte";
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

  let modalEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLElement | null = null;

  const isSingle = $derived(solutionNames.length === 1);

  function handleConfirm() {
    onConfirm("");
  }

  function handleClose() {
    if (!loading) {
      onCancel();
      triggerEl?.focus();
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget && !loading) {
      handleClose();
    }
  }

  function getFocusableElements(): HTMLElement[] {
    if (!modalEl) return [];
    return Array.from(
      modalEl.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && open && !loading) {
      handleClose();
      return;
    }

    if (e.key === "Tab" && open) {
      const focusable = getFocusableElements();
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  }

  $effect(() => {
    if (open && modalEl) {
      triggerEl = document.activeElement as HTMLElement;
      // Focus the first focusable element in the modal
      const focusable = getFocusableElements();
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    use:portal
    class="confirm-backdrop"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div
      bind:this={modalEl}
      class="confirm-card"
    >
      <!-- Header -->
      <div class="confirm-header">
        <div>
          <p class="confirm-eyebrow">Deep Research</p>
          <h2 class="confirm-title">Validate your shortlist</h2>
        </div>
        <button
          onclick={handleClose}
          disabled={loading}
          aria-label="Close modal"
          class="confirm-close"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="confirm-body">
        {#if isSingle}
          <div class="confirm-selection">
            <span class="confirm-selection-count">1 idea selected</span>
            <strong>{displayMap.get(solutionNames[0]) || solutionNames[0]}</strong>
          </div>
        {:else}
          <div class="confirm-selection">
            <span class="confirm-selection-count">{solutionNames.length} ideas selected</span>
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

        <div class="confirm-scope">
          <span>What gets tested</span>
          <p>Demand signals, competition, market size, pricing, SEO demand, and go-to-market risk.</p>
        </div>

        <div class="confirm-cost">
          <span><Coins class="w-3.5 h-3.5" aria-hidden="true" />{creditCost} credits</span>
          <span>one-time</span>
        </div>

        {#if errorMessage}
          <div
            class="confirm-error"
          >
            <AlertCircle class="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div
        class="confirm-footer"
      >
        <button
          onclick={handleClose}
          disabled={loading}
          class="confirm-secondary"
        >
          Cancel
        </button>
        <button
          onclick={handleConfirm}
          disabled={loading}
          class="confirm-primary"
        >
          {#if loading}
            <Loader2 class="w-4 h-4 animate-spin" />
            Starting...
          {:else}
            Start Deep Research
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .confirm-backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: clamp(0.75rem, 2vw, 1.35rem);
    background: rgba(246, 246, 244, 0.9);
  }

  .confirm-card {
    width: min(34rem, 100%);
    overflow: hidden;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 0.95rem;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.92),
      0 24px 64px rgba(24, 24, 27, 0.14);
  }

  .confirm-header,
  .confirm-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.1rem;
  }

  .confirm-header {
    border-bottom: 1px solid var(--color-border);
  }

  .confirm-eyebrow {
    margin: 0 0 0.18rem;
    font-size: 0.7rem;
    font-weight: 780;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }

  .confirm-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.12rem;
    font-weight: 800;
    line-height: 1.15;
    color: var(--color-text-primary);
  }

  .confirm-close {
    display: grid;
    place-items: center;
    width: 2.15rem;
    height: 2.15rem;
    border: 1px solid transparent;
    border-radius: 0.58rem;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .confirm-close:hover:not(:disabled) {
    transform: translateY(-1px);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .confirm-body {
    display: grid;
    gap: 0.85rem;
    padding: 1rem 1.1rem 1.1rem;
  }

  .confirm-selection {
    display: grid;
    gap: 0.28rem;
    padding: 0.8rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.72rem;
  }

  .confirm-selection-count {
    font-size: 0.72rem;
    font-weight: 760;
    color: var(--color-text-muted);
  }

  .confirm-selection strong,
  .confirm-selection p {
    margin: 0;
    color: var(--color-text-primary);
    font-size: 0.9rem;
    line-height: 1.42;
  }

  .confirm-list {
    display: grid;
    gap: 0.44rem;
    margin: 0;
    padding: 0;
  }

  .confirm-list li {
    display: grid;
    grid-template-columns: 0.44rem minmax(0, 1fr);
    gap: 0.52rem;
    align-items: start;
    color: var(--color-text-primary);
    font-size: 0.86rem;
    font-weight: 700;
    line-height: 1.35;
  }

  .confirm-dot {
    width: 0.42rem;
    height: 0.42rem;
    margin-top: 0.38rem;
    border-radius: 50%;
    background: var(--color-accent);
  }

  .confirm-original-name {
    display: block;
    margin-top: 0.16rem;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 650;
    color: var(--color-text-muted);
  }

  .confirm-scope {
    display: grid;
    gap: 0.22rem;
  }

  .confirm-scope span {
    font-size: 0.72rem;
    font-weight: 760;
    color: var(--color-text-muted);
  }

  .confirm-scope p {
    margin: 0;
    color: var(--color-text-secondary);
    font-size: 0.86rem;
    line-height: 1.48;
    text-wrap: pretty;
  }

  .confirm-cost {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-top: 0.72rem;
    border-top: 1px solid var(--color-border);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.72rem;
  }

  .confirm-cost span {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .confirm-error {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.7rem 0.78rem;
    background: color-mix(in srgb, var(--color-error) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-error) 18%, var(--color-border));
    border-radius: 0.62rem;
    color: var(--color-error);
    font-size: 0.82rem;
  }

  .confirm-footer {
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
  }

  .confirm-secondary,
  .confirm-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    min-height: 2.35rem;
    padding: 0.48rem 0.82rem;
    border-radius: 0.62rem;
    font-family: var(--font-body);
    font-size: 0.84rem;
    font-weight: 780;
    cursor: pointer;
    transition:
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background 220ms cubic-bezier(0.32, 0.72, 0, 1),
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      border-color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .confirm-secondary {
    background: transparent;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary);
  }

  .confirm-primary {
    background: var(--color-accent);
    border: 1px solid var(--color-accent);
    color: white;
  }

  .confirm-secondary:hover:not(:disabled),
  .confirm-primary:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  .confirm-secondary:hover:not(:disabled) {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }

  .confirm-primary:hover:not(:disabled) {
    background: var(--color-accent-hover);
  }

  .confirm-close:focus-visible,
  .confirm-secondary:focus-visible,
  .confirm-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .confirm-close:disabled,
  .confirm-secondary:disabled,
  .confirm-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 520px) {
    .confirm-footer {
      display: grid;
    }
    .confirm-secondary,
    .confirm-primary {
      width: 100%;
    }
  }
</style>
