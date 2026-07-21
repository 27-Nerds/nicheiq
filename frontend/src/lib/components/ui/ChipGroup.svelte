<script lang="ts">
  interface ChipOption {
    value: string;
    label: string;
  }

  interface Props {
    options: ChipOption[];
    values?: string[];
    /** Selection cap. At the cap, remaining chips disable and the counter turns error-text. */
    max?: number;
    /** Accessible name for the group. */
    label: string;
    disabled?: boolean;
    onChange?: (values: string[]) => void;
  }

  let {
    options,
    values = $bindable([]),
    max,
    label,
    disabled = false,
    onChange,
  }: Props = $props();

  const atCap = $derived(max !== undefined && values.length >= max);

  function toggle(option: ChipOption) {
    if (disabled) return;
    const picked = values.includes(option.value);
    if (!picked && atCap) return;
    values = picked
      ? values.filter((v) => v !== option.value)
      : [...values, option.value];
    onChange?.(values);
  }
</script>

<div class="chip-group">
  {#if max !== undefined}
    <span class="chip-count" class:is-full={atCap}>{values.length} / {max}</span>
  {/if}
  <div class="chip-row" role="group" aria-label={label}>
    {#each options as option (option.value)}
      <button
        type="button"
        class="chip"
        aria-pressed={values.includes(option.value)}
        disabled={disabled || (atCap && !values.includes(option.value))}
        onclick={() => toggle(option)}
      >
        {option.label}
      </button>
    {/each}
  </div>
</div>

<style>
  .chip-group {
    display: grid;
    gap: 0.4rem;
  }

  .chip-count {
    justify-self: end;
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .chip-count.is-full {
    color: var(--color-error-text);
  }

  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .chip {
    padding: 0.32rem 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-full);
    background: var(--color-bg-elevated);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .chip:hover:not(:disabled) {
    border-color: var(--color-input-border-hover);
    color: var(--color-text-primary);
  }

  .chip:active:not(:disabled) {
    transform: scale(0.98);
  }

  .chip[aria-pressed="true"] {
    border-color: var(--color-accent);
    background: var(--color-accent-subtle);
    color: var(--color-accent-dark);
    font-weight: 600;
  }

  .chip:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .chip:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  @media (prefers-reduced-motion: reduce) {
    .chip {
      transition: none;
    }

    .chip:active:not(:disabled) {
      transform: none;
    }
  }
</style>
