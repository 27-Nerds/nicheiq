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

  const variantClasses: Record<BadgeVariant, string> = {
    default: "badge",
    success: "badge badge-success",
    error: "badge badge-error",
    warning: "badge badge-warning",
    muted: "badge badge-muted",
    info: "badge badge-info",
    accent: "badge badge-accent",
  };

  const sizeClass = $derived(size === "sm" ? "badge-sm" : "");
</script>

<span class="{variantClasses[variant]} {sizeClass} {className}" {title}>
  {@render children()}
</span>
