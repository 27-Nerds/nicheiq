<script lang="ts">
  interface SegmentOption {
    value: string;
    label: string;
    description?: string;
    /** Disables this one option (e.g. an outcome a data-quality warning rules out). */
    disabled?: boolean;
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
    disabled?: boolean;
    onChange?: (value: string) => void;
  }

  let {
    options,
    value = $bindable(),
    density = "compact",
    label,
    labelledBy,
    disabled = false,
    onChange,
  }: Props = $props();

  let groupEl = $state<HTMLDivElement>();

  const selectedIndex = $derived(options.findIndex((o) => o.value === value));

  // Roving tabindex: the checked radio (or the first, when none is checked)
  // is the group's single tab stop.
  function tabIndexFor(index: number): number {
    if (selectedIndex === -1) return index === 0 ? 0 : -1;
    return index === selectedIndex ? 0 : -1;
  }

  function select(option: SegmentOption) {
    if (disabled || option.disabled) return;
    if (option.value !== value) {
      value = option.value;
      onChange?.(option.value);
    }
  }

  function handleKeydown(event: KeyboardEvent, index: number) {
    let next: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      next = (index + 1) % options.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      next = (index - 1 + options.length) % options.length;
    } else if (event.key === "Home") {
      next = 0;
    } else if (event.key === "End") {
      next = options.length - 1;
    }
    if (next === null) return;
    event.preventDefault();
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
>
  {#each options as option, index (option.value)}
    <button
      type="button"
      role="radio"
      aria-checked={option.value === value}
      tabindex={tabIndexFor(index)}
      class={density === "card" ? "segment-card" : "segment"}
      disabled={disabled || option.disabled}
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

<style>
  /* ── Card density ── */
  .segment-cards {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .segment-card {
    display: grid;
    gap: 0.25rem;
    align-content: start;
    padding: 0.75rem 0.85rem;
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
    line-height: 1.4;
  }

  /* ── Compact density ── */
  .segment-track {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 2px;
    padding: 3px;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .segment {
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: transparent;
    padding: 0.3rem 0.7rem;
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
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
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
    opacity: 0.45;
    cursor: not-allowed;
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
