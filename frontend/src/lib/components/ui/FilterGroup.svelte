<script lang="ts">
  import { Filter } from "lucide-svelte";

  interface FilterOption {
    value: string;
    label: string;
    count?: number;
  }

  interface Props {
    label?: string;
    options: FilterOption[];
    selected: string | string[];
    multiple?: boolean;
    showCounts?: boolean;
    showAllOption?: boolean;
    class?: string;
    onchange?: (selected: string | string[]) => void;
  }

  let {
    label,
    options,
    selected = $bindable(),
    multiple = false,
    showCounts = false,
    showAllOption = true,
    class: className = "",
    onchange,
  }: Props = $props();

  const isSelected = (value: string): boolean => {
    if (multiple && Array.isArray(selected)) {
      return selected.includes(value);
    }
    return selected === value;
  };

  const handleClick = (value: string) => {
    if (multiple && Array.isArray(selected)) {
      if (value === "all") {
        selected = [];
      } else if (selected.includes(value)) {
        selected = selected.filter((v) => v !== value);
      } else {
        selected = [...selected, value];
      }
    } else {
      selected = value === selected ? "" : value;
    }
    onchange?.(selected);
  };

  const isAllSelected = $derived(
    multiple ? Array.isArray(selected) && selected.length === 0 : !selected,
  );
</script>

<div class="filter-group {className}">
  {#if label}
    <div class="filter-label">
      <Filter class="w-3.5 h-3.5" />
      <span>{label}</span>
    </div>
  {/if}

  <div class="filter-buttons">
    {#if showAllOption}
      <button
        class="filter-button"
        class:active={isAllSelected}
        onclick={() => handleClick("all")}
        type="button"
      >
        All
      </button>
    {/if}

    {#each options as option}
      <button
        class="filter-button"
        class:active={isSelected(option.value)}
        onclick={() => handleClick(option.value)}
        type="button"
      >
        {option.label}
        {#if showCounts && option.count !== undefined}
          <span class="filter-count">{option.count}</span>
        {/if}
      </button>
    {/each}
  </div>
</div>

<style>
  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .filter-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .filter-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .filter-button {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    cursor: pointer;
    transition: color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
  }

  .filter-button:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-hover);
    border-color: var(--color-border-emphasis);
  }

  .filter-button.active {
    color: var(--color-accent);
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
  }

  .filter-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    background: var(--color-bg-hover);
    border-radius: 10px;
  }

  .filter-button.active .filter-count {
    color: var(--color-accent);
    background: var(--color-border-accent);
  }

  @media (max-width: 640px) {
    .filter-button {
      padding: 0.375rem 0.75rem;
      font-size: 0.75rem;
    }
  }
</style>
