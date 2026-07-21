<script lang="ts">
  import type { ComponentType } from "svelte";

  interface Props {
    href?: string;
    onclick?: (e: MouseEvent) => void;
    icon?: ComponentType;
    iconPosition?: "start" | "end";
    label: string;
    disabled?: boolean;
    target?: string;
    rel?: string;
    title?: string;
    class?: string;
  }

  let {
    href,
    onclick,
    icon: Icon,
    iconPosition = "start",
    label,
    disabled = false,
    target,
    rel,
    title,
    class: className = "btn-primary",
  }: Props = $props();
</script>

{#if href}
  <a {href} class={className} {target} {rel} {title} {onclick}>
    {#if Icon && iconPosition === "start"}<Icon class="w-4 h-4" />{/if}
    {label}
    {#if Icon && iconPosition === "end"}<Icon class="w-4 h-4" />{/if}
  </a>
{:else}
  <button {onclick} {disabled} class={className} {title}>
    {#if Icon && iconPosition === "start"}<Icon class="w-4 h-4" />{/if}
    {label}
    {#if Icon && iconPosition === "end"}<Icon class="w-4 h-4" />{/if}
  </button>
{/if}

<style>
  /* v3 ghost recipe (DESIGN_SYSTEM.md §6). The global .btn-* migration is a
     later wave; this scoped rule lets Button render class="btn-ghost" today. */
  .btn-ghost {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2rem;
    padding: 0 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    transition:
      background var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .btn-ghost:hover:not(:disabled) {
    border-color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .btn-ghost:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .btn-ghost:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (prefers-reduced-motion: reduce) {
    .btn-ghost {
      transition: none;
    }
  }
</style>
