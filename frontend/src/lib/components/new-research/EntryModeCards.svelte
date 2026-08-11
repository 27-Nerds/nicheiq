<script lang="ts" module>
  export type EntryMode = "idea" | "audience" | "discovery" | "validate_idea";
</script>

<script lang="ts">
  import { Lightbulb, Users, ClipboardCheck } from "lucide-svelte";

  interface Props {
    selected: EntryMode;
    onselect: (mode: EntryMode) => void;
  }

  let { selected, onselect }: Props = $props();

  const modes = [
    {
      id: "idea" as EntryMode,
      title: "Explore a niche",
      description: "You have a market or problem in mind",
      icon: Lightbulb,
    },
    {
      id: "audience" as EntryMode,
      title: "Solve for a group",
      description: "You know who you want to build for",
      icon: Users,
    },
    {
      id: "validate_idea" as EntryMode,
      title: "Check my idea",
      description: "You have a specific product in mind",
      icon: ClipboardCheck,
    },
  ] as const;

  let optionEls = $state<HTMLButtonElement[]>([]);

  // Roving-tabindex arrow-key navigation for the radio group. Moving focus
  // also moves selection, matching the ARIA radiogroup pattern.
  function handleKeydown(e: KeyboardEvent, i: number) {
    let next = -1;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      next = (i + 1) % modes.length;
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      next = (i - 1 + modes.length) % modes.length;
    } else if (e.key === "Home") {
      next = 0;
    } else if (e.key === "End") {
      next = modes.length - 1;
    }
    if (next === -1) return;
    e.preventDefault();
    onselect(modes[next].id);
    optionEls[next]?.focus();
  }
</script>

<div class="mode-group" role="radiogroup" aria-label="Research starting point">
  {#each modes as mode, i}
    {@const isSelected = selected === mode.id}
    <button
      bind:this={optionEls[i]}
      type="button"
      role="radio"
      aria-checked={isSelected}
      tabindex={isSelected ? 0 : -1}
      class="mode-option"
      class:selected={isSelected}
      onclick={() => onselect(mode.id)}
      onkeydown={(e) => handleKeydown(e, i)}
    >
      <mode.icon class="mode-icon" aria-hidden="true" />
      <span class="mode-body">
        <span class="mode-title">{mode.title}</span>
        <span class="mode-desc">{mode.description}</span>
      </span>
    </button>
  {/each}
</div>

<style>
  .mode-group {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  @media (min-width: 640px) {
    .mode-group {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .mode-option {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    text-align: left;
    padding: 0.875rem 1rem;
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
    cursor: pointer;
    transition:
      border-color 0.15s ease,
      background-color 0.15s ease,
      color 0.15s ease;
  }
  .mode-option:hover:not(.selected) {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-base);
  }
  .mode-option.selected {
    border-color: var(--color-border-accent);
    background: var(--color-accent-subtle);
  }
  .mode-option:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .mode-option:active {
    transform: scale(0.99);
  }

  .mode-option :global(.mode-icon) {
    width: 1.25rem;
    height: 1.25rem;
    flex-shrink: 0;
    margin-top: 0.125rem;
    color: var(--color-text-muted);
  }
  /* Icon FILL uses accent on the active option — exempt from the accent-as-text rule. */
  .mode-option.selected :global(.mode-icon) {
    color: var(--color-accent);
  }

  .mode-body {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .mode-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .mode-option.selected .mode-title {
    color: var(--color-accent-dark);
  }
  .mode-desc {
    font-size: 0.75rem;
    margin-top: 0.125rem;
    color: var(--color-text-muted);
  }

  @media (max-width: 639px) {
    .mode-option {
      align-items: center;
      padding: 0.75rem 0.875rem;
    }
    .mode-option :global(.mode-icon) {
      margin-top: 0;
    }
    .mode-desc {
      display: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .mode-option {
      transition: none;
    }
    .mode-option:active {
      transform: none;
    }
  }
</style>
