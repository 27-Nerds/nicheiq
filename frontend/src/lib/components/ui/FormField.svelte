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
    oninput?: (e: Event) => void;
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
    oninput,
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
      name={id}
      bind:value
      {placeholder}
      {required}
      {minlength}
      {maxlength}
      {rows}
      {disabled}
      {onkeydown}
      {oninput}
      {onblur}
      class="field-control field-textarea"
      class:is-error={!!error}
      aria-invalid={error ? "true" : undefined}
      aria-describedby={describedBy}
    ></textarea>
  {:else if kind === "select"}
    <div class="field-select-wrap">
      <select
        {id}
        name={id}
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
      <svg class="field-select-chevron" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>
  {:else}
    <input
      {type}
      {id}
      name={id}
      bind:value
      {placeholder}
      {required}
      {minlength}
      {maxlength}
      {disabled}
      {onkeydown}
      {oninput}
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
        <span
          class="char-count"
          class:is-near={value.length >= maxlength * 0.8}
          class:is-full={value.length >= maxlength}
        >
          {value.length} / {maxlength}
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .field {
    display: grid;
    gap: var(--space-1-5);
  }

  .field-label {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
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
    margin: 0;
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    color: var(--color-text-muted);
  }

  .field-control {
    width: 100%;
    min-height: var(--space-10);
    padding: 0 var(--space-3);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
    font: inherit;
    font-size: var(--text-13);
    line-height: var(--leading-normal);
    transition:
      border-color var(--duration-fast) var(--ease-default),
      box-shadow var(--duration-fast) var(--ease-default);
  }

  .field-control::placeholder {
    color: var(--color-text-muted);
  }

  .field-textarea {
    min-height: var(--space-20);
    padding: var(--space-2) var(--space-3);
    resize: vertical;
  }

  .field-select {
    appearance: none;
    padding-right: var(--space-8);
  }

  .field-select-wrap {
    position: relative;
    color: var(--color-text-secondary);
  }

  .field-select-chevron {
    position: absolute;
    top: 50%;
    right: var(--space-3);
    pointer-events: none;
    transform: translateY(-50%);
  }

  .field-select-wrap:has(.field-select:disabled) {
    color: var(--color-text-muted);
  }

  .field-control:hover:not(:disabled):not(.is-error) {
    border-color: var(--color-input-border-hover);
  }

  .field-control:focus {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }

  .field-control:focus:not(:focus-visible) {
    outline: none;
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
    gap: var(--space-3);
  }

  .field-error {
    display: flex;
    align-items: flex-start;
    gap: var(--space-1-5);
    flex: 1;
    margin: 0;
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    color: var(--color-error-text);
  }

  .field-error svg {
    flex: 0 0 auto;
    margin-top: var(--space-1);
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
    opacity: 0;
    transition: opacity var(--duration-fast) var(--ease-default);
  }

  .field:focus-within .char-count,
  .field:has(.field-error) .char-count,
  .char-count.is-near {
    opacity: 1;
  }

  .char-count.is-full {
    opacity: 1;
    color: var(--color-error-text);
  }

  .field:focus-within .char-count:not(.is-full):not(.is-near) {
    color: var(--color-text-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    .field-control,
    .char-count {
      transition: none;
    }
  }
</style>
