<script lang="ts">
  import {
    AlertTriangle,
    FileQuestion,
    Search,
    Database,
    Info,
  } from "lucide-svelte";
  import type { ComponentType } from "svelte";

  interface Props {
    icon?: ComponentType;
    title: string;
    description?: string;
    variant?: "default" | "warning" | "info" | "muted";
    size?: "sm" | "md" | "lg";
    children?: import("svelte").Snippet;
  }

  let {
    icon: Icon = FileQuestion,
    title,
    description = "",
    variant = "default",
    size = "md",
    children,
  }: Props = $props();

  const iconSizes = {
    sm: "w-8 h-8",
    md: "w-12 h-12",
    lg: "w-16 h-16",
  };

  const containerPadding = {
    sm: "py-4 px-4",
    md: "py-8 px-6",
    lg: "py-12 px-8",
  };
</script>

<div class="empty-state {variant} {containerPadding[size]}">
  <div class="empty-state-icon {variant}">
    <Icon class={iconSizes[size]} />
  </div>
  <h4
    class="empty-state-title"
    class:text-lg={size === "lg"}
    class:text-sm={size === "sm"}
  >
    {title}
  </h4>
  {#if description}
    <p class="empty-state-description" class:text-sm={size !== "lg"}>
      {description}
    </p>
  {/if}
  {#if children}
    <div class="empty-state-actions">
      {@render children()}
    </div>
  {/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    border-radius: 0.75rem;
    background: var(--empty-bg, var(--color-bg-surface));
    border: 1px dashed var(--empty-border, var(--color-border));
  }

  .empty-state.default {
    --empty-bg: var(--color-bg-surface);
    --empty-border: var(--color-border);
    --empty-icon-bg: rgba(100, 116, 139, 0.1);
    --empty-icon-color: var(--color-text-muted);
  }

  .empty-state.warning {
    --empty-bg: rgba(245, 158, 11, 0.04);
    --empty-border: rgba(245, 158, 11, 0.3);
    --empty-icon-bg: rgba(245, 158, 11, 0.12);
    --empty-icon-color: var(--color-warning);
  }

  .empty-state.info {
    --empty-bg: rgba(99, 102, 241, 0.04);
    --empty-border: rgba(99, 102, 241, 0.3);
    --empty-icon-bg: rgba(99, 102, 241, 0.12);
    --empty-icon-color: var(--color-secondary);
  }

  .empty-state.muted {
    --empty-bg: transparent;
    --empty-border: var(--color-border);
    --empty-icon-bg: var(--color-bg-hover);
    --empty-icon-color: var(--color-text-muted);
  }

  .empty-state-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 4rem;
    height: 4rem;
    margin-bottom: 1rem;
    border-radius: 1rem;
    background: var(--empty-icon-bg);
    color: var(--empty-icon-color);
  }

  .empty-state-title {
    font-family: var(--font-display);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 0.5rem;
  }

  .empty-state-description {
    color: var(--color-text-secondary);
    max-width: 32ch;
    margin: 0;
    line-height: 1.5;
  }

  .empty-state-actions {
    margin-top: 1.25rem;
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    justify-content: center;
  }
</style>
