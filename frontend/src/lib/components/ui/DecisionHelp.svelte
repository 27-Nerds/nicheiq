<script lang="ts">
  import { HelpCircle } from "lucide-svelte";
  import type { Snippet } from "svelte";
  import Popover from "./Popover.svelte";

  interface Props {
    title: string;
    label?: string;
    position?: "top" | "bottom" | "left" | "right";
    children: Snippet;
  }

  let {
    title,
    label,
    position = "top",
    children,
  }: Props = $props();

  const accessibleLabel = $derived(label ?? `Help: ${title}`);
</script>

<Popover {title} label={accessibleLabel} {position} class="decision-help__trigger">
  {#snippet trigger()}
    <HelpCircle size={16} strokeWidth={1.8} aria-hidden="true" />
    {#if label}<span>{label}</span>{/if}
  {/snippet}

  {@render children()}
</Popover>

<style>
  :global(button.decision-help__trigger) {
    width: 2rem;
    height: 2rem;
    justify-content: center;
    color: var(--color-text-muted);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 999px;
  }

  :global(button.decision-help__trigger:has(span)) {
    width: auto;
    padding: 0 0.7rem;
    gap: 0.4rem;
    border-radius: 0.55rem;
    font-size: 0.72rem;
    font-weight: 700;
  }

  :global(button.decision-help__trigger:hover) {
    color: var(--color-text-primary);
    background: var(--color-bg-subtle);
    border-color: var(--color-border-emphasis);
    opacity: 1;
  }

  :global(button.decision-help__trigger:focus-visible) {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>
