<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";

  interface Props {
    id: string;
    label: string;
    /** Control kind. For "select", pass <option> elements via children. */
    kind?: "input" | "select" | "textarea";
    /** Input type (kind="input" only). */
    type?: string;
    value: string;
    placeholder?: string;
    /** Renders the muted "Optional" marker beside the label. */
    optional?: boolean;
    /** One earned sentence between label and control. */
    hint?: string;
    /** Inline error below the control (role="alert"). */
    error?: string;
    required?: boolean;
    minlength?: number;
    /** Caps the control and renders the mono char-count. */
    maxlength?: number;
    rows?: number;
    disabled?: boolean;
    onkeydown?: (e: KeyboardEvent) => void;
    onchange?: (e: Event) => void;
    onblur?: (e: FocusEvent) => void;
    /** @deprecated v2 icon-led API. Ignored: the v3 field recipe has no leading icon. */
    icon?: ComponentType;
    class?: string;
    /** <option> elements for kind="select". */
    children?: Snippet;
  }

  let {
    id,
    label,
    kind = "input",
    type = "text",
    value = $bindable(),
    placeholder,
    optional = false,
    hint,
    error,
    required = false,
    minlength,
    maxlength,
    rows,
    disabled = false,
    onkeydown,
    onchange,
    onblur,
    icon,
    class: className = "",
    children,
  }: Props = $props();

  $effect(() => {
    if (icon) {
      console.warn(
        "FormField: the `icon` prop is deprecated and ignored (the v3 field recipe has no leading icon).",
      );
    }
  });

  const hintId = $derived(hint ? `${id}-hint` : undefined);
  const errorId = $derived(error ? `${id}-error` : undefined);
  const describedBy = $derived(
    [hintId, errorId].filter(Boolean).join(" ") || undefined,
  );
</script>

<div class="field {className}">
  <label class="field-label" for={id}>
    {label}
    {#if optional}<span class="opt">Optional</span>{:else if required}<span class="req">Required</span>{/if}
  </label>
  {#if hint}
    <p class="field-hint" id={hintId}>{hint}</p>
  {/if}

  {#if kind === "textarea"}
    <textarea
      {id}
      bind:value
      {placeholder}
      {required}
      {minlength}
      {maxlength}
      {rows}
      {disabled}
      {onkeydown}
      {onblur}
      class="field-control field-textarea"
      class:is-error={!!error}
      aria-invalid={error ? "true" : undefined}
      aria-describedby={describedBy}
    ></textarea>
  {:else if kind === "select"}
    <select
      {id}
      bind:value
      {required}
      {disabled}
      {onkeydown}
      {onchange}
      {onblur}
      class="field-control field-select"
      class:is-error={!!error}
      aria-invalid={error ? "true" : undefined}
      aria-describedby={describedBy}
    >
      {@render children?.()}
    </select>
  {:else}
    <input
      {type}
      {id}
      bind:value
      {placeholder}
      {required}
      {minlength}
      {maxlength}
      {disabled}
      {onkeydown}
      {onblur}
      class="field-control"
      class:is-error={!!error}
      aria-invalid={error ? "true" : undefined}
      aria-describedby={describedBy}
    />
  {/if}

  {#if error || maxlength !== undefined}
    <div class="field-meta">
      {#if error}
        <p class="field-error" id={errorId} role="alert">
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <circle cx="6" cy="6" r="5.4" fill="currentColor" />
            <rect x="5.35" y="2.8" width="1.3" height="4" rx="0.65" fill="var(--color-bg-elevated)" />
            <circle cx="6" cy="8.9" r="0.75" fill="var(--color-bg-elevated)" />
          </svg>
          {error}
        </p>
      {/if}
      {#if maxlength !== undefined}
        <span class="char-count" class:is-full={value.length >= maxlength}>
          {value.length} / {maxlength}
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .field {
    display: grid;
    gap: 0.4rem;
  }

  .field-label {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    font-size: var(--text-13);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .field-label .opt,
  .field-label .req {
    font-size: var(--text-11);
    font-weight: 500;
    color: var(--color-text-muted);
  }

  .field-hint {
    margin: -0.1rem 0 0;
    font-size: var(--text-sm);
    line-height: 1.45;
    color: var(--color-text-muted);
  }

  .field-control {
    width: 100%;
    min-height: 2.35rem;
    padding: 0 0.65rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-13);
    line-height: 1.45;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      box-shadow var(--duration-fast) var(--ease-default);
  }

  .field-control::placeholder {
    color: var(--color-text-muted);
  }

  .field-textarea {
    min-height: 4.6rem;
    padding: 0.55rem 0.65rem;
    resize: vertical;
  }

  .field-select {
    appearance: none;
    padding-right: 2rem;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5 6 8l3.5-3.5' fill='none' stroke='%2352525B' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 0.65rem center;
  }

  .field-control:hover:not(:disabled):not(.is-error) {
    border-color: var(--color-input-border-hover);
  }

  .field-control:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }

  .field-control.is-error {
    border-color: var(--color-error-text);
  }

  .field-control.is-error:focus {
    box-shadow: 0 0 0 3px var(--color-error-subtle);
  }

  .field-control:disabled {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }

  .field-meta {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .field-error {
    display: flex;
    align-items: flex-start;
    gap: 0.35rem;
    flex: 1;
    margin: 0;
    font-size: var(--text-sm);
    line-height: 1.4;
    color: var(--color-error-text);
  }

  .field-error svg {
    flex: 0 0 auto;
    margin-top: 0.14rem;
  }

  .char-count {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .char-count.is-full {
    color: var(--color-error-text);
  }

  @media (prefers-reduced-motion: reduce) {
    .field-control {
      transition: none;
    }
  }
</style>
