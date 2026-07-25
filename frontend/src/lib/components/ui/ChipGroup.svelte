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
		labelledBy?: string;
		describedBy?: string;
    disabled?: boolean;
		disabledReason?: string;
    onChange?: (values: string[]) => void;
  }

  let {
    options,
    values = $bindable([]),
    max,
    label,
		labelledBy,
		describedBy,
    disabled = false,
		disabledReason,
    onChange,
  }: Props = $props();

  const atCap = $derived(max !== undefined && values.length >= max);
	const componentId = $props.id();
	const capStatusId = `${componentId}-cap-status`;
	const disabledReasonId = `${componentId}-disabled-reason`;
	const groupDescribedBy = $derived(
		[
			describedBy,
			atCap ? capStatusId : undefined,
			disabled && disabledReason ? disabledReasonId : undefined,
		].filter(Boolean).join(" ") || undefined,
	);

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
  <div
		class="chip-row"
		role="group"
		aria-label={labelledBy ? undefined : label}
		aria-labelledby={labelledBy}
		aria-describedby={groupDescribedBy}
	>
    {#each options as option (option.value)}
      <button
        type="button"
        class="chip"
        aria-pressed={values.includes(option.value)}
        disabled={disabled || (atCap && !values.includes(option.value))}
			title={atCap && !values.includes(option.value) ? `Maximum ${max} selected` : undefined}
        onclick={() => toggle(option)}
      >
        {option.label}
      </button>
    {/each}
  </div>
	{#if atCap}
		<p id={capStatusId} class="chip-status" role="status" aria-live="polite">
			Maximum {max} selected. Remove one to choose another.
		</p>
	{/if}
	{#if disabled && disabledReason}
		<p id={disabledReasonId} class="chip-status">{disabledReason}</p>
	{/if}
</div>

<style>
  .chip-group {
    display: grid;
    gap: var(--space-1-5);
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
    gap: var(--space-2);
  }

  .chip {
    padding: var(--space-1) var(--space-3);
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
		border-color: var(--color-border-emphasis);
		background: var(--color-bg-surface);
		color: var(--color-text-muted);
    cursor: not-allowed;
  }

	.chip-status {
		margin: 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		line-height: var(--leading-snug);
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
