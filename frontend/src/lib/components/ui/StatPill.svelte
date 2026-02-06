<script lang="ts">
  import type { Component } from "svelte";

  interface Props {
    icon?: Component;
    value: string | number;
    label: string;
    variant?: "default" | "success" | "warning" | "error" | "accent";
    iconBg?: boolean;
    class?: string;
  }

  let {
    icon,
    value,
    label,
    variant = "default",
    iconBg = false,
    class: className = "",
  }: Props = $props();
</script>

<div class="stat-pill stat-pill--{variant} {className}" class:icon-bg={iconBg}>
  {#if icon}
    {@const Icon = icon}
    <span class="stat-icon" class:icon-bg={iconBg}>
      <Icon class="icon" />
    </span>
  {/if}
  <span class="stat-label">{label}</span>
  <span class="stat-value">{value}</span>
</div>

<style>
  .stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 999px;
  }

  .stat-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .stat-icon :global(.icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
  }

  .stat-icon.icon-bg {
    width: 1.5rem;
    height: 1.5rem;
    background: var(--color-bg-elevated);
    border-radius: 50%;
  }

  .stat-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .stat-value {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  /* Variants */
  .stat-pill--success {
    background: rgba(34, 197, 94, 0.08);
    border-color: rgba(34, 197, 94, 0.2);
  }

  .stat-pill--success .stat-value {
    color: var(--color-success);
  }

  .stat-pill--success .stat-icon :global(.icon) {
    color: var(--color-success);
  }

  .stat-pill--warning {
    background: rgba(234, 179, 8, 0.08);
    border-color: rgba(234, 179, 8, 0.2);
  }

  .stat-pill--warning .stat-value {
    color: var(--color-warning);
  }

  .stat-pill--warning .stat-icon :global(.icon) {
    color: var(--color-warning);
  }

  .stat-pill--error {
    background: rgba(239, 68, 68, 0.08);
    border-color: rgba(239, 68, 68, 0.2);
  }

  .stat-pill--error .stat-value {
    color: var(--color-error);
  }

  .stat-pill--error .stat-icon :global(.icon) {
    color: var(--color-error);
  }

  .stat-pill--accent {
    background: rgba(229, 90, 40, 0.08);
    border-color: rgba(229, 90, 40, 0.2);
  }

  .stat-pill--accent .stat-value {
    color: var(--color-accent);
  }

  .stat-pill--accent .stat-icon :global(.icon) {
    color: var(--color-accent);
  }
</style>
