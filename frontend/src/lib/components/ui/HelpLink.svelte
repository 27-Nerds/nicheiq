<script lang="ts">
  interface Props {
    href: string;
    label: string;
    newTab?: boolean;
    class?: string;
  }

  let {
    href,
    label,
    newTab = true,
    class: className = "",
  }: Props = $props();

  const accessibleLabel = $derived(
    newTab ? `${label} (opens in a new tab)` : label,
  );
</script>

<a
  {href}
  class="help-link {className}"
  target={newTab ? "_blank" : undefined}
  rel={newTab ? "noopener noreferrer" : undefined}
  aria-label={accessibleLabel}
>
  <span class="help-link__label">{label}</span>
  {#if newTab}<span class="help-link__marker" aria-hidden="true">↗</span>{/if}
</a>

<style>
  .help-link {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    min-width: 0;
    min-height: var(--space-7);
    border-radius: var(--radius-sm);
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: var(--text-13);
    font-weight: 600;
    line-height: 1.35;
    text-decoration-line: underline;
    text-decoration-color: var(--color-border-emphasis);
    text-decoration-thickness: 1px;
    text-underline-offset: 3px;
    transition:
      color var(--duration-fast) var(--ease-default),
      text-decoration-color var(--duration-fast) var(--ease-default);
  }

  .help-link__label {
    min-width: 0;
    text-wrap: pretty;
  }

  .help-link__marker {
    flex-shrink: 0;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    transition: transform var(--duration-fast) var(--ease-default);
  }

  .help-link:hover {
    color: var(--color-text-primary);
    text-decoration-color: currentColor;
  }

  .help-link:hover .help-link__marker {
    transform: translate(0.08rem, -0.08rem);
  }

  .help-link:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  @media (prefers-reduced-motion: reduce) {
    .help-link,
    .help-link__marker {
      transition: none;
    }
    .help-link:hover .help-link__marker {
      transform: none;
    }
  }
</style>
