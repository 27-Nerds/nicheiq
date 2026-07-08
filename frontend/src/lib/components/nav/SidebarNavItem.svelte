<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    /** Active row — neutral text + slim accent left-rail (dashboard idiom). */
    active?: boolean;
    /** Preview tier — dimmed until hovered (deep-research previews). */
    preview?: boolean;
    /** Render as a link when set; otherwise a <button>. */
    href?: string;
    /** Leading element (icon / dot). Give icons the `sidebar-nav-ic` class. */
    leading?: Snippet;
    /** Label content. */
    children: Snippet;
    /** Trailing element (count / badge / check / lock). */
    trailing?: Snippet;
    /** Extra modifier class(es) on the item (e.g. a caller's "done" tier). */
    class?: string;
    /** Forwarded to the underlying element (onclick, disabled, aria-*, title). */
    [key: string]: unknown;
  }

  let {
    active = false,
    preview = false,
    href,
    leading,
    children,
    trailing,
    class: className = "",
    ...rest
  }: Props = $props();
</script>

{#snippet body()}
  {@render leading?.()}
  <span class="sidebar-nav-item-label">{@render children()}</span>
  {@render trailing?.()}
{/snippet}

{#if href}
  <a class="sidebar-nav-item {className}" class:active class:preview {href} {...rest}>
    {@render body()}
  </a>
{:else}
  <button class="sidebar-nav-item {className}" class:active class:preview type="button" {...rest}>
    {@render body()}
  </button>
{/if}

<style>
  .sidebar-nav-item {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.625rem;
    width: 100%;
    padding: 0.5rem 1.5rem;
    background: transparent;
    border: none;
    text-align: left;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    transition:
      color 180ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 180ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 180ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  .sidebar-nav-item:hover:not(.active):not(:disabled) {
    background: color-mix(in srgb, var(--color-bg-surface) 64%, transparent);
    color: var(--color-text-primary);
  }
  .sidebar-nav-item:not(:disabled):active {
    transform: scale(0.99);
  }
  .sidebar-nav-item:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }

  /* Active: neutral text + slim accent rail (fills exempt from text contrast). */
  .sidebar-nav-item.active {
    color: var(--color-text-primary);
    font-weight: 700;
  }
  .sidebar-nav-item.active::before {
    content: "";
    position: absolute;
    left: 0.8rem;
    top: 0.55rem;
    bottom: 0.55rem;
    width: 2px;
    border-radius: 999px;
    background: var(--color-accent);
  }

  .sidebar-nav-item:disabled {
    cursor: default;
    opacity: 0.45;
  }
  .sidebar-nav-item.preview {
    opacity: 0.75;
  }
  .sidebar-nav-item.preview:hover {
    opacity: 1;
  }

  .sidebar-nav-item-label {
    flex: 1;
    line-height: 1.4;
    min-width: 0;
  }

  /* Shared leading icon: 18px, half-opacity, brighter when active. */
  .sidebar-nav-item :global(.sidebar-nav-ic) {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    opacity: 0.5;
    transition: opacity 0.15s ease;
  }
  .sidebar-nav-item.active :global(.sidebar-nav-ic) {
    opacity: 0.82;
  }
</style>
