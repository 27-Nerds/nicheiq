<script lang="ts">
  interface SegmentOption {
    value: string;
    label: string;
    description?: string;
    /** Disables this one option (e.g. an outcome a data-quality warning rules out). */
    disabled?: boolean;
		disabledReason?: string;
  }

  interface Props {
    options: SegmentOption[];
    value?: string;
    density?: "card" | "compact";
    /** Accessible name for the radiogroup. Ignored when `labelledBy` is set. */
    label: string;
    /** Associates the radiogroup with an existing visible label instead of the
     *  invisible `label` string (avoids an orphaned duplicate label). */
    labelledBy?: string;
		describedBy?: string;
		invalid?: boolean;
    disabled?: boolean;
		disabledReason?: string;
    onChange?: (value: string) => void;
  }

  let {
    options,
    value = $bindable(),
    density = "compact",
    label,
    labelledBy,
		describedBy,
		invalid = false,
    disabled = false,
		disabledReason,
    onChange,
  }: Props = $props();

  let groupEl = $state<HTMLDivElement>();

  const selectedIndex = $derived(options.findIndex((o) => o.value === value));
	const componentId = $props.id();
	const disabledReasonId = `${componentId}-disabled-reason`;
	const groupDescribedBy = $derived(
		[describedBy, disabled && disabledReason ? disabledReasonId : undefined]
			.filter(Boolean)
			.join(" ") || undefined,
	);

	function isDisabled(option: SegmentOption): boolean {
		return disabled || !!option.disabled;
	}

	function enabledIndices(): number[] {
		return options.flatMap((option, index) => (isDisabled(option) ? [] : [index]));
	}

  // Roving tabindex: the checked radio (or the first, when none is checked)
  // is the group's single tab stop.
  function tabIndexFor(index: number): number {
		if (isDisabled(options[index])) return -1;
		const enabled = enabledIndices();
		if (selectedIndex === -1 || isDisabled(options[selectedIndex])) {
			return index === enabled[0] ? 0 : -1;
		}
		return index === selectedIndex ? 0 : -1;
  }

  function select(option: SegmentOption) {
		if (isDisabled(option)) return;
    if (option.value !== value) {
      value = option.value;
      onChange?.(option.value);
    }
  }

  function handleKeydown(event: KeyboardEvent, index: number) {
		const enabled = enabledIndices();
		if (enabled.length === 0) return;
		const current = enabled.indexOf(index);
		let nextPosition: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
			nextPosition = (current + 1) % enabled.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
			nextPosition = (current - 1 + enabled.length) % enabled.length;
    } else if (event.key === "Home") {
			nextPosition = 0;
    } else if (event.key === "End") {
			nextPosition = enabled.length - 1;
    }
		if (nextPosition === null) return;
    event.preventDefault();
		const next = enabled[nextPosition];
    select(options[next]);
    const radios = groupEl?.querySelectorAll<HTMLButtonElement>('[role="radio"]');
    radios?.[next]?.focus();
  }
</script>

<div
  bind:this={groupEl}
  class={density === "card" ? "segment-cards" : "segment-track"}
  role="radiogroup"
  aria-label={labelledBy ? undefined : label}
  aria-labelledby={labelledBy}
	aria-describedby={groupDescribedBy}
	aria-invalid={invalid || undefined}
>
  {#each options as option, index (option.value)}
    <button
      type="button"
      role="radio"
      aria-checked={option.value === value}
      tabindex={tabIndexFor(index)}
      class={density === "card" ? "segment-card" : "segment"}
      disabled={disabled || option.disabled}
			aria-label={option.disabledReason ? `${option.label}. Unavailable: ${option.disabledReason}` : undefined}
			title={option.disabledReason}
      onclick={() => select(option)}
      onkeydown={(event) => handleKeydown(event, index)}
    >
      {#if density === "card"}
        <strong>{option.label}</strong>
        {#if option.description}<span>{option.description}</span>{/if}
      {:else}
        {option.label}
      {/if}
    </button>
  {/each}
</div>
{#if disabled && disabledReason}
	<p id={disabledReasonId} class="segment-disabled-reason">{disabledReason}</p>
{/if}

<style>
  /* ── Card density ── */
  .segment-cards {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-2);
  }

  .segment-card {
    display: grid;
    gap: var(--space-1);
    align-content: start;
    padding: var(--space-3);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    text-align: left;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default);
  }

  .segment-card:hover:not(:disabled) {
    background: var(--color-bg-surface);
  }

  .segment-card:active:not(:disabled) {
    transform: scale(0.98);
  }

  .segment-card[aria-checked="true"] {
    border-color: var(--color-accent);
    background: var(--color-accent-subtle);
  }

  .segment-card strong {
    font-size: var(--text-13);
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .segment-card span {
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
  }

  /* ── Compact density ── */
  .segment-track {
    display: inline-flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    padding: var(--space-1);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .segment {
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: transparent;
    min-height: var(--space-8);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default);
  }

  .segment:hover:not(:disabled) {
    color: var(--color-text-primary);
  }

  .segment:active:not(:disabled) {
    transform: scale(0.98);
  }

  .segment[aria-checked="true"] {
    border-color: var(--color-accent);
    background: var(--color-accent-subtle);
    color: var(--color-accent-dark);
    box-shadow: var(--shadow-sm);
  }

  /* ── Shared states ── */
  .segment-card:focus-visible,
  .segment:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .segment-card:disabled,
  .segment:disabled {
		border-color: var(--color-border-emphasis);
		background: var(--color-bg-surface);
		color: var(--color-text-muted);
    cursor: not-allowed;
  }

	.segment-disabled-reason {
		margin: var(--space-1) 0 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		line-height: var(--leading-normal);
	}

  @media (max-width: 720px) {
    .segment-cards {
      grid-template-columns: 1fr;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .segment-card,
    .segment {
      transition: none;
    }

    .segment-card:active:not(:disabled),
    .segment:active:not(:disabled) {
      transform: none;
    }
  }
</style>
