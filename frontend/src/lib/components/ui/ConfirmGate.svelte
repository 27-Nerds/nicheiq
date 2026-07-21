<script lang="ts">
  interface Props {
    /** Trigger button text (verb-first, keeps its name through the flow). */
    label: string;
    confirmLabel: string;
    variant?: "paid" | "free";
    /** Paid gate line, caller-formatted, e.g. "2 CREDITS · 42 LEFT". */
    costLine?: string;
    /** Free-but-irreversible gate line, e.g. "BECOMES IMMUTABLE". */
    consequence?: string;
    onConfirm: () => void;
    busy?: boolean;
    disabled?: boolean;
  }

  let {
    label,
    confirmLabel,
    variant = "paid",
    costLine,
    consequence,
    onConfirm,
    busy = false,
    disabled = false,
  }: Props = $props();

  let armed = $state(false);
  let gateEl = $state<HTMLDivElement>();
  let confirmEl = $state<HTMLButtonElement>();

  const gateLine = $derived(variant === "paid" ? costLine : consequence);

  function arm() {
    if (disabled || busy) return;
    armed = true;
  }

  function confirm() {
    if (busy) return;
    armed = false;
    onConfirm();
  }

  // Arm state expires on any click outside the gate.
  $effect(() => {
    if (!armed) return;
    function handleOutsideClick(event: MouseEvent) {
      if (gateEl && event.target instanceof Node && !gateEl.contains(event.target)) {
        armed = false;
      }
    }
    document.addEventListener("click", handleOutsideClick, true);
    return () => document.removeEventListener("click", handleOutsideClick, true);
  });

  $effect(() => {
    if (armed) confirmEl?.focus();
  });
</script>

{#if armed}
  <div class="confirm-gate" bind:this={gateEl}>
    {#if gateLine}<span class="gate-line">{gateLine}</span>{/if}
    <span class="gate-actions">
      <button
        type="button"
        class="gate-cancel"
        disabled={busy}
        onclick={() => (armed = false)}
      >
        Cancel
      </button>
      <button
        type="button"
        class="gate-confirm"
        bind:this={confirmEl}
        disabled={busy}
        aria-busy={busy || undefined}
        onclick={confirm}
      >
        {confirmLabel}
      </button>
    </span>
  </div>
{:else}
  <button
    type="button"
    class="gate-trigger"
    disabled={disabled || busy}
    onclick={arm}
  >
    {label}
  </button>
{/if}

<style>
  .confirm-gate {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    flex-wrap: wrap;
    padding: 0.6rem 0.75rem;
    /* Neutral border, never warning orange. */
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .gate-line {
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    color: var(--color-text-primary);
  }

  .gate-actions {
    display: flex;
    gap: 0.5rem;
  }

  .gate-trigger,
  .gate-cancel {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.1rem;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  /* Trigger and confirm both reserve min-width so the armed relabel can't shift layout. */
  .gate-trigger {
    min-width: 9.5rem;
  }

  .gate-trigger:hover:not(:disabled),
  .gate-cancel:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .gate-trigger:active:not(:disabled),
  .gate-cancel:active:not(:disabled) {
    transform: scale(0.98);
  }

  .gate-confirm {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.1rem;
    min-width: 9.5rem;
    padding: 0.35rem 0.8rem;
    border: 0;
    border-radius: var(--radius-md);
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }

  .gate-confirm:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .gate-confirm:active:not(:disabled) {
    transform: scale(0.98);
  }

  .gate-trigger:focus-visible,
  .gate-cancel:focus-visible,
  .gate-confirm:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .gate-trigger:disabled,
  .gate-cancel:disabled,
  .gate-confirm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (prefers-reduced-motion: reduce) {
    .gate-trigger,
    .gate-cancel,
    .gate-confirm {
      transition: none;
    }

    .gate-trigger:active:not(:disabled),
    .gate-cancel:active:not(:disabled),
    .gate-confirm:active:not(:disabled) {
      transform: none;
    }
  }
</style>
