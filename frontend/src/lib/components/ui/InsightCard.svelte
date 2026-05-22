<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    variant?:
      | "default"
      | "success"
      | "warning"
      | "error"
      | "accent"
      | "muted"
      | "info";
    border?: "none" | "left" | "top" | "all";
    hoverable?: boolean;
    padding?: "sm" | "md" | "lg";
    header?: Snippet;
    meta?: Snippet;
    footer?: Snippet;
    children: Snippet;
    class?: string;
  }

  let {
    variant = "default",
    border = "all",
    hoverable = false,
    padding = "md",
    header,
    meta,
    footer,
    children,
    class: className = "",
  }: Props = $props();
</script>

<div
  class="insight-card insight-card--{variant} insight-card--border-{border} insight-card--padding-{padding} {className}"
  class:hoverable
>
  {#if header}
    <div class="insight-card__header">
      {@render header()}
    </div>
  {/if}

  {#if meta}
    <div class="insight-card__meta">
      {@render meta()}
    </div>
  {/if}

  <div class="insight-card__content">
    {@render children()}
  </div>

  {#if footer}
    <div class="insight-card__footer">
      {@render footer()}
    </div>
  {/if}
</div>

<style>
  .insight-card {
    background: var(--color-bg-elevated);
    border-radius: 0.625rem;
  }

  /* Padding sizes */
  .insight-card--padding-sm {
    padding: 0.75rem;
  }

  .insight-card--padding-md {
    padding: 1rem;
  }

  .insight-card--padding-lg {
    padding: 1.25rem;
  }

  /* Border styles */
  .insight-card--border-all {
    border: 1px solid var(--color-border);
  }

  .insight-card--border-left {
    border: 1px solid var(--color-border);
    border-left-width: 2px;
  }

  .insight-card--border-top {
    border: 1px solid var(--color-border);
    border-top-width: 3px;
  }

  .insight-card--border-none {
    border: none;
  }

  /* Default variant */
  .insight-card--default {
    background: var(--color-bg-elevated);
  }

  .insight-card--default.insight-card--border-left,
  .insight-card--default.insight-card--border-top {
    border-left-color: var(--color-border);
    border-top-color: var(--color-border);
  }

  /* Success variant — flat surface, semantic border (Phase 5) */
  .insight-card--success {
    background: var(--color-bg-elevated);
    border-color: rgba(34, 197, 94, 0.15);
  }

  .insight-card--success.insight-card--border-left {
    border-left-color: var(--color-success);
  }

  .insight-card--success.insight-card--border-top {
    border-top-color: var(--color-success);
  }

  .insight-card--success.hoverable:hover {
    border-color: rgba(34, 197, 94, 0.3);
  }

  /* Warning variant — flat surface, semantic border (Phase 5) */
  .insight-card--warning {
    background: var(--color-bg-elevated);
    border-color: rgba(234, 179, 8, 0.15);
  }

  .insight-card--warning.insight-card--border-left {
    border-left-color: var(--color-warning);
  }

  .insight-card--warning.insight-card--border-top {
    border-top-color: var(--color-warning);
  }

  .insight-card--warning.hoverable:hover {
    border-color: rgba(234, 179, 8, 0.3);
  }

  /* Error variant — flat surface, semantic border (Phase 5) */
  .insight-card--error {
    background: var(--color-bg-elevated);
    border-color: rgba(239, 68, 68, 0.15);
  }

  .insight-card--error.insight-card--border-left {
    border-left-color: var(--color-error);
  }

  .insight-card--error.insight-card--border-top {
    border-top-color: var(--color-error);
  }

  .insight-card--error.hoverable:hover {
    border-color: rgba(239, 68, 68, 0.3);
  }

  /* Accent variant — flat surface, semantic border (Phase 5) */
  .insight-card--accent {
    background: var(--color-bg-elevated);
    border-color: var(--color-accent-glow);
  }

  .insight-card--accent.insight-card--border-left {
    border-left-color: var(--color-accent);
  }

  .insight-card--accent.insight-card--border-top {
    border-top-color: var(--color-accent);
  }

  .insight-card--accent.hoverable:hover {
    border-color: var(--color-border-accent);
  }

  /* Info variant (purple) — flat surface, semantic border (Phase 5) */
  .insight-card--info {
    background: var(--color-bg-elevated);
    border-color: rgba(99, 102, 241, 0.15);
  }

  .insight-card--info.insight-card--border-left {
    border-left-color: var(--color-secondary);
  }

  .insight-card--info.insight-card--border-top {
    border-top-color: var(--color-secondary);
  }

  .insight-card--info.hoverable:hover {
    border-color: rgba(99, 102, 241, 0.3);
  }

  /* Muted variant */
  .insight-card--muted {
    background: var(--color-bg-surface);
    border-color: var(--color-border);
  }

  .insight-card--muted.insight-card--border-left {
    border-left-color: var(--color-text-muted);
  }

  .insight-card--muted.insight-card--border-top {
    border-top-color: var(--color-text-muted);
  }

  /* Card sections */
  .insight-card__header {
    margin-bottom: 0.75rem;
  }

  .insight-card__meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .insight-card__content {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.55;
  }

  .insight-card__footer {
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--color-border);
  }
</style>
