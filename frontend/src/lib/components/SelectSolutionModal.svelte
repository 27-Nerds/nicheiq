<script lang="ts">
  import { portal } from "$lib/actions/portal";
  import { X, Loader2, AlertCircle, Coins } from "lucide-svelte";

  interface Props {
    open: boolean;
    solutionNames: string[];
    loading?: boolean;
    error?: string;
    creditCost?: number;
    onConfirm: (rationale: string) => void;
    onCancel: () => void;
  }

  let {
    open = $bindable(false),
    solutionNames,
    loading = false,
    error: errorMessage = "",
    creditCost = 0,
    onConfirm,
    onCancel,
  }: Props = $props();

  let rationale = $state("");
  let modalEl: HTMLDivElement | undefined = $state();
  let triggerEl: HTMLElement | null = null;

  const isSingle = $derived(solutionNames.length === 1);

  function handleConfirm() {
    onConfirm(rationale);
  }

  function handleClose() {
    if (!loading) {
      rationale = "";
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
        'button:not([disabled]), textarea:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
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
          Confirm Selection
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
            Run deep analysis on <span class="font-semibold text-text-primary">{solutionNames[0]}</span>. We'll evaluate market demand, technical feasibility, SEO potential, and competitive landscape — you'll get a go/no-go verdict and a strategic action plan.
          </p>
        {:else}
          <p class="text-sm text-text-secondary">
            Run deep analysis on {solutionNames.length} solutions. We'll score each on market fit, feasibility, and SEO potential. Your report will feature the strongest as your primary recommendation with the rest as alternatives.
          </p>
          <ul class="space-y-1">
            {#each solutionNames as name}
              <li class="text-sm text-text-primary flex items-start gap-2">
                <span class="text-accent mt-0.5 shrink-0">&#x2022;</span>
                <span class="font-medium">{name}</span>
              </li>
            {/each}
          </ul>
        {/if}

        <div>
          <label
            for="rationale"
            class="block text-sm font-medium text-text-primary mb-1.5"
          >
            Why {isSingle ? 'this solution' : 'these solutions'}? <span class="text-text-muted font-normal">(optional — but helpful)</span>
          </label>
          <textarea
            id="rationale"
            bind:value={rationale}
            placeholder="e.g., Matches my technical skills, strong recurring revenue potential, underserved niche I know well..."
            rows={3}
            maxlength={2000}
            disabled={loading}
            class="input w-full resize-none text-sm"
          ></textarea>
          <div class="mt-1 flex items-center justify-between">
            <p class="text-xs text-text-muted">
              Share your thinking — we'll use this to align the analysis with your situation.
            </p>
            <span
              class="text-xs tabular-nums {rationale.length > 1800
                ? 'text-warning'
                : 'text-text-muted'}"
            >
              {rationale.length}/2000
            </span>
          </div>
        </div>

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
            Run Deep Analysis
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
