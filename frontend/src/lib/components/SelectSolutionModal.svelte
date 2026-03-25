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

  const MODAL_OUTCOMES = [
    'Whether this market has real demand — or is already saturated',
    'Which keywords your customers actually search for',
    'How big the opportunity is — and what slice you can capture',
    'Who you\'d compete with — and where the gaps are',
    'What to charge and how to position against alternatives',
    'What to build and launch first — a 30-day playbook',
  ];

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
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div
      bind:this={modalEl}
      class="bg-bg-surface border border-border rounded-xl shadow-2xl w-full max-w-md"
    >
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-border">
        <h2 class="text-lg font-semibold text-text-primary">
          Start Your Market Analysis
        </h2>
        <button
          onclick={handleClose}
          disabled={loading}
          aria-label="Close modal"
          class="p-1 rounded-lg hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="p-4 space-y-4">
        {#if isSingle}
          <p class="text-sm text-text-secondary">
            Validating <span class="font-semibold text-text-primary">{displayMap.get(solutionNames[0]) || solutionNames[0]}</span>.
          </p>
        {:else}
          <p class="text-sm text-text-secondary">
            Validating <span class="font-semibold text-text-primary">{solutionNames.length} solutions</span>. The strongest becomes your primary recommendation; the rest appear as alternatives.
          </p>
          <ul class="space-y-1">
            {#each solutionNames as name}
              <li class="text-sm text-text-primary flex items-start gap-2">
                <span class="text-accent mt-0.5 shrink-0">&#x2022;</span>
                <span class="font-medium">
                  {displayMap.get(name) || name}
                  {#if displayMap.get(name) && displayMap.get(name) !== name}
                    <span class="text-[10px] font-mono text-text-muted/60 ml-1">{name}</span>
                  {/if}
                </span>
              </li>
            {/each}
          </ul>
        {/if}

        <div class="rounded-lg border border-border bg-bg-elevated/50 p-3">
          <p class="text-xs font-semibold text-text-primary uppercase tracking-wider mb-2.5">What you'll know after this</p>
          <ul class="space-y-2">
            {#each MODAL_OUTCOMES as outcome}
              <li class="flex items-start gap-2 text-sm">
                <span class="text-accent mt-0.5 shrink-0">&#x2713;</span>
                <span class="text-text-secondary">{outcome}</span>
              </li>
            {/each}
          </ul>
          <div class="mt-3 pt-2.5 border-t border-border flex items-center gap-2 text-xs text-text-muted">
            <span class="flex items-center gap-1">
              <span class="inline-block w-1.5 h-1.5 rounded-full bg-success"></span>
              ~20 minutes
            </span>
            <span class="ml-auto">You'll get an email when ready</span>
          </div>
        </div>

        <p class="text-sm text-text-secondary">
          Your analysis starts immediately — results by email in ~20 minutes.
        </p>

        {#if errorMessage}
          <div
            class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
          >
            <AlertCircle class="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-end gap-3 p-4 border-t border-border"
      >
        <button
          onclick={handleClose}
          disabled={loading}
          class="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text-secondary hover:bg-bg-hover transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onclick={handleConfirm}
          disabled={loading}
          class="btn-primary px-4 py-2 text-sm font-medium rounded-lg flex items-center gap-2 disabled:opacity-50"
        >
          {#if loading}
            <Loader2 class="w-4 h-4 animate-spin" />
            Submitting...
          {:else}
            Validate my picks
            {#if creditCost > 0}
              <span class="inline-flex items-center gap-1 text-xs opacity-80">
                <Coins class="w-3 h-3" />{creditCost}
              </span>
            {/if}
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
