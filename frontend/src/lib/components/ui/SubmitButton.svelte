<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";

  interface Props {
    onclick?: () => void;
    disabled?: boolean;
    loading?: boolean;
    loadingText: string;
    /** Set true after a successful submit: shows check + past-tense label, auto-clears after 1.5s. */
    success?: boolean;
    /** Past-tense label for the success state (e.g. "Saved"). Falls back to `label`. */
    successLabel?: string;
    icon?: ComponentType;
    iconPosition?: "start" | "end";
    keepIconOnLoad?: boolean;
    label: string;
    suffix?: Snippet;
    type?: "button" | "submit";
    /** Associates a submit button with a form rendered elsewhere in the DOM. */
    form?: string;
    title?: string;
    /** Width contract so state relabels never shift layout (DESIGN_SYSTEM.md §6). */
    minWidth?: string;
    class?: string;
  }

  let {
    onclick,
    disabled = false,
    loading = false,
    loadingText,
    success = $bindable(false),
    successLabel,
    icon: Icon,
    iconPosition = "start",
    keepIconOnLoad = false,
    label,
    suffix,
    type = "submit",
    form,
    title,
    minWidth = "12.5rem",
    class: className = "btn-primary w-full",
  }: Props = $props();

  // Success is a moment, not a mode: auto-clear after 1.5s.
  $effect(() => {
    if (!success) return;
    const timer = setTimeout(() => {
      success = false;
    }, 1500);
    return () => clearTimeout(timer);
  });
</script>

<button
  {type}
  {form}
  {onclick}
  disabled={disabled || loading || success}
  class="submit-btn {className}"
  class:is-loading={loading}
  class:is-success={success && !loading}
  aria-busy={loading || undefined}
  style:min-width={minWidth}
  {title}
>
  {#if loading}
    {#if keepIconOnLoad && Icon}
      <Icon class="w-4 h-4 animate-spin" />
    {:else}
      <span class="spinner" aria-hidden="true"></span>
    {/if}
    {#if loadingText}{loadingText}{/if}
  {:else if success}
    <svg width="13" height="13" viewBox="0 0 13 13" aria-hidden="true">
      <path
        d="M2.4 7 5.3 9.8 10.6 3.6"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    {successLabel ?? label}
  {:else}
    {#if Icon && iconPosition === "start"}<Icon class="w-4 h-4" />{/if}
    {label}
    {#if suffix}{@render suffix()}{/if}
    {#if Icon && iconPosition === "end"}<Icon class="w-4 h-4" />{/if}
  {/if}
</button>

<style>
  .submit-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2.4rem;
    padding: 0.5rem 1rem;
    border: 0;
    border-radius: var(--radius-md);
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    font-size: var(--text-13);
    font-weight: 700;
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }

  .submit-btn:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }

  .submit-btn:active:not(:disabled) {
    transform: scale(0.98);
  }

  .submit-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* Disabled = bg-hover + muted text, never opacity. */
  .submit-btn:disabled {
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
    opacity: 1;
    transform: none;
  }

  /* Loading and success keep the accent fill (never green). */
  .submit-btn.is-loading:disabled {
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    cursor: wait;
  }

  .submit-btn.is-success:disabled {
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    cursor: default;
  }

  .spinner {
    width: 0.875rem;
    height: 0.875rem;
    border: 2px solid color-mix(in srgb, var(--color-text-on-accent) 35%, transparent);
    border-top-color: var(--color-text-on-accent);
    border-radius: 50%;
    animation: spin 600ms linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .submit-btn {
      transition: none;
    }

    .submit-btn:active:not(:disabled) {
      transform: none;
    }

    .spinner {
      animation-duration: 1.5s;
    }
  }
</style>
