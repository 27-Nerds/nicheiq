<script lang="ts">
  import { tick } from "svelte";

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
		disabledReason?: string;
		loadingText?: string;
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
		disabledReason,
		loadingText = "Working…",
  }: Props = $props();

  let armed = $state(false);
  let gateEl = $state<HTMLDivElement>();
  let confirmEl = $state<HTMLButtonElement>();
  let triggerEl = $state<HTMLButtonElement>();

  const gateLine = $derived(variant === "paid" ? costLine : consequence);
	const componentId = $props.id();
	const disabledReasonId = `${componentId}-disabled-reason`;

  function arm() {
    if (disabled || busy) return;
    armed = true;
  }

  function confirm() {
		if (disabled || busy) return;
    armed = false;
    onConfirm();
  }

  /** Escape while armed disarms the gate and returns focus to the trigger,
   *  without bubbling to an enclosing overlay's own Escape handling. */
  async function disarmOnEscape(event: KeyboardEvent) {
    if (event.key !== "Escape" || !armed) return;
    event.preventDefault();
    event.stopPropagation();
    armed = false;
    await tick();
    triggerEl?.focus();
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

	$effect(() => {
		if (disabled) armed = false;
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
        onkeydown={disarmOnEscape}
      >
        Cancel
      </button>
      <button
        type="button"
        class="gate-confirm"
			bind:this={confirmEl}
			disabled={disabled || busy}
        aria-busy={busy || undefined}
			aria-label={confirmLabel}
        onclick={confirm}
        onkeydown={disarmOnEscape}
      >
			{#if busy}
				<span class="gate-spinner animate-spin" aria-hidden="true"></span>
				{loadingText}
			{:else}
				{confirmLabel}
			{/if}
      </button>
    </span>
  </div>
{:else}
  <button
    type="button"
    class="gate-trigger"
    bind:this={triggerEl}
    disabled={disabled || busy}
		aria-busy={busy || undefined}
		aria-label={busy ? label : undefined}
		aria-describedby={disabled && disabledReason ? disabledReasonId : undefined}
    onclick={arm}
  >
		{#if busy}
			<span class="gate-spinner animate-spin" aria-hidden="true"></span>
			{loadingText}
		{:else}
			{label}
		{/if}
  </button>
{/if}
{#if disabled && disabledReason}
	<p id={disabledReasonId} class="gate-disabled-reason">{disabledReason}</p>
{/if}

<style>
  .confirm-gate {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
    padding: var(--space-2) var(--space-3);
    /* Neutral border, never warning orange. */
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .gate-line {
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 700;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    color: var(--color-text-primary);
  }

  .gate-actions {
    display: flex;
    gap: var(--space-2);
  }

  .gate-trigger,
  .gate-cancel {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.1rem;
    padding: var(--space-1-5) var(--space-3);
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

  /* Trigger, cancel, and confirm all reserve min-width so the armed relabel can't shift layout. */
  .gate-trigger,
  .gate-cancel {
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
    padding: var(--space-1-5) var(--space-3);
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
		background: var(--color-bg-hover);
		color: var(--color-text-muted);
		border-color: var(--color-border-emphasis);
    cursor: not-allowed;
  }

	.gate-confirm[aria-busy="true"] {
		background: var(--color-accent-hover);
		color: var(--color-text-on-accent);
		cursor: wait;
	}

	.gate-spinner {
		width: var(--space-3);
		height: var(--space-3);
		border: 2px solid color-mix(in srgb, currentColor 35%, transparent);
		border-top-color: currentColor;
		border-radius: var(--radius-full);
		animation: spin var(--duration-slowest) linear infinite;
	}

	.gate-disabled-reason {
		margin: var(--space-1) 0 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		line-height: var(--leading-snug);
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
