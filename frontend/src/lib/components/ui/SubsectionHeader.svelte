<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";
  import Badge from "./Badge.svelte";

  interface Props {
    title: string;
    icon?: ComponentType;
    count?: number | null;
    variant?: "default" | "success" | "warning" | "info";
    children?: Snippet;
  }

  let {
    title,
    icon: Icon,
    count = null,
    variant = "default",
    children,
  }: Props = $props();

  const variantColors: Record<string, string> = {
    default: "var(--color-accent)",
    success: "var(--color-success)",
    warning: "var(--color-warning)",
    info: "#6366F1",
  };

  const iconColor = $derived(variantColors[variant] || variantColors.default);
  const hasRightContent = $derived(!!children);
</script>

<div class="subsection-header" class:has-right-content={hasRightContent}>
  <div class="subsection-left">
    {#if Icon}
      <Icon class="subsection-icon" style="color: {iconColor}" />
    {/if}
    <span class="subsection-title">{title}</span>
    {#if count != null}
      <Badge variant="muted" size="sm">{count}</Badge>
    {/if}
  </div>
  {#if children}
    <div class="subsection-right">
      {@render children()}
    </div>
  {/if}
</div>

<style>
  .subsection-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .subsection-header.has-right-content {
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .subsection-left {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  :global(.subsection-icon) {
    width: 1rem;
    height: 1rem;
    flex-shrink: 0;
  }

  .subsection-title {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .subsection-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
</style>
