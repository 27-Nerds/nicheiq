<script lang="ts">
  import type { Snippet } from "svelte";

  type BadgeVariant =
    | "default"
    | "success"
    | "error"
    | "warning"
    | "muted"
    | "info"
    | "accent";
  type BadgeSize = "sm" | "md";

  interface Props {
    variant?: BadgeVariant;
    size?: BadgeSize;
    class?: string;
    title?: string;
    children: Snippet;
  }

  let {
    variant = "default",
    size = "md",
    class: className = "",
    title,
    children,
  }: Props = $props();

  // v3 outline .tag recipe: strength = green, risk = red, neutral = gray;
  // status colors from the *-text ramp only.
  const variantClasses: Record<BadgeVariant, string> = {
    default: "tag-neutral",
    muted: "tag-neutral",
    success: "tag-strength",
    error: "tag-risk",
    warning: "tag-warning",
    info: "tag-info",
    accent: "tag-accent",
  };

  const sizeClass = $derived(size === "sm" ? "tag-size-sm" : "");
</script>

<span class="tag {variantClasses[variant]} {sizeClass} {className}" {title}>
  {@render children()}
</span>

<style>
  .tag {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 0.125rem 0.5rem;
    border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
    border-radius: var(--radius-md);
    background: transparent;
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .tag-neutral {
    color: var(--color-text-muted);
  }

  .tag-strength {
    color: var(--color-success-text);
  }

  .tag-risk {
    color: var(--color-error-text);
  }

  .tag-warning {
    color: var(--color-warning-text);
  }

  .tag-info {
    color: var(--color-info-dark);
  }

  .tag-accent {
    color: var(--color-accent-dark);
  }

  .tag-size-sm {
    padding: 0.0625rem 0.375rem;
  }
</style>
